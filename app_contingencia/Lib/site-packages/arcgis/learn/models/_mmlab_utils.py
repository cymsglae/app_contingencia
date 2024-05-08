import os
from pathlib import Path
import warnings
import logging
from functools import partial
import types
from mmengine.config import Config
from mmdet.registry import MODELS
from mmengine.runner.checkpoint import (
    load_checkpoint,
    CheckpointLoader,
    load_from_http,
)
import arcgis
from mmseg.registry import MODELS as MMSeg_Models
from mmdet.structures import DetDataSample
from mmseg.structures import SegDataSample
from mmengine.structures import InstanceData, PixelData
import numpy as np
import torch
from mmengine.registry import MODELS as MMengine_Models
from mmseg.models.backbones.unet import InterpConv

# register InterpConv module in mmengine to resolve the Unet error
try:
    MMengine_Models.register_module("InterpConv", module=InterpConv)
except:
    pass


def get_mmlab_cfg(**kwargs):
    config = kwargs.get("model", False)
    checkpoint = kwargs.get("model_weight", False)
    model_type = kwargs.get("model_type")
    if config[-2:] != "py":
        config += ".py"
    arcgis_path = Path(arcgis.__file__).parent / "learn"
    if os.path.exists(Path(config)):
        pass
    elif model_type == "Segmentation":
        config = arcgis_path / "_mmseg_config" / config
    elif model_type == "Detection":
        config = arcgis_path / "_mmdetection_config" / config
    elif model_type == "Detection3D":
        config = arcgis_path / "_mmdet3d_config" / config

    cfg = Config.fromfile(config)
    cfg.model.pop("pretrained")
    if not checkpoint:
        checkpoint = cfg.get("checkpoint", False)

    return cfg, checkpoint


def load_mmlab_checkpoint(model, checkpoint):
    CheckpointLoader._schemes["https://"] = partial(
        load_from_http, model_dir=None, progress=True
    )
    CheckpointLoader._schemes["http://"] = CheckpointLoader._schemes["https://"]
    CheckpointLoader._schemes["https://"].__name__ = "load_from_http"
    load_checkpoint(model, checkpoint, "cpu", False, logging.getLogger())


def set_detctor_parms(data, cfg):
    if hasattr(cfg.model, "roi_head"):
        if isinstance(cfg.model.roi_head.bbox_head, list):
            for box_head in cfg.model.roi_head.bbox_head:
                box_head.num_classes = data.c - 1
        else:
            cfg.model.roi_head.bbox_head.num_classes = data.c - 1
    else:
        cfg.model.bbox_head.num_classes = data.c - 1

    if cfg.model.backbone.type == "DetectoRS_ResNet" and getattr(
        data, "_is_multispectral", False
    ):
        if hasattr(cfg.model.neck, "rfp_backbone"):
            cfg.model.neck.rfp_backbone.in_channels = len(data._extract_bands)
    return cfg


def set_segmentor_parms(data, cfg, **kwargs):
    class_weight = kwargs.get("class_weight", None)
    if isinstance(cfg.model.decode_head, list):
        for dcd_head in cfg.model.decode_head:
            dcd_head.num_classes = data.c
            dcd_head.loss_decode.class_weight = class_weight
    else:
        cfg.model.decode_head.num_classes = data.c
        if hasattr(cfg.model.decode_head, "loss_cls"):
            cfg.model.decode_head.loss_cls.class_weight = (
                class_weight if class_weight else [1.0] * data.c
            ) + [0.1]
        else:
            if cfg.model.decode_head.loss_decode.type == "DiceLoss":
                pass
            else:
                cfg.model.decode_head.loss_decode.class_weight = class_weight

    if hasattr(cfg.model, "auxiliary_head"):
        if isinstance(cfg.model.auxiliary_head, list):
            for aux_head in cfg.model.auxiliary_head:
                aux_head.num_classes = data.c
                aux_head.loss_decode.class_weight = class_weight
        else:
            cfg.model.auxiliary_head.num_classes = data.c
            if cfg.model.auxiliary_head.loss_decode.type == "DiceLoss":
                pass
            else:
                cfg.model.auxiliary_head.loss_decode.class_weight = class_weight
    if cfg.model.backbone.type == "CGNet" and getattr(data, "_is_multispectral", False):
        cfg.model.backbone.in_channels = len(data._extract_bands)

    return cfg


def change_norm_layer(cfg):
    for k, v in cfg.items():
        if k == "norm_cfg":
            cfg[k].type = "BN"
        elif isinstance(cfg[k], dict):
            change_norm_layer(cfg[k])
    return cfg


def forward_mmlab(self, inputs, data_samples=None):
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        if self.training:
            batch_losses = self.loss(inputs, data_samples)
            losses = self.parse_losses(batch_losses)[0]
            output = None
            train_val = getattr(self, "train_val", False)
            if train_val:
                self.eval()
                output = self.predict(inputs, data_samples)
            return output, losses
        else:
            data_samples = inputs[1]
            inputs = inputs[0]
            output = self.predict(inputs, data_samples)
            return output


def predict_mmseg(self, inputs, data_samples):
    batch_img_metas = [data_sample.metainfo for data_sample in data_samples]
    seg_logits = self.encode_decode(inputs, batch_img_metas)

    return seg_logits


def stack_batch_gt(self, batch_data_samples):
    if not isinstance(batch_data_samples, list):
        return batch_data_samples
    gt_semantic_segs = [
        data_sample.gt_sem_seg.data for data_sample in batch_data_samples
    ]
    return torch.stack(gt_semantic_segs, dim=0)


def prepare_mmbatch(batch_shape, **kwargs):
    metas_dict = {}
    scale_factor = np.array([1.0, 1.0], dtype=np.float32)
    metas_dict["pad_shape"] = batch_shape[1:3]
    metas_dict["img_shape"] = batch_shape[1:3]
    metas_dict["ori_shape"] = batch_shape[1:3]
    metas_dict["scale_factor"] = scale_factor
    model_type = kwargs.get("model_type")

    if model_type == "Detection":
        data_sample = DetDataSample()
        instance_data = InstanceData()
        if "bboxes" in kwargs.keys():
            instance_data["bboxes"] = kwargs.get("bboxes")
            instance_data["labels"] = kwargs.get("labels")
        data_sample.set_metainfo(metas_dict)
        data_sample.gt_instances = instance_data
    else:
        data_sample = SegDataSample()
        if "gt_sem_seg" in kwargs.keys():
            data_sample.gt_sem_seg = PixelData(**dict(data=kwargs.get("gt_sem_seg")))
        data_sample.set_metainfo(metas_dict)

    return data_sample


def mmlab_models(data, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logging.disable(logging.WARNING)

        cfg, checkpoint = get_mmlab_cfg(**kwargs)

        if kwargs.get("model_type") == "Detection":
            cfg = set_detctor_parms(data, cfg)
            model = MODELS.build(cfg.model)
        else:
            cfg = change_norm_layer(cfg)
            cfg = set_segmentor_parms(data, cfg, **kwargs)
            model = MMSeg_Models.build(cfg.model)
            model.predict = types.MethodType(predict_mmseg, model)
            if cfg.model.type == "CascadeEncoderDecoder":
                for i in range(cfg.model.num_stages):
                    model.decode_head[i]._stack_batch_gt = types.MethodType(
                        stack_batch_gt, model.decode_head[i]
                    )
            else:
                model.decode_head._stack_batch_gt = types.MethodType(
                    stack_batch_gt, model
                )

        if checkpoint:
            load_mmlab_checkpoint(model, checkpoint)
        model.forward = types.MethodType(forward_mmlab, model)

        logging.disable(0)
    return model, cfg
