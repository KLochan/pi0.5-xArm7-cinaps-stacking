#!/usr/bin/env python3

import time
from dynamixel_sdk import (
    PortHandler,
    PacketHandler,
    COMM_SUCCESS,
)

PORT = "/dev/serial/by-id/usb-FTDI_USB__-__Serial_Converter_FTBIN9YP-if00-port0"
BAUD = 57600

ARM_IDS = [1, 2, 3, 4, 5, 6, 7]

# XL330 control-table addresses
ADDR_OPERATING_MODE = 11
ADDR_TORQUE_ENABLE = 64
ADDR_GOAL_CURRENT = 102
ADDR_GOAL_POSITION = 116
ADDR_PRESENT_POSITION = 132

CURRENT_BASED_POSITION_MODE = 5

# Very conservative first test, approximately mA
CURRENT_MA = {
    1: 30,
    2: 60,
    3: 60,
    4: 40,
    5: 30,
    6: 25,
    7: 20,
}

port = PortHandler(PORT)
packet = PacketHandler(2.0)


def check(comm, err, text):
    if comm != COMM_SUCCESS:
        raise RuntimeError(
            f"{text}: {packet.getTxRxResult(comm)}"
        )
    if err != 0:
        raise RuntimeError(
            f"{text}: {packet.getRxPacketError(err)}"
        )


try:
    if not port.openPort():
        raise RuntimeError("Could not open GELLO serial port")

    if not port.setBaudRate(BAUD):
        raise RuntimeError("Could not set GELLO baud rate")

    print("\nGELLO stiffness test")
    print("Hold the GELLO in its current pose.")
    print("IDs 1-7 only. Gripper ID 8 is untouched.\n")

    # --------------------------------------------------------
    # 1. Disable torque before changing operating mode
    # --------------------------------------------------------
    for dxl_id in ARM_IDS:
        comm, err = packet.write1ByteTxRx(
            port,
            dxl_id,
            ADDR_TORQUE_ENABLE,
            0,
        )
        check(comm, err, f"Disable torque ID {dxl_id}")

    # --------------------------------------------------------
    # 2. Set current-based position mode
    # --------------------------------------------------------
    for dxl_id in ARM_IDS:
        comm, err = packet.write1ByteTxRx(
            port,
            dxl_id,
            ADDR_OPERATING_MODE,
            CURRENT_BASED_POSITION_MODE,
        )
        check(comm, err, f"Set mode ID {dxl_id}")

    # --------------------------------------------------------
    # 3. Read the ACTUAL current position
    #    and immediately make that the goal position
    # --------------------------------------------------------
    goal_positions = {}

    for dxl_id in ARM_IDS:
        pos, comm, err = packet.read4ByteTxRx(
            port,
            dxl_id,
            ADDR_PRESENT_POSITION,
        )
        check(comm, err, f"Read position ID {dxl_id}")
        goal_positions[dxl_id] = pos

    for dxl_id in ARM_IDS:
        comm, err = packet.write4ByteTxRx(
            port,
            dxl_id,
            ADDR_GOAL_POSITION,
            goal_positions[dxl_id],
        )
        check(comm, err, f"Set goal position ID {dxl_id}")

    # --------------------------------------------------------
    # 4. Set small current limits
    # --------------------------------------------------------
    for dxl_id in ARM_IDS:
        current = CURRENT_MA[dxl_id]

        comm, err = packet.write2ByteTxRx(
            port,
            dxl_id,
            ADDR_GOAL_CURRENT,
            current,
        )
        check(comm, err, f"Set current ID {dxl_id}")

    # --------------------------------------------------------
    # 5. Enable torque LAST
    # --------------------------------------------------------
    for dxl_id in ARM_IDS:
        comm, err = packet.write1ByteTxRx(
            port,
            dxl_id,
            ADDR_TORQUE_ENABLE,
            1,
        )
        check(comm, err, f"Enable torque ID {dxl_id}")

    print("Stiffness enabled.")
    print("Move GELLO gently by hand.")
    print("Press Ctrl+C to disable torque and exit.")

    while True:
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nStopping...")

finally:
    print("Disabling GELLO arm torque...")

    try:
        for dxl_id in ARM_IDS:
            packet.write1ByteTxRx(
                port,
                dxl_id,
                ADDR_TORQUE_ENABLE,
                0,
            )
    except Exception:
        pass

    port.closePort()

    print("Torque disabled. GELLO is passive again.")
