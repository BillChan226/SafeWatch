import os
import json
import shutil
from tqdm import tqdm

# Directories
OLD_FINAL_DATASET_DIR = "/scratch/czr/Video_moderation/final_dataset_10_19"
NEW_DATASET_ROOT = "/scratch/czr/SafeWatch/dataset"
ANNOTATION_ROOT = os.path.join(NEW_DATASET_ROOT, "annotation")

def map_old_path(old_path):
    """
    Convert an old path:
      /scratch/czr/Video_moderation/clips/...    => ("dataset/clip/...", "clip/...")
      /scratch/czr/Video_moderation/dataset/... => ("dataset/full/...", "full/...")
    
    Returns (new_rel_for_json, new_rel_for_fs).
      - new_rel_for_json:  what goes in the updated JSON (e.g. "dataset/clip/abuse_1/...")
      - new_rel_for_fs:    the folder structure on disk (e.g. "clip/abuse_1/...")
    """
    norm = os.path.normpath(old_path)
    clips_prefix = "/scratch/czr/Video_moderation/clips"
    dataset_prefix = "/scratch/czr/Video_moderation/dataset"

    if norm.startswith(clips_prefix):
        # old_path after the prefix
        remainder = norm[len(clips_prefix):]  # e.g. "/abuse_1/target/myvideo.mp4"
        new_rel_for_json = os.path.join("dataset", "clip") + remainder
        new_rel_for_fs = os.path.join("clip") + remainder
        return (
            os.path.normpath(new_rel_for_json).lstrip("/"),
            os.path.normpath(new_rel_for_fs).lstrip("/")
        )
    elif norm.startswith(dataset_prefix):
        remainder = norm[len(dataset_prefix):]
        new_rel_for_json = os.path.join("dataset", "full") + remainder
        new_rel_for_fs = os.path.join("full") + remainder
        return (
            os.path.normpath(new_rel_for_json).lstrip("/"),
            os.path.normpath(new_rel_for_fs).lstrip("/")
        )
    else:
        # If it doesn't match either known prefix, return None
        return None, None

def copy_file_once(old_path):
    """
    Copy a single video from old_path to /scratch/czr/SafeWatch/dataset/.
    If the file doesn't exist, print the original path and return (None, None).
    If successful, return (new_rel_for_json, new_rel_for_fs).
    """
    if not os.path.exists(old_path):
        print(f"Missing file: {old_path}")

        return None, None

    new_rel_json, new_rel_fs = map_old_path(old_path)
    if new_rel_json is None or new_rel_fs is None:
        print(f"Unrecognized prefix, skipping file: {old_path}")
        return None, None

    new_abs_path = os.path.join(NEW_DATASET_ROOT, new_rel_fs)
    os.makedirs(os.path.dirname(new_abs_path), exist_ok=True)

    if not os.path.exists(new_abs_path):
        shutil.copy2(old_path, new_abs_path)

    return new_rel_json, new_rel_fs

def process_full_json(full_json_path):
    """
    1. Load full.json
    2. For each item with 'video', attempt copy_file_once.
    3. If success, update item["video"], record old2new_map[old_path] => new_rel_json
       If fail, skip that item entirely.
    4. Return (updated_list, old2new_map).
    """
    with open(full_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        return [], {}

    updated = []
    old2new_map = {}

    for item in tqdm(data, desc=f"Processing {os.path.basename(full_json_path)}"):
        if "video" in item:
            old_path = item["video"]
            new_rel_json, _ = copy_file_once(old_path)
            if new_rel_json is not None:
                item["video"] = new_rel_json
                updated.append(item)
                old2new_map[old_path] = new_rel_json
            # else skip
        else:
            # if "video" not present, we can just keep the item as-is (or skip)
            updated.append(item)

    return updated, old2new_map

def process_full_gt_json(full_gt_json_path, old2new_map):
    """
    1. Load full_gt.json
    2. For each item with 'video_path', see if old_path is in old2new_map
    3. If yes, update item["video_path"]; if not, skip.
    4. Return updated list.
    """
    with open(full_gt_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        return []

    updated = []
    for item in data:
        if "video_path" in item:
            old_path = item["video_path"]
            if old_path in old2new_map:
                item["video_path"] = old2new_map[old_path]
                updated.append(item)
            else:
                # old_path wasn't copied or didn't exist
                pass
        else:
            updated.append(item)

    return updated

def main():
    # Iterate subfolders in /scratch/czr/Video_moderation/final_dataset_10_19
    categories = [d for d in os.listdir(OLD_FINAL_DATASET_DIR)
                  if os.path.isdir(os.path.join(OLD_FINAL_DATASET_DIR, d))]

    for category_name in tqdm(categories, desc="Processing categories"):
        cat_path = os.path.join(OLD_FINAL_DATASET_DIR, category_name)
        full_json = os.path.join(cat_path, "full.json")
        full_gt_json = os.path.join(cat_path, "full_gt.json")

        # 1) Process full.json
        updated_full, old2new_map = [], {}
        if os.path.exists(full_json):
            updated_full, old2new_map = process_full_json(full_json)

        # 2) Write updated full.json
        if updated_full:
            ann_dir = os.path.join(ANNOTATION_ROOT, category_name)
            os.makedirs(ann_dir, exist_ok=True)
            out_full_json = os.path.join(ann_dir, "full.json")
            with open(out_full_json, "w", encoding="utf-8") as f_out:
                json.dump(updated_full, f_out, indent=4)

        # 3) Process full_gt.json (using old2new_map)
        if os.path.exists(full_gt_json):
            updated_full_gt = process_full_gt_json(full_gt_json, old2new_map)
            if updated_full_gt:
                ann_dir = os.path.join(ANNOTATION_ROOT, category_name)
                os.makedirs(ann_dir, exist_ok=True)
                out_full_gt_json = os.path.join(ann_dir, "full_gt.json")
                with open(out_full_gt_json, "w", encoding="utf-8") as f_out:
                    json.dump(updated_full_gt, f_out, indent=4)

if __name__ == "__main__":
    main()