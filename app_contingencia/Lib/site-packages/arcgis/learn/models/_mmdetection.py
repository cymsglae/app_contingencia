from pathlib import Path
import json
import warnings
from ._model_extension import ModelExtension

try:
    from fastai.vision import flatten_model, ImageList
    from fastai.vision import imagenet_stats
    import torch
    from fastai.torch_core import split_model_idx
    from .._utils.pascal_voc_rectangles import ObjectDetectionCategoryList
    from .._utils.common import get_multispectral_data_params_from_emd, _get_emd_path
    from ._ssd_utils import AveragePrecision
    from ._model_extension_config import MMDetectionConfig

    HAS_FASTAI = True

except Exception as e:
    HAS_FASTAI = False


class MMDetection(ModelExtension):
    """
    =============================   =============================================
    **Parameter**                    **Description**
    -----------------------------   ---------------------------------------------
    data                            Required fastai Databunch. Returned data object from
                                    :meth:`~arcgis.learn.prepare_data`  function.
    -----------------------------   ---------------------------------------------
    model                           Required model name or path to the configuration file
                                    from :class:`~arcgis.learn.MMDetection` repository. The list of the
                                    supported models can be queried using
                                    :attr:`~arcgis.learn.MMDetection.supported_models` .
    -----------------------------   ---------------------------------------------
    model_weight                    Optional path of the model weight from
                                    :class:`~arcgis.learn.MMDetection` repository.
    -----------------------------   ---------------------------------------------
    pretrained_path                 Optional string. Path where pre-trained model is
                                    saved.
    =============================   =============================================

    :return: :class:`~arcgis.learn.MMDetection` Object
    """

    def __init__(self, data, model, model_weight=False, pretrained_path=None, **kwargs):
        self._check_dataset_support(data)

        super().__init__(
            data,
            MMDetectionConfig,
            pretrained_path=pretrained_path,
            model=model,
            model_weight=model_weight,
        )
        self.learn.metrics = [AveragePrecision(self, data.c - 1)]
        idx = self._freeze()
        self.learn.layer_groups = split_model_idx(self.learn.model, [idx])
        self.learn.create_opt(lr=3e-3)

    def unfreeze(self):
        for _, param in self.learn.model.named_parameters():
            param.requires_grad = True

    def _freeze(self):
        "Freezes the pretrained backbone."
        for idx, i in enumerate(flatten_model(self.learn.model.backbone)):
            if isinstance(i, (torch.nn.BatchNorm2d)):
                continue
            for p in i.parameters():
                p.requires_grad = False
        return idx

    @staticmethod
    def _available_metrics():
        return ["valid_loss"]

    @property
    def _is_mmsegdet(self):
        return True

    @property
    def supported_datasets(self):
        """Supported dataset types for this model."""
        return MMDetection._supported_datasets()

    @staticmethod
    def _supported_datasets():
        return ["PASCAL_VOC_rectangles", "KITTI_rectangles"]

    supported_models = [
        "atss",
        "carafe",
        "cascade_rcnn",
        "cascade_rpn",
        "dcn",
        "detectors",
        "double_heads",
        "dynamic_rcnn",
        "empirical_attention",
        "fcos",
        "foveabox",
        "fsaf",
        "ghm",
        "hrnet",
        "libra_rcnn",
        "nas_fcos",
        "pafpn",
        "pisa",
        "regnet",
        "reppoints",
        "res2net",
        "sabl",
        "vfnet",
    ]
    """
    List of models supported by this class.
    """

    @classmethod
    def from_model(cls, emd_path, data=None):
        """
        Creates a :class:`~arcgis.learn.MMDetection` object from an Esri Model Definition (EMD) file.

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

        :return: :class:`~arcgis.learn.MMDetection` Object
        """
        emd_path = _get_emd_path(emd_path)

        with open(emd_path) as f:
            emd = json.load(f)

        model_file = Path(emd["ModelFile"])

        if not model_file.is_absolute():
            model_file = emd_path.parent / model_file

        dataset_type = emd.get("DatasetType", "PASCAL_VOC_rectangles")
        chip_size = emd["ImageWidth"]
        resize_to = emd.get("resize_to", None)
        kwargs = emd.get("Kwargs", {})
        if isinstance(resize_to, list):
            resize_to = (resize_to[0], resize_to[1])

        try:
            class_mapping = {i["Value"]: i["Name"] for i in emd["Classes"]}
            color_mapping = {i["Value"]: i["Color"] for i in emd["Classes"]}
        except KeyError:
            class_mapping = {i["ClassValue"]: i["ClassName"] for i in emd["Classes"]}
            color_mapping = {i["ClassValue"]: i["Color"] for i in emd["Classes"]}

        data_passed = True
        if data is None:
            data_passed = False
            train_tfms = []
            val_tfms = []
            ds_tfms = (train_tfms, val_tfms)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                sd = ImageList([], path=emd_path.parent.parent).split_by_idx([])
                data = (
                    sd.label_const(
                        0,
                        label_cls=ObjectDetectionCategoryList,
                        classes=list(class_mapping.values()),
                    )
                    .transform(ds_tfms)
                    .databunch()
                    .normalize(imagenet_stats)
                )
            # Add 1 for background class
            data.c += 1
            data.chip_size = chip_size
            data.class_mapping = class_mapping
            data.color_mapping = color_mapping
            data.classes = ["background"] + list(class_mapping.values())
            data._is_empty = True
            data.emd_path = emd_path
            data.emd = emd
            data = get_multispectral_data_params_from_emd(data, emd)
            data.dataset_type = dataset_type

        data.resize_to = resize_to
        frcnn = cls(data, pretrained_path=str(model_file), **kwargs)

        if not data_passed:
            frcnn.learn.data.single_ds.classes = frcnn._data.classes
            frcnn.learn.data.single_ds.y.classes = frcnn._data.classes

        return frcnn

    def predict(
        self,
        image_path,
        threshold=0.5,
        nms_overlap=0.1,
        return_scores=False,
        visualize=False,
        resize=False,
    ):
        """
        Runs prediction on an Image. This method is only supported for RGB images.

        =====================   ===========================================
        **Parameter**            **Description**
        ---------------------   -------------------------------------------
        image_path              Required. Path to the image file to make the
                                predictions on.
        ---------------------   -------------------------------------------
        threshold               Optional float. The probability above which
                                a detection will be considered valid.
        ---------------------   -------------------------------------------
        nms_overlap             Optional float. The intersection over union
                                threshold with other predicted bounding
                                boxes, above which the box with the highest
                                score will be considered a true positive.
        ---------------------   -------------------------------------------
        return_scores           Optional boolean. Will return the probability
                                scores of the bounding box predictions if True.
        ---------------------   -------------------------------------------
        visualize               Optional boolean. Displays the image with
                                predicted bounding boxes if True.
        ---------------------   -------------------------------------------
        resize                  Optional boolean. Resizes the image to the same size
                                (chip_size parameter in prepare_data) that the model was trained on,
                                before detecting objects.
                                Note that if resize_to parameter was used in prepare_data,
                                the image is resized to that size instead.

                                By default, this parameter is false and the detections are run
                                in a sliding window fashion by applying the model on cropped sections
                                of the image (of the same size as the model was trained on).
        =====================   ===========================================

        :return: Returns a tuple with predictions, labels and optionally confidence scores
                  if return_scores=True. The predicted bounding boxes are returned as a list
                  of lists containing the  xmin, ymin, width and height of each predicted object
                  in each image. The labels are returned as a list of class values and the
                  confidence scores are returned as a list of floats indicating the confidence
                  of each prediction.
        """

    def predict_video(
        self,
        input_video_path,
        metadata_file,
        threshold=0.5,
        nms_overlap=0.1,
        track=False,
        visualize=False,
        output_file_path=None,
        multiplex=False,
        multiplex_file_path=None,
        tracker_options={
            "assignment_iou_thrd": 0.3,
            "vanish_frames": 40,
            "detect_frames": 10,
        },
        visual_options={
            "show_scores": True,
            "show_labels": True,
            "thickness": 2,
            "fontface": 0,
            "color": (255, 255, 255),
        },
        resize=False,
    ):
        """
        Runs prediction on a video and appends the output VMTI predictions in the metadata file.
        This method is only supported for RGB images.

        =====================   ===========================================
        **Parameter**            **Description**
        ---------------------   -------------------------------------------
        input_video_path        Required. Path to the video file to make the
                                predictions on.
        ---------------------   -------------------------------------------
        metadata_file           Required. Path to the metadata csv file where
                                the predictions will be saved in VMTI format.
        ---------------------   -------------------------------------------
        threshold               Optional float. The probability above which
                                a detection will be considered.
        ---------------------   -------------------------------------------
        nms_overlap             Optional float. The intersection over union
                                threshold with other predicted bounding
                                boxes, above which the box with the highest
                                score will be considered a true positive.
        ---------------------   -------------------------------------------
        track                   Optional bool. Set this parameter as True to
                                enable object tracking.
        ---------------------   -------------------------------------------
        visualize               Optional boolean. If True a video is saved
                                with prediction results.
        ---------------------   -------------------------------------------
        output_file_path        Optional path. Path of the final video to be saved.
                                If not supplied, video will be saved at path input_video_path
                                appended with _prediction.
        ---------------------   -------------------------------------------
        multiplex               Optional boolean. Runs Multiplex using the VMTI detections.
        ---------------------   -------------------------------------------
        multiplex_file_path     Optional path. Path of the multiplexed video to be saved.
                                By default a new file with _multiplex.MOV extension is saved
                                in the same folder.
        ---------------------   -------------------------------------------
        tracking_options        Optional dictionary. Set different parameters for
                                object tracking. assignment_iou_thrd parameter is used
                                to assign threshold for assignment of trackers,
                                vanish_frames is the number of frames the object should
                                be absent to consider it as vanished, detect_frames
                                is the number of frames an object should be detected
                                to track it.
        ---------------------   -------------------------------------------
        visual_options          Optional dictionary. Set different parameters for
                                visualization.
                                show_scores boolean, to view scores on predictions,
                                show_labels boolean, to view labels on predictions,
                                thickness integer, to set the thickness level of box,
                                fontface integer, fontface value from opencv values,
                                color tuple (B, G, R), tuple containing values between
                                0-255.
        ---------------------   -------------------------------------------
        resize                  Optional boolean. Resizes the video frames to the same size
                                (chip_size parameter in prepare_data) that the model was trained on,
                                before detecting objects.
                                Note that if resize_to parameter was used in prepare_data,
                                the video frames are resized to that size instead.

                                By default, this parameter is false and the detections are run
                                in a sliding window fashion by applying the model on cropped sections
                                of the frame (of the same size as the model was trained on).
        =====================   ===========================================

        """

    def average_precision_score(
        self, detect_thresh=0.2, iou_thresh=0.1, mean=False, show_progress=True
    ):
        """
        Computes average precision on the validation set for each class.

        =====================   ===========================================
        **Parameter**            **Description**
        ---------------------   -------------------------------------------
        detect_thresh           Optional float. The probability above which
                                a detection will be considered for computing
                                average precision.
        ---------------------   -------------------------------------------
        iou_thresh              Optional float. The intersection over union
                                threshold with the ground truth labels, above
                                which a predicted bounding box will be
                                considered a true positive.
        ---------------------   -------------------------------------------
        mean                    Optional bool. If False returns class-wise
                                average precision otherwise returns mean
                                average precision.
        =====================   ===========================================

        :return: `dict` if mean is False otherwise `float`
        """

    def show_results(self, rows=5, thresh=0.5, nms_overlap=0.1):
        """
        Displays the results of a trained model on a part of the validation set.

        =====================   ===========================================
        **Parameter**            **Description**
        ---------------------   -------------------------------------------
        rows                    Optional int. Number of rows of results
                                to be displayed.
        ---------------------   -------------------------------------------
        thresh                  Optional float. The probability above which
                                a detection will be considered valid.
        ---------------------   -------------------------------------------
        nms_overlap             Optional float. The intersection over union
                                threshold with other predicted bounding
                                boxes, above which the box with the highest
                                score will be considered a true positive.
        =====================   ===========================================

        """
