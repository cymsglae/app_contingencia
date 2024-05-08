class MMDetectionConfig:
    try:
        import torch
    except:
        pass

    def get_model(self, data, backbone=None, **kwargs):
        from arcgis.learn.models._mmlab_utils import mmlab_models, prepare_mmbatch

        kwargs["model_type"] = "Detection"
        model, cfg = mmlab_models(data, **kwargs)
        self.model = model
        self.cfg = cfg
        self.prepare_mmbatch = prepare_mmbatch
        return model

    def on_batch_begin(self, learn, model_input_batch, model_target_batch, **kwargs):
        if kwargs.get("train"):
            self.model.train_val = False
        else:
            self.set_test_parms()
            self.model.train_val = True
        learn.model.train()

        batch_shape = model_input_batch.permute(0, 2, 3, 1).shape
        gt_batch = []
        for bboxes, classes in zip(*model_target_batch):
            non_pad_index = bboxes.sum(dim=1) != 0
            bboxes = bboxes[non_pad_index]
            classes = classes[non_pad_index] - 1

            bboxes = ((bboxes + 1) / 2) * learn.data.chip_size
            if bboxes.nelement() == 0:
                bboxes = self.torch.tensor([[0.0, 0.0, 1.0, 1.0]]).to(learn.data.device)
                classes = self.torch.tensor([0]).to(learn.data.device)
            # box format conversion [y1,x1,y2,x2] to [x1, y1, x2, y2]
            bboxes = self.torch.index_select(
                bboxes, 1, self.torch.tensor([1, 0, 3, 2]).to(learn.data.device)
            )

            data_sample = self.prepare_mmbatch(
                batch_shape, bboxes=bboxes, labels=classes, model_type="Detection"
            )
            gt_batch.append(data_sample)

        model_input = [model_input_batch, gt_batch]
        # Model target is not required in traing mode so just return the same model_target to train the model.
        model_target = model_target_batch

        # return model_input and model_target
        return model_input, model_target

    def set_test_parms(self, thresh=0.2, nms_overlap=0.1):
        if hasattr(self.model, "roi_head"):
            self.nms_thres = self.model.roi_head.test_cfg.nms.iou_threshold
            self.thresh = self.model.roi_head.test_cfg.score_thr
            self.model.roi_head.test_cfg.nms.iou_threshold = nms_overlap
            self.model.roi_head.test_cfg.score_thr = thresh
        else:
            self.nms_thres = self.model.bbox_head.test_cfg.nms.iou_threshold
            self.thresh = self.model.bbox_head.test_cfg.score_thr
            self.model.bbox_head.test_cfg.nms.iou_threshold = nms_overlap
            self.model.bbox_head.test_cfg.score_thr = thresh

    def transform_input(self, xb, thresh=0.5, nms_overlap=0.1):
        self.set_test_parms(thresh, nms_overlap)
        batch_shape = xb.permute(0, 2, 3, 1).shape
        img_metas = []
        for _ in range(xb.shape[0]):
            data_sample = self.prepare_mmbatch(batch_shape, model_type="Detection")
            img_metas.append(data_sample)

        model_input = [xb, img_metas]
        return model_input

    def transform_input_multispectral(self, xb, thresh=0.5, nms_overlap=0.1):
        return self.transform_input(xb, thresh, nms_overlap)

    def loss(self, model_output, *model_target):
        return model_output[1]

    def post_process(self, pred, nms_overlap, thres, chip_size, device):
        self.set_test_parms(self.thresh, self.nms_thres)
        post_processed_pred = []
        for p in pred:
            bbox = p.pred_instances.bboxes
            label = p.pred_instances.labels + 1
            score = p.pred_instances.scores
            kip_pred = score > self.thresh
            bbox, label, score = (
                bbox[kip_pred],
                label[kip_pred],
                score[kip_pred],
            )
            # convert bboxes in range -1 to 1.
            bbox = bbox / (chip_size / 2) - 1
            # convert bboxes in format [y1,x1,y2,x2]
            bbox = self.torch.index_select(
                bbox, 1, self.torch.tensor([1, 0, 3, 2]).to(bbox.device)
            )
            # Append the tuple in list for each image
            post_processed_pred.append(
                (bbox.data.to(device), label.to(device), score.to(device))
            )

        return post_processed_pred


class MMSegmentationConfig:
    """
    Create class with following fixed function names and the number of arguents to train your model from external source
    """

    try:
        import torch
    except:
        pass

    def get_model(self, data, backbone=None, **kwargs):
        from arcgis.learn.models._mmlab_utils import mmlab_models, prepare_mmbatch

        model_name = kwargs.get("model")
        if model_name.startswith("prithvi100m"):
            # register custom prithvi head
            from arcgis.learn.models._prithvi_archs import TemporalViTEncoder

        kwargs["model_type"] = "Segmentation"
        model, cfg = mmlab_models(data, **kwargs)
        model._is_transformer = kwargs.get("is_transformer", False)
        self.model = model
        self.cfg = cfg
        self.prepare_mmbatch = prepare_mmbatch
        return model

    def on_batch_begin(self, learn, model_input_batch, model_target_batch, **kwargs):
        if kwargs.get("train"):
            self.model.train_val = False
        else:
            self.model.train_val = True
        learn.model.train()
        batch_shape = model_input_batch.permute(0, 2, 3, 1).shape
        gt_batch = []
        for gt_sem_seg in model_target_batch:
            data_sample = self.prepare_mmbatch(
                batch_shape, gt_sem_seg=gt_sem_seg, model_type="Segmentation"
            )
            gt_batch.append(data_sample)

        # handle batch size one in training
        if model_input_batch.shape[0] < 2:
            model_input_batch = self.torch.cat((model_input_batch, model_input_batch))
            gt_batch.append(gt_batch[0])

        model_input = [model_input_batch, gt_batch]
        return model_input, model_target_batch

    def transform_input(self, xb):
        batch_shape = xb.permute(0, 2, 3, 1).shape
        img_metas = []
        for _ in range(xb.shape[0]):
            data_sample = self.prepare_mmbatch(batch_shape, model_type="Segmentation")
            img_metas.append(data_sample)

        model_input = [xb, img_metas]
        return model_input

    def transform_input_multispectral(self, xb):
        return self.transform_input(xb)

    def loss(self, model_output, *model_target):
        return model_output[1]

    def post_process(self, pred, thres=0.5, thinning=True, prob_raster=False):
        """
        In this function you have to return list with appended output for each image in the batch with shape [C=1,H,W]!
        """
        if prob_raster:
            return pred
        else:
            pred = self.torch.unsqueeze(pred.argmax(dim=1), dim=1)
        return pred
