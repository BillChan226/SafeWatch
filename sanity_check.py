import os
import json
import math
from tqdm import tqdm

ANNOTATION_DIR = "/scratch/czr/SafeWatch/dataset/annotation"
DATASET_ROOT = "/scratch/czr/SafeWatch/"

def human_readable_size(num_bytes):
    """
    Convert an integer number of bytes into a human-readable string (e.g., '2.34 GB').
    """
    if num_bytes == 0:
        return "0 B"
    size_units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = int(math.floor(math.log(num_bytes, 1024)))
    p = math.pow(1024, idx)
    size = round(num_bytes / p, 2)
    return f"{size} {size_units[idx]}"

def check_annotation_files():
    """
    1) Traverse all JSON files under ANNOTATION_DIR.
    2) For each file, parse JSON, look for 'video' or 'video_path' in each item.
    3) Check that the file exists under DATASET_ROOT + that relative path.
    4) Print any missing file paths found.
    """
    missing_files = []  # Will store tuples of (json_file, missing_video_path)

    # Walk through all subdirs of ANNOTATION_DIR
    for root, dirs, files in os.walk(ANNOTATION_DIR):
        # Filter for JSON files
        json_files = [f for f in files if f.lower().endswith(".json")]
        for jf in json_files:
            json_path = os.path.join(root, jf)
            # Load JSON
            with open(json_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    print(f"WARNING: Could not decode JSON: {json_path}")
                    continue

            # If data is not a list, skip or adapt as needed
            if not isinstance(data, list):
                continue

            # Check each item for "video" or "video_path"
            for item in data:
                video_paths = []
                if "video" in item:
                    video_paths.append(item["video"])
                if "video_path" in item:
                    video_paths.append(item["video_path"])

                for vp in video_paths:
                    # The JSON typically has something like "dataset/full/abuse_1/..."
                    # The actual file path is /scratch/czr/SafeWatch/dataset/ + vp
                    abs_path = os.path.join(DATASET_ROOT, vp.lstrip("/"))

                    if not os.path.exists(abs_path):
                        print(abs_path)
                        input()
                        missing_files.append((json_path, vp))

    # Print summary
    if missing_files:
        print("\n=== MISSING FILES FOUND ===")
        for json_file, vid_path in missing_files:
            print(f"JSON: {json_file}\n  Missing Video Path: {vid_path}\n")
    else:
        print("\nNo missing files detected under annotation JSONs.\n")


def compute_total_storage_used(directory):
    """
    Recursively compute total size of all files in `directory`.
    """
    total_bytes = 0
    # Use tqdm for a progress bar while walking
    for root, dirs, files in tqdm(os.walk(directory), desc="Calculating total size"):
        for f in files:
            fp = os.path.join(root, f)
            if os.path.isfile(fp):
                total_bytes += os.path.getsize(fp)
    return total_bytes

def main():
    # 1) Check annotation JSON files for missing videos
    check_annotation_files()

    # 2) Compute total storage used by /scratch/czr/SafeWatch/dataset
    total_bytes = compute_total_storage_used(DATASET_ROOT)
    readable = human_readable_size(total_bytes)
    print(f"\nTotal storage used by '{DATASET_ROOT}': {readable}\n")

if __name__ == "__main__":
    main()