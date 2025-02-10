import os
import json
import re
from tqdm import tqdm

def extract_video_content(model_output):
    pattern = r"VIDEO_CONTENT:\s*(.*?)(?=\nVIOLATE_REASON:|$)"
    match = re.search(pattern, model_output, re.DOTALL)
    return match.group(1).strip() if match else ""

def extract_violate_reason(model_output):
    pattern = r"VIOLATE_REASON:\s*(.*?)(?=\nMODERATION_RESULT:|$)"
    match = re.search(pattern, model_output, re.DOTALL)
    return match.group(1).strip() if match else ""

def update_benchmark_json(test_set_folder, original_dataset_folder):
    # Iterate over each JSON file in the test set folder
    for root, dirs, files in os.walk(test_set_folder):
        for file_name in tqdm(files):
            if file_name.endswith('.json'):
                
                test_file_path = os.path.join(root, file_name)
                print(test_file_path)
                
                # Load the test JSON file
                with open(test_file_path, 'r') as test_file:
                    test_data = json.load(test_file)

                # Update each entry in the test set
                for benchmark in tqdm(test_data):
                    video_filename = os.path.basename(benchmark['video_path'])
                    # print("video_filename: ", video_filename)
                    # Find corresponding entry in the original dataset
                    for orig_root, orig_dirs, orig_files in os.walk(original_dataset_folder):
                        if 'full.json' in orig_files:

                            with open(os.path.join(orig_root, 'full.json'), 'r') as orig_file:
                                original_data = json.load(orig_file)
                                for entry in original_data:
                                    if video_filename in entry['video']:
                                        # input(entry)
                                        # Found matching video entry, extract content
                                        for conversation in entry['conversations']:
                                            if 'gpt' in conversation['from']:
                                                model_output = conversation['value']
                                                video_content = extract_video_content(model_output)
                                                violate_reason = extract_violate_reason(model_output)
                                                
                                                # Add extracted fields to the benchmark
                                                benchmark['video_content'] = video_content
                                                benchmark['violate_reason'] = violate_reason
                                                # print(benchmark)
                                                # input()
                                                break
                                        
                # Save the updated benchmark data back to the file
                with open(test_file_path, 'w') as updated_test_file:
                    json.dump(test_data, updated_test_file, indent=4)
                
                # input("Press Enter to continue...")

# Set the test set and original dataset folder paths
test_set_folder = '/scratch/czr/Video_moderation/benchmark_09_06_C4'
original_dataset_folder = '/scratch/czr/Video_moderation/final_dataset_benign'

# Run the update process
update_benchmark_json(test_set_folder, original_dataset_folder)
