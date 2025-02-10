import os
import json
from tqdm import tqdm
import random
import jsonlines

# Define the base directory to search for json files and benchmark videos
base_dir = 'dataset/annotation/'
benchmark_dir = 'safewatch_bench/real_10_22'

# Step 1: Gather all JSON files named 'clips.json' and 'original.json' from the base directory and its subfolders
json_files = []
for root, _, files in os.walk(base_dir):
    for file in files:
        # if file in ['clips.json', 'original.json']:
        if file in ['full.json']:
            json_files.append(os.path.join(root, file))

# Step 2: Load the benchmark video paths
benchmark_video_paths = set()
for root, _, files in os.walk(benchmark_dir):
    continue
    for file in files:
        if file.endswith('.json'):
            if "abuse" in file:
                print("abuse")
                continue
            with open(os.path.join(root, file), 'r') as f:
                data = json.load(f)
                # for entry in data:
                #     benchmark_video_paths.add(entry['video_path'])
                for entry in data:
                    video_filename = os.path.basename(entry['video_path'])  # Extract the file name only
                    benchmark_video_paths.add(video_filename)

# Step 3: Load data from JSON files and merge them into a single list, filtering out entries already in the benchmark
merged_data = []
for json_file in tqdm(json_files, desc="Processing JSON files"):
    with open(json_file, 'r') as f:
        data = json.load(f)
        print("data", len(data))
        for entry in data:
            if os.path.basename(entry['video']) not in benchmark_video_paths:
                merged_data.append(entry)



# Step 4: Randomly shuffle the merged data
random.seed(42)
random.shuffle(merged_data)

# # Step 4: Save the filtered list to a new JSON file
# with open(output_json_path, 'w') as f:
#     json.dump(merged_data, f, indent=4)
print("All data length", len(merged_data))
# save 10% of the data for validation
validation_data = merged_data[:int(0.01 * len(merged_data))]
output_json_path = 'training_set/internvl_swift_sft_10_22_val_vgp.jsonl'
with jsonlines.open(output_json_path, 'w') as f:
    for entry in validation_data:
        new_item = {}
        new_item["query"] = entry["conversations"][0]["value"].replace("<video>\n\n", "").replace("<video>\n", "")
        new_item["response"] = entry["conversations"][1]["value"]
        if "specific ethnic group" in new_item["response"]:
            continue
        new_item["history"] = []
        new_item["videos"] = [entry["video"]]
        f.write(new_item)

print("Validation data length", len(validation_data))

# save the rest of the data for training
train_data = merged_data[int(0.01 * len(merged_data)):]
output_json_path = 'training_set/internvl_swift_sft_10_22_train_vgp.jsonl'
with jsonlines.open(output_json_path, 'w') as f:
    for entry in train_data:
        new_item = {}
        new_item["query"] = entry["conversations"][0]["value"].replace("<video>\n\n", "").replace("<video>\n", "")
        new_item["response"] = entry["conversations"][1]["value"]
        if "specific ethnic group" in new_item["response"]:
            continue
        new_item["history"] = []
        new_item["videos"] = [entry["video"]]
        f.write(new_item)

print("Training data length", len(train_data))
print(f"Filtered fine-tune data saved to {output_json_path}")

