import types
import torch
import torch.nn.functional as F
import numpy as np
import logging
from ._mmlab_utils import get_mmlab_cfg, load_mmlab_checkpoint
from mmdet3d.registry import MODELS as MM3D_MODELS
from ._arcgis_model import _EmptyData


def get_backbone_channel(model_cfg, data, data_preprocessor):
    temp_model = MM3D_MODELS.build(model_cfg).to(data.device)

    x_batch = torch.rand(
        (10000, data.num_features), dtype=torch.float32, device=data.device
    )
    x_batch[:, :3] = (x_batch[:, :3] - 0.5) / 0.5
    x_batch[:, :3] *= data.scale_factor
    voxel_dict = data_preprocessor.voxelize([x_batch], data_samples=None)
    voxel_features = temp_model.voxel_encoder(
        voxel_dict["voxels"], voxel_dict["num_points"], voxel_dict["coors"]
    )
    batch_size = voxel_dict["coors"][-1, 0].item() + 1
    backbone_feature = temp_model.middle_encoder(
        voxel_features, voxel_dict["coors"], batch_size
    )

    return backbone_feature.shape[1]


def get_voxel_size(voxel_parms, data):
    pc_range = np.array(data.range)
    pc_lwh = pc_range[3:] - pc_range[:3]
    # keep the minimum resolution of point cloud grid to (200, 200) in x, y direction
    tile_voxel_size = ([0.005, 0.005, 0.02] * pc_lwh).tolist()
    default_voxel_size = list(map(min, zip(tile_voxel_size, data.voxel_size)))
    voxel_size = voxel_parms.get("voxel_size", None)
    if voxel_size is None:
        voxel_size = default_voxel_size
    else:
        if len(voxel_size) != 3:
            raise Exception("voxel_size list should contain 3 items.")
        # check if given voxel_size is creating at least 64x64x8 voxels
        grid_size = pc_lwh / voxel_size
        if min(grid_size) < 64:
            raise Exception(f"The size {voxel_size} of the voxel is too big.")

    grid_size = torch.tensor(pc_lwh / voxel_size).round().long().tolist()[::-1]

    return voxel_size, grid_size


def get_max_voxels(voxel_parms, grid_size):
    no_of_voxels = np.prod(grid_size, dtype=np.uint64).tolist()
    max_voxels = voxel_parms.get("max_voxels", None)
    if max_voxels is None:
        max_voxels = list(
            map(max, [20000, 40000], [no_of_voxels // 3000, no_of_voxels // 2000])
        )
    else:
        if len(max_voxels) != 2:
            raise Exception("max_voxels list should contain 2 items.")
        if min(max_voxels) < 20000:
            raise Exception("The minimum values in max_voxel should be at least 20000.")
    return max_voxels


def set_voxel_info(voxel_parms, data):
    voxel_size, grid_size = get_voxel_size(voxel_parms, data)
    max_voxels = get_max_voxels(voxel_parms, grid_size)
    voxel_points = voxel_parms.get("voxel_points", None)
    if voxel_points is None:
        voxel_points = max(10, int(data.no_of_points_per_tile // (max_voxels[0] * 0.3)))
    if voxel_points < 10:
        raise Exception("voxel_points should be greater than or equal to 10.")

    voxel_parms["voxel_size"] = voxel_size
    voxel_parms["sparse_shape"] = grid_size
    voxel_parms["max_voxels"] = max_voxels
    voxel_parms["voxel_points"] = voxel_points

    return voxel_parms


def model_data_preprocessor(preprocessor_cfg, data, **kwargs):
    voxel_parms = kwargs.get("voxel_parms")
    voxel_parms = set_voxel_info(voxel_parms, data)

    preprocessor_cfg.voxel_layer.voxel_size = voxel_parms["voxel_size"]
    preprocessor_cfg.voxel_layer.max_voxels = voxel_parms["max_voxels"]
    preprocessor_cfg.voxel_layer.max_num_points = voxel_parms["voxel_points"]
    preprocessor_cfg.voxel_layer.point_cloud_range = data.range
    data.voxel_sparse_shape = voxel_parms["sparse_shape"]

    data_preprocessor = MM3D_MODELS.build(preprocessor_cfg)

    return data_preprocessor


def model_config(model_cfg, data, **kwargs):
    model_cfg.voxel_encoder.num_features = data.num_features
    model_cfg.middle_encoder.in_channels = data.num_features

    # set correctly otherwise RuntimeError: CUDA error: an illegal memory access was encountered
    model_cfg.middle_encoder.sparse_shape = (
        data.voxel_sparse_shape
    )  # voxel_parms["sparse_shape"]

    model_cfg.backbone.in_channels = get_backbone_channel(
        model_cfg, data, kwargs.get("data_preprocessor")
    )

    model_cfg.bbox_head.num_classes = data.c
    model_cfg.bbox_head.bbox_coder.code_size = 7
    model_cfg.bbox_head.anchor_generator.ranges = data.anchor_range
    model_cfg.bbox_head.anchor_generator.sizes = data.average_box_size
    model_cfg.bbox_head.anchor_generator.rotations = [0.0, 1.57]

    return model_cfg


def forward_mmlab(self, inputs):
    if not self.prediction:
        batch_losses = self.loss(inputs["inputs"], inputs["data_samples"])
        losses = self.parse_losses(batch_losses)[0]
        output = None
        if not self.training:
            self.eval()
            output = self.predict(inputs["inputs"], inputs["data_samples"])
        return output, losses
    else:
        output = self.predict(inputs["inputs"], inputs["data_samples"])
        return output


def forward_neck(self, x):
    assert len(x) == len(self.in_channels)
    ups = [deblock(x[i]) for i, deblock in enumerate(self.deblocks)]
    size = ups[0].shape[-2:]
    ups = [F.interpolate(up, size, mode="bilinear", align_corners=False) for up in ups]
    if len(ups) > 1:
        out = torch.cat(ups, dim=1)
    else:
        out = ups[0]
    return [out]


def get_model(data, **kwargs):
    logging.disable(logging.WARNING)
    cfg, checkpoint = get_mmlab_cfg(model_type="Detection3D", **kwargs)
    data_preprocessor = model_data_preprocessor(cfg.data_preprocessor, data, **kwargs)
    if isinstance(data, _EmptyData):
        data.data_preprocessor_3d = data_preprocessor
    else:
        data.train_dl.data_preprocessor_3d = data_preprocessor
        data.valid_dl.data_preprocessor_3d = data_preprocessor
    cfg.model = model_config(
        cfg.model, data, data_preprocessor=data_preprocessor, **kwargs
    )
    model = MM3D_MODELS.build(cfg.model)
    model.data_preprocessor = data_preprocessor
    if checkpoint:
        load_mmlab_checkpoint(model, checkpoint)
    model.forward = types.MethodType(forward_mmlab, model)
    if cfg.model.neck.type == "SECONDFPN":
        model.neck.forward = types.MethodType(forward_neck, model.neck)

    model.prediction = False

    logging.disable(0)
    return model, cfg
