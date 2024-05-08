import os
import json

import numpy as np
import pandas as pd
from copy import deepcopy

from ..models._arcgis_model import ArcGISModel, model_characteristics_folder
from .._utils.text_data import TextDataObject, save_data_in_model_metrics_html
from .._utils.llm_utils import (
    data_sanity_llm,
    lower_nesting,
    extract_entities_from_file,
    process_text,
)
from ._ner_transformer import backbone_models_reverse_map
from ._llm import LLM
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
)
from .._utils.text_data import copy_metrics


class _LlmEntityRecognizer(ArcGISModel):
    def __init__(self, data, backbone="llm", **kwargs):
        super().__init__(data, backbone, **kwargs)
        kwargs["task"] = "ner"
        kwargs = data_sanity_llm(data, **kwargs)
        self._l2id = []
        self._submodel = kwargs.get("submodel", None)
        if data is None:  # create a dummy data object
            data = TextDataObject(task="ner")
            data.create_empty_object_for_ner(
                entities=[], address_tag="Address", label2id={}, batch_size=4
            )
            examples = [np.array(list(i[1].keys())) for i in kwargs.get("examples", [])]
        else:
            data.prepare_data_for_transformer()
            data = data.get_data_object()
            data._is_empty = False
            self._l2id = list(data._unique_tags - {"O"})
        data._backbone = backbone
        self._llm = LLM(**kwargs)
        self._data = data
        self._address_tag = self._data._address_tag
        self.stats = "macro"
        self._validation_response = None

    def save(
        self,
        name_or_path,
        framework="PyTorch",
        publish=False,
        gis=None,
        compute_metrics=True,
        save_optimizer=False,
        save_inference_file=True,
        **kwargs,
    ):
        from ..models._arcgis_model import _create_zip

        zip_files = kwargs.pop("zip_files", True)
        overwrite = kwargs.pop("overwrite", False)

        path = super().save(
            name_or_path,
            "pytorch",
            publish=False,
            gis=None,
            compute_metrics=compute_metrics,
            save_optimizer=False,
            zip_files=False,
            **kwargs,
        )
        self._save_df_to_html(path)

        if zip_files:
            _create_zip(path.name, str(path))

        if publish:
            self._publish_dlpk(
                (path / path.stem).with_suffix(".dlpk"), gis=gis, overwrite=overwrite
            )
        self._validation_response = None

    def _get_emd_params(self, save_inference_file):
        _emd_template = {}
        if self._data is not None:
            _emd_template["AddressTag"] = self._address_tag
            _emd_template["Label2Id"] = {}
        # populate this. First rely on user input followed by the information in the data handle
        _emd_template["Labels"] = self._l2id
        _emd_template["prompt"] = self._llm.backup_prompt
        _emd_template["examples"] = self._llm.examples
        _emd_template["ModelType"] = "llm"
        _emd_template["MixedPrecisionTraining"] = False
        _emd_template["backend"] = "pytorch"
        _emd_template["SequenceLength"] = None
        return _emd_template

    @classmethod
    def from_model(cls, data, backbone, emd_json):
        emd_json["task"] = "ner"
        return cls(data, "llm", **emd_json)

    def _save_df_to_html(self, path):
        if getattr(self._data, "_is_empty", False):
            if self._data.emd_path:
                copy_metrics(self._data.emd_path, path, model_characteristics_folder)
            return

        if self._data._is_empty:
            return

        metrics_per_label = self.metrics_per_label(show_progress=False)
        metrics_per_label_str = metrics_per_label.to_html().replace(">\n", ">")
        #
        dataframe = self.show_results()
        show_result_df_str = dataframe.to_html(index=False, justify="left").replace(
            ">\n", ">"
        )

        show_result_msg = "<p><b>Sample Results</b></p>"
        metrics_per_label_msg = "<p><b>Metrics per label</b></p>"
        #
        text = f"\n\n{metrics_per_label_msg}\n\n{metrics_per_label_str}\n\n{show_result_msg}\n\n{show_result_df_str}"
        #
        save_data_in_model_metrics_html(text, path, model_characteristics_folder)

    @property
    def _model_metrics(self):
        from IPython.utils import io

        if self._data._is_empty:  # Don't calculate model if the data loader is blank
            return {}

        # with io.capture_output() as captured:
        self._validation_response = None
        metrics = self._calculate_model_metrics()

        per_class_metric_df = self.metrics_per_label()
        metrics["metrics_per_label"] = per_class_metric_df.transpose().to_dict()

        return {"Metrics": json.dumps(metrics)}

    def _calculate_model_metrics(self, metric_type="all"):
        metrics = {}
        valid_tag, valid_tag_predicted = self._list_calc()
        if metric_type in ["precision_score", "all"]:
            metrics["precision_score"] = round(
                precision_score(
                    valid_tag,
                    valid_tag_predicted,
                    average=self.stats,
                    zero_division=0,
                    labels=[i.lower() for i in self._data._label2id.keys()],
                ),
                2,
            )

        if metric_type in ["recall_score", "all"]:
            metrics["recall_score"] = round(
                recall_score(
                    valid_tag,
                    valid_tag_predicted,
                    average=self.stats,
                    zero_division=0,
                    labels=[i.lower() for i in self._data._label2id.keys()],
                ),
                2,
            )

        if metric_type in ["f1_score", "all"]:
            metrics["f1_score"] = round(
                f1_score(
                    valid_tag,
                    valid_tag_predicted,
                    average=self.stats,
                    zero_division=0,
                    labels=[i.lower() for i in self._data._label2id.keys()],
                ),
                2,
            )
        if metric_type in ["accuracy_score", "all"]:
            metrics["accuracy"] = round(
                accuracy_score(valid_tag, valid_tag_predicted), 2
            )
        return metrics

    @staticmethod
    def _create_dataframe_from_dict(out_dict):
        out_dict.pop("accuracy", None)
        out_dict.pop("macro avg", None)
        out_dict.pop("weighted avg", None)
        df = pd.DataFrame(out_dict)
        df.drop("support", inplace=True, errors="ignore")
        dataframe = df.T.round(2)
        column_mappings = {
            "precision": "Precision_score",
            "recall": "Recall_score",
            "f1-score": "F1_score",
        }
        dataframe.rename(columns=column_mappings, inplace=True)
        return dataframe

    def extract_entities(
        self, text_list, batch_size=4, drop=True, debug=False, show_progress=False
    ):
        # if the provided input is path or list of documents
        file_name, process_rec = [], []
        if isinstance(text_list, str):
            if os.path.exists(text_list):
                if os.path.isdir(text_list):
                    file_name = os.listdir(text_list)
                else:
                    file_name = [text_list]
        elif isinstance(text_list, list):
            # Check if the first record is the path
            if os.path.exists(text_list[0]):
                file_name = text_list
        # if there is a list of file name. Then recreate the text_list
        if len(file_name):
            text_list = {}
            for i in file_name:
                with open(i) as f:
                    text_list[i] = f.readlines()
            temp_val = [(k, i) for (k, v) in text_list.items() for i in v]
            file_name = [j[0] for j in temp_val]
            text_list = [j[1] for j in temp_val]

        result = self._llm.process(
            text_list,
            show_progress=show_progress,
            task="learn_text",
            batch_size=batch_size,
        )
        result = lower_nesting(result)
        _keep_labels = [i.lower() for i in self._l2id]
        # Add final formatting for upstream
        result = pd.DataFrame.from_dict(result, orient="columns").T.fillna("")
        keep_labels = set(result.columns).intersection(set(_keep_labels))
        result = result[list(keep_labels)]
        result.insert(0, "TEXT", value=text_list)
        extra_labels = set(_keep_labels).difference(keep_labels)
        for idx, col in enumerate(extra_labels):
            result.insert(idx + 1, col, value=[""] * len(result))

        result.index = [int(i) for i in result.index]
        result = result.applymap(
            lambda a: a if not isinstance(a, list) else ",".join(a)
        )
        if not len(file_name):
            file_name = [f"Example_{i}" for i in range(len(result))]
        result["Filename"] = file_name
        return result.sort_index()

    def unfreeze(self):
        raise Exception(
            f"This method is not supported when the backbone is configured as {self._submodel}."
        )

    def freeze(self):
        raise Exception(
            f"This method is not supported when the backbone is configured as {self._submodel}."
        )

    def _flatten_list(self, samples):
        sample = []
        for i in samples:
            i = [j.lower() for j in i]
            sample += i
        return sample

    def _list_calc(self):
        valid_token = deepcopy(self._data._valid_tokens)
        valid_tag = deepcopy(self._data._valid_tags)
        tags = []
        tokens = []

        for i, j in zip(valid_token, valid_tag):
            entities = extract_entities_from_file(i, j)
            entity_dict = dict()
            _ = [
                entity_dict.setdefault(x[1], []).append(process_text(" ".join(x[0])))
                for x in entities
                if x[0]
            ]

            val = {k: key for key, val in entity_dict.items() for k in val}
            tokens.append(list(val.keys()))
            tags.append(list(val.values()))

        # make it format agnostic

        valid_tag = tags
        valid_tag_predicted = deepcopy(valid_tag)

        for idx, j in enumerate(valid_tag_predicted):
            valid_tag_predicted[idx] = ["O" for i in j]

        # Convert valid token to sentences
        valid_sentence = [" ".join(x) for x in valid_token]

        for idx, j in enumerate(tokens):
            valid_token[idx] = [i.lower() for i in j]

        if len(valid_token) == 0:
            raise Exception("Can't calculate metric with no data object")

        if self._validation_response is None:
            self._validation_response = self.extract_entities(valid_sentence)
            del self._validation_response["TEXT"]

        if "Filename" in self._validation_response.columns:
            del self._validation_response["Filename"]

        for idx, i in enumerate(self._validation_response.to_dict(orient="records")):
            for key, vals in i.items():
                try:
                    for val in vals.split(","):
                        if val in valid_token[idx]:
                            index = valid_token[idx].index(val)
                            valid_tag_predicted[idx][index] = key
                except:
                    pass

        valid_tag_predicted = self._flatten_list(valid_tag_predicted)
        valid_tag = self._flatten_list(valid_tag)

        return valid_tag, valid_tag_predicted

    def metrics_per_label(self, show_progress=True):
        valid_tag, valid_tag_predicted = self._list_calc()
        report = classification_report(
            valid_tag,
            valid_tag_predicted,
            labels=[i.lower() for i in self._data._label2id.keys()],
            output_dict=True,
            zero_division=0,
        )
        return self._create_dataframe_from_dict(report)

    def plot_losses(self, show=None):
        raise Exception(
            f"This method is not supported when the backbone is configured as {self._submodel}."
        )

    def precision_score(self):
        return self._calculate_model_metrics()["precision_score"]

    def f1_score(self):
        return self._calculate_model_metrics()["f1_score"]

    def recall_score(self):
        return self._calculate_model_metrics()["recall_score"]

    def show_results(self, ds_type="valid"):
        if self._data._is_empty:
            raise Exception("Data object is empty or supplied as None")
        else:
            valid_token = deepcopy(self._data._valid_tokens)
            # Convert valid token to sentences
            valid_sentence = [" ".join(x) for x in valid_token]
            validation_response = self.extract_entities(valid_sentence)
            # validation_response.insert(0, "TEXT", value=valid_sentence)
            if "Filename" in validation_response.columns:
                del validation_response["Filename"]
            return validation_response

    def fit(
        self,
        epochs=10,
        lr=None,
        one_cycle=True,
        early_stopping=False,
        checkpoint=True,  # "all", "best", True, False ("best" and True are same.)
        tensorboard=False,
        monitor="valid_loss",  # whatever is passed here, earlystopping and checkpointing will use that.
        **kwargs,
    ):
        raise Exception(
            f"This method is not supported when the backbone is configured as {self._submodel}."
        )

    def load(self, name_or_path, **kwargs):
        raise Exception(
            f"This method is not supported when the backbone is configured as {self._submodel}."
        )

    def lr_find(self, allow_plot=True):
        raise Exception(
            f"This method is not supported when the backbone is configured as {self._submodel}."
        )
