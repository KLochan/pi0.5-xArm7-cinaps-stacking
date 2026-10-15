#!/usr/bin/env python3

import time
import numpy as np
import rclpy

from openpi_client import websocket_client_policy

from xarm_pi05_cinaps_one_shot import (
    CinapsOneShot,
    PROMPT,
    HOME,
)


# ============================================================
# DEMONSTRATION-BASED LIMITS
# ============================================================

# Conservative values slightly below the measured p95
# per-frame motion in the 50 CINAPS demonstrations.
STEP_LIMIT_DEG = np.array(
    [
        2.4,   # J1
        2.4,   # J2
        0.85,  # J3
        2.4,   # J4
        1.6,   # J5
        2.3,   # J6
        3.3,   # J7
    ],
    dtype=np.float64,
)

STEP_LIMIT = np.deg2rad(STEP_LIMIT_DEG)

# Require this test to begin near the original CINAPS HOME.
START_HOME_LIMIT = np.deg2rad(2.0)

# Actual joint ranges observed in the CINAPS demonstrations.
TRAIN_MIN_DEG = np.array([
    -44.236,
    -56.892,
    -34.107,
    -4.238,
    -51.482,
    -10.333,
    -140.263,
])

TRAIN_MAX_DEG = np.array([
    86.354,
    28.503,
    37.843,
    69.063,
    34.160,
    79.657,
    66.470,
])

TRAIN_MIN = np.deg2rad(TRAIN_MIN_DEG)
TRAIN_MAX = np.deg2rad(TRAIN_MAX_DEG)


def check_training_range(q):

    return bool(
        np.all(q >= TRAIN_MIN)
        and np.all(q <= TRAIN_MAX)
    )


def execute_target(node, target, label):

    node.refresh(0.3)

    q_before = node.joints.astype(np.float64)

    delta = target - q_before

    print()
    print("--------------------------------------------")
    print(label)
    print("--------------------------------------------")

    print("Current [deg]:")
    print(np.rad2deg(q_before))

    print()
    print("Target [deg]:")
    print(np.rad2deg(target))

    print()
    print("Requested movement [deg]:")
    print(np.rad2deg(delta))

    if not check_training_range(target):
        raise RuntimeError(
            "Target is outside the joint ranges observed "
            "in the CINAPS demonstrations."
        )

    answer = input(
        "\nType MOVE to execute this step, "
        "or STOP to abort: "
    ).strip().upper()

    if answer != "MOVE":
        print("Stopped. No command sent.")
        return False

    response = node.move_joint_once(target)

    if response is None:
        raise RuntimeError(
            "No response from /xarm/set_servo_angle."
        )

    print(
        "Move response:",
        response.ret,
        response.message,
    )

    if response.ret != 0:
        raise RuntimeError(
            "xArm rejected the movement."
        )

    time.sleep(1.0)

    node.refresh(0.4)

    q_after = node.joints.astype(np.float64)

    print()
    print("Actual movement [deg]:")
    print(
        np.rad2deg(
            q_after - q_before
        )
    )

    return True


def main():

    rclpy.init()

    node = CinapsOneShot()

    print()
    print("============================================")
    print("CINAPS π0.5 SHORT-CHUNK TEST")
    print("ACTIONS 1 → 2 → 3 → 4 → 5")
    print("GRIPPER DISABLED")
    print("============================================")

    print()
    print("Waiting for robot and cameras...")

    while rclpy.ok():

        rclpy.spin_once(
            node,
            timeout_sec=0.1,
        )

        if (
            node.joints is not None
            and node.external_image is not None
            and node.wrist_image is not None
        ):
            break

    node.refresh(0.5)

    q_current = node.joints.astype(
        np.float64
    )

    print()
    print("Starting joints [deg]:")
    print(np.rad2deg(q_current))

    print()
    print("Offset from HOME [deg]:")
    print(
        np.rad2deg(
            q_current - HOME
        )
    )

    if np.max(
        np.abs(
            q_current - HOME
        )
    ) > START_HOME_LIMIT:

        raise RuntimeError(
            "Robot is not sufficiently close to CINAPS HOME. "
            "Return HOME before running this chunk test."
        )

    raw_gripper, gripper_norm = (
        node.get_gripper()
    )

    print()
    print("Raw gripper:", raw_gripper)
    print("Normalized gripper:", gripper_norm)

    state = np.concatenate(
        [
            q_current.astype(np.float32),
            np.array(
                [gripper_norm],
                dtype=np.float32,
            ),
        ]
    )

    observation = {
        "observation/state": state,
        "observation/image":
            node.external_image,
        "observation/wrist_image":
            node.wrist_image,
        "prompt": PROMPT,
    }

    policy = (
        websocket_client_policy
        .WebsocketClientPolicy(
            host="127.0.0.1",
            port=8000,
        )
    )

    print()
    print("Running ONE π0.5 inference...")

    start = time.time()

    result = policy.infer(
        observation
    )

    elapsed = time.time() - start

    actions = np.asarray(
        result["actions"],
        dtype=np.float64,
    )[:, :8]

    if (
        actions.shape[0] < 5
        or not np.all(np.isfinite(actions))
    ):
        raise RuntimeError(
            "Invalid π0.5 output."
        )

    print(
        "Inference time:",
        elapsed,
        "seconds",
    )

    q1 = actions[0, :7]
    q2 = actions[1, :7]
    q3 = actions[2, :7]
    q4 = actions[3, :7]
    q5 = actions[4, :7]

    print()
    print("Action 1 [deg]:")
    print(np.rad2deg(q1))

    print()
    print("Action 2 [deg]:")
    print(np.rad2deg(q2))

    print()
    print("Action 3 [deg]:")
    print(np.rad2deg(q3))

    print()
    print("Action 4 [deg]:")
    print(np.rad2deg(q4))

    print()
    print("Action 5 [deg]:")
    print(np.rad2deg(q5))

    print()
    print("Gripper predictions A1-A5:")
    print(actions[:5, 7])

    print()
    print("GRIPPER WILL NOT BE COMMANDED.")

    # ========================================================
    # BUILD SAFE BRIDGE FROM CURRENT → ACTION 1
    # ========================================================

    first_delta = (
        q1 - q_current
    )

    required_segments = np.ceil(
        np.abs(first_delta)
        / STEP_LIMIT
    )

    num_bridge = max(
        1,
        int(
            np.max(
                required_segments
            )
        ),
    )

    print()
    print("Current → Action 1 delta [deg]:")
    print(np.rad2deg(first_delta))

    print()
    print(
        "Bridge segments required:",
        num_bridge,
    )

    # Avoid unexpectedly huge bridge sequences.
    if num_bridge > 5:
        raise RuntimeError(
            "Action 1 is too far from current pose. "
            "No motion sent."
        )

    # Validate action-to-action motion before moving.
    d12 = q2 - q1
    d23 = q3 - q2
    d34 = q4 - q3
    d45 = q5 - q4

    print()
    print("Action 1 → Action 2 [deg]:")
    print(np.rad2deg(d12))

    print()
    print("Action 2 → Action 3 [deg]:")
    print(np.rad2deg(d23))

    print()
    print("Action 3 → Action 4 [deg]:")
    print(np.rad2deg(d34))

    print()
    print("Action 4 → Action 5 [deg]:")
    print(np.rad2deg(d45))

    if np.any(
        np.abs(d12) > STEP_LIMIT
    ):
        raise RuntimeError(
            "Action 1→2 exceeds demonstration-based "
            "step limits."
        )

    if np.any(np.abs(d23) > STEP_LIMIT):
        raise RuntimeError(
            "Action 2→3 exceeds demonstration-based step limits."
        )

    if np.any(np.abs(d34) > STEP_LIMIT):
        raise RuntimeError(
            "Action 3→4 exceeds demonstration-based step limits."
        )

    if np.any(np.abs(d45) > STEP_LIMIT):
        raise RuntimeError(
            "Action 4→5 exceeds demonstration-based step limits."
        )

    for q in [q1, q2, q3, q4, q5]:
        if not check_training_range(q):
            raise RuntimeError(
                "Predicted action is outside CINAPS "
                "training joint range."
            )

    print()
    print("============================================")
    print("TRAJECTORY VALIDATED")
    print("Nothing has moved yet.")
    print("============================================")

    answer = input(
        "\nType START to begin the manually approved chunk: "
    ).strip().upper()

    if answer != "START":

        print("Cancelled.")
        node.destroy_node()
        rclpy.shutdown()
        return

    # Set Mode 6 once.
    mode_response = node.set_mode(6)

    if (
        mode_response is None
        or mode_response.ret != 0
    ):
        raise RuntimeError(
            "Could not set xArm Mode 6."
        )

    state_response = node.set_state(0)

    if (
        state_response is None
        or state_response.ret != 0
    ):
        raise RuntimeError(
            "Could not set robot state 0."
        )

    time.sleep(0.2)

    # ========================================================
    # CURRENT → ACTION 1 BRIDGE
    # ========================================================

    for i in range(
        1,
        num_bridge + 1,
    ):

        alpha = (
            i / num_bridge
        )

        target = (
            q_current
            + alpha * first_delta
        )

        if not execute_target(
            node,
            target,
            f"BRIDGE {i}/{num_bridge}",
        ):
            node.destroy_node()
            rclpy.shutdown()
            return

    # ========================================================
    # ACTION 2
    # ========================================================

    if not execute_target(
        node,
        q2,
        "π0.5 ACTION 2",
    ):
        node.destroy_node()
        rclpy.shutdown()
        return

    # ========================================================
    # ACTION 3
    # ========================================================

    if not execute_target(
        node,
        q3,
        "π0.5 ACTION 3",
    ):
        node.destroy_node()
        rclpy.shutdown()
        return

    if not execute_target(
        node,
        q4,
        "π0.5 ACTION 4",
    ):
        node.destroy_node()
        rclpy.shutdown()
        return

    if not execute_target(
        node,
        q5,
        "π0.5 ACTION 5",
    ):
        node.destroy_node()
        rclpy.shutdown()
        return

    node.refresh(0.5)

    q_final = node.joints.astype(
        np.float64
    )

    print()
    print("============================================")
    print("SHORT CHUNK COMPLETE")
    print("============================================")

    print("Final joints [deg]:")
    print(np.rad2deg(q_final))

    print()
    print(
        "Total movement from start [deg]:"
    )
    print(
        np.rad2deg(
            q_final - q_current
        )
    )

    print()
    print("GRIPPER WAS NEVER COMMANDED.")
    print("STOP HERE AND INSPECT C POSITION.")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
