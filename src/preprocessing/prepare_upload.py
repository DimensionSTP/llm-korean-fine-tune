import dotenv

dotenv.load_dotenv(
    override=True,
)

import os
import re

import torch

from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig

from safetensors.torch import save_file

from tqdm import tqdm

import hydra
from omegaconf import DictConfig


@hydra.main(
    config_path="../../configs/",
    config_name="huggingface.yaml",
)
def prepare_upload(
    config: DictConfig,
) -> None:
    save_dir = f"{config.connected_dir}/prepare_upload/{config.pretrained_model_name}/epoch={config.epoch}"
    checkpoint = torch.load(f"{config.ckpt_path}/model.pt")
    checkpoint_state_dict = checkpoint["state_dict"]
    model_state_dict = {}
    for k, v in list(checkpoint_state_dict.items()):
        if k.startswith("model."):
            k = re.sub(
                r"(model\.)+(.*)",
                r"model.\2",
                k,
            )
            if k.startswith("model.lm_head"):
                k = k.replace(
                    "model.",
                    "",
                )
            model_state_dict[k] = v

    original_model = AutoModelForCausalLM.from_pretrained(config.pretrained_model_name)
    original_model.load_state_dict(model_state_dict)
    state_dict = original_model.state_dict()
    keys = list(state_dict.keys())
    num_splits = 5
    split_size = len(keys) // num_splits

    if not os.path.exists(save_dir):
        os.makedirs(
            save_dir,
            exist_ok=True,
        )
    for i in tqdm(range(0, len(keys), split_size)):
        part_state_dict = {k: state_dict[k] for k in keys[i : i + split_size]}
        save_file(part_state_dict, f"{save_dir}/model_part_{i//split_size}.safetensors")
    tokenizer = AutoTokenizer.from_pretrained(config.pretrained_model_name)
    tokenizer.save_pretrained(save_dir)
    model_config = AutoConfig.from_pretrained(config.pretrained_model_name)
    model_config._name_or_path = f"{config.user_name}/{config.model_type}-scientificQA"
    model_config.torch_dtype = "float32"
    model_config.save_pretrained(save_dir)


if __name__ == "__main__":
    prepare_upload()
