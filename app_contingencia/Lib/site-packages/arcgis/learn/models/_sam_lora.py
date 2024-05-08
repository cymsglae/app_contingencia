import json
from pathlib import Path
from ._model_extension import ModelExtension
from ._arcgis_model import _EmptyData
import logging

logger = logging.getLogger()

try:
    from fastai.vision import flatten_model
    from fastai.torch_core import split_model_idx
    from .._utils.common import get_multispectral_data_params_from_emd, _get_emd_path

    HAS_FASTAI = True

except Exception as e:
    HAS_FASTAI = False


class SamLoRAConfig:
    try:
        import torch
        import os
        from pathlib import Path
    except:
        pass

    def on_batch_begin(self, learn, model_input_batch, model_target_batch, **kwargs):
        """
        Function to transform the input data and the targets in accordance to the model for training.
        """

        # model_input: [BxCxHxW], Normalized using ImageNet stats
        model_input = model_input_batch
        # model_target: [BxHxW], values in 0-n, n is #classes
        model_target = (model_target_batch).squeeze(dim=1)
        return model_input, model_target

    def transform_input(self, xb):
        """
        Function to transform the inputs for inferencing.
        """
        model_input = xb

        return model_input

    def transform_input_multispectral(self, xb):
        """
        Function to transform the multispectral inputs for inferencing.
        """
        model_input = xb
        return model_input

    def get_model(self, data, backbone=None, **kwargs):
        """
        Function used to define the model architecture.
        """
        from arcgis.learn.models._sam_lora_utils import LoRA_Sam, sam_model_registry
        from arcgis.learn._utils.utils import compare_checksum

        self.num_classes = data.c - 1  # 0-background, 1-buildings
        img_size = data.chip_size
        vit_name = backbone if type(backbone) is str else backbone.__name__
        ckpt = {
            "vit_b": "sam_vit_b_01ec64.pth",
            "vit_l": "sam_vit_l_0b3195.pth",
            "vit_h": "sam_vit_h_4b8939.pth",
        }
        file_checksum = {
            "vit_b": 1442441403,
            "vit_l": 1653302572,
            "vit_h": 2791087151,
        }

        rank = 4

        load_sam_weights = kwargs.get("load_sam_weights", False)
        if load_sam_weights:
            # Download (if required) SAM pretrained weights
            weights_path = self.os.path.join(self.Path.home(), ".cache", "weights")
            weights_file = self.os.path.join(weights_path, ckpt[vit_name])

            # Delete incomplete/corrupt downloads
            if self.os.path.exists(weights_file) and not compare_checksum(
                weights_file, file_checksum[vit_name]
            ):
                self.os.remove(weights_file)

            if not self.os.path.exists(weights_file):
                if not self.os.path.exists(weights_path):
                    self.os.makedirs(weights_path)
                try:
                    self.download_sam_weights(weights_file, ckpt[vit_name])
                except Exception as e:
                    print(e)
                    print(
                        "[INFO] Can't download SAM pretrained weights.\nProceeding without pretrained weights."
                    )
                    weights_file = None
        else:
            # Not to load sam weights if dlpk is to be used
            weights_file = None

        # register model
        sam, img_embedding_size = sam_model_registry[vit_name](
            image_size=img_size,
            num_classes=self.num_classes,
            checkpoint=weights_file,
        )
        model = LoRA_Sam(sam, rank).cuda()

        multimask_output = True
        low_res = img_embedding_size * 4

        self.model = model
        return model

    def loss(self, model_output, *model_target):
        """
        Function to define the loss calculations.
        """
        from torch.nn.modules.loss import CrossEntropyLoss

        ce_loss = CrossEntropyLoss()
        dice_weight = 0.8
        label = model_target[0]  # model_target is a single element tuple

        # Not using the Dice Loss from SAMed
        # Calculating loss by using image size output masks and target labels.
        # from arcgis.learn.models._sam_lora_utils import DiceLoss

        # loss_ce = ce_loss(model_output, label[:].long())
        # dice_loss = DiceLoss(self.num_classes + 1)
        # loss_dice = dice_loss(model_output, label, softmax=True)
        # loss = (1 - dice_weight) * loss_ce + dice_weight * loss_dice
        # final_loss = loss

        # Using common Dice Loss
        from arcgis.learn._utils.segmentation_loss_functions import DiceLoss

        dice_loss = DiceLoss(
            ce_loss,
            dice_weight,
            weighted_dice=False,
            dice_average="micro",
        )
        final_loss = dice_loss(model_output, label)

        return final_loss

    def post_process(self, pred, thres, thinning=True, prob_raster=False):
        """
        Fuction to post process the output of the model in validation/infrencing mode.
        """
        if prob_raster:
            return pred
        else:
            output_masks = self.torch.argmax(
                self.torch.softmax(pred, dim=1), dim=1, keepdim=True
            )
            post_processed_pred = output_masks
        return post_processed_pred

    def download_sam_weights(self, weights_path, ckpt):
        from urllib.request import urlretrieve

        url = f"https://dl.fbaipublicfiles.com/segment_anything/{ckpt}"
        urlretrieve(url, weights_path)


class SamLoRA(ModelExtension):
    """
    =====================   ===========================================
    **Parameter**            **Description**
    ---------------------   -------------------------------------------
    data                    Required fastai Databunch. Returned data object from
                            :meth:`~arcgis.learn.prepare_data`  function.
    ---------------------   -------------------------------------------
    pretrained_path         Optional string. Path where pre-trained model is
                            saved.
    =====================   ===========================================

    **kwargs**

    =====================   ===========================================
    class_balancing         Optional boolean. If True, it will balance the
                            cross-entropy loss inverse to the frequency
                            of pixels per class. Default: False.
    ---------------------   -------------------------------------------
    ignore_classes          Optional list. It will contain the list of class
                            values on which model will not incur loss.
                            Default: []
    =====================   ===========================================

    :return: :class:`~arcgis.learn.SamLoRA` Object
    """

    def __init__(self, data, backbone="vit_b", pretrained_path=None, **kwargs):
        self._check_dataset_support(data)
        if not (self._check_backbone_support(backbone)):
            raise Exception(
                f"Enter only compatible backbones from {', '.join(self.supported_backbones)}"
            )

        self._ignore_classes = kwargs.get("ignore_classes", [])
        self.class_balancing = kwargs.get("class_balancing", False)
        if self._ignore_classes != [] and len(data.classes) <= 2:
            raise Exception(
                f"`ignore_classes` parameter can only be used when the dataset has more than 2 classes."
            )

        data_classes = list(data.class_mapping.keys())
        if 0 not in list(data.class_mapping.values()):
            self._ignore_mapped_class = [
                data_classes.index(k) + 1 for k in self._ignore_classes if k != 0
            ]
        else:
            self._ignore_mapped_class = [
                data_classes.index(k) + 1 for k in self._ignore_classes
            ]
        if self._ignore_classes != []:
            if 0 not in self._ignore_mapped_class:
                self._ignore_mapped_class.insert(0, 0)

        class_weight = None
        if self.class_balancing:
            if data.class_weight is not None:
                # Handle condition when nodata is already at pixel value 0 in data
                if (data.c - 1) == data.class_weight.shape[0]:
                    class_weight = [
                        data.class_weight.mean()
                    ] + data.class_weight.tolist()
                else:
                    class_weight = data.class_weight.tolist()
            else:
                if getattr(data, "overflow_encountered", False):
                    logger.warning(
                        "Overflow Encountered. Ignoring `class_balancing` parameter."
                    )
                    class_weight = [1.0] * len(data.classes)
                else:
                    logger.warning(
                        "Could not find 'NumPixelsPerClass' in 'esri_accumulated_stats.json'. Ignoring `class_balancing` parameter."
                    )

        if self._ignore_classes != []:
            if not self.class_balancing:
                class_weight = [1.0] * data.c
            for idx in self._ignore_mapped_class:
                class_weight[idx] = 0.0

        self._final_class_weight = class_weight

        if pretrained_path is None:
            kwargs["load_sam_weights"] = True
        else:
            kwargs["load_sam_weights"] = False

        super().__init__(
            data,
            SamLoRAConfig,
            backbone=backbone,
            pretrained_path=pretrained_path,
            **kwargs,
        )
        self._backbone = backbone

    @property
    def supported_datasets(self):
        """Supported dataset types for this model."""
        return SamLoRA._supported_datasets()

    @staticmethod
    def _supported_datasets():
        return ["Classified_Tiles"]

    @property
    def supported_backbones(self):
        """Supported list of backbones for this model."""
        return SamLoRA._supported_backbones()

    @staticmethod
    def _supported_backbones():
        return ["vit_h", "vit_l", "vit_b"]

    @staticmethod
    def _available_metrics():
        return ["valid_loss", "accuracy"]

    @classmethod
    def from_model(cls, emd_path, data=None):
        """
        Creates a :class:`~arcgis.learn.SamLoRA` object from an Esri Model Definition (EMD) file.

        =====================   ===========================================
        **Parameter**            **Description**
        ---------------------   -------------------------------------------
        emd_path                Required string. Path to Deep Learning Package
                                (DLPK) or Esri Model Definition(EMD) file.
        ---------------------   -------------------------------------------
        data                    Required fastai Databunch or None. Returned data
                                object from :meth:`~arcgis.learn.prepare_data`
                                function or None for inferencing.
        =====================   ===========================================

        :return: :class:`~arcgis.learn.SamLoRA` Object
        """
        emd_path = _get_emd_path(emd_path)

        with open(emd_path) as f:
            emd = json.load(f)

        model_file = Path(emd["ModelFile"])

        if not model_file.is_absolute():
            model_file = emd_path.parent / model_file

        kwargs = emd.get("Kwargs", {})
        backbone = emd["ModelParameters"].get("backbone", None)

        try:
            class_mapping = {i["Value"]: i["Name"] for i in emd["Classes"]}
            color_mapping = {i["Value"]: i["Color"] for i in emd["Classes"]}
        except KeyError:
            class_mapping = {i["ClassValue"]: i["ClassName"] for i in emd["Classes"]}
            color_mapping = {i["ClassValue"]: i["Color"] for i in emd["Classes"]}

        if data is None:
            data = _EmptyData(
                path=emd_path.parent.parent,
                loss_func=None,
                c=len(class_mapping) + 1,
                chip_size=emd["ImageHeight"],
            )
            data.class_mapping = class_mapping
            data.color_mapping = color_mapping
            data._is_empty = True
            data.emd_path = emd_path
            data.emd = emd
            data.classes = ["background"]
            for k, v in class_mapping.items():
                data.classes.append(v)
            data = get_multispectral_data_params_from_emd(data, emd)
            data.dataset_type = emd["DatasetType"]

        return cls(data, backbone=backbone, pretrained_path=str(model_file), **kwargs)

    def show_results(self, rows=5, **kwargs):
        """
        Displays the results of a trained model on a part of the validation set.
        =====================   ===========================================
        **Parameter**            **Description**
        ---------------------   -------------------------------------------
        rows                    Optional Integer. Number of rows of results
                                to be displayed.
        =====================   ===========================================
        **kwargs**
        =====================   ===========================================
        **Parameter**            **Description**
        ---------------------   -------------------------------------------
        alpha                   Optional Float. Default value is 0.5.
                                Opacity of the lables for the corresponding
                                images. Values range between 0 and 1, where
                                1 means opaque.
        =====================   ===========================================
        """
