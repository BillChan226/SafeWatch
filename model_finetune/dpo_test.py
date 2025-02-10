import jsonlines
from tqdm import tqdm

data_list = []
with jsonlines.open("/scratch/czr/Video_moderation/sft_data/internvl_swift_sft_09_01_val_vg.jsonl") as f:
    for line in f:
        data_list.append(line)


for item in tqdm(data_list):
    item["rejected_response"] = "I am a test"

with jsonlines.open("/scratch/czr/Video_moderation/sft_data/internvl_swift_sft_09_01_val_vg_dpo.jsonl", mode="w") as f:
    for item in data_list:
        f.write(item)