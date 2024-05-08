import ast
import json
import os
import re
import torch
import numpy as np
from pathlib import Path

import requests
import warnings
from abc import ABC
from typing import Dict, List
from pydantic import BaseModel
from fastprogress.fastprogress import master_bar, progress_bar
from torch.utils.data import DataLoader, Dataset
from .._utils.llm_utils import (
    SYSTEM_PROMPT,
    TASK_EXAMPLE,
    MAPPING_DICT,
    TestNer,
    safe_extract_ner,
    safe_ner_check,
    safe_literal_eval_dict,
    completion_message,
    format_result,
    CustomDataset,
    ner_pydantic_template,
)
from .._utils.common import _get_device_id
from ._prompt_schema import textclassifierprompt, nerprompt
from transformers import AutoModelForCausalLM, AutoTokenizer
from string import Template
from copy import deepcopy

HAS_TENACITY = True
try:
    import tenacity
except:
    HAS_TENACITY = False


if HAS_TENACITY:
    from tenacity import stop_after_attempt, wait_exponential, retry_if_exception_type


def retry(func):
    if HAS_TENACITY:
        return tenacity.retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(min=5, max=60),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )(func)
    return func


@retry
def calling_api(url, header, payload):
    s = requests.request(
        method="POST", url=url, headers=header, data=json.dumps(payload)
    )
    if s.status_code == 404:
        raise requests.exceptions.ConnectionError(
            f"Please verify the LLM configuration. Provided {s.json()['error']['message']}"
        )
    elif s.status_code == 429:
        # raise requests.exceptions.TooManyRedirects(f"{s.json()['error']['message']}")
        raise requests.exceptions.TooManyRedirects(
            f"The API has exceeded the allocated rate limit."
        )
    elif s.status_code == 401:
        raise Exception(
            f"The API key appears to be invalid. Please verify the LLM parameters."
        )
    elif s.status_code >= 400:
        # raise Exception(f"{s.json()['error']['message']}")
        raise Exception(
            "The API server has encountered an error. Please try again later."
        )
    return s


class AbstractLLM(ABC):
    def __init__(self, **llm_config) -> None:
        if llm_config is None:
            llm_config = {}
        self.API_BASE = llm_config.get("api_base_or_org_name", None)

        self.API_KEY = llm_config.get("api_key", None)

        self.API_VERSION = llm_config.get("api_version", "2023-05-15")
        self.API_TYPE = llm_config.get("api_type", "mistral")
        self.model_name = llm_config.get("api_model", "gpt-35-turbo-16k")
        self.engine = llm_config.get("api_engine", None)
        self.temperature = llm_config.get("temperature", 0.1)
        self.agent = llm_config.get("agent", None)

        if self.API_TYPE == "azure":
            assert (
                self.API_KEY is not None and self.API_BASE is not None
            ), "LLM config must be supplied."
        elif self.API_TYPE == "openai":
            assert (
                self.API_KEY is not None
            ), "LLM config must have following keys - `api_key` and `api_type`"
        elif self.API_TYPE == "mistral":
            pass
        else:
            raise Exception(f"llm_params should include `api_type` set to `openai`")
        self.header = None


# wrap the llm base class
class llm_base(AbstractLLM):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tokenizer = None
        self._llm_model = None
        self.max_token = 4096
        self._device = _get_device_id()
        self.setup_agent()

    def setup_agent(self):
        if self.API_TYPE == "azure":
            self.header = {"Content-Type": "application/json", "api-key": self.API_KEY}
            self.API_BASE = f"{self.API_BASE}/openai/deployments/{self.engine}/chat/completions?api-version={self.API_VERSION}"
        elif self.API_TYPE == "openai":
            self.header = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.API_KEY}",
            }
            self.API_BASE = f"https://api.openai.com/v1/chat/completions"
        else:
            model_path = Path.home() / "AppData\Local\ESRI\DeepLearning\Mistral"
            if not os.path.exists(model_path):
                raise FileNotFoundError(
                    "Mistral model is not installed. To install Mistral backbone follow"
                    " https://github.com/Esri/deep-learning-frameworks?tab=readme-ov-file#additional-installation-for-disconnected-environment"
                )
            self._llm_model = (
                AutoModelForCausalLM.from_pretrained(model_path).half().to(self._device)
            )
            self._tokenizer = AutoTokenizer.from_pretrained(model_path)
            self._tokenizer.pad_token_id = self._tokenizer.eos_token_id

    def _llm_onprim_inference(self, messages, direct=False):
        # current processing pipeline does not use any batching due to memory restrictions
        if not direct:
            encodes = self._tokenizer.apply_chat_template(
                messages["messages"], return_tensors="pt"
            )
        else:
            encodes = self._tokenizer([messages], return_tensors="pt", padding=True).to(
                self._device
            )["input_ids"]

        model_inputs = encodes.to(self._device)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", module="transformers")
            generated_ids = self._llm_model.generate(
                model_inputs,
                max_new_tokens=200,
                do_sample=False,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        resp = self._tokenizer.batch_decode(
            [generated_ids[0][len(model_inputs[0]) : -1]]
        )[0]
        return resp

    def _llm_onprim_inference_batch(
        self, messages: List, show_progress=False, batch_size=4
    ):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", module="transformers")
            formatted_message = []
            formatted_message_retry = []
            for message in messages:
                formatted_message.append(
                    self._tokenizer.apply_chat_template(
                        message["messages"], tokenize=False
                    )
                )
                message["messages"] += [{"role": "assistant", "content": "s"}]
                message["messages"] += [
                    {
                        "role": "user",
                        "content": "Notice you have missed { and } in your response. "
                        "Please regenerate your response following the schema. ",
                    }
                ]
                formatted_message_retry.append(
                    self._tokenizer.apply_chat_template(
                        message["messages"], tokenize=False
                    )
                )
            dl = DataLoader(
                CustomDataset(formatted_message), batch_size=batch_size, shuffle=False
            )
            dl_formatted = DataLoader(
                CustomDataset(formatted_message_retry),
                batch_size=batch_size,
                shuffle=False,
            )
            response = []
            for batch, batch_retry in progress_bar(
                list(zip(dl, dl_formatted)), display=show_progress
            ):
                batch_token = self._tokenizer(
                    batch, return_tensors="pt", padding=True
                ).to("cuda")
                resps = self._llm_model.generate(
                    **batch_token,
                    max_new_tokens=200,
                    do_sample=True,
                    pad_token_id=self._tokenizer.eos_token_id,
                )
                for idx, generated_ids in enumerate(resps):
                    sliced_response = self._tokenizer.batch_decode(
                        [generated_ids[len(batch_token["input_ids"][idx]) : -1]],
                        skip_special_tokens=True,
                    )[0]
                    if retry_can(sliced_response):
                        data = batch_retry[idx]
                        sliced_response = self._llm_onprim_inference(data, direct=True)
                    response.append(sliced_response)
        return response

    def _validate_prompt_length(self, message):
        return True

    def __call__(self, *args, **kwargs):
        """
        This module will make the LLM calls internally
        :param args:
        :param kwargs:
        :return:
        """
        system_message = kwargs.get("system", None)
        messages = kwargs.get("messages", None)
        show_progress = kwargs.get("show_progress", False)
        batch_size = kwargs.get("batch_size", 4)
        if isinstance(messages, str):
            messages = [messages]

        payload = []

        for message in messages:
            if self._validate_prompt_length(f"{system_message}\n\n{message}"):
                temp_message = deepcopy(system_message)
                temp_message.append({"role": "user", "content": f"{message}"})
                payload.append({"messages": temp_message})

        if not HAS_TENACITY:
            raise Exception("tenacity package is missing from environment")

        final_resp = []
        if len(payload):
            if self.API_TYPE in ["azure", "openai"]:
                for data in progress_bar(payload, display=show_progress):
                    try:
                        if self.API_TYPE == "openai":
                            data["model"] = "gpt-3.5-turbo-16k"
                        s = calling_api(self.API_BASE, self.header, data)
                    except requests.exceptions.ConnectionError as e:
                        return str(e), 1
                    except requests.exceptions.TooManyRedirects as e:
                        return str(e), 1
                    except Exception as e:
                        return str(e), 1

                    if s.status_code == 200:
                        final_resp.append(completion_message(s.json()).generations)
                    else:
                        final_resp.append(completion_message([]).generations)
            else:
                # can we put safe inference by putting it in try catch
                # s = self._llm_onprim_inference(data)
                # if retry_can(s):
                #     data["messages"] += [{"role": "assistant", "content": "s"}]
                #     data["messages"] += [{"role": "user", "content": "Notice you have missed { and } in your response. Please regenerate your response following the schema. "}]
                #     print("---------------- retrying ------------------")
                #     s = self._llm_onprim_inference(data)
                # print("generated resp", s)
                # final_resp.append(s)
                final_resp = self._llm_onprim_inference_batch(
                    payload, show_progress=show_progress, batch_size=batch_size
                )
        return final_resp, 0


def retry_can(text):
    if text.find("{") >= 0:
        return False
    else:
        return True


class caller:
    def __init__(self, **kwargs):
        self.token = kwargs.get("token", None)
        self.llm_base_object = llm_base(**kwargs)

    def __call__(self, *args, **kwargs):
        task = kwargs["task"]
        assert task is not None
        # method = kwargs.get("method", "GET")
        messages = kwargs.get("messages", None)
        prompt = kwargs.get("prompt", None)
        show_progress = kwargs.get("show_progress", False)
        batch_size = kwargs.get("batch_size", 4)
        resp, status = self.llm_base_object(
            messages=messages,
            system=prompt,
            show_progress=show_progress,
            batch_size=batch_size,
        )
        # output = []
        if not status:
            return resp
        else:
            raise Exception(resp)


class LLM:
    def __init__(self, **kwargs) -> None:
        self._llm = caller(**kwargs)
        self.data = kwargs.get("data", None)
        self.prompt = kwargs.get("prompt", None)
        self.backup_prompt = kwargs.get("prompt", None)
        self.example = kwargs.get("examples", [])
        if not self.example and self.data:
            raise Exception(
                "Please supply a data object or examples as keyword arguments"
            )

        self.examples = kwargs.get("examples", [])
        self.additional_info = kwargs.get("labels", None)
        self.task = kwargs.get("task", None)
        if self.task is not None:
            self.format_control = MAPPING_DICT.get(self.task, None)
            if self.format_control is None:
                raise Exception(
                    f"Task name is not valid - please select one of the following\n "
                    f"{list(MAPPING_DICT.keys())}"
                )

        self._validate_prompt()
        self.format_prompt()
        self.temp_prompt = None

    def _validate_prompt(self):
        prompt_dict = {
            "examples": self.example,
            "labels": self.additional_info,
            "prompt": self.prompt,
        }

        if self.task == "text-classifier":
            try:
                ne = textclassifierprompt(**prompt_dict)
            except:
                raise Exception(
                    f"{self.task} requires the examples in the below format \n"
                    f"Pydantic Schema: Dict[str, List]\n"
                    f"Example: {TASK_EXAMPLE[self.task]}"
                )
            ne._valid()
            self.example = ne._format_example()

        elif self.task == "ner":
            try:
                ne = nerprompt(**prompt_dict)
            except:
                raise Exception(
                    f"{self.task} requires the examples in the below format \n"
                    f"Pydantic Schema: Dict[str, List]\n"
                    f"Example: {TASK_EXAMPLE[self.task]}"
                )
            ne._valid()
            self.example = ne._format_example()
        else:
            return None

    def get_prompt(self):
        return self.prompt

    def add_context(self, context):
        self.temp_prompt = f"{self.prompt}\n\nContext: {context}"

    def process(self, user_input, show_progress=False, task=None, batch_size=4):
        results = []
        prompt_token_length = 0

        if isinstance(user_input, str):
            messages = [user_input]
        else:
            messages = user_input

        if self.temp_prompt is not None:
            resp = self._llm(
                messages=messages,
                prompt=self.temp_prompt,
                task=task,
                show_progress=show_progress,
                batch_size=batch_size,
            )
        else:
            resp = self._llm(
                messages=messages,
                prompt=self.prompt,
                task=task,
                show_progress=show_progress,
                batch_size=batch_size,
            )
        return format_result(resp, self.task)

    def format_prompt(self):
        # build the payload dict
        if self.prompt is None:
            self.prompt = MAPPING_DICT.get(self.task).get("prompt")

        add_str = {}
        key_list = []
        if self.task == "ner":
            example = self.examples[0][1]
            for key, val in example.items():
                add_str[f"{key}"] = "List"
                key_list.append(key)
        else:
            key_list = list(self.examples.keys())
            add_str["class"] = "List"

        if self.task == "ner":
            payload = {
                "user_prompt": self.prompt,
                "sentence": self.example[0].split("\n\n")[0],
                "answer": self.example[0].split("\n\n")[1],
                "next_sentence": self.example[1].split("\n\n")[0],
                "schema": str(add_str),
                "classes": ",".join(key_list),
            }
        else:
            payload = {
                "user_prompt": self.prompt,
                "sentence": self.example[0].split("\n\n")[0],
                "answer": (
                    self.example[0].split("\n\n")[1]
                    if self.task == "ner"
                    else str({"class": self.example[0].split("\n\n")[1]})
                ),
                "next_sentence": self.example[1].split("\n\n")[0],
                "schema": str(add_str),
                "classes": ",".join(key_list),
            }
        system_prompt = Template(
            MAPPING_DICT.get(self.task).get("system_prompt")
        ).substitute(**payload)

        # split the example in user and assistant
        self.prompt = [{"role": "user", "content": system_prompt}]
        user, assistant = [], []
        # build the chain, Since we have already sampled the records from the user and assistant.
        if self.task == "ner":
            for idx, i in enumerate(self.example):
                # print(idx, self.prompt)
                if idx == 0:
                    pass
                elif idx == 1:
                    self.prompt += [
                        {"role": "assistant", "content": i.split("\n\n")[1]}
                    ]
                else:
                    self.prompt += [{"role": "user", "content": i.split("\n\n")[0]}]
                    self.prompt += [
                        {"role": "assistant", "content": i.split("\n\n")[1]}
                    ]
        else:
            for idx, i in enumerate(self.example):
                if idx == 0:
                    pass
                elif idx == 1:
                    self.prompt += [
                        {
                            "role": "assistant",
                            "content": str({"class": i.split("\n\n")[1]}),
                        }
                    ]
                else:
                    self.prompt += [{"role": "user", "content": i.split("\n\n")[0]}]
                    self.prompt += [
                        {
                            "role": "assistant",
                            "content": str({"class": i.split("\n\n")[1]}),
                        }
                    ]

    def _parse_and_return(self):
        if isinstance(self.additional_info, (list, tuple)):
            return ",".join(self.additional_info)
        elif isinstance(self.additional_info, dict):
            return ",".join(self.additional_info.keys())
        else:
            raise Exception("Could not parse the labels")
