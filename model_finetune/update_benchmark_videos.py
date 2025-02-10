# import os
# import json
# import shutil
# from tqdm import tqdm

# # Define source and target directories
# source_dir = '/scratch/czr/Video_moderation/benchmark_10_17'
# target_dir = '/scratch/czr/Video_moderation/benchmark_10_22'
# target_videos_dir = os.path.join(target_dir, 'videos')

# # Step 1: Traverse each JSON file in the source directory
# for root, _, files in os.walk(source_dir):
#     for file in files:
#         if file.endswith('.json'):
#             json_file_path = os.path.join(root, file)

#             # Load the JSON file
#             with open(json_file_path, 'r') as f:
#                 data = json.load(f)

#             # Determine the category from the JSON file's directory structure
#             category = os.path.basename(root)  # This assumes the immediate parent folder of JSON is the category (e.g., C1, C2)

#             # Create target directory for the JSON file
#             target_json_subdir = os.path.join(target_dir, category)
#             os.makedirs(target_json_subdir, exist_ok=True)

#             # Create target directory for the videos
#             json_filename_without_ext = os.path.splitext(file)[0]  # Get the name of the JSON file without extension
#             target_video_subdir = os.path.join(target_videos_dir, category, json_filename_without_ext)
#             os.makedirs(target_video_subdir, exist_ok=True)

#             print(f"Processing JSON file: {file} in category {category}")

#             # Step 2: Process each entry in the JSON file to copy the video files
#             for entry in data:
#                 video_path = entry['video_path']

#                 if not os.path.exists(video_path):
#                     raise FileNotFoundError(f"Video file not found: {video_path}")

#                 # Define the target path for the video file
#                 video_filename = os.path.basename(video_path)
#                 target_video_path = os.path.join(target_video_subdir, video_filename)

#                 # Copy the video file
#                 shutil.copy2(video_path, target_video_path)

#                 # Adjust the path in the JSON entry to reflect the new location
#                 entry['video_path'] = target_video_path

#                 # Print out the video filename being processed
#                 # print(f"  Copying video: {video_filename} to {target_video_path}")

#             # Step 3: Save the modified JSON file to the appropriate category folder
#             target_json_path = os.path.join(target_json_subdir, file)
#             with open(target_json_path, 'w') as f:
#                 json.dump(data, f, indent=4)

#             # Print the number of entries (videos) in each JSON subcategory
#             print(f"  Number of video entries in {file}: {len(data)}\n")


import os
import json
import shutil
from tqdm import tqdm

# Define source and target directories
source_dir = '/scratch/czr/Video_moderation/benchmark_10_17'
target_dir = '/scratch/czr/Video_moderation/benchmark_10_22'
target_videos_dir = os.path.join(target_dir, 'videos')

# Step 1: Traverse each JSON file in the source directory
for root, _, files in os.walk(source_dir):
    for file in files:
        if file.endswith('.json'):
            json_file_path = os.path.join(root, file)

            # Load the JSON file
            with open(json_file_path, 'r') as f:
                data = json.load(f)

            # Determine the category from the JSON file's directory structure
            category = os.path.basename(root)  # This assumes the immediate parent folder of JSON is the category (e.g., C1, C2)

            # Create target directory for the JSON file
            target_json_subdir = os.path.join(target_dir, category)
            os.makedirs(target_json_subdir, exist_ok=True)

            # Create target directory for the videos
            json_filename_without_ext = os.path.splitext(file)[0]  # Get the name of the JSON file without extension
            target_video_subdir = os.path.join(target_videos_dir, category, json_filename_without_ext)
            os.makedirs(target_video_subdir, exist_ok=True)

            print(f"Processing JSON file: {file} in category {category}")

            # Step 2: Process each entry in the JSON file to copy the video files
            video_counter = 1  # Initialize a counter to rename the videos
            for entry in data:
                video_path = entry['video_path']

                if not os.path.exists(video_path):
                    raise FileNotFoundError(f"Video file not found: {video_path}")

                # Define the new video filename as an incrementing number (e.g., 1.mp4, 2.mp4, ...)
                new_video_filename = f"{video_counter}.mp4"
                target_video_path = os.path.join(target_video_subdir, new_video_filename)

                # Copy the video file and rename it
                shutil.copy2(video_path, target_video_path)

                # Adjust the path in the JSON entry to reflect the new location and name
                entry['video_path'] = target_video_path

                # Increment the counter for the next video
                video_counter += 1

                # Print out the video filename being processed
                # print(f"  Copying and renaming video: {new_video_filename} to {target_video_path}")

            # Step 3: Save the modified JSON file to the appropriate category folder
            target_json_path = os.path.join(target_json_subdir, file)
            with open(target_json_path, 'w') as f:
                json.dump(data, f, indent=4)

            # Print the number of entries (videos) in each JSON subcategory
            print(f"  Number of video entries in {file}: {len(data)}\n")
