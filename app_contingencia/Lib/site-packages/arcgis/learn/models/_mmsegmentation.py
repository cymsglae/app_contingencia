from pathlib import Path
import json

from ._model_extension import ModelExtension
from ._arcgis_model import _EmptyData
import logging

from .._mmseg_config.prithvi100m_burn_scar import img_norm_burn_model
from .._mmseg_config.prithvi100m_crop_classification import img_norm_crop_model
from .._mmseg_config.prithvi100m_sen1floods import img_norm_flood_model

logger = logging.getLogger()

try:
    from fastai.vision import flatten_model
    import fastai
    import torch
    from fastai.torch_core import split_model_idx
    from .._utils.common import get_multispectral_data_params_from_emd, _get_emd_path
    from ._model_extension_config import MMSegmentationConfig

    HAS_FASTAI = True

except Exception as e:
    HAS_FASTAI = False


def norm_prithvi(data, model):
    scaling_info = {
        "prithvi100m_burn_scar": (
            img_norm_burn_model.get("means"),
            img_norm_burn_model.get("stds"),
        ),
        "prithvi100m_sen1floods": (
            img_norm_flood_model.get("means"),
            img_norm_flood_model.get("stds"),
        ),
        "prithvi100m_crop_classification": (
            img_norm_crop_model.get("means"),
            img_norm_crop_model.get("stds"),
        ),
        "prithvi100m": (
            data._scaled_mean_values.tolist(),
            data._scaled_std_values.tolist(),
        ),
    }

    means, stds = scaling_info[model]
    data._scaled_mean_values, data._scaled_std_values = torch.tensor(
        means
    ), torch.tensor(stds)

    data._min_max_scaler = None

    if (data._band_max_values.mean() > 1) and (
        model != "prithvi100m_crop_classification"
    ):
        div_value = 10000
    else:
        div_value = None

    data.valid_ds.x._div = div_value
    data.train_ds.x._div = div_value

    data = data.normalize(
        stats=(data._scaled_mean_values, data._scaled_std_values), do_x=True, do_y=False
    )

    return data


class MMSegmentation(ModelExtension):
    """
    =====================   ===========================================
    **Parameter**            **Description**
    ---------------------   -------------------------------------------
    data                    Required fastai Databunch. Returned data object from
                            :meth:`~arcgis.learn.prepare_data`  function.
    ---------------------   -------------------------------------------
    model                   Required model name or path to the configuration file
                            from :class:`~arcgis.learn.MMSegmentation` repository. The list of the
                            supported models can be queried using
                            :attr:`~arcgis.learn.MMSegmentation.supported_models`
    ---------------------   -------------------------------------------
    model_weight            Optional path of the model weight from
                            :class:`~arcgis.learn.MMSegmentation` repository.
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

    :return: :class:`~arcgis.learn.MMSegmentation` Object
    """

    def __init__(self, data, model, model_weight=False, pretrained_path=None, **kwargs):
        self._check_dataset_support(data)

        if model.startswith("prithvi100m"):
            data.remove_tfm(data.norm)
            data.norm, data.denorm = None, None
            data = norm_prithvi(data, model)

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
        is_transformer = False
        if model in self.supported_transformer_models:
            is_transformer = True

        super().__init__(
            data,
            MMSegmentationConfig,
            pretrained_path=pretrained_path,
            model=model,
            model_weight=model_weight,
            ignore_class=self._ignore_mapped_class,
            class_weight=self._final_class_weight,
            is_transformer=is_transformer,
        )
        idx = self._freeze()
        self.learn.layer_groups = split_model_idx(self.learn.model, [idx])
        self.learn.create_opt(lr=3e-3)

    def unfreeze(self):
        for _, param in self.learn.model.named_parameters():
            param.requires_grad = True

    def _freeze(self):
        "Freezes the pretrained backbone."
        if self._model_conf.cfg.model.backbone.type == "CGNet":
            return 6

        layers = flatten_model(self.learn.model.backbone)
        idx = len(layers) // 2
        start_idx = 0
        if self._is_multispectral:
            start_idx = 2
        for layer in layers[start_idx:idx]:
            if (
                isinstance(layer, (torch.nn.BatchNorm2d))
                or isinstance(layer, (fastai.torch_core.ParameterModule))
                or isinstance(layer, (torch.nn.BatchNorm1d))
                or isinstance(layer, (torch.nn.LayerNorm))
            ):
                continue
            for p in layer.parameters():
                p.requires_grad = False
        return idx

    @staticmethod
    def _available_metrics():
        return ["valid_loss", "accuracy"]

    @property
    def _is_mmsegdet(self):
        return True

    @property
    def supported_datasets(self):
        """Supported dataset types for this model."""
        return MMSegmentation._supported_datasets()

    @staticmethod
    def _supported_datasets():
        return ["Classified_Tiles"]

    supported_models = [
        "ann",
        "apcnet",
        "ccnet",
        "cgnet",
        "deeplabv3",
        "deeplabv3plus",
        "dmnet",
        "dnlnet",
        "emanet",
        "fastscnn",
        "fcn",
        "gcnet",
        "hrnet",
        "mask2former",
        "mobilenet_v2",
        "nonlocal_net",
        "ocrnet",
        "psanet",
        "pspnet",
        "resnest",
        "sem_fpn",
        "unet",
        "upernet",
    ]
    """
    List of models supported by this class.
    """

    supported_transformer_models = ["mask2former"]
    """
    List of transformer based models supported by this class.
    """

    @classmethod
    def from_model(cls, emd_path, data=None):
        """
        Creates a :class:`~arcgis.learn.MMSegmentation` object from an Esri Model Definition (EMD) file.

        =====================   ===========================================
        **Parameter**            **Description**
        ---------------------   -------------------------------------------
        emd_path                Required string. Path to Deep Learning Package
                                (DLPK) or Esri Model Definition(EMD) file.
        ---------------------   -------------------------------------------
        data                    Required fastai Databunch or None. Returned data
                                object from :meth:`~arcgis.learn.prepare_data`  function or None for
                                inferencing.

        =====================   ===========================================

        :return: :class:`~arcgis.learn.MMSegmentation` Object
        """
        emd_path = _get_emd_path(emd_path)

        with open(emd_path) as f:
            emd = json.load(f)

        model_file = Path(emd["ModelFile"])

        if not model_file.is_absolute():
            model_file = emd_path.parent / model_file

        kwargs = emd.get("Kwargs", {})

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

        return cls(data, pretrained_path=str(model_file), **kwargs)

    def show_results(self, rows=5, thresh=0.5, thinning=True, **kwargs):
        """
        Displays the results of a trained model on a part of the validation set.
        """
