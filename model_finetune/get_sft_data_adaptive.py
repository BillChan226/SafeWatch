import os
import json
import random
from glob import glob
import sys
sys.path.append("./")
from utility.prompt_template import video_moderation_prompt_vg_fine_grained_final

# Define paths
base_dir = "/scratch/czr/Video_moderation/annotation/final"
categories = ["benign_sharegpt4video"]  # You can include other categories as needed
dataset_dir = "/scratch/czr/Video_moderation/dataset"
output_dir = "/scratch/czr/Video_moderation/clips"

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

save_dataset_folder = "final_dataset_10_18"

# Full list of policies in order
all_policies = [
    {
        "original_code": "C1",
        "name": "Sexual Content",
        "explanation": """<box>
C1: Sexual Content:
Core Value: Protect users, especially minors, from sexual exploitation and unwanted exposure to sexually explicit content.
[BLOCKED] Content involving sexual exploitation or abuse of minors, including child sexual abuse imagery, should be flagged.
[BLOCKED] Content containing pornography or sexually explicit material primarily intended for arousal should be flagged.
[BLOCKED] Content promoting sexual services and sexual implications should be flagged.
[ALLOWED] Non-sexual contexts (e.g. breastfeeding, art), dancing, gymnastics, live performances, and sports are allowed.
</box>"""
    },
    {
        "original_code": "C2",
        "name": "Harassment & Bullying",
        "explanation": """<box>
C2: Harassment & Bullying:
Core Value: Foster a safe and respectful environment where users are protected from harassment, intimidation, and privacy violations.
[BLOCKED] No bullying, harassment including sexual, animal, child abuse, cyberbullying, and campus bullying.
[BLOCKED] No sharing others' private info or images of them in private spaces without consent.
[BLOCKED] No potential abuse and cruelty to animals, child, and students including speech and actions.
</box>"""
    },
    {
        "original_code": "C3",
        "name": "Threats, Violence & Harm",
        "explanation": """<box>
C3: Threats, Violence & Harm:
Core Value: Prevent the promotion and glorification of violence, self-harm, and dangerous activities to ensure user safety.
[BLOCKED] Content involving violence, dangerous behavior such as fighting, shooting, vandalism, assault that result in injury or destruction of property.
[BLOCKED] Content intending to cause harm or violence to the audience or other people should be flagged.
[BLOCKED] Content depicting graphic violence, or dangerous activities that could incite harm or violence should be flagged.
</box>"""
    },
    {
        "original_code": "C4",
        "name": "False & Deceptive Information",
        "explanation": """<box>
C4: False & Deceptive Information:
Core Value: Maintain a trustworthy platform by combating the spread of false information, deception, and fraudulent activities.
[BLOCKED] Content spreading false information that causes harm or is malicious, such as denying the existence of tragic events, unsubstantiated medical claims.
[BLOCKED] Content spreading misinformation, out-of-date facts, alteration of videos, AI-generated content, or other false information should be flagged.
[BLOCKED] Content that involves individuals acting to deceive or manipulate others, such as impersonation, false identity, or false claims, should be flagged.
</box>"""
    },
    {
        "original_code": "C5",
        "name": "Illegal/Regulated Activities",
        "explanation": """<box>
C5: Illegal/Regulated Activities:
Core Value: Comply with legal requirements and prevent the promotion of illegal activities to protect users and society at large.
[BLOCKED] Content promoting illegal activity like selling drugs, weapons, or exploitation should be flagged.
[BLOCKED] Content containing unauthorized promotion of regulated goods like gambling, alcohol, or tobacco should be flagged.
[BLOCKED] Content involving regulated activities such as arson, explosion, robbery, shoplifting should be flagged.
[BLOCKED] Content involving war scenes, military actions, terrorism actions, heresy activities should be flagged.
</box>"""
    },
    {
        "original_code": "C6",
        "name": "Hateful Content & Extremism",
        "explanation": """<box>
C6: Hateful Content & Extremism:
Core Value: Stand against hatred, discrimination, and extremism to create an inclusive community that respects diversity.
[BLOCKED] Content involving extremely disturbing content, such as torture, gore, mutilation, or self-harm, should be flagged.
[BLOCKED] Content inciting anti-social behavior, depression, self-harm, or suicide should be flagged.
</box>"""
    }
]

# List of safe video messages
safe_messages = [
    "The video is appropriate and complies with all safety guidelines.",
    "No safety violations were detected in the video.",
    "The content of the video is safe and acceptable.",
    "The video does not contain any harmful or unsafe material.",
    "All reviewed content appears to be within safety standards.",
    "The video is free of any content that requires moderation.",
    "No inappropriate or unsafe content was found in the video.",
    "The video complies with all policies and is safe for viewing.",
    "There are no violations; the video is appropriate.",
    "The content is safe and does not breach any guidelines."
]

# Function to aggregate labels based on selected policies
def aggregate_labels(labels, selected_policies):
    aggregated = {policy['original_code']: False for policy in selected_policies}
    for label in labels:
        for policy in selected_policies:
            if label == policy['original_code']:
                aggregated[policy['original_code']] = True
    return aggregated

sft_data = []
gt_data = []

# Read and merge all JSON files in each category folder
for high_category in categories:
    category_dir = os.path.join(base_dir, high_category)
    json_files = glob(os.path.join(category_dir, "*.json"))
    
    annotations = []
    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)
            annotations.extend(data)
    
    # Prepare SFT data for whole videos
    annotations = annotations[:500]
    for annotation in annotations:
        for video_file, video_data in annotation.items():
            video_path = os.path.join(dataset_dir, high_category, "target", video_file)
            # Randomly select number of policies (1 to 6)
            num_policies = random.randint(1, 6)
            random.shuffle(all_policies)
            # Select the first num_policies policies starting from C1
            selected_policies = all_policies[:num_policies]
            # Randomly shuffle the selected policies
            shuffled_policies = selected_policies.copy()
            random.shuffle(shuffled_policies)
            # Assign new codes starting from C1
            new_codes = [f"C{i+1}" for i in range(len(shuffled_policies))]
            for i, policy in enumerate(shuffled_policies):
                policy['new_code'] = new_codes[i]
            # Build the prompt
            policy_codes = [f"{policy['new_code']}: {policy['name']}" for policy in shuffled_policies]
            policy_codes_str = "; ".join(policy_codes)
            policy_explanations = "\n".join([policy['explanation'].replace(policy['original_code'], policy['new_code']) for policy in shuffled_policies])
            prompt = f"""
You are a helpful video guardrail model to detect if a video contains unsafe, harmful content that needs to be moderated.

**As a guardrail model, your tasks are:**

**1. Summarize the content of the video, beginning with "DESCRIPTION:".**
**2. Analyze the video for the presence of the following harmful content categories:**

<BEGIN HARMFUL CATEGORIES>
{policy_codes_str};
<END HARMFUL CATEGORIES>

**Refer to the detailed explanations of each category below:**

<BEGIN HARMFUL CATEGORIES EXPLANATIONS>
{policy_explanations}
<END HARMFUL CATEGORIES EXPLANATIONS>

**Provide the guardrail result in the following JSON format:**

GUARDRAIL = {{
{', '.join([f'"{policy["new_code"]}({policy["name"]})": boolean' for policy in shuffled_policies])}
}}

**Set the value to true ONLY for the most relevant categories found in the video. If no harmful content is detected, set all values to false.**
**The first line must be the summarization of the content of the video, beginning with "DESCRIPTION:"**
**The second line must be the JSON format of "GUARDRAIL", beginning with "GUARDRAIL:"**
**For each category flagged as true, provide a brief explanation of why it was flagged and list the specific policy violations within that category in the third line, beginning with "EXPLANATION:"**
"""
            # Aggregate labels for the whole video
            labels = set()
            subcategory_labels = []
            video_content = ""
            violate_reason = ""
            for timestamp, timestamp_data in video_data["timestamps"].items():
                if "video_content" in timestamp_data:
                    video_content += timestamp_data["video_content"] + "\n"
                if "violate_reason" in timestamp_data:
                    violate_reason += timestamp_data["violate_reason"] + "\n"
                for category, subcategories in timestamp_data["labels"].items():
                    labels.add(category)
                    subcategory_labels.extend(subcategories)

            subcategory_labels = list(set(subcategory_labels))
            # Aggregate labels based on selected policies
            moderation_result = aggregate_labels(labels, selected_policies)
            # Map the aggregated results to the new codes
            moderation_result_mapped = {}
            for policy in shuffled_policies:
                original_code = policy['original_code']
                new_code = policy['new_code']
                key = f"{new_code}({policy['name']})"
                moderation_result_mapped[key] = moderation_result[original_code]
            moderation_result_str = json.dumps(moderation_result_mapped, indent=4)
            # Ground truth labels (indices)
            gt_labels = [i+1 for i, policy in enumerate(shuffled_policies) if moderation_result[policy['original_code']]]
            gt_item = {"video_path": video_path, "labels": gt_labels, "subcategories": subcategory_labels}
            gt_data.append(gt_item)

            video_content = video_content.split("MODERATION_RESULT")[0]
            video_content = video_content.strip()
            
            # Adjust VIOLATE_REASON based on moderation_result
            if all(not value for value in moderation_result_mapped.values()):
                violate_reason = random.choice(safe_messages)
            else:
                violate_reason = violate_reason.split("MODERATION_RESULT")[0]
                violate_reason = violate_reason.strip()

            sft_data.append({
                "id": len(sft_data) + 1,
                "video": video_path,
                "conversations": [
                    {
                        "from": "human",
                        "value": f"<video>\n{prompt}"
                    },
                    {
                        "from": "gpt",
                        "value": f"DESCRIPTION: {video_content}\nGUARDRAIL: {moderation_result_str}\nEXPLANATION: {violate_reason}"
                    }
                ]
            })

    # Save the dataset
    high_category_modified = high_category + "_adaptive"

    if not os.path.exists(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", high_category_modified)):
        os.makedirs(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", high_category_modified))

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category_modified}/full.json"), 'w') as f:
        json.dump(sft_data, f, indent=4)

    with open(os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", f"{high_category_modified}/full_gt.json"), 'w') as f:
        json.dump(gt_data, f, indent=4)
    
    print("Number of data instances: ", len(sft_data))    
    print("SFT data preparation complete for category:", high_category)
