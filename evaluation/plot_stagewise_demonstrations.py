#!/usr/bin/env python3
import csv
import statistics
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt

DATASET_ROOT = Path.home() / "xarm_demos_cinaps_staged_50_corrected"
OUT_PATH = Path("assets") / "cinaps_stagewise_frame_count.png"

episodes = sorted(DATASET_ROOT.glob("episode_*"))

stage_to_counts = defaultdict(list)

for ep in episodes:
    csv_path = ep / "robot_data.csv"
    if not csv_path.exists():
        continue

    count = 0
    stage_letter = None

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            count += 1
            if stage_letter is None and "stage_letter" in row:
                stage_letter = row["stage_letter"]

    if stage_letter is None:
        stage_letter = "UNKNOWN"

    stage_to_counts[stage_letter].append(count)

stage_order = ["C", "I", "N", "A", "P", "S", "FULL"]
labels = []
means = []
medians = []
mins = []
maxs = []
all_counts = []

for stage in stage_order:
    counts = stage_to_counts.get(stage, [])
    if not counts:
        continue
    labels.append(stage)
    means.append(statistics.mean(counts))
    medians.append(statistics.median(counts))
    mins.append(min(counts))
    maxs.append(max(counts))
    all_counts.append(counts)

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

x = range(len(labels))

plt.figure(figsize=(12, 6))
plt.bar(x, means, label="Mean frame count")
plt.plot(x, medians, marker="o", linestyle="--", label="Median frame count")

plt.xticks(list(x), labels)
plt.xlabel("Stage")
plt.ylabel("Recorded frames")
plt.title("CINAPS staged dataset: stage-wise frame count")
plt.legend()
plt.grid(True, axis="y")
plt.tight_layout()
plt.savefig(OUT_PATH, dpi=200, bbox_inches="tight")

print(f"Saved plot to: {OUT_PATH}")
print()

for label, counts in zip(labels, all_counts):
    print(
        f"{label}: demos={len(counts)}, "
        f"mean={statistics.mean(counts):.2f}, "
        f"median={statistics.median(counts):.2f}, "
        f"min={min(counts)}, max={max(counts)}"
    )

