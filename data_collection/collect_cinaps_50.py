#!/usr/bin/env python3
import csv, json, os, shutil, signal, subprocess, threading, time
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
TASK = "Arrange the scattered letters to spell CINAPS from left to right."

ROOT = Path.home() / "xarm_demos_cinaps_50"
STATE_FILE = Path("/tmp/gello_xarm_demo_state.json")
PAUSE_FILE = Path("/tmp/gello_pause")

XARM_IP = "192.168.1.226"
HOME_DEG = [1.7, -11.8, 6.6, 46.1, -1.3, 49.8, 6.2]

GELLO_DIR = Path.home() / "ufactory_teleop" / "gello_teleop"
GELLO_PY = Path.home() / "ufactory_teleop" / ".venv-gello" / "bin" / "python"
GELLO_SCRIPT = GELLO_DIR / "safe_gello_with_gripper.py"
GELLO_CONFIG = GELLO_DIR / "config" / "xarm7_gello_arm_only.yaml"

EXTERNAL_SERIAL = "346522071371"
WRIST_SERIAL = "346222072244"
EXTERNAL_TOPIC = "/camera/external/color/image_raw"
WRIST_TOPIC = "/camera/wrist/color/image_raw"

LOG_DIR = Path.home() / "cinaps_collection_logs"
PROCS = []
LOGS = []


class CameraNode(Node):
    def __init__(self):
        super().__init__("cinaps_collection_camera_node")
        self.bridge = CvBridge()
        self.lock = threading.Lock()
        self.external = None
        self.wrist = None
        self.external_time = None
        self.wrist_time = None
        self.external_seq = 0
        self.wrist_seq = 0

        self.create_subscription(
            Image, EXTERNAL_TOPIC, self._external_cb, qos_profile_sensor_data
        )
        self.create_subscription(
            Image, WRIST_TOPIC, self._wrist_cb, qos_profile_sensor_data
        )

    def _external_cb(self, msg):
        try:
            img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().error(f"external conversion failed: {e}")
            return
        with self.lock:
            self.external = img
            self.external_time = time.time()
            self.external_seq += 1

    def _wrist_cb(self, msg):
        try:
            img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().error(f"wrist conversion failed: {e}")
            return
        with self.lock:
            self.wrist = img
            self.wrist_time = time.time()
            self.wrist_seq += 1

    def snapshot(self):
        with self.lock:
            if self.external is None or self.wrist is None:
                return None
            return {
                "external": self.external.copy(),
                "wrist": self.wrist.copy(),
                "external_time": self.external_time,
                "wrist_time": self.wrist_time,
                "external_seq": self.external_seq,
                "wrist_seq": self.wrist_seq,
            }


def launch(name, command, stdin_text=None):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    log_f = open(log_path, "w", buffering=1)
    LOGS.append(log_f)

    proc = subprocess.Popen(
        ["bash", "-lc", command],
        stdin=subprocess.PIPE if stdin_text is not None else subprocess.DEVNULL,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=os.setsid,
    )
    if stdin_text is not None:
        proc.stdin.write(stdin_text)
        proc.stdin.flush()
        proc.stdin.close()

    PROCS.append((name, proc, log_path))
    return proc, log_path



def launch_interactive(name, command):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{name}.log"
    log_f = open(log_path, "w", buffering=1)
    LOGS.append(log_f)

    proc = subprocess.Popen(
        ["bash", "-lc", command],
        stdin=subprocess.PIPE,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=os.setsid,
    )

    PROCS.append((name, proc, log_path))
    return proc, log_path

def tail(path, n=25):
    try:
        return "\n".join(Path(path).read_text(errors="replace").splitlines()[-n:])
    except Exception:
        return "(log unavailable)"


def wait_for_log(proc, log_path, needle, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"{proc.args} exited early.\nLast log lines:\n{tail(log_path)}"
            )
        try:
            text = Path(log_path).read_text(errors="replace")
        except Exception:
            text = ""
        if needle in text:
            return
        time.sleep(0.5)
    raise TimeoutError(
        f"Timed out waiting for '{needle}'.\nLast log lines:\n{tail(log_path)}"
    )


def pause_gello():
    PAUSE_FILE.touch(exist_ok=True)
    time.sleep(0.5)


def resume_gello():
    try:
        PAUSE_FILE.unlink()
    except FileNotFoundError:
        pass
    time.sleep(0.3)


def move_home():
    """Move xArm to HOME while GELLO is paused. Never auto-clears errors."""
    pause_gello()
    helper = f"""
import sys, time
from xarm.wrapper import XArmAPI

arm = XArmAPI({XARM_IP!r})
err = arm.get_err_warn_code()
print("ERR/WARN before HOME:", err)

if err[0] != 0 or err[1][0] != 0:
    print("REFUSING HOME MOVE: active controller error.")
    arm.disconnect()
    sys.exit(2)

arm.motion_enable(enable=True)
arm.set_mode(0)
arm.set_state(state=0)
time.sleep(0.3)

ret = arm.set_servo_angle(
    angle={HOME_DEG!r},
    speed=10,
    mvacc=50,
    wait=True,
    is_radian=False,
)
print("HOME move return:", ret)

if ret != 0:
    arm.disconnect()
    sys.exit(3)

arm.set_mode(6)
arm.set_state(state=0)
time.sleep(0.2)

print("HOME joints:", arm.get_servo_angle(is_radian=False))
print("ERR/WARN after HOME:", arm.get_err_warn_code())
arm.disconnect()
"""
    result = subprocess.run(
        [str(GELLO_PY), "-c", helper],
        capture_output=True,
        text=True,
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    if result.returncode != 0:
        raise RuntimeError(
            "HOME move failed. GELLO remains PAUSED. Check the xArm before continuing."
        )


CSV_HEADER = (
    ["frame", "timestamp", "state_timestamp",
     "external_timestamp", "wrist_timestamp"]
    + [f"joint{i}" for i in range(1, 8)]
    + ["gripper_position"]
    + [f"action_joint{i}" for i in range(1, 8)]
    + ["action_gripper", "g2_target_mm", "task"]
)


def read_state():
    try:
        d = json.loads(STATE_FILE.read_text())
    except Exception:
        return None
    needed = {"timestamp", "joint_position", "arm_command",
              "g2_target_mm", "g2_normalized"}
    if not needed.issubset(d):
        return None
    if len(d["joint_position"]) != 7 or len(d["arm_command"]) != 7:
        return None
    return d


def record_episode(node, episode_dir, stop_event, stats):
    ext_dir = episode_dir / "external"
    wrist_dir = episode_dir / "wrist"
    ext_dir.mkdir(parents=True)
    wrist_dir.mkdir(parents=True)

    frame = 0
    last_ext = -1
    last_wrist = -1
    period = 1.0 / FPS
    next_tick = time.monotonic()

    with open(episode_dir / "robot_data.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        f.flush()

        while not stop_event.is_set():
            now_mono = time.monotonic()
            if now_mono < next_tick:
                time.sleep(min(0.01, next_tick - now_mono))
                continue
            next_tick += period

            snap = node.snapshot()
            state = read_state()
            if snap is None or state is None:
                continue

            if snap["external_seq"] == last_ext or snap["wrist_seq"] == last_wrist:
                continue

            now = time.time()
            state_time = float(state["timestamp"])
            if abs(now - state_time) > 0.5:
                continue

            q = np.asarray(state["joint_position"], dtype=float)
            a = np.asarray(state["arm_command"], dtype=float)
            grip = float(state["g2_normalized"])
            g2_mm = float(state["g2_target_mm"])

            ext_file = ext_dir / f"{frame:06d}.jpg"
            wrist_file = wrist_dir / f"{frame:06d}.jpg"

            if not cv2.imwrite(str(ext_file), snap["external"]):
                raise RuntimeError(f"Could not save {ext_file}")
            if not cv2.imwrite(str(wrist_file), snap["wrist"]):
                raise RuntimeError(f"Could not save {wrist_file}")

            w.writerow(
                [frame, now, state_time,
                 snap["external_time"], snap["wrist_time"]]
                + q.tolist()
                + [grip]
                + a.tolist()
                + [grip, g2_mm, TASK]
            )
            f.flush()

            last_ext = snap["external_seq"]
            last_wrist = snap["wrist_seq"]
            frame += 1

    stats["frames"] = frame


def next_episode():
    ROOT.mkdir(parents=True, exist_ok=True)
    nums = []
    for p in ROOT.glob("episode_*"):
        if p.is_dir():
            try:
                nums.append(int(p.name.split("_")[1]))
            except Exception:
                pass
    return max(nums, default=0) + 1


def stop_children():
    for _, proc, _ in reversed(PROCS):
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            except Exception:
                pass
    time.sleep(1.0)
    for _, proc, _ in reversed(PROCS):
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                pass
    for f in LOGS:
        try:
            f.close()
        except Exception:
            pass


def main():
    print("\n======================================================")
    print(" CINAPS 50-DEMONSTRATION COLLECTION")
    print("======================================================")
    print("Task :", TASK)
    print("Data :", ROOT)
    print("FPS  :", FPS)
    print("HOME :", HOME_DEG)
    print()
    print("One demo = scattered letters -> C I N A P S -> finish.")
    print("Cameras, GELLO, recording and automatic HOME are managed here.")
    print("No automatic xArm error clearing is performed.")
    print("======================================================\n")

    for p in (GELLO_PY, GELLO_SCRIPT, GELLO_CONFIG):
        if not p.exists():
            raise FileNotFoundError(p)

    pause_gello()

    input(
        "Close any old camera/GELLO processes.\n"
        "Put GELLO in its straight comfortable posture and clear the robot path.\n"
        "Press ENTER to start the complete system..."
    )

    external_cmd = f"""
source /opt/ros/jazzy/setup.bash
exec ros2 launch realsense2_camera rs_launch.py \
  camera_namespace:=camera \
  camera_name:=external \
  serial_no:="'{EXTERNAL_SERIAL}'"
"""
    wrist_cmd = f"""
source /opt/ros/jazzy/setup.bash
exec ros2 launch realsense2_camera rs_launch.py \
  camera_namespace:=camera \
  camera_name:=wrist \
  serial_no:="'{WRIST_SERIAL}'"
"""

    print("\nStarting external camera...")
    launch("external_camera", external_cmd)
    print("Starting wrist camera...")
    launch("wrist_camera", wrist_cmd)

    rclpy.init()
    node = CameraNode()
    ros_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    ros_thread.start()

    print("Waiting for both cameras...")
    deadline = time.time() + 30
    while time.time() < deadline:
        if node.snapshot() is not None:
            break
        time.sleep(0.2)
    else:
        raise RuntimeError(
            f"Camera timeout. Expected {EXTERNAL_TOPIC} and {WRIST_TOPIC}"
        )
    print("Both cameras READY.")

    gello_cmd = f"""
cd {GELLO_DIR}
exec {GELLO_PY} -u {GELLO_SCRIPT.name} --config {GELLO_CONFIG}
"""
    print("\nStarting GELLO...")
    gello_proc, gello_log = launch_interactive("gello", gello_cmd)

    print("Waiting for GELLO preparation prompt...")
    wait_for_log(gello_proc, gello_log, "Press Enter when ready >>>")

    print("\n======================================================")
    print(" GELLO SYNCHRONIZATION")
    print("======================================================")
    print("xArm is at the HOME/reference pose.")
    print("1. Put GELLO in the straight comfortable corresponding pose.")
    print("2. Preferably keep GELLO gripper OPEN.")
    print("3. Hold GELLO completely still.")
    input("Press ENTER HERE when GELLO is ready to synchronize...")

    gello_proc.stdin.write("\n")
    gello_proc.stdin.flush()

    print("Synchronizing GELLO with xArm...")
    wait_for_log(gello_proc, gello_log, "Teleoperation starts PAUSED")
    print("GELLO READY and PAUSED.")

    print("\nSending xArm to CINAPS HOME...")
    move_home()

    ep = next_episode()
    if ep > TOTAL_DEMOS:
        print(f"Dataset already reaches episode {ep - 1}.")
        return

    while ep <= TOTAL_DEMOS:
        print("\n======================================================")
        print(f" DEMO {ep:04d} / {TOTAL_DEMOS:04d}")
        print("======================================================")
        print("xArm is HOME. GELLO is PAUSED.")
        print("1. Move GELLO by hand to its straight comfortable HOME.")
        print("2. Scatter all C I N A P S letters.")
        print("3. Keep all six individually graspable.")
        print("4. Do NOT move the target markers.")

        ans = input(
            "\nPress ENTER to START recording and enable GELLO "
            "(q = quit): "
        ).strip().lower()
        if ans == "q":
            break

        episode_dir = ROOT / f"episode_{ep:04d}"
        if episode_dir.exists():
            raise RuntimeError(f"Refusing to overwrite {episode_dir}")

        stop_event = threading.Event()
        stats = {"frames": 0}
        rec_thread = threading.Thread(
            target=record_episode,
            args=(node, episode_dir, stop_event, stats),
            daemon=True,
        )
        rec_thread.start()

        time.sleep(0.5)
        resume_gello()

        print("\n*** RECORDING NOW ***")
        print("Use GELLO to arrange:")
        print("C -> I -> N -> A -> P -> S")
        print("When the FULL CINAPS arrangement is complete,")
        input("press ENTER here to FINISH this demonstration: ")

        pause_gello()
        stop_event.set()
        rec_thread.join(timeout=5)

        if rec_thread.is_alive():
            raise RuntimeError("Recorder thread did not stop cleanly.")

        print(f"Recorded frames: {stats['frames']}")

        print("Returning xArm to HOME...")
        move_home()

        if stats["frames"] == 0:
            print("Zero frames recorded -> discarding automatically.")
            shutil.rmtree(episode_dir, ignore_errors=True)
            continue

        ans = input(
            "Keep demo? ENTER=yes | d=discard/repeat | q=keep-and-quit: "
        ).strip().lower()

        if ans == "d":
            shutil.rmtree(episode_dir, ignore_errors=True)
            print(f"Discarded episode_{ep:04d}; repeat same number.")
            continue

        print(f"Saved episode_{ep:04d}.")
        if ans == "q":
            break

        ep += 1

    print("\nCollection stopped.")
    print("Dataset:", ROOT)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCtrl+C received.")
    except Exception as e:
        print(f"\nERROR: {e}")
    finally:
        try:
            pause_gello()
        except Exception:
            pass
        stop_children()
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass
        print("\nCollector processes stopped.")
        print("No automatic error clearing was performed.")
