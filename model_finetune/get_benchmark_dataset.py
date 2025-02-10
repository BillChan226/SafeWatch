import os
import json
import random
import shutil
from collections import defaultdict

# Define the base directory to traverse and output directories
base_dir = '/scratch/czr/Video_moderation/final_dataset'
output_root = '/scratch/czr/Video_moderation/benchmark_10_21_backup'
output_original_video_dir = os.path.join(output_root, 'original/videos')
output_clip_video_dir = os.path.join(output_root, 'clips/videos')

# Define paths for benign videos for each category
benign_paths = {
    "C1": "/scratch/czr/Video_moderation/dataset/benign_sexual_4/target",
    "C2": "/scratch/czr/Video_moderation/dataset/violence_3_weak/benign",
    "C3": "/scratch/czr/Video_moderation/dataset/violence_4/benign",
    "C4": [
        "/scratch/czr/Video_moderation/dataset/benign_misinformation_1/target",
        "/scratch/czr/Video_moderation/dataset/benign_misinformation_2/target"
    ],
    "C5": "/scratch/czr/Video_moderation/dataset/benign_sharegpt4video/target",
    "C6": "/scratch/czr/Video_moderation/dataset/benign_sharegpt4video/target"
}

# Define the subcategory sample sizes
sample_sizes = {
    "subtle": 50,
    "evident": 50,
    "implication": 25,
    "hentai": 25,
    "abuse": 25,
    "sexual violence": 50,
    "sexual abuse": 25,
    "child abuse": 50,
    "campus bullying": 50,
    "sexual bullying": 20,
    "animal abuse": 50,
    "assault": 25,
    "fighting": 25,
    "shooting": 25,
    "road accident": 25,
    "sexual violence": 20,
    "vandalism": 25,
    "explosion": 25,
    "incitement to violence": 25,
    "acting": 20,
    "misinformation": 20,
    "out-of-date": 20,
    "alternation": 20,
    "aigc content": 20,
    "arson and vandalism": 20,
    "robbery and burglary": 20,
    "shoplifting and stealing": 20,
    "drugs": 20,
    "war and military actions": 25,
    "terrorism": 25,
    "heresy campaigns": 20,
    "suicide and self-harm": 25,
    "extremely disturbing content": 25,
    "incitement to mental depression": 25
}

# Define the category map with subcategory mappings
subcategory_to_category_map = {
    "evident": "C1",
    "subtle": "C1",
    "implication": "C1",
    "hentai": "C1",
    
    "abuse": "C2",
    "sexual bullying": "C2",
    "sexual abuse": "C2",
    "child abuse": "C2",
    "campus bullying": "C2",
    "animal abuse": "C2",
    
    "assault": "C3",
    "fighting": "C3",
    "shooting": "C3",
    "road accident": "C3",
    "sexual violence": "C3",
    "vandalism": "C3",
    "explosion": "C3",
    "incitement to violence": "C3",
    
    "acting": "C4",
    "misinformation": "C4",
    "out-of-date": "C4",
    "alternation": "C4",
    "aigc content": "C4",
    
    "arson and vandalism": "C5",
    "robbery and burglary": "C5",
    "shoplifting and stealing": "C5",
    "drugs": "C5",
    "war and military actions": "C5",
    "terrorism": "C5",
    "heresy campaigns": "C5",
    
    "terrorism": "C6",
    "suicide and self-harm": "C6",
    "extremely disturbing content": "C6",
    "incitement to violence": "C6",
    "incitement to mental depression": "C6"
}

# Function to normalize subcategory names to lowercase
def normalize_subcategory(subcategory):
    return subcategory.lower()

# Function to process JSON files, sample videos, and save results
def process_json_files(json_files, output_json_dir, output_video_dir):
    # Dictionary to store video paths categorized by subcategory
    video_paths_by_subcategory = defaultdict(list)

    # Traverse and collect video paths by subcategory
    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)
            for item in data:
                for subcategory in item['subcategories']:
                    normalized_subcategory = normalize_subcategory(subcategory)
                    category_name = subcategory_to_category_map.get(normalized_subcategory)
                    if category_name:
                        video_paths_by_subcategory[normalized_subcategory].append(item)

    # Report the number of samples and perform sampling
    for subcategory, items in video_paths_by_subcategory.items():
        sample_size = sample_sizes.get(subcategory, 0) * 2
        sampled_items = random.sample(items, min(sample_size, len(items)))
        category_name = subcategory_to_category_map[subcategory]
        
        # Create output directory if it doesn't exist
        output_dir = os.path.join(output_json_dir, category_name)
        os.makedirs(output_dir, exist_ok=True)
        
        # Prepare the output JSON file path
        output_json_path = os.path.join(output_dir, f"{subcategory}_benchmark.json")
        output_items = []
        
        # Copy videos and update paths in JSON
        for item in sampled_items:
            original_video_path = item['video_path']
            video_filename = os.path.basename(original_video_path)
            new_video_dir = os.path.join(output_video_dir, category_name, subcategory)
            os.makedirs(new_video_dir, exist_ok=True)
            new_video_path = os.path.join(new_video_dir, video_filename)
            
            # Copy the video to the new location
            shutil.copy2(original_video_path, new_video_path)
            
            # Update the video path in the JSON dict
            item['video_path'] = new_video_path
            output_items.append(item)
        
        # Save the modified JSON data
        with open(output_json_path, 'w') as f:
            json.dump(output_items, f, indent=4)
        
        # Report the number of samples
        print(f"{subcategory} (in {category_name}): {len(sampled_items)} videos sampled")

# Function to sample benign videos and generate JSON
def sample_benign_videos(category, source_dirs, output_json_dir, output_video_dir):
    if isinstance(source_dirs, list):
        video_files = []
        for source_dir in source_dirs:
            video_files.extend([os.path.join(source_dir, f) for f in os.listdir(source_dir) if f.endswith(('.mp4', '.avi', '.mov'))])
    else:
        video_files = [os.path.join(source_dirs, f) for f in os.listdir(source_dirs) if f.endswith(('.mp4', '.avi', '.mov'))]

    # Sample 100 videos or as many as available
    sampled_videos = random.sample(video_files, min(10, len(video_files)))

    # Create output directory if it doesn't exist
    benign_output_dir = os.path.join(output_video_dir, category, "benign")
    os.makedirs(benign_output_dir, exist_ok=True)

    # Prepare JSON data
    json_data = []

    for video_path in sampled_videos:
        video_filename = os.path.basename(video_path)
        new_video_path = os.path.join(benign_output_dir, video_filename)
        
        # Copy video to the new location
        shutil.copy2(video_path, new_video_path)
        
        # Prepare JSON entry
        json_entry = {
            "video_path": new_video_path,
            "labels": [],
            "subcategories": []
        }
        json_data.append(json_entry)

    # Save JSON file in the corresponding JSON directory
    json_output_path = os.path.join(output_json_dir, category, "benign_benchmark.json")
    with open(json_output_path, 'w') as json_file:
        json.dump(json_data, json_file, indent=4)

    print(f"{len(sampled_videos)} benign videos sampled and saved for {category}.")

# Collect all `original_gt.json` and `clips_gt.json` files
original_json_files = []
clip_json_files = []

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file == 'original_gt.json':
            original_json_files.append(os.path.join(root, file))
        elif file == 'clips_gt.json':
            clip_json_files.append(os.path.join(root, file))

# Process original video set
print("Processing original video set...")
process_json_files(original_json_files, os.path.join(output_root, 'original'), output_original_video_dir)

# Process clip video set
print("Processing clip video set...")
process_json_files(clip_json_files, os.path.join(output_root, 'clips'), output_clip_video_dir)

# Process benign videos
print("Processing benign videos...")
for category, source_dir in benign_paths.items():
    output_json_dir = os.path.join(output_root, 'original')
    sample_benign_videos(category, source_dir, output_json_dir, output_original_video_dir)

print("Sampling, copying, and saving completed for original, clip, and benign sets.")
