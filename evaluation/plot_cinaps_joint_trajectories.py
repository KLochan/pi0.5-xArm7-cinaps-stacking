#!/usr/bin/env python3
import csv
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = Path.home() / "xarm_demos_cinaps_staged_50_corrected"
out = Path("assets")
out.mkdir(exist_ok=True)

stages = {
    "C": range(1, 9),
    "I": range(9, 17),
    "N": range(17, 25),
    "A": range(25, 33),
    "P": range(33, 41),
    "S": range(41, 49),
    "FULL": range(49, 51),
}

for stage, episodes in stages.items():
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    for ep in episodes:
        path = root / f"episode_{ep:04d}" / "robot_data.csv"

        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))

        if not rows:
            raise ValueError(f"Empty CSV: {path}")

        progress = np.linspace(0, 100, len(rows))
        joints = np.array([
            [float(r[f"joint{i}"]) for i in range(1, 8)]
            for r in rows
        ])
        gripper = np.array([
            float(r["gripper_position"]) for r in rows
        ])

        for j in range(7):
            axes[0].plot(progress, joints[:, j], alpha=0.3)

        axes[1].plot(
            progress, gripper,
            label=f"Episode {ep:04d}", linewidth=1.2
        )

    axes[0].set_title(f"CINAPS {stage}: Joint trajectories")
    axes[0].set_ylabel("Joint position (rad)")
    axes[0].grid(True, alpha=0.3)

    axes[1].set_title("Gripper trajectories")
    axes[1].set_xlabel("Episode progress (%)")
    axes[1].set_ylabel("Normalized gripper position")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(fontsize=8, ncol=4)

    fig.tight_layout()
    filename = out / f"cinaps_trajectories_{stage.lower()}.png"
    fig.savefig(filename, dpi=180)
    plt.close(fig)
    print("Saved:", filename)

print("Finished all 50 demonstrations.")
