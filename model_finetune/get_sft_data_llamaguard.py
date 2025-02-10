import os
import json
import random
import copy
import re
from glob import glob

# Define paths
base_dir = "/scratch/czr/Video_moderation/annotation/final"
# categories = ["benign_sharegpt4video", "extremism", "extremism_1", "illegal", "misinformation_1", "misinformation_2", "sexual_2", "sexual_4", "sexual_5", "violence_1", "violence_4", "benign_sexual_4", "benign_misinformation_1", "benign_misinformation_2", "sexual_abuse"]
count = 300
categories = ["benign_misinformation_2"]  # You can include other categories as needed
dataset_dir = "/scratch/czr/Video_moderation/dataset"
output_dir = "/scratch/czr/Video_moderation/clips"

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)

save_dataset_folder = "final_dataset_10_17"

# Full list of policies with rephrased names and definitions
all_policies = [
    {
        "original_code": "C1",
        "name_variants": ["Sexual Content", "NSFW Content", "Adult Material", "Explicit Sexual Content"],
        "definition_variants": [
            """<box>
C1: [Policy Name Placeholder]
Core Value: Protect users, especially minors, from sexual exploitation and unwanted exposure to sexually explicit content.
[BLOCKED] Content involving sexual exploitation or abuse of minors, including child sexual abuse imagery, should be flagged.
[BLOCKED] Content containing pornography or sexually explicit material primarily intended for arousal should be flagged.
[BLOCKED] Content promoting sexual services and sexual implications should be flagged.
[ALLOWED] Non-sexual contexts (e.g., breastfeeding, art), dancing, gymnastics, live performances, and sports are allowed.
</box>""",
            # Additional rephrased definitions can be added here
        ]
    },
    {
        "original_code": "C2",
        "name_variants": ["Harassment & Bullying", "Abuse and Harassment", "Bullying and Intimidation", "Harassment and Abuse"],
        "definition_variants": [
            """<box>
C2: [Policy Name Placeholder]
Core Value: Foster a safe and respectful environment where users are protected from harassment, intimidation, and privacy violations.
[BLOCKED] No bullying, harassment including sexual, animal, child abuse, cyberbullying, and campus bullying.
[BLOCKED] No sharing others' private info or images of them in private spaces without consent.
[BLOCKED] No potential abuse and cruelty to animals, children, and students including speech and actions.
</box>""",
            # Additional rephrased definitions can be added here
        ]
    },
    {
        "original_code": "C3",
        "name_variants": ["Threats, Violence & Harm", "Violence and Harmful Acts", "Threatening and Dangerous Behavior", "Violence, Threats, and Harm"],
        "definition_variants": [
            """<box>
C3: [Policy Name Placeholder]
Core Value: Prevent the promotion and glorification of violence, self-harm, and dangerous activities to ensure user safety.
[BLOCKED] Content involving violence, dangerous behavior such as fighting, shooting, vandalism, assault that result in injury or destruction of property.
[BLOCKED] Content intending to cause harm or violence to the audience or other people should be flagged.
[BLOCKED] Content depicting graphic violence, or dangerous activities that could incite harm or violence should be flagged.
</box>""",
            # Additional rephrased definitions can be added here
        ]
    },
    {
        "original_code": "C4",
        "name_variants": ["False & Deceptive Information", "Misinformation and Deception", "False and Misleading Content", "Deceptive Information"],
        "definition_variants": [
            """<box>
C4: [Policy Name Placeholder]
Core Value: Maintain a trustworthy platform by combating the spread of false information, deception, and fraudulent activities.
[BLOCKED] Content spreading false information that causes harm or is malicious, such as denying the existence of tragic events, unsubstantiated medical claims.
[BLOCKED] Content spreading misinformation, out-of-date facts, alteration of videos, AI-generated content, or other false information should be flagged.
[BLOCKED] Content that involves individuals acting to deceive or manipulate others, such as impersonation, false identity, or false claims, should be flagged.
</box>""",
            # Additional rephrased definitions can be added here
        ]
    },
    {
        "original_code": "C5",
        "name_variants": ["Illegal/Regulated Activities", "Unlawful and Regulated Content", "Illegal Activities and Restricted Goods", "Prohibited and Regulated Actions"],
        "definition_variants": [
            """<box>
C5: [Policy Name Placeholder]
Core Value: Comply with legal requirements and prevent the promotion of illegal activities to protect users and society at large.
[BLOCKED] Content promoting illegal activity like selling drugs, weapons, or exploitation should be flagged.
[BLOCKED] Content containing unauthorized promotion of regulated goods like gambling, alcohol, or tobacco should be flagged.
[BLOCKED] Content involving regulated activities such as arson, explosion, robbery, shoplifting should be flagged.
[BLOCKED] Content involving war scenes, military actions, terrorism actions, extremist activities should be flagged.
</box>""",
            # Additional rephrased definitions can be added here
        ]
    },
    {
        "original_code": "C6",
        "name_variants": ["Hateful Content & Extremism", "Hate Speech and Extremism", "Disturbing Content and Self-Harm", "Extremist and Hateful Material"],
        "definition_variants": [
            """<box>
C6: [Policy Name Placeholder]
Core Value: Stand against hatred, discrimination, and extremism to create an inclusive community that respects diversity.
[BLOCKED] Content involving extremely disturbing content, such as torture, gore, mutilation, or self-harm, should be flagged.
[BLOCKED] Content inciting anti-social behavior, depression, self-harm, or suicide should be flagged.
</box>""",
            # Additional rephrased definitions can be added here
        ]
    }
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
    annotations = annotations[:count]
    for annotation in annotations:
        for video_file, video_data in annotation.items():
            video_path = os.path.join(dataset_dir, high_category, "target", video_file)
            # Randomly select number of policies (1 to 6)
            num_policies = random.randint(1, 6)
            random.shuffle(all_policies)
            # Select the first num_policies policies
            selected_policies = copy.deepcopy(all_policies[:num_policies])
            # Randomly shuffle the selected policies
            random.shuffle(selected_policies)
            # Assign new codes starting from C1
            new_codes = [f"C{i+1}" for i in range(len(selected_policies))]
            # Create a mapping from original codes/names to new codes/names
            code_name_mapping = {}
            for i, policy in enumerate(selected_policies):
                policy['new_code'] = new_codes[i]
                # Randomly select a policy name and definition variant
                policy_name = random.choice(policy['name_variants'])
                policy_def = random.choice(policy['definition_variants'])
                policy['selected_name'] = policy_name
                policy['selected_definition'] = policy_def.replace("[Policy Name Placeholder]", policy_name)
                # Build mapping
                # Map 'C1', 'C1 (Sexual Content)', 'category C1', 'category C1 (Sexual Content)'
                original_code_pattern = re.escape(policy['original_code'])
                original_name_pattern = re.escape(policy['name_variants'][0])
                # Map original code with name in parentheses
                code_name_mapping[rf"{original_code_pattern} ?\((.*?)\)"] = f"{policy['new_code']}({policy['selected_name']})"
                # Map original code alone
                code_name_mapping[rf"\b{original_code_pattern}\b"] = policy['new_code']
                # Map original name
                code_name_mapping[rf"\b{original_name_pattern}\b"] = policy['selected_name']
                # Map 'category C1'
                code_name_mapping[rf"category {original_code_pattern}"] = f"category {policy['new_code']}"
                # Map 'category {original_code} (Original Name)'
                code_name_mapping[rf"category {original_code_pattern} ?\((.*?)\)"] = f"category {policy['new_code']}({policy['selected_name']})"
            # Build the prompt
            policy_codes = [f"{policy['new_code']}: {policy['selected_name']}" for policy in selected_policies]
            policy_codes_str = "; ".join(policy_codes)
            policy_explanations = "\n".join([policy['selected_definition'].replace(policy['original_code'], policy['new_code']) for policy in selected_policies])
            prompt = f"""
You are a helpful assistant to detect if a video contains unsafe, harmful content that needs to be moderated.

**As a moderation assistant, your tasks are:**

**1. Analyze the video for the presence of the following harmful content categories:**

<BEGIN HARMFUL CATEGORIES>
{policy_codes_str};
<END HARMFUL CATEGORIES>

**Refer to the detailed explanations of each category below:**

<BEGIN HARMFUL CATEGORIES EXPLANATIONS>
{policy_explanations}
<END HARMFUL CATEGORIES EXPLANATIONS>

**Provide your safety assessment:**

First line must read 'safe' or 'unsafe'.
If unsafe, a second line must include a comma-separated list of violated categories.
"""
            # Aggregate labels for the whole video
            labels = set()
            subcategory_labels = []
            for timestamp, timestamp_data in video_data["timestamps"].items():
                for category, subcategories in timestamp_data["labels"].items():
                    labels.add(category)
                    subcategory_labels.extend(subcategories)
            subcategory_labels = list(set(subcategory_labels))
            # Aggregate labels based on selected policies
            moderation_result = aggregate_labels(labels, selected_policies)
            # Determine if video is safe or unsafe
            if any(moderation_result.values()):
                assessment = "unsafe"
                violated_categories = []
                for i, policy in enumerate(selected_policies):
                    if moderation_result[policy['original_code']]:
                        violated_categories.append(f"{policy['new_code']}({policy['selected_name']})")
                violated_categories_str = ", ".join(violated_categories)
                assistant_response = f"{assessment}\n{violated_categories_str}"
            else:
                assessment = "safe"
                assistant_response = f"{assessment}"
            # Ground truth labels (indices)
            gt_labels = [i+1 for i, policy in enumerate(selected_policies) if moderation_result[policy['original_code']]]
            gt_item = {"video_path": video_path, "labels": gt_labels, "subcategories": subcategory_labels}
            gt_data.append(gt_item)
            # Prepare the conversation data
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
                        "value": assistant_response
                    }
                ]
            })

    # Save the dataset
    high_category_modified = high_category + "_assessment_randomized"

    output_folder = os.path.join(f"/scratch/czr/Video_moderation/{save_dataset_folder}", high_category_modified)
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with open(os.path.join(output_folder, f"full.json"), 'w') as f:
        json.dump(sft_data, f, indent=4)

    with open(os.path.join(output_folder, f"full_gt.json"), 'w') as f:
        json.dump(gt_data, f, indent=4)
    
    print("Number of data instances: ", len(sft_data))    
    print("SFT data preparation complete for category:", high_category)
