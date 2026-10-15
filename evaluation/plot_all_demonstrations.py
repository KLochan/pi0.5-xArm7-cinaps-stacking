#!/usr/bin/env python3
import csv
import statistics
from pathlib import Path

import matplotlib.pyplot as plt

DATASET_ROOT = Path.home() / "xarm_demos_cinaps_staged_50_corrected"
OUT_PATH = Path("assets") / "cinaps_all_demonstrations_frame_count.png"

episodes = sorted(DATASET_ROOT.glob("episode_*"))

episode_numbers = []
frame_counts = []
stage_labels = []

for ep in episodes:
    csv_path = ep / "robot_data.csv"
    if not csv_path.exists():
        continue

    count = 0
    first_stage = ""
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            count += 1
            if count == 1 and "stage_letter" in row:
                first_stage = row["stage_letter"]

    try:
        ep_num = int(ep.name.split("_")[1])
    except Exception:
        continue

    episode_numbers.append(ep_num)
    frame_counts.append(count)
    stage_labels.append(first_stage)

if not episode_numbers:
    raise RuntimeError(f"No valid episode data found in {DATASET_ROOT}")

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

mean_frames = statistics.mean(frame_counts)
median_frames = statistics.median(frame_counts)
min_frames = min(frame_counts)
max_frames = max(frame_counts)

plt.figure(figsize=(14, 6))
plt.bar(episode_numbers, frame_counts)
plt.axhline(mean_frames, linestyle="--", label=f"Mean = {mean_frames:.1f}")
plt.xlabel("Episode number")
plt.ylabel("Recorded frames")
plt.title("CINAPS staged dataset: frame count across all demonstrations")
plt.xticks(episode_numbers, rotation=90)
plt.legend()
plt.grid(True, axis="y")
plt.tight_layout()
plt.savefig(OUT_PATH, dpi=200, bbox_inches="tight")

print(f"Saved plot to: {OUT_PATH}")
print(f"Total demonstrations: {len(frame_counts)}")
print(f"Total frames: {sum(frame_counts)}")
print(f"Mean frames/demo: {mean_frames:.2f}")
print(f"Median frames/demo: {median_frames:.2f}")
print(f"Min frames/demo: {min_frames}")
print(f"Max frames/demo: {max_frames}")
