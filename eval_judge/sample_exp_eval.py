import os
import json
import random

# Define the folder path
folder_path = './safewatch_bench/real'

# Prepare a dictionary to store the categorized and sampled video entries by category and subcategory
categorized_video_entries = {}

# Loop through each category folder (C1, C2, etc.)
for category_folder in os.listdir(folder_path):
    category_path = os.path.join(folder_path, category_folder)
    
    if os.path.isdir(category_path):
        # Initialize a dict for the current category
        categorized_video_entries[category_folder] = {}

        # Loop through each json file in the category folder (representing subcategories)
        for json_file in os.listdir(category_path):
            if json_file.endswith('.json'):
                subcategory = json_file.replace('_benchmark.json', '')  # Remove the '_benchmark.json' part to get subcategory name
                json_file_path = os.path.join(category_path, json_file)
                
                # Open and load the json file
                with open(json_file_path, 'r') as file:
                    json_data = json.load(file)
                
                # Initialize the subcategory
                categorized_video_entries[category_folder][subcategory] = []
                
                # Filter entries with "video_content" and "violate_reason" prioritized
                prioritized_entries = [entry for entry in json_data if "video_content" in entry and "violate_reason" in entry]
                other_entries = [entry for entry in json_data if entry not in prioritized_entries]

                print("file", json_file)
                try:
                    # Sample 5 entries from prioritized first, then from other entries if needed
                    sampled_entries = random.sample(prioritized_entries, min(5, len(prioritized_entries))) \
                                  + random.sample(other_entries, max(0, 5 - len(prioritized_entries)))
                except:
                    sampled_entries = random.sample(prioritized_entries, min(4, len(prioritized_entries))) \
                                  + random.sample(other_entries, max(0, 4 - len(prioritized_entries)))
                # Append the full entry (with video path, video content, and violate reason) to the subcategory
                categorized_video_entries[category_folder][subcategory].extend(sampled_entries)

# Output the categorized and sampled video entries (with full details) to a json file
output_file_path = './sampled_exp_real.json'
with open(output_file_path, 'w') as output_file:
    json.dump(categorized_video_entries, output_file, indent=4)

print(f"Sampled categorized video entries saved to {output_file_path}")
