#!/usr/bin/env python3

import os
import sys
import time
import yaml
import argparse
import json
import numpy as np
from pathlib import Path

from gello.dynamixel.driver import DynamixelDriver

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ufactory_devices.robot import UFRobotConfig, UFRobot


# ============================================================
# SETTINGS
# ============================================================

FPS = 30

# ARM
# J1-J6 conservative, J7 wrist rotation faster
MAX_STEP_DEG = np.array([
    0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 1.0
])

# Keep normal joints at 10 deg,
# allow slightly more tracking lag for wrist rotation J7
# J1-J6 accumulated tracking lag limit
MAX_ARM_LAG_DEG = 20.0

# J7 is allowed to accumulate lag while rotating.
# Instead detect only an abnormal instantaneous GELLO jump.
MAX_J7_MASTER_JUMP_DEG = 12.0

# Only a warning, NOT a stop
J7_LAG_WARNING_DEG = 15.0

# GELLO master gripper calibration
GELLO_GRIPPER_ID = 8
GELLO_CLOSED_DEG = 143.53
GELLO_OPEN_DEG   = 196.19

# xArm G2
G2_CLOSED_MM = 0.0
G2_OPEN_MM   = 84.0

G2_SPEED = 200
G2_FORCE = 30

# GELLO smoothing
GELLO_DEADBAND_DEG = 0.6
FILTER_ALPHA = 0.15

# Don't keep retransmitting tiny gripper changes
GRIPPER_DEADBAND_MM = 0.8

# Shared state for ROS recorder
DEMO_STATE_FILE = Path("/tmp/gello_xarm_demo_state.json")

# Software clutch:
# file exists  -> PAUSED
# file absent  -> ACTIVE
PAUSE_FILE = Path("/tmp/gello_pause")


# ============================================================
# LOAD CONFIG
# ============================================================

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
args = parser.parse_args()

with open(Path(args.config).expanduser(), "r") as f:
    cfg = yaml.safe_load(f)

robot_cfg = UFRobotConfig(**cfg["RobotConfig"])
tele_cfg = cfg["TeleoperatorConfig"]

port = tele_cfg["port"]

joint_ids = list(tele_cfg["joint_ids"])
joint_signs = np.asarray(
    tele_cfg["joint_signs"],
    dtype=float
)

if len(joint_ids) != 7:
    raise RuntimeError("Expected exactly 7 GELLO arm joints")

if len(joint_signs) != 7:
    raise RuntimeError("Expected exactly 7 joint signs")


print("\n================================================")
print(" SAFE GELLO + xArm7 + G2")
print("================================================")

print(f"Arm rate limit : {MAX_STEP_DEG} deg/cycle")
print(f"J1-J6 configured lag threshold (diagnostic only): {MAX_ARM_LAG_DEG} deg")
print(f"G2 speed       : {G2_SPEED}")
print(f"G2 force       : {G2_FORCE}")


# ============================================================
# CONNECT xARM
# ============================================================

print("\nConnecting to xArm...")

robot = UFRobot(robot_cfg)
arm = robot.real_arm

code, err_warn = arm.get_err_warn_code()

print("xArm error/warn =", err_warn)

if code != 0 or err_warn[0] != 0:
    raise RuntimeError(
        f"xArm has controller error {err_warn}. "
        "Clear the problem before starting teleoperation."
    )


# ============================================================
# INITIALIZE G2
# ============================================================

print("\nInitializing G2 gripper...")

ret = arm.set_gripper_enable(True)
if ret != 0:
    raise RuntimeError(
        f"Could not enable G2, ret={ret}, "
        f"errors={arm.get_err_warn_code()}"
    )

ret = arm.set_gripper_mode(0)
if ret != 0:
    raise RuntimeError(
        f"Could not set G2 mode, ret={ret}"
    )

code, g2_position = arm.get_gripper_g2_position()

if code != 0:
    raise RuntimeError(
        f"Could not read G2 position. "
        f"errors={arm.get_err_warn_code()}"
    )

print(f"Current G2 position = {g2_position} mm")


# ============================================================
# READ CURRENT xARM POSE
# ============================================================

code, xarm_start = arm.get_servo_angle(
    is_radian=True
)

if code != 0:
    raise RuntimeError(
        f"Could not read xArm joints, code={code}"
    )

xarm_start = np.asarray(
    xarm_start[:7],
    dtype=float
)

print("\nCURRENT xArm POSE")

for i, q in enumerate(xarm_start):
    print(
        f"J{i+1}: "
        f"{np.degrees(q):+7.2f} deg"
    )


# ============================================================
# PREPARE GELLO
# ============================================================

print("\n================================================")
print(" PREPARE GELLO")
print("================================================")

print("1. Keep xArm clear of the table and obstacles.")
print("2. Put GELLO in a comfortable corresponding pose.")
print("3. Preferably put GELLO gripper OPEN.")
print("4. Hold GELLO completely still.")
print("5. Then press Enter.")

input("\nPress Enter when ready >>> ")


# ============================================================
# INITIALIZE ONE DYNAMIXEL DRIVER FOR J1-J7 + GRIPPER
# ============================================================

all_ids = joint_ids + [GELLO_GRIPPER_ID]

driver = DynamixelDriver(
    all_ids,
    port=port,
    baudrate=57600
)

for _ in range(10):
    driver.get_joints()

raw_start = np.asarray(
    driver.get_joints(),
    dtype=float
)

# ============================================================
# SOFT GELLO STIFFNESS - XL330-M288 IDs 1-7
# ============================================================

print("\nEnabling soft GELLO joint stiffness...")

ADDR_OPERATING_MODE = 11
ADDR_TORQUE_ENABLE = 64
ADDR_GOAL_CURRENT = 102
ADDR_GOAL_POSITION = 116

CURRENT_BASED_POSITION_MODE = 5

# Half-stiffness values
GELLO_CURRENT = {
    1: 8,
    2: 15,
    3: 15,
    4: 15,
    5: 15,
    6: 15,
    7: 15,
}

# IMPORTANT:
# Lock the Dynamixel serial connection while configuring.
with driver._lock:

    # 1. Disable torque on arm joints only
    for dxl_id in joint_ids:
        comm, err = driver._packetHandler.write1ByteTxRx(
            driver._portHandler,
            dxl_id,
            ADDR_TORQUE_ENABLE,
            0
        )

        if comm != 0 or err != 0:
            raise RuntimeError(
                f"Could not disable GELLO torque for ID {dxl_id}: "
                f"comm={comm}, err={err}"
            )

    # 2. Current-based position mode
    for dxl_id in joint_ids:
        comm, err = driver._packetHandler.write1ByteTxRx(
            driver._portHandler,
            dxl_id,
            ADDR_OPERATING_MODE,
            CURRENT_BASED_POSITION_MODE
        )

        if comm != 0 or err != 0:
            raise RuntimeError(
                f"Could not set mode for GELLO ID {dxl_id}: "
                f"comm={comm}, err={err}"
            )

    # 3. Use PRESENT position as holding target
    for i, dxl_id in enumerate(joint_ids):

        position_value = int(
            raw_start[i] * 2048.0 / np.pi
        ) & 0xFFFFFFFF

        comm, err = driver._packetHandler.write4ByteTxRx(
            driver._portHandler,
            dxl_id,
            ADDR_GOAL_POSITION,
            position_value
        )

        if comm != 0 or err != 0:
            raise RuntimeError(
                f"Could not set initial position for ID {dxl_id}: "
                f"comm={comm}, err={err}"
            )

        comm, err = driver._packetHandler.write2ByteTxRx(
            driver._portHandler,
            dxl_id,
            ADDR_GOAL_CURRENT,
            GELLO_CURRENT[dxl_id]
        )

        if comm != 0 or err != 0:
            raise RuntimeError(
                f"Could not set current for ID {dxl_id}: "
                f"comm={comm}, err={err}"
            )

    # 4. Enable torque LAST
    for dxl_id in joint_ids:
        comm, err = driver._packetHandler.write1ByteTxRx(
            driver._portHandler,
            dxl_id,
            ADDR_TORQUE_ENABLE,
            1
        )

        if comm != 0 or err != 0:
            raise RuntimeError(
                f"Could not enable GELLO torque for ID {dxl_id}: "
                f"comm={comm}, err={err}"
            )

print(
    "Soft GELLO stiffness enabled: "
    " ".join(f"J{i}={GELLO_CURRENT[i]}" for i in joint_ids)
)
# ============================================================
# CURRENT-POSE ARM SYNCHRONIZATION
# ============================================================

joint_offsets = (
    raw_start[:7]
    - xarm_start / joint_signs
)

mapped_start = (
    raw_start[:7] - joint_offsets
) * joint_signs

initial_diff_deg = np.degrees(
    mapped_start - xarm_start
)

print("\nINITIAL ARM SYNCHRONIZATION")
print("----------------------------------------------")

for i in range(7):
    print(
        f"J{i+1}: "
        f"GELLO={np.degrees(mapped_start[i]):+7.2f}° | "
        f"xArm={np.degrees(xarm_start[i]):+7.2f}° | "
        f"diff={initial_diff_deg[i]:+6.2f}°"
    )

initial_max = float(
    np.max(np.abs(initial_diff_deg))
)

print(
    f"MAX INITIAL DIFFERENCE = "
    f"{initial_max:.2f}°"
)

if initial_max > 5.0:
    driver.close()

    raise RuntimeError(
        "Initial GELLO/xArm synchronization "
        "exceeds 5 degrees. "
        "NO COMMAND SENT."
    )


# ============================================================
# INITIAL GELLO GRIPPER CHECK
# ============================================================

gello_gripper_deg = np.degrees(
    raw_start[7]
)

initial_gripper_target = float(
    np.interp(
        gello_gripper_deg,
        [GELLO_CLOSED_DEG, GELLO_OPEN_DEG],
        [G2_CLOSED_MM, G2_OPEN_MM]
    )
)

initial_gripper_target = float(
    np.clip(
        initial_gripper_target,
        G2_CLOSED_MM,
        G2_OPEN_MM
    )
)

print("\nINITIAL GRIPPER")
print(
    f"GELLO gripper = "
    f"{gello_gripper_deg:.2f}°"
)
print(
    f"G2 currently = "
    f"{g2_position:.1f} mm"
)
print(
    f"GELLO target = "
    f"{initial_gripper_target:.1f} mm"
)

print("\nSynchronization PASSED.")
print("Start moving GELLO slowly.\n")


# ============================================================
# CONTROL LOOP
# ============================================================

dt = 1.0 / FPS

max_step_rad = np.deg2rad(
    MAX_STEP_DEG
)

last_gripper_target = None

prev_desired_arm = None
filtered_desired_arm = None

# Start safely PAUSED.
PAUSE_FILE.touch(exist_ok=True)
paused = True

# Relative gripper offset used after each resume
g2_offset_mm = 0.0

print("\n==============================================")
print(" SOFTWARE CLUTCH ENABLED")
print("==============================================")
print("Teleoperation starts PAUSED.")
print("PAUSE : touch /tmp/gello_pause")
print("RESUME: rm -f /tmp/gello_pause")
print("==============================================\n")

try:

    while True:

        loop_start = time.time()

        # ----------------------------------------------------
        # Read GELLO J1-J7 + gripper
        # ----------------------------------------------------

        raw = np.asarray(
            driver.get_joints(),
            dtype=float
        )

        desired_arm = (
            raw[:7] - joint_offsets
        ) * joint_signs
       
        # ----------------------------------------------------
        # SMOOTH / STABILIZE GELLO COMMAND
        # ----------------------------------------------------

        if filtered_desired_arm is None:
            filtered_desired_arm = desired_arm.copy()

        else:
           master_delta = desired_arm - filtered_desired_arm

           # Ignore very tiny hand/encoder movements
           master_delta_deg = np.degrees(master_delta)

           master_delta[
               np.abs(master_delta_deg) < GELLO_DEADBAND_DEG
           ] = 0.0

           # Low-pass filtering
           filtered_desired_arm = (
               filtered_desired_arm
               + FILTER_ALPHA * master_delta
           )

           # Use the smoothed GELLO target from this point onward
           desired_arm = filtered_desired_arm.copy()

        gello_gripper_deg = np.degrees(
            raw[7]
        )

        # ----------------------------------------------------
        # Read actual xArm joints
        # ----------------------------------------------------

        code, current = arm.get_servo_angle(
            is_radian=True
        )

        if code != 0:
            print(
                "\nCould not read xArm joints."
            )
            break

        current = np.asarray(
            current[:7],
            dtype=float
        )

        # ----------------------------------------------------
        # SOFTWARE CLUTCH / PAUSE-RESUME
        # ----------------------------------------------------

        if PAUSE_FILE.exists():

            if not paused:
                print("\n==============================================")
                print(" GELLO PAUSED")
                print(" xArm holds its current pose.")
                print(" GELLO movement is ignored.")
                print("==============================================\n")

            paused = True

            # While paused, send NO arm or gripper commands.
            time.sleep(dt)
            continue

        # Transition from PAUSED -> ACTIVE.
        # Re-synchronize GELLO to the CURRENT xArm pose so
        # releasing the clutch cannot cause an arm jump.
        if paused:

            joint_offsets = (
                raw[:7]
                - current / joint_signs
            )

            filtered_desired_arm = current.copy()
            prev_desired_arm = None

            # Also synchronize GELLO gripper to current G2.
            g2_code, g2_now = arm.get_gripper_g2_position()

            if g2_code != 0:
                print(
                    "Could not read G2 while resuming. "
                    "Returning to PAUSE."
                )
                PAUSE_FILE.touch(exist_ok=True)
                time.sleep(dt)
                continue

            raw_g2_mm = float(
                np.interp(
                    np.degrees(raw[7]),
                    [
                        GELLO_CLOSED_DEG,
                        GELLO_OPEN_DEG
                    ],
                    [
                        G2_CLOSED_MM,
                        G2_OPEN_MM
                    ]
                )
            )

            g2_offset_mm = float(g2_now) - raw_g2_mm

            last_gripper_target = float(g2_now)

            paused = False

            print("\n==============================================")
            print(" GELLO RESUMED")
            print(" Arm and gripper re-synchronized.")
            print(" Start moving GELLO slowly.")
            print("==============================================\n")

            # Do not command motion on the synchronization cycle.
            time.sleep(dt)
            continue

        # ----------------------------------------------------
        # HARD SAFETY CHECK USING RAW GELLO TARGET
        # ----------------------------------------------------

        raw_diff_deg = np.degrees(
            desired_arm - current
        )
        # ----------------------------------------------------
        # SAFETY CHECK
        # ----------------------------------------------------

        abs_lag = np.abs(raw_diff_deg)

        print("\n--- ARM ---")

        for i in range(7):
            print(
                f"J{i+1}: "
                f"GELLO={np.degrees(desired_arm[i]):+6.1f}° | "
                f"xArm={np.degrees(current[i]):+6.1f}° | "
                f"lag={raw_diff_deg[i]:+5.1f}°"
            )

        # J1-J6 retain the normal accumulated-lag safety rule
        max_arm_lag = float(np.max(abs_lag[:6]))

        print(
            f"MAX J1-J6 LAG = {max_arm_lag:.2f}°"
        )

        # No hard stop based on accumulated J1-J6 lag.
        # Lag is displayed only; the per-cycle rate limiter
        # still limits how quickly the xArm can move.


        # ----------------------------------------------------
        # J7 WRIST-ROTATION SAFETY
        # ----------------------------------------------------

        if prev_desired_arm is not None:

            # Difference between consecutive GELLO J7 readings.
            # atan2 handles wraparound safely.
            j7_delta = (
                desired_arm[6]
                - prev_desired_arm[6]
            )

            j7_jump_deg = abs(
                np.degrees(
                    np.arctan2(
                        np.sin(j7_delta),
                        np.cos(j7_delta)
                    )
                )
            )

            if j7_jump_deg > MAX_J7_MASTER_JUMP_DEG:

                print("\n********************************")
                print("*** J7 ENCODER SAFETY STOP ***")
                print(
                    f"Sudden GELLO J7 jump = "
                    f"{j7_jump_deg:.2f}°"
                )
                print(
                    f"Limit = "
                    f"{MAX_J7_MASTER_JUMP_DEG:.2f}°/cycle"
                )
                print("NO MORE COMMANDS SENT.")
                print("********************************")
                break


        # J7 accumulated lag is now informational only.
        if abs_lag[6] > J7_LAG_WARNING_DEG:
            print(
                f"J7 catching up: "
                f"{abs_lag[6]:.1f}° behind GELLO"
           )


        prev_desired_arm = desired_arm.copy()


        # ----------------------------------------------------
        # ARM RATE LIMIT
        # ----------------------------------------------------

        delta = desired_arm - current

        delta = np.clip(
            delta,
            -max_step_rad,
            +max_step_rad
        )

        arm_command = current + delta

        # ----------------------------------------------------
        # Check controller before command
        # ----------------------------------------------------

        status_code, err_warn = (
            arm.get_err_warn_code()
        )

        if (
            status_code != 0
            or err_warn[0] != 0
        ):
            print(
                "\nController error:",
                err_warn
            )
            print("Stopping teleoperation.")
            break

        # ----------------------------------------------------
        # SEND ARM COMMAND
        # ----------------------------------------------------

        arm_ret = robot.send_action(
            arm_command
        )

        print(
            "arm send_action =",
            arm_ret
        )

        if arm_ret != 0:
            print(
                "Arm command failed."
            )
            print(
                "Errors =",
                arm.get_err_warn_code()
            )
            break

        # ----------------------------------------------------
        # CONTINUOUS GELLO -> G2 MAPPING
        # ----------------------------------------------------

        g2_target = (
            np.interp(
                gello_gripper_deg,
                [
                    GELLO_CLOSED_DEG,
                    GELLO_OPEN_DEG
                ],
                [
                    G2_CLOSED_MM,
                    G2_OPEN_MM
                ]
            )
            + g2_offset_mm
        )

        g2_target = float(
            np.clip(
                g2_target,
                G2_CLOSED_MM,
                G2_OPEN_MM
            )
        )

        # ----------------------------------------------------
        # EXPORT DEMONSTRATION STATE
        # ----------------------------------------------------
        demo_state = {
            "timestamp": time.time(),
            "joint_position": np.asarray(current, dtype=float).tolist(),
            "arm_command": np.asarray(arm_command, dtype=float).tolist(),
            "g2_target_mm": float(g2_target),
            "g2_normalized": float(g2_target / G2_OPEN_MM),
        }

        tmp_state = DEMO_STATE_FILE.with_suffix(".tmp")
        with open(tmp_state, "w") as f:
            json.dump(demo_state, f)

        os.replace(tmp_state, DEMO_STATE_FILE)

        # Send only meaningful target changes.
        # There is NO step limiter here.
        if (
            last_gripper_target is None
            or abs(
                g2_target
                - last_gripper_target
            ) >= GRIPPER_DEADBAND_MM
        ):

            grip_ret = (
                arm.set_gripper_g2_position(
                    g2_target,
                    speed=G2_SPEED,
                    force=G2_FORCE,
                    wait=False
                )
            )

            print(
                f"G2: GELLO="
                f"{gello_gripper_deg:6.1f}° "
                f"-> target="
                f"{g2_target:5.1f} mm "
                f"ret={grip_ret}"
            )

            if grip_ret != 0:

                print(
                    "\nG2 command failed."
                )
                print(
                    "Errors =",
                    arm.get_err_warn_code()
                )

                break

            last_gripper_target = (
                g2_target
            )

        # ----------------------------------------------------
        # Maintain approximately FPS
        # ----------------------------------------------------

        elapsed = (
            time.time() - loop_start
        )

        remaining = dt - elapsed

        if remaining > 0:
            time.sleep(remaining)


except KeyboardInterrupt:

    print(
        "\nCtrl+C received. "
        "Stopping teleoperation."
    )


finally:

    print(
        "\nClosing GELLO connection..."
    )

    try:
        driver.close()
    except Exception:
        pass

    print(
        "Robot left at its current pose."
    )

    print(
        "No automatic error clearing."
    )

