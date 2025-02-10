import sys
import os
import torch
import json
import time
from tqdm import tqdm
sys.path.append('./')
# from utility.models.model import VideoModerator
from utility.prompt_template_new import * 
import argparse
from torch.profiler import profile, record_function, ProfilerActivity

argparser = argparse.ArgumentParser()

argparser.add_argument("--model", "-m", type=str, required=True)
argparser.add_argument("--checkpoint", "-c", type=str, required=False, default=None)

args = argparser.parse_args()


# Model Configuration
model_name = args.model
device = "cuda"

if args.checkpoint is not None:
    model_name = model_name + "_" + args.checkpoint.split("/")[-1]

# Initialize the moderation model
# moderation_model = VideoModerator(model_name, device=device, ckpt_dir=args.checkpoint)
moderation_model = None
# Define the directory structure
benchmark_root = "./safewatch_bench"
result_root = f"./result/{model_name}"


# Ensure the result directory exists
os.makedirs(result_root, exist_ok=True)


def evaluate_videos(json_file_path, result_dir, model):
    # Load the benchmark JSON file
    with open(json_file_path, 'r') as f:
        print(json_file_path)
        input()
        data_list = json.load(f)

    response_list = []
    t1 = time.time()

    if os.path.exists(os.path.join(result_dir, os.path.basename(json_file_path))):
        print(f"Result file already exists: {os.path.join(result_dir, os.path.basename(json_file_path))}")
        return len(data_list)

    for idx, item in tqdm(enumerate(data_list), total=len(data_list)):

        video_path = item["video_path"]
        labels = item.get("labels", [])

        print(f"Processing video: {video_path}")

        new_dict = {"video_path": video_path, "labels": labels}
        
        # Generate the moderation prompt
        prompt = video_moderation_prompt_vg_fine_grained_final
        try:
            print("video_path", video_path)
            response = model.generate_response(prompt, video_path)
            print(response)
        except Exception as e:
            print(f"Error processing video {video_path}: {e}")
            continue

        new_dict["response"] = response

        response_list.append(new_dict)

    # Save the responses to the appropriate result directory
    result_file_path = os.path.join(result_dir, os.path.basename(json_file_path))
    with open(result_file_path, 'w') as f:
        json.dump(response_list, f, indent=4)

    t2 = time.time()
    average_latency_per_sample = (t2 - t1) / len(data_list)
    return len(data_list)


def evaluate_benchmark(benchmark_root, result_root, model):
    # Walk through the benchmark directory structure
    t_start = time.time()
    num_videos = 0
    for root, dirs, files in os.walk(benchmark_root):
        for file in files:
            if file.endswith('.json'):
                # Create the corresponding result directory
                relative_path = os.path.relpath(root, benchmark_root)

                result_dir = os.path.join(result_root, relative_path)

                os.makedirs(result_dir, exist_ok=True)

                # Process each JSON file
                json_file_path = os.path.join(root, file)
                num_videos += evaluate_videos(json_file_path, result_dir, model)
                # print(f"Number of videos processed: {num_videos}")

    t_end = time.time()
    average_latency_per_sample = (t_end - t_start) / num_videos
    print(f"Number of videos processed: {num_videos}")
    print(f"Average latency per sample: {average_latency_per_sample:.6f} seconds")

if __name__ == "__main__":
    # Start the evaluation
    evaluate_benchmark(benchmark_root, result_root, moderation_model)
