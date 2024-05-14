from typing import Dict, Any, List

import pandas as pd

import torch
from torch.utils.data import Dataset

from transformers import AutoTokenizer


class UpStageDialoguesDataset(Dataset):
    def __init__(
        self,
        data_path: str,
        split: str,
        seed: int,
        target_column_name: str,
        num_devices: int,
        batch_size: int,
        pretrained_model_name: str,
        is_llama: bool,
        text_max_length: int,
    ) -> None:
        self.data_path = data_path
        self.split = split
        self.seed = seed
        self.target_column_name = target_column_name
        self.num_devices = num_devices
        self.batch_size = batch_size
        self.data_encoder = AutoTokenizer.from_pretrained(
            pretrained_model_name,
            use_fast=True,
        )
        if is_llama:
            self.data_encoder.pad_token = "[PAD]"
            self.data_encoder.padding_side = "left"
        dataset = self.get_dataset()
        self.datas = dataset["datas"]
        self.labels = dataset["labels"]
        self.text_max_length = text_max_length

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(
        self,
        idx: int,
    ) -> Dict[str, Any]:
        encoded = self.encode_text(self.datas[idx])
        label = self.encode_text(self.labels[idx])["input_ids"]
        encoded["labels"] = label
        if "token_type_ids" in encoded.keys():
            del encoded["token_type_ids"]
        return {
            "encoded": encoded,
            "index": idx,
        }

    def get_dataset(self) -> Dict[str, List[Any]]:
        if self.split in ["train", "test"]:
            csv_path = f"{self.data_path}/{self.split}.csv"
            data = pd.read_csv(csv_path)
            data = data.fillna("_")
        elif self.split == "val":
            csv_path = f"{self.data_path}/dev.csv"
            data = pd.read_csv(csv_path)
            data = data.fillna("_")
        elif self.split == "predict":
            csv_path = f"{self.data_path}/test.csv"
            data = pd.read_csv(csv_path)
            data = data.fillna("_")
            if self.num_devices > 1:
                last_row = data.iloc[-1]
                total_batch_size = self.num_devices * self.batch_size
                remainder = (len(data) % total_batch_size) % self.num_devices
                if remainder != 0:
                    num_dummies = self.num_devices - remainder
                    repeated_rows = pd.DataFrame([last_row] * num_dummies)
                    repeated_rows.reset_index(
                        drop=True,
                        inplace=True,
                    )
                    data = pd.concat(
                        [
                            data,
                            repeated_rows,
                        ],
                        ignore_index=True,
                    )
        else:
            raise ValueError(f"Inavalid split: {self.split}")
        datas = data["dialogue"].tolist()
        labels = data[self.target_column_name].tolist()
        return {
            "datas": datas,
            "labels": labels,
        }

    def encode_text(
        self,
        data: str,
    ) -> Dict[str, torch.Tensor]:
        encoded = self.data_encoder(
            data,
            padding="max_length",
            max_length=self.text_max_length,
            truncation=True,
            return_tensors="pt",
            add_special_tokens=True,
        )
        encoded = {k: v.squeeze(0) for k, v in encoded.items()}
        return encoded
