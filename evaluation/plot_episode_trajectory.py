#!/usr/bin/env python3
import csv
from pathlib import Path
import matplotlib.pyplot as plt

CSV_PATH = Path.home() / "xarm_demos_cinaps_staged_50_corrected" / "episode_0001" / "robot_data.csv"
OUT_PATH = Path("assets") / "episode_0001_joint_gripper_plot.png"

frames = []
joints = {f"joint{i}": [] for i in range(1, 8)}
gripper = []

with open(CSV_PATH, "r", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        frames.append(int(row["frame"]))
        for i in range(1, 8):
            joints[f"joint{i}"].append(float(row[f"joint{i}"]))
        gripper.append(float(row["gripper_position"]))

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

fig = plt.figure(figsize=(12, 8))

ax1 = fig.add_subplot(2, 1, 1)
for i in range(1, 8):
    ax1.plot(frames, joints[f"joint{i}"], label=f"joint{i}")
ax1.set_title("Episode 0001: xArm7 Joint Trajectories")
ax1.set_xlabel("Frame")
ax1.set_ylabel("Joint position (rad)")
ax1.legend(loc="upper right", ncol=4)
ax1.grid(True)

ax2 = fig.add_subplot(2, 1, 2)
ax2.plot(frames, gripper, label="gripper_position")
ax2.set_title("Episode 0001: Gripper Trajectory")
ax2.set_xlabel("Frame")
ax2.set_ylabel("Normalized gripper position")
ax2.grid(True)

plt.tight_layout()
plt.savefig(OUT_PATH, dpi=200, bbox_inches="tight")
print(f"Saved plot to: {OUT_PATH}")
