from pathlib import Path
import shutil

import numpy as np
import pandas as pd
from PIL import Image

from lerobot.common.datasets.lerobot_dataset import (
    HF_LEROBOT_HOME,
    LeRobotDataset,
)


# ============================================================
# SETTINGS
# ============================================================

RAW_DATA_DIR = Path.home() / "xarm_demos_cinaps_staged_50_corrected"

REPO_NAME = "lochan/xarm_cinaps_staged_50_corrected"

FPS = 6

TASK = (
    "Arrange the scattered letters to spell CINAPS "
    "in order on the target positions."
)


# ============================================================
# MAIN CONVERSION
# ============================================================

def main():

    output_path = HF_LEROBOT_HOME / REPO_NAME

    print()
    print("=" * 70)
    print("CINAPS xArm -> LeRobot conversion")
    print("=" * 70)
    print("Raw dataset :", RAW_DATA_DIR)
    print("Output      :", output_path)
    print("FPS         :", FPS)
    print("Task        :", TASK)
    print("=" * 70)

    if not RAW_DATA_DIR.exists():
        raise FileNotFoundError(
            f"Raw CINAPS dataset not found: {RAW_DATA_DIR}"
        )

    # --------------------------------------------------------
    # FIND EPISODES
    # --------------------------------------------------------

    episode_dirs = sorted(
        RAW_DATA_DIR.glob("episode_*")
    )

    print()
    print(f"Found {len(episode_dirs)} episodes.")

    if len(episode_dirs) != 50:
        raise RuntimeError(
            f"Expected 50 episodes, found {len(episode_dirs)}."
        )

    # --------------------------------------------------------
    # REMOVE PREVIOUS CONVERSION ONLY
    # --------------------------------------------------------

    if output_path.exists():
        print()
        print("Removing previous CINAPS LeRobot conversion:")
        print(output_path)

        # This removes only the converted LeRobot copy,
        # NOT the raw demonstrations.
        shutil.rmtree(output_path)

    # --------------------------------------------------------
    # CREATE LEROBOT DATASET
    # --------------------------------------------------------

    dataset = LeRobotDataset.create(
        repo_id=REPO_NAME,
        robot_type="xarm7",
        fps=FPS,

        features={

            "external_image": {
                "dtype": "image",
                "shape": (720, 1280, 3),
                "names": [
                    "height",
                    "width",
                    "channel",
                ],
            },

            "wrist_image": {
                "dtype": "image",
                "shape": (720, 1280, 3),
                "names": [
                    "height",
                    "width",
                    "channel",
                ],
            },

            # 7 xArm joint positions in radians
            "joint_position": {
                "dtype": "float32",
                "shape": (7,),
                "names": [
                    "joint_position",
                ],
            },

            # Normalized G2 state
            "gripper_position": {
                "dtype": "float32",
                "shape": (1,),
                "names": [
                    "gripper_position",
                ],
            },

            # 7 commanded arm joints + normalized gripper command
            "actions": {
                "dtype": "float32",
                "shape": (8,),
                "names": [
                    "actions",
                ],
            },
        },

        image_writer_threads=4,
        image_writer_processes=0,
    )

    total_frames = 0

    # ========================================================
    # PROCESS EPISODES
    # ========================================================

    for episode_index, episode_dir in enumerate(
        episode_dirs
    ):

        print()
        print(
            f"[{episode_index + 1:02d}/50] "
            f"{episode_dir.name}"
        )

        csv_path = (
            episode_dir /
            "robot_data.csv"
        )

        external_dir = (
            episode_dir /
            "external"
        )

        wrist_dir = (
            episode_dir /
            "wrist"
        )

        if not csv_path.exists():
            raise FileNotFoundError(
                f"Missing CSV: {csv_path}"
            )

        if not external_dir.exists():
            raise FileNotFoundError(
                f"Missing external directory: {external_dir}"
            )

        if not wrist_dir.exists():
            raise FileNotFoundError(
                f"Missing wrist directory: {wrist_dir}"
            )

        df = pd.read_csv(
            csv_path,
            keep_default_na=False,
        )

        required_columns = [
            "frame",

            "joint1",
            "joint2",
            "joint3",
            "joint4",
            "joint5",
            "joint6",
            "joint7",

            "gripper_position",

            "action_joint1",
            "action_joint2",
            "action_joint3",
            "action_joint4",
            "action_joint5",
            "action_joint6",
            "action_joint7",

            "action_gripper",

            "task",
            "stage_letter",
            "already_placed",
            "demo_in_stage",
        ]

        missing = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing:
            raise RuntimeError(
                f"{episode_dir.name}: missing columns {missing}"
            )

        if len(df) == 0:
            raise RuntimeError(
                f"{episode_dir.name}: CSV has zero frames."
            )

        # ----------------------------------------------------
        # PRINT STAGE INFORMATION
        # ----------------------------------------------------

        stage_letter = str(
            df.iloc[0]["stage_letter"]
        )

        already_placed = str(
            df.iloc[0]["already_placed"]
        )

        demo_in_stage = str(
            df.iloc[0]["demo_in_stage"]
        )

        print(
            f"  stage          : {stage_letter}"
        )

        print(
            f"  already placed : "
            f"{already_placed if already_placed else '-'}"
        )

        print(
            f"  demo in stage  : {demo_in_stage}"
        )

        print(
            f"  frames         : {len(df)}"
        )

        # ====================================================
        # PROCESS FRAMES
        # ====================================================

        for row_index, row in df.iterrows():

            frame_id = int(
                row["frame"]
            )

            external_path = (
                external_dir /
                f"{frame_id:06d}.jpg"
            )

            wrist_path = (
                wrist_dir /
                f"{frame_id:06d}.jpg"
            )

            if not external_path.exists():
                raise FileNotFoundError(
                    f"Missing external image: "
                    f"{external_path}"
                )

            if not wrist_path.exists():
                raise FileNotFoundError(
                    f"Missing wrist image: "
                    f"{wrist_path}"
                )

            # ------------------------------------------------
            # RGB IMAGES
            # ------------------------------------------------

            external_image = np.asarray(
                Image.open(
                    external_path
                ).convert("RGB")
            )

            wrist_image = np.asarray(
                Image.open(
                    wrist_path
                ).convert("RGB")
            )

            if external_image.shape != (
                720,
                1280,
                3,
            ):
                raise RuntimeError(
                    f"{external_path}: unexpected shape "
                    f"{external_image.shape}"
                )

            if wrist_image.shape != (
                720,
                1280,
                3,
            ):
                raise RuntimeError(
                    f"{wrist_path}: unexpected shape "
                    f"{wrist_image.shape}"
                )

            # ------------------------------------------------
            # OBSERVATION STATE
            # ------------------------------------------------

            joint_position = np.asarray(
                [
                    row["joint1"],
                    row["joint2"],
                    row["joint3"],
                    row["joint4"],
                    row["joint5"],
                    row["joint6"],
                    row["joint7"],
                ],
                dtype=np.float32,
            )

            gripper_position = np.asarray(
                [
                    row["gripper_position"],
                ],
                dtype=np.float32,
            )

            # ------------------------------------------------
            # ACTION
            # ------------------------------------------------

            actions = np.asarray(
                [
                    row["action_joint1"],
                    row["action_joint2"],
                    row["action_joint3"],
                    row["action_joint4"],
                    row["action_joint5"],
                    row["action_joint6"],
                    row["action_joint7"],
                    row["action_gripper"],
                ],
                dtype=np.float32,
            )

            # ------------------------------------------------
            # FINITE VALUE CHECK
            # ------------------------------------------------

            if not np.all(
                np.isfinite(
                    joint_position
                )
            ):
                raise RuntimeError(
                    f"{episode_dir.name} frame "
                    f"{frame_id}: invalid joint state"
                )

            if not np.all(
                np.isfinite(
                    gripper_position
                )
            ):
                raise RuntimeError(
                    f"{episode_dir.name} frame "
                    f"{frame_id}: invalid gripper state"
                )

            if not np.all(
                np.isfinite(
                    actions
                )
            ):
                raise RuntimeError(
                    f"{episode_dir.name} frame "
                    f"{frame_id}: invalid action"
                )

            # ------------------------------------------------
            # ADD FRAME
            # ------------------------------------------------

            dataset.add_frame(
                {
                    "external_image":
                        external_image,

                    "wrist_image":
                        wrist_image,

                    "joint_position":
                        joint_position,

                    "gripper_position":
                        gripper_position,

                    "actions":
                        actions,

                    # Keep ONE global task instruction.
                    "task":
                        TASK,
                }
            )

        # ----------------------------------------------------
        # SAVE EPISODE
        # ----------------------------------------------------

        dataset.save_episode()

        total_frames += len(df)

        print(
            f"  SAVED {len(df)} frames."
        )

    # ========================================================
    # FINALIZE
    # ========================================================

    print()
    print("Finalizing LeRobot dataset...")

    if hasattr(
        dataset,
        "finalize",
    ):
        dataset.finalize()

    print()
    print("=" * 70)
    print("CINAPS -> LeRobot conversion COMPLETE")
    print("=" * 70)
    print(f"Episodes     : {len(episode_dirs)}")
    print(f"Total frames : {total_frames}")
    print(f"FPS          : {FPS}")
    print(f"Task         : {TASK}")
    print()
    print("Dataset saved at:")
    print(output_path)
    print("=" * 70)


if __name__ == "__main__":
    main()
