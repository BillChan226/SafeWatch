import os
import json
from glob import glob
import sys
sys.path.append("./")
from utility.prompt_template import video_moderation_prompt, video_moderation_prompt_vg, video_moderation_prompt_vg_fine_grained_final, video_moderation_prompt_vg_fine_grained_final_add_animal, video_moderation_prompt_vg_fine_grained_final_add_crash, video_moderation_prompt_vg_fine_grained_final_add_religion
# Define paths
base_dir = "/scratch/czr/Video_moderation/annotation/final"
# categories = ["benign_sharegpt4video", "extremism", "extremism_1", "illegal", "misinformation_1", "misinformation_2", "sexual_2", "sexual_4", "sexual_5", "violence_1", "violence_4", "benign_sexual_4", "benign_misinformation_1", "benign_misinformation_2", "sexual_abuse"]
categories = ["benign_sexual_4"]
dataset_dir = "/scratch/czr/Video_moderation/dataset"
output_dir = "/scratch/czr/Video_moderation/clips"

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

save_dataset_folder = "final_dataset_10_17"

# Function to aggregate labels
def aggregate_labels(labels):
    aggregated = {
        "C1(Sexual Content)": False,
        "C2(Harassment & Bullying)": False,
        "C3(Threats, Violence & Harm)": False,
        "C4(False & Deceptive Information)": False,
        "C5(Illegal/Regulated Activities)": False,
        "C6(Hateful Content & Extremism)": False,
        # "C7(Religious & Ritual activities)": False
    }
    for label in labels:
        if label.startswith("C1"):
            aggregated["C1(Sexual Content)"] = True
        elif label.startswith("C2"):
            aggregated["C2(Harassment & Bullying)"] = True
        elif label.startswith("C3"):
            aggregated["C3(Threats, Violence & Harm)"] = True
        elif label.startswith("C4"):
            aggregated["C4(False & Deceptive Information)"] = True
        elif label.startswith("C5"):
            aggregated["C5(Illegal/Regulated Activities)"] = True
        elif label.startswith("C6"):
            aggregated["C6(Hateful Content & Extremism)"] = True
        # elif label.startswith("C7"):
        #     aggregated["C7(Religious & Ritual activities)"] = True
    return aggregated

def get_gt_labels(aggregated_result):

    category_map = {
        "C1(Sexual Content)": 1,
        "C2(Harassment & Bullying)": 2,
        "C3(Threats, Violence & Harm)": 3,
        "C4(False & Deceptive Information)": 4,
        "C5(Illegal/Regulated Activities)": 5,
        "C6(Hateful Content & Extremism)": 6,
        # "C7(Religious & Ritual activities)": 7,
    }
    labels = []
    for key, value in aggregated_result.items():
        if value:
            labels.append(category_map[key])
    return labels


# prompt = video_moderation_prompt_vg
prompt = video_moderation_prompt_vg_fine_grained_final
# prompt = video_moderation_prompt_vg_fine_grained_final_add_animal
# prompt = video_moderation_prompt_vg_fine_grained_final_add_crash
# prompt = video_moderation_prompt_vg_fine_grained_final_add_religion

# Read and merge all JSON files in each category folder
for high_category in categories:

    sft_data = []
    gt_data = []

    sft_original = []
    gt_original = []

    sft_clips = []
    gt_clips = []


    category_dir = os.path.join(base_dir, high_category)
    json_files = glob(os.path.join(category_dir, "*.json"))
    
    annotations = []
    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)
            annotations.extend(data)
    
    # Prepare SFT data for whole videos
    annotations = annotations[:2000]
    for annotation in annotations:
        for video_file, video_data in annotation.items():
            video_path = os.path.join(dataset_dir, high_category, "target", video_file)

            # Aggregate labels for the whole video
            labels = set()
            # labels = {}
            subcategory_labels = []

            for timestamp, timestamp_data in video_data["timestamps"].items():
                for category, subcategories in timestamp_data["labels"].items():
                    labels.add(category)
                    subcategory_labels.extend(subcategories)

            video_content = video_data["video_content"]
            violate_reason = video_data["violate_reason"]
            
            subcategory_labels = list(set(subcategory_labels))
            moderation_result = aggregate_labels(labels)
            moderation_result_str = json.dumps(moderation_result, indent=4)
            gt_labels = get_gt_labels(moderation_result)
            gt_item = {"video_path": video_path, "labels": gt_labels, "subcategories": subcategory_labels}
            gt_original.append(gt_item)

            if isinstance(video_content, list):
                video_content = video_content[0]
            if isinstance(violate_reason, list):
                violate_reason = violate_reason[0]

            video_content = video_content.split("MODERATION_RESULT")[0]
            content_sentence_list = video_content.split(". ")
            video_content = ""
            content_idx = 0
            for sentence in content_sentence_list:
                if "MODERATION_RESULT" in sentence or "VIOLATE_REASON" in sentence or "Evident" in sentence or "Subtle" in sentence or "Implication" in sentence or "Violence" in sentence or "Abuse" in sentence or "Bullying" in sentence:
                    continue
                content_idx += 1
                if content_idx > 3:
                    break
                video_content += sentence + ". "

            violate_reason = violate_reason.split("nGUARDRAIL")[0]
            violate_reason_sentence_list = violate_reason.split(". ")
            violate_reason = ""
            content_idx = 0
            for sentence in violate_reason_sentence_list:
                if "MODERATION_RESULT" in sentence or "VIOLATE_REASON" in sentence or "Evident" in sentence or "Subtle" in sentence or "Implication" in sentence or "Violence" in sentence or "Abuse" in sentence or "Bullying" in sentence:
                    continue
                content_idx += 1
                if content_idx > 3:
                    break
                violate_reason += sentence + ". "
            
            sft_original.append({
                "id": len(sft_original) + 1,
                "video": video_path,
                "conversations": [
                    {
                        "from": "human",
                        "value": f"<video>\n{prompt}"
                    },
                    {
                        "from": "gpt",
                        "value": f"DESCRIPTION: {video_content.strip()}\nGUARDRAIL: {moderation_result_str}\nEXPLANATION: {violate_reason.strip()}"
                    }
                ]
            })
    
    # Prepare SFT data for video clips
    
    for annotation in annotations:
        for video_file, video_data in annotation.items():
            for timestamp, timestamp_data in video_data["timestamps"].items():
                start_time_str = timestamp_data["start_time"]
                end_time_str = timestamp_data["end_time"]
                clip_path = timestamp_data["clips"]#[0]
                
                subcategory_labels = []
                for category, subcategories in timestamp_data["labels"].items():
                    subcategory_labels.extend(subcategories)
                subcategory_labels = list(set(subcategory_labels))
                moderation_result = aggregate_labels(timestamp_data["labels"].keys())
                moderation_result_str = json.dumps(moderation_result, indent=4)
                gt_labels = get_gt_labels(moderation_result)
                gt_item = {"video_path": os.path.join(output_dir, clip_path), "labels": gt_labels, "subcategories": subcategory_labels}
                gt_clips.append(gt_item)
                
                if "video_content" in timestamp_data:
                    timestamp_data['video_content'] = timestamp_data['video_content'].split("nGUARDRAIL")[0]
                else:
                    timestamp_data['video_content'] = ""
                if "violate_reason" in timestamp_data:
                    timestamp_data['violate_reason'] = timestamp_data['violate_reason'].split("MODERATION_RESULT")[0]
                else:
                    timestamp_data['violate_reason'] = ""
                sft_clips.append({
                    "id": len(sft_clips) + 1,
                    "video": os.path.join(output_dir, clip_path),
                    "conversations": [
                        {
                            "from": "human",
                            "value": f"<video>\n{prompt}"
                        },
                        {
                            "from": "gpt",
                            "value": f"DESCRIPTION: {timestamp_data['video_content']}\nGUARDRAIL: {moderation_result_str}\nEXPLANATION: {timestamp_data['violate_reason']}"
                        }
                    ]
                })
    
    if not os.path.exists(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", high_category)):
        os.makedirs(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", high_category))

    # Save the SFT data for the clips
    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}/original.json"), 'w') as f:
        json.dump(sft_original, f, indent=4)

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}/original_gt.json"), 'w') as f:
        json.dump(gt_original, f, indent=4)

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}/clips.json"), 'w') as f:
        json.dump(sft_clips, f, indent=4)

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}/clips_gt.json"), 'w') as f:
        json.dump(gt_clips, f, indent=4)

    sft_data = sft_original + sft_clips
    gt_data = gt_original + gt_clips

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}/full.json"), 'w') as f:
        json.dump(sft_data, f, indent=4)

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}/full_gt.json"), 'w') as f:
        json.dump(gt_data, f, indent=4)
    
    print("Number of original data: ", len(sft_original))
    print("Number of clips data: ", len(sft_clips))
    print("Number of full data: ", len(sft_data))    

    print("SFT data preparation complete.")
