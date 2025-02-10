import os
import json
from glob import glob
import sys
sys.path.append("./")
from utility.prompt_template import video_moderation_prompt, video_moderation_prompt_vg, video_moderation_prompt_vg_fine_grained_final, video_moderation_prompt_vg_fine_grained_final_add_animal, video_moderation_prompt_vg_fine_grained_final_add_crash, video_moderation_prompt_vg_fine_grained_final_add_religion
# Define paths
base_dir = "/scratch/czr/Video_moderation/annotation/final_qa"
# categories = ["benign_sharegpt4video", "extremism", "extremism_1", "illegal", "misinformation_1", "misinformation_2", "sexual_2", "sexual_4", "sexual_5", "violence_1", "violence_4", "benign_sexual_4", "benign_misinformation_1", "benign_misinformation_2"]
categories = ["benign_misinformation_2"]
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
        # "C7(Religious & Ritual activities)": 7
    }
    labels = []
    for key, value in aggregated_result.items():
        if value:
            labels.append(category_map[key])
    return labels


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
    annotations = annotations[:300]
    for annotation in annotations:
        for video_file, video_data in annotation.items():
            video_path = os.path.join(dataset_dir, high_category, "target", video_file)
            # print("video_data", video_data)
            query = video_data["query"]
            response = video_data["response"]

            sft_original.append({
                "id": len(sft_original) + 1,
                "video": video_path,
                "conversations": [
                    {
                        "from": "human",
                        "value": f"<video>\n\n{query}"
                    },
                    {
                        "from": "gpt",
                        "value": f"{response}"
                    }
                ]
            })

                     
    if not os.path.exists(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}_qa")):
        os.makedirs(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}_qa"))

    # Save the SFT data for the clips
    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}_qa/original.json"), 'w') as f:
        json.dump(sft_original, f, indent=4)

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}_qa/original_gt.json"), 'w') as f:
        json.dump(gt_original, f, indent=4)

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}_qa/clips.json"), 'w') as f:
        json.dump(sft_clips, f, indent=4)

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}_qa/clips_gt.json"), 'w') as f:
        json.dump(gt_clips, f, indent=4)

    sft_data = sft_original + sft_clips
    gt_data = gt_original + gt_clips

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}_qa/full.json"), 'w') as f:
        json.dump(sft_data, f, indent=4)

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category}_qa/full_gt.json"), 'w') as f:
        json.dump(gt_data, f, indent=4)
    
    print("Number of original data: ", len(sft_original))
    print("Number of clips data: ", len(sft_clips))
    print("Number of full data: ", len(sft_data))    

    print("SFT data preparation complete.")
