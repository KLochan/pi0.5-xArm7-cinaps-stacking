#!/usr/bin/env python3

import csv
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

TOTAL_DEMOS = 50
FPS = 6.0
TASK = "Arrange the scattered letters to spell CINAPS in order on the target positions."

DATA_ROOT = Path.home() / "xarm_demos_cinaps_staged_50"
EXTERNAL_TOPIC = "/camera/external/color/image_raw"
WRIST_TOPIC = "/camera/wrist/color/image_raw"
GELLO_STATE_FILE = Path("/tmp/gello_xarm_demo_state.json")
GELLO_PAUSE_FILE = Path("/tmp/gello_pause")
XARM_IP = "192.168.1.226"
HOME_DEG = [1.7, -11.8, 6.6, 46.1, -1.3, 49.8, 6.2]
GELLO_PYTHON = Path.home() / "ufactory_teleop" / ".venv-gello" / "bin" / "python"

STAGE_PLAN = [
    (1, 8, "C", "", "Pick only C and place it correctly on the C target."),
    (9, 16, "I", "C", "Keep C fixed. Pick only I and place it correctly on the I target."),
    (17, 24, "N", "CI", "Keep C and I fixed. Pick only N and place it correctly on the N target."),
    (25, 32, "A", "CIN", "Keep C, I and N fixed. Pick only A and place it correctly on the A target."),
    (33, 40, "P", "CINA", "Keep C, I, N and A fixed. Pick only P and place it correctly on the P target."),
    (41, 48, "S", "CINAP", "Keep C, I, N, A and P fixed. Pick only S and place it correctly on the S target."),
    (49, 50, "FULL", "", "Arrange the complete word C -> I -> N -> A -> P -> S."),
]


def get_stage(episode):
    for start, end, letter, already_placed, action_text in STAGE_PLAN:
        if start <= episode <= end:
            return {
                "start": start,
                "end": end,
                "stage_letter": letter,
                "already_placed": already_placed,
                "demo_in_stage": episode - start + 1,
                "action_text": action_text,
            }
    raise ValueError(f"No stage mapping for episode {episode}")


def print_stage_instructions(episode, stage):
    print("\n" + "=" * 66)
    print(f" DEMO {episode:04d} / {TOTAL_DEMOS:04d}")
    print("=" * 66)

    if stage["stage_letter"] == "FULL":
        print("STAGE: FULL CINAPS")
        print("Prepare the scene:")
        print("  - Scatter ALL six letters C I N A P S.")
        print("  - None should already be on a target.")
        print("  - Keep them visible, separated, and graspable.")
        print("During recording:")
        print("  - Arrange C -> I -> N -> A -> P -> S.")
    else:
        letter = stage["stage_letter"]
        already = stage["already_placed"]
        print(f"STAGE: {letter} (demo {stage['demo_in_stage']} of 8 for this letter)")
        print("Prepare the scene:")
        if already:
            print("  - Already correctly placed on targets: " + " ".join(list(already)))
            print("  - DO NOT move those already-placed letters.")
            remaining = [x for x in "CINAPS" if x not in already]
            print("  - Scatter/jumble the remaining letters: " + " ".join(remaining))
        else:
            print("  - NONE of C I N A P S is on a target.")
            print("  - Scatter/jumble all six letters.")
        print(f"  - Make {letter} visible and graspable.")
        print("During recording:")
        print(f"  - {stage['action_text']}")
        print("  - Finish immediately after that placement.")

    print("Keep fixed: cameras, HOME, six target markers, target order C I N A P S.")
    print("Vary: starting positions/orientations of the unplaced letters.")
    print("=" * 66)


class CameraNode(Node):
    def __init__(self):
        super().__init__("cinaps_staged_recorder")
        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.external = None
        self.wrist = None
        self.external_seq = 0
        self.wrist_seq = 0
        self.external_time = None
        self.wrist_time = None
        self.create_subscription(Image, EXTERNAL_TOPIC, self._external_cb, qos_profile_sensor_data)
        self.create_subscription(Image, WRIST_TOPIC, self._wrist_cb, qos_profile_sensor_data)

    def _external_cb(self, msg):
        try:
            image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as exc:
            self.get_logger().error(f"External conversion failed: {exc}")
            return
        with self.lock:
            self.external = image
            self.external_seq += 1
            self.external_time = time.time()

    def _wrist_cb(self, msg):
        try:
            image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as exc:
            self.get_logger().error(f"Wrist conversion failed: {exc}")
            return
        with self.lock:
            self.wrist = image
            self.wrist_seq += 1
            self.wrist_time = time.time()

    def snapshot(self):
        with self.lock:
            if self.external is None or self.wrist is None:
                return None
            return {
                "external": self.external.copy(),
                "wrist": self.wrist.copy(),
                "external_seq": self.external_seq,
                "wrist_seq": self.wrist_seq,
                "external_time": self.external_time,
                "wrist_time": self.wrist_time,
            }


def pause_gello():
    GELLO_PAUSE_FILE.touch(exist_ok=True)
    time.sleep(0.35)


def resume_gello():
    try:
        GELLO_PAUSE_FILE.unlink()
    except FileNotFoundError:
        pass
    time.sleep(0.35)


def read_gello_state():
    try:
        state = json.loads(GELLO_STATE_FILE.read_text())
    except Exception:
        return None
    required = {"timestamp", "joint_position", "arm_command", "g2_target_mm", "g2_normalized"}
    if not required.issubset(state):
        return None
    if len(state["joint_position"]) != 7 or len(state["arm_command"]) != 7:
        return None
    return state


def move_xarm_home():
    pause_gello()
    helper = f'''
import sys
import time
from xarm.wrapper import XArmAPI

arm = XArmAPI({XARM_IP!r})
state = arm.get_state()
err = arm.get_err_warn_code()
print("STATE before HOME   :", state)
print("ERR/WARN before HOME:", err)
if err[0] != 0 or err[1][0] != 0:
    print("ACTIVE ERROR - refusing HOME move.")
    arm.disconnect()
    sys.exit(2)
arm.motion_enable(enable=True)
arm.set_mode(0)
arm.set_state(state=0)
time.sleep(0.3)
ret = arm.set_servo_angle(angle={HOME_DEG!r}, speed=10, mvacc=50, wait=True, is_radian=False)
print("HOME move return:", ret)
print("HOME joints     :", arm.get_servo_angle(is_radian=False))
print("ERR/WARN after  :", arm.get_err_warn_code())
print("G2 POS          :", arm.get_gripper_g2_position())
if ret != 0:
    arm.disconnect()
    sys.exit(3)
arm.set_mode(6)
arm.set_state(state=0)
time.sleep(0.2)
arm.disconnect()
'''
    result = subprocess.run([str(GELLO_PYTHON), "-c", helper], text=True)
    if result.returncode != 0:
        raise RuntimeError("HOME move failed. GELLO remains PAUSED. Check xArm STATE / ERR-WARN before continuing.")


CSV_HEADER = (
    ["frame", "timestamp", "state_timestamp", "external_timestamp", "wrist_timestamp"]
    + [f"joint{i}" for i in range(1, 8)]
    + ["gripper_position"]
    + [f"action_joint{i}" for i in range(1, 8)]
    + ["action_gripper", "g2_target_mm", "task", "stage_letter", "already_placed", "demo_in_stage"]
)


def record_episode(node, episode_dir, stop_event, stats, error_box, stage):
    try:
        external_dir = episode_dir / "external"
        wrist_dir = episode_dir / "wrist"
        external_dir.mkdir(parents=True)
        wrist_dir.mkdir(parents=True)
        csv_path = episode_dir / "robot_data.csv"
        frame = 0
        last_external_seq = -1
        last_wrist_seq = -1
        period = 1.0 / FPS
        next_tick = time.monotonic()
        with open(csv_path, "w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(CSV_HEADER)
            csv_file.flush()
            while not stop_event.is_set():
                now_mono = time.monotonic()
                if now_mono < next_tick:
                    time.sleep(min(0.01, next_tick - now_mono))
                    continue
                next_tick += period
                camera = node.snapshot()
                state = read_gello_state()
                if camera is None or state is None:
                    continue
                if camera["external_seq"] == last_external_seq or camera["wrist_seq"] == last_wrist_seq:
                    continue
                now = time.time()
                state_timestamp = float(state["timestamp"])
                if abs(now - state_timestamp) > 0.5:
                    continue
                q = np.asarray(state["joint_position"], dtype=float)
                action = np.asarray(state["arm_command"], dtype=float)
                gripper = float(state["g2_normalized"])
                g2_target_mm = float(state["g2_target_mm"])
                external_file = external_dir / f"{frame:06d}.jpg"
                wrist_file = wrist_dir / f"{frame:06d}.jpg"
                if not cv2.imwrite(str(external_file), camera["external"]):
                    raise RuntimeError(f"Failed to save external image {external_file}")
                if not cv2.imwrite(str(wrist_file), camera["wrist"]):
                    raise RuntimeError(f"Failed to save wrist image {wrist_file}")
                writer.writerow(
                    [frame, now, state_timestamp, camera["external_time"], camera["wrist_time"]]
                    + q.tolist()
                    + [gripper]
                    + action.tolist()
                    + [gripper, g2_target_mm, TASK, stage["stage_letter"], stage["already_placed"], stage["demo_in_stage"]]
                )
                csv_file.flush()
                last_external_seq = camera["external_seq"]
                last_wrist_seq = camera["wrist_seq"]
                frame += 1
        stats["frames"] = frame
    except Exception as exc:
        error_box.append(exc)


def wait_for_inputs(node):
    print("\nChecking camera streams...")
    deadline = time.time() + 15.0
    while time.time() < deadline:
        if node.snapshot() is not None:
            print("External camera : READY")
            print("Wrist camera    : READY")
            break
        time.sleep(0.2)
    else:
        raise RuntimeError(f"Camera timeout. Expected {EXTERNAL_TOPIC} and {WRIST_TOPIC}")

    print("Checking GELLO state export...")
    deadline = time.time() + 10.0
    while time.time() < deadline:
        state = read_gello_state()

        if state is not None:
            age = abs(time.time() - float(state["timestamp"]))

            if GELLO_PAUSE_FILE.exists():
                print("GELLO state     : READY (PAUSED)")
                print(f"GELLO state age : {age:.1f} s")
                return

            if age <= 0.5:
                print("GELLO state     : READY")
                print(f"GELLO state age : {age:.3f} s")
                return

        time.sleep(0.2)
    raise RuntimeError(f"No fresh GELLO state at {GELLO_STATE_FILE}. Keep safe_gello_with_gripper.py running and synchronized.")


def next_episode_number():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    numbers = []
    for path in DATA_ROOT.glob("episode_*"):
        if not path.is_dir():
            continue
        try:
            numbers.append(int(path.name.split("_")[1]))
        except Exception:
            pass
    return max(numbers, default=0) + 1


def main():
    print()
    print("=" * 66)
    print(" CINAPS STAGE-WISE 50-DEMONSTRATION COLLECTION")
    print("=" * 66)
    print("Task :", TASK)
    print("FPS  :", FPS)
    print("Data :", DATA_ROOT)
    print("HOME :", HOME_DEG)
    print("Plan : 01-08 C | 09-16 I | 17-24 N | 25-32 A | 33-40 P | 41-48 S | 49-50 FULL")
    print("Cameras and GELLO must already be running.")
    print("No automatic xArm error clearing is performed.")
    print("=" * 66)

    if not GELLO_PYTHON.exists():
        raise FileNotFoundError(f"xArm/GELLO Python not found: {GELLO_PYTHON}")

    rclpy.init()
    node = CameraNode()
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()

    # SAFETY: GELLO stays paused while robot moves HOME.
    pause_gello()

    print("\nMoving xArm to CINAPS HOME FIRST...")
    move_xarm_home()

    # Only after HOME is reached, verify cameras/GELLO state.
    wait_for_inputs(node)

    episode = next_episode_number()
    if episode > TOTAL_DEMOS:
        print(f"\nDataset already contains episode_{TOTAL_DEMOS:04d}.")
        return

    while episode <= TOTAL_DEMOS:
        stage = get_stage(episode)
        print_stage_instructions(episode, stage)
        answer = input("\nWhen the physical scene is ready, press ENTER to START recording + enable GELLO (q = quit): ").strip().lower()
        if answer == "q":
            break

        episode_dir = DATA_ROOT / f"episode_{episode:04d}"
        if episode_dir.exists():
            raise RuntimeError(f"Refusing to overwrite existing {episode_dir}")

        stop_event = threading.Event()
        stats = {"frames": 0}
        error_box = []
        recorder_thread = threading.Thread(
            target=record_episode,
            args=(node, episode_dir, stop_event, stats, error_box, stage),
            daemon=True,
        )
        recorder_thread.start()
        time.sleep(0.5)
        resume_gello()

        print("\n*** RECORDING NOW — GELLO ACTIVE ***")
        print(stage["action_text"])
        input("\nWhen this stage action is COMPLETE, press ENTER to FINISH the demonstration: ")

        pause_gello()
        stop_event.set()
        recorder_thread.join(timeout=5.0)
        if recorder_thread.is_alive():
            raise RuntimeError("Recorder thread did not stop cleanly.")
        if error_box:
            raise error_box[0]

        print(f"\nRecorded frames: {stats['frames']}")
        if stats["frames"] == 0:
            print("Zero frames recorded. Discarding this episode automatically.")
            shutil.rmtree(episode_dir, ignore_errors=True)
            continue

        print("Returning xArm to HOME...")
        move_xarm_home()

        answer = input("\nKeep demo? ENTER=yes | d=discard/repeat | q=keep-and-quit: ").strip().lower()
        if answer == "d":
            shutil.rmtree(episode_dir, ignore_errors=True)
            print(f"Discarded episode_{episode:04d}; repeat the same episode number.")
            continue

        print(f"Saved episode_{episode:04d}")
        if answer == "q":
            break
        episode += 1

    pause_gello()
    print("\nCollection stopped.")
    print("Dataset:", DATA_ROOT)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCtrl+C received.")
    except Exception as exc:
        print(f"\nERROR: {exc}")
    finally:
        try:
            pause_gello()
        except Exception:
            pass
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass
        print("\nGELLO left PAUSED.")
        print("No automatic xArm error clearing was performed.")
