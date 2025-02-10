import os
import json

def update_video_paths_and_count(base_dir):
    """
    Recursively walk through 'base_dir' looking for .json files.
    For each file:
      - Determine if it resides under the 'genai' subfolder or not (i.e., 'real').
      - Load the JSON, which should be a list of dicts each containing a 'video_path'.
      - Replace the old prefixes:
          '/scratch/czr/Video_moderation/benchmark_10_22_genai/' -> 'genai/'
          '/scratch/czr/Video_moderation/benchmark_10_22/'       -> 'real/'
      - Save the updated JSON back to file.
      - Keep track of the total number of entries belonging to genai and real.
    """
    
    # These are the prefixes to strip/replace:
    genai_old_prefix = "/scratch/czr/Video_moderation/benchmark_10_22_genai/"
    real_old_prefix  = "/scratch/czr/Video_moderation/benchmark_10_22/"
    
    # Counters for the total number of entries
    genai_count = 0
    real_count  = 0

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".json"):
                json_path = os.path.join(root, file)

                # Determine if this JSON file is under 'genai' or 'real'
                # (Check if 'genai' is a directory in the path)
                if "genai" + os.sep in root or root.endswith("genai"):
                    # It's under the genai folder
                    folder_type = "genai"
                    old_prefix = genai_old_prefix
                else:
                    # Otherwise, assume it's under 'real'
                    folder_type = "real"
                    old_prefix = real_old_prefix

                # Load the JSON
                with open(json_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        print(f"Skipping invalid JSON file: {json_path}")
                        continue

                # data is expected to be a list of dicts
                if not isinstance(data, list):
                    print(f"Skipping file because top-level JSON is not a list: {json_path}")
                    continue

                # Update each entry's 'video_path'
                for entry in data:
                    video_path = entry.get("video_path", "")
                    # Replace the old prefix if present
                    if video_path.startswith(old_prefix):
                        entry["video_path"] = video_path.replace(old_prefix, folder_type + "/")

                # Update the counters
                if folder_type == "genai":
                    genai_count += len(data)
                else:
                    real_count += len(data)

                # Write the updated list back to the JSON file
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

    return real_count, genai_count

if __name__ == "__main__":
    base_directory = "/scratch/czr/SafeWatch/safewatch_bench"  # Modify this as needed
    real_total, genai_total = update_video_paths_and_count(base_directory)
    print(f"Total 'real' entries updated: {real_total}")
    print(f"Total 'genai' entries updated: {genai_total}")