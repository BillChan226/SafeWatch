import os
import json
from collections import defaultdict

# Define the path to the dataset directory
base_dir = '/scratch/czr/Video_moderation/final_dataset'

# Define the category map with subcategory mappings
subcategory_to_category_map = {
    "evident": "C1 (Sexual Content)",
    "subtle": "C1 (Sexual Content)",
    "implication": "C1 (Sexual Content)",
    "hentai": "C1 (Sexual Content)",
    "benign": "C1 (Sexual Content)",
    
    "abuse": "C2 (Harassment & Bullying)",
    "sexual bullying": "C2 (Harassment & Bullying)",
    
    "assault": "C3 (Threats, Violence & Harm)",
    "fighting": "C3 (Threats, Violence & Harm)",
    "shooting": "C3 (Threats, Violence & Harm)",
    "road accident": "C3 (Threats, Violence & Harm)",
    "sexual violence": "C3 (Threats, Violence & Harm)",
    "vandalism": "C3 (Threats, Violence & Harm)",
    "explosion": "C3 (Threats, Violence & Harm)",
    "incitement to violence": "C3 (Threats, Violence & Harm)",
    
    "acting": "C4 (False & Deceptive Information)",
    "misinformation": "C4 (False & Deceptive Information)",
    "out-of-date": "C4 (False & Deceptive Information)",
    "alternation": "C4 (False & Deceptive Information)",
    "aigc content": "C4 (False & Deceptive Information)",
    
    "arson and vandalism": "C5 (Illegal/Regulated Activities)",
    "robbery and burglary": "C5 (Illegal/Regulated Activities)",
    "shoplifting and stealing": "C5 (Illegal/Regulated Activities)",
    "drugs": "C5 (Illegal/Regulated Activities)",
    "war and military actions": "C5 (Illegal/Regulated Activities)",
    "terrorism": "C5 (Illegal/Regulated Activities)",
    "heresy campaigns": "C5 (Illegal/Regulated Activities)",
    
    "terrorism": "C6 (Hateful Content & Extremism)",
    "suicide and self-harm": "C6 (Hateful Content & Extremism)",
    "extremely disturbing content": "C6 (Hateful Content & Extremism)",
    "incitement to violence": "C6 (Hateful Content & Extremism)",
    "heresy campaigns": "C6 (Hateful Content & Extremism)",
    "incitement to mental depression": "C6 (Hateful Content & Extremism)"
}

# Initialize counters for each category and sub-category
category_count = defaultdict(int)
subcategory_count = defaultdict(lambda: defaultdict(int))

# Function to normalize subcategory names to lowercase
def normalize_subcategory(subcategory):
    return subcategory.lower()

# Traverse the base directory to find all original_gt.json files
for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file == 'original_gt.json':
            file_path = os.path.join(root, file)
            with open(file_path, 'r') as f:
                data = json.load(f)
                for item in data:
                    # Count for high-level categories based on the subcategories
                    for subcategory in item['subcategories']:
                        normalized_subcategory = normalize_subcategory(subcategory)
                        category_name = subcategory_to_category_map.get(normalized_subcategory, "Unknown Category")
                        
                        # Increment the count for the appropriate category and subcategory
                        category_count[category_name] += 1
                        subcategory_count[category_name][normalized_subcategory] += 1

# Display the results
print("Category Counts:")
for category, count in category_count.items():
    print(f"{category}: {count}")

print("\nSubcategory Counts:")
for category, subcategories in subcategory_count.items():
    print(f"\n{category}:")
    for subcategory, count in subcategories.items():
        print(f"  {subcategory}: {count}")