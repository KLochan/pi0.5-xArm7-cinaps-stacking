#!/usr/bin/env python3

import time
import numpy as np

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import JointState, Image
from cv_bridge import CvBridge

from xarm_msgs.srv import GetFloat32, MoveJoint, SetInt16
from openpi_client import websocket_client_policy


# ============================================================
# CINAPS SETTINGS
# ============================================================

PROMPT = (
    "Arrange the scattered letters to spell CINAPS "
    "in order on the target positions."
)

EXTERNAL_TOPIC = "/camera/external/color/image_raw"
WRIST_TOPIC = "/camera/wrist/color/image_raw"

# CINAPS HOME used during collection
HOME = np.array(
    [
        0.029671,
        -0.205949,
        0.115192,
        0.804597,
        -0.022689,
        0.869174,
        0.108210,
    ],
    dtype=np.float64,
)

# We only allow this first test near HOME.
MAX_HOME_ERROR = 0.15       # rad

# Reject obviously unreasonable raw prediction.
MAX_RAW_DELTA = 0.50        # rad

# Maximum physical change from CURRENT position for one test.
MAX_STEP = np.deg2rad(
    np.array(
        [
            0.5,   # J1
            0.5,   # J2
            0.5,   # J3
            0.5,   # J4
            0.5,   # J5
            0.5,   # J6
            0.8,   # J7
        ],
        dtype=np.float64,
    )
)

# Conservative MoveJoint settings.
MOVE_SPEED = 0.05      # rad/s
MOVE_ACC = 0.10        # rad/s^2
MOVE_TIME = 0.5        # s


class CinapsOneShot(Node):

    def __init__(self):
        super().__init__("cinaps_one_shot_test")

        self.bridge = CvBridge()

        self.joints = None
        self.external_image = None
        self.wrist_image = None

        self.create_subscription(
            JointState,
            "/xarm/joint_states",
            self.joint_callback,
            10,
        )

        self.create_subscription(
            Image,
            EXTERNAL_TOPIC,
            self.external_callback,
            10,
        )

        self.create_subscription(
            Image,
            WRIST_TOPIC,
            self.wrist_callback,
            10,
        )

        self.gripper_client = self.create_client(
            GetFloat32,
            "/xarm/get_gripper_position",
        )

        self.mode_client = self.create_client(
            SetInt16,
            "/xarm/set_mode",
        )

        self.state_client = self.create_client(
            SetInt16,
            "/xarm/set_state",
        )

        self.joint_move_client = self.create_client(
            MoveJoint,
            "/xarm/set_servo_angle",
        )

    def joint_callback(self, msg):

        data = dict(zip(msg.name, msg.position))

        try:
            self.joints = np.array(
                [
                    data["joint1"],
                    data["joint2"],
                    data["joint3"],
                    data["joint4"],
                    data["joint5"],
                    data["joint6"],
                    data["joint7"],
                ],
                dtype=np.float32,
            )
        except KeyError:
            pass

    def external_callback(self, msg):

        self.external_image = np.asarray(
            self.bridge.imgmsg_to_cv2(
                msg,
                desired_encoding="rgb8",
            ),
            dtype=np.uint8,
        )

    def wrist_callback(self, msg):

        self.wrist_image = np.asarray(
            self.bridge.imgmsg_to_cv2(
                msg,
                desired_encoding="rgb8",
            ),
            dtype=np.uint8,
        )

    def refresh(self, seconds=0.5):

        start = time.time()

        while time.time() - start < seconds:
            rclpy.spin_once(
                self,
                timeout_sec=0.05,
            )

    def get_gripper(self):

        while not self.gripper_client.wait_for_service(
            timeout_sec=1.0
        ):
            print("Waiting for gripper read service...")

        future = self.gripper_client.call_async(
            GetFloat32.Request()
        )

        rclpy.spin_until_future_complete(
            self,
            future,
        )

        response = future.result()

        if response is None or response.ret != 0:
            raise RuntimeError(
                "Could not read gripper."
            )

        raw = float(response.data)

        # CINAPS convention:
        # 0    = closed
        # 850  = open
        normalized = float(
            np.clip(
                raw / 850.0,
                0.0,
                1.0,
            )
        )

        return raw, normalized

    def set_mode(self, mode):

        while not self.mode_client.wait_for_service(
            timeout_sec=1.0
        ):
            print("Waiting for /xarm/set_mode...")

        req = SetInt16.Request()
        req.data = int(mode)

        future = self.mode_client.call_async(req)

        rclpy.spin_until_future_complete(
            self,
            future,
        )

        return future.result()

    def set_state(self, state):

        while not self.state_client.wait_for_service(
            timeout_sec=1.0
        ):
            print("Waiting for /xarm/set_state...")

        req = SetInt16.Request()
        req.data = int(state)

        future = self.state_client.call_async(req)

        rclpy.spin_until_future_complete(
            self,
            future,
        )

        return future.result()

    def move_joint_once(self, target):

        while not self.joint_move_client.wait_for_service(
            timeout_sec=1.0
        ):
            print("Waiting for /xarm/set_servo_angle...")

        req = MoveJoint.Request()

        req.angles = [
            float(x)
            for x in target
        ]

        req.speed = float(MOVE_SPEED)
        req.acc = float(MOVE_ACC)
        req.mvtime = float(MOVE_TIME)

        # Important for Mode 6 online joint-space command.
        req.wait = False
        req.timeout = -1.0
        req.radius = -1.0
        req.relative = False

        future = self.joint_move_client.call_async(
            req
        )

        rclpy.spin_until_future_complete(
            self,
            future,
        )

        return future.result()


def main():

    rclpy.init()

    node = CinapsOneShot()

    print()
    print("============================================")
    print("CINAPS π0.5 ONE-SHOT ARM TEST")
    print("GRIPPER COMMANDS DISABLED")
    print("============================================")
    print()

    print("Waiting for robot + both cameras...")

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

    node.refresh()

    q_current = node.joints.astype(
        np.float64
    )

    home_error = np.abs(
        q_current - HOME
    )

    print()
    print("Current joints [rad]:")
    print(q_current)

    print()
    print("HOME difference [deg]:")
    print(np.rad2deg(home_error))

    if np.max(home_error) > MAX_HOME_ERROR:
        raise RuntimeError(
            "Robot is too far from CINAPS HOME. "
            "No motion will be sent."
        )

    raw_gripper, gripper_norm = (
        node.get_gripper()
    )

    print()
    print("Raw gripper:", raw_gripper)
    print(
        "Normalized gripper:",
        gripper_norm,
    )

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
        "observation/state":
            state,

        "observation/image":
            node.external_image,

        "observation/wrist_image":
            node.wrist_image,

        "prompt":
            PROMPT,
    }

    policy = (
        websocket_client_policy
        .WebsocketClientPolicy(
            host="127.0.0.1",
            port=8000,
        )
    )

    print()
    print("Running π0.5 inference...")

    start = time.time()

    result = policy.infer(
        observation
    )

    elapsed = time.time() - start

    actions = np.asarray(
        result["actions"],
        dtype=np.float64,
    )[:, :8]

    if actions.shape[0] < 1:
        raise RuntimeError(
            "Policy returned no actions."
        )

    if not np.all(np.isfinite(actions)):
        raise RuntimeError(
            "Policy returned NaN/Inf. "
            "No motion will be sent."
        )

    first_action = actions[0]

    q_predicted = first_action[:7]

    raw_delta = (
        q_predicted - q_current
    )

    print()
    print("Inference time:")
    print(elapsed, "s")

    print()
    print("π0.5 first 8-D action:")
    print(first_action)

    print()
    print("Predicted absolute joints [rad]:")
    print(q_predicted)

    print()
    print("Raw target-current delta [deg]:")
    print(np.rad2deg(raw_delta))

    if np.max(np.abs(raw_delta)) > MAX_RAW_DELTA:
        raise RuntimeError(
            "Raw π0.5 target is unexpectedly far "
            "from current pose. No motion sent."
        )

    # --------------------------------------------------------
    # SAFETY LIMITER
    # --------------------------------------------------------

    safe_delta = np.clip(
        raw_delta,
        -MAX_STEP,
        MAX_STEP,
    )

    q_safe = (
        q_current + safe_delta
    )

    print()
    print("============================================")
    print("PROPOSED FIRST PHYSICAL MOVEMENT")
    print("============================================")

    print()
    print("Safe delta [deg]:")
    print(np.rad2deg(safe_delta))

    print()
    print("Current joints [deg]:")
    print(np.rad2deg(q_current))

    print()
    print("Safe target [deg]:")
    print(np.rad2deg(q_safe))

    print()
    print(
        "π0.5 gripper prediction:",
        float(first_action[7]),
    )

    print(
        "GRIPPER WILL NOT MOVE IN THIS TEST."
    )

    print()
    print(
        "Maximum commanded joint change:",
        float(
            np.max(
                np.abs(
                    np.rad2deg(safe_delta)
                )
            )
        ),
        "deg",
    )

    print()
    print("Robot has NOT moved yet.")
    print()
    print(
        "Keep your hand near the emergency stop."
    )

    answer = input(
        "\nType exactly MOVE to send this ONE tiny arm command: "
    )

    if answer.strip() != "MOVE":

        print()
        print("Cancelled.")
        print("NO MOTION COMMAND SENT.")

        node.destroy_node()
        rclpy.shutdown()
        return

    # --------------------------------------------------------
    # ONLY NOW CHANGE ROBOT MODE / STATE
    # --------------------------------------------------------

    print()
    print("Setting xArm Mode 6...")

    mode_response = node.set_mode(6)

    print(
        "Mode response:",
        mode_response.ret,
        mode_response.message,
    )

    if mode_response.ret != 0:
        raise RuntimeError(
            "Could not set Mode 6."
        )

    print("Setting robot state 0...")

    state_response = node.set_state(0)

    print(
        "State response:",
        state_response.ret,
        state_response.message,
    )

    if state_response.ret != 0:
        raise RuntimeError(
            "Could not set robot state 0."
        )

    time.sleep(0.2)

    # Read latest joints again.
    node.refresh(0.3)

    q_before = node.joints.astype(
        np.float64
    )

    # Re-anchor the same safe displacement to
    # the freshest measured position.
    q_command = (
        q_before + safe_delta
    )

    print()
    print("Fresh joints before movement [deg]:")
    print(np.rad2deg(q_before))

    print()
    print("FINAL commanded target [deg]:")
    print(np.rad2deg(q_command))

    print()
    print("Sending ONE set_servo_angle command...")

    response = node.move_joint_once(
        q_command
    )

    if response is None:
        raise RuntimeError(
            "No response from set_servo_angle."
        )

    print()
    print(
        "Move response:",
        response.ret,
        response.message,
    )

    # Give the small movement time to complete,
    # then read actual result.
    time.sleep(1.0)

    node.refresh(0.5)

    q_after = node.joints.astype(
        np.float64
    )

    print()
    print("Actual joints after test [deg]:")
    print(np.rad2deg(q_after))

    print()
    print("Actual movement [deg]:")
    print(
        np.rad2deg(
            q_after - q_before
        )
    )

    print()
    print("============================================")
    print("ONE-SHOT TEST COMPLETE")
    print("NO SECOND POLICY ACTION WILL BE EXECUTED")
    print("GRIPPER WAS NOT COMMANDED")
    print("============================================")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
