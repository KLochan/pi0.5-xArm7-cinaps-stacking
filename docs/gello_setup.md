# GELLO + xArm7: verified startup and implementation notes

Platform: `cinaps-ws`, Ubuntu 24.04, ROS 2 Jazzy, UFactory xArm7, UF G2, Dynamixel GELLO.

> **Hardware safety:** Commands which launch teleoperation can move the real robot. Only run them under direct supervision, with a clear workspace and accessible emergency stop. Never start multiple processes controlling the arm or the same GELLO serial port. Software pause is not an emergency stop.

## 1. Workstation and robot connectivity (read only)

```bash
hostname
ip -4 addr show enp130s0
ping -c 4 192.168.1.226
```

The workstation previously used `192.168.1.100/24` and the controller `192.168.1.226`. Successful ping confirms Ethernet reachability, **not motion readiness**. On October 15, ping succeeded with 4/4 replies.

## 2. GELLO environment and serial device (read only)

```bash
cd ~/ufactory_teleop/gello_teleop
source ../.venv-gello/bin/activate
ls -l /dev/serial/by-id/
ls -lah config/
ls -l safe_gello_with_gripper.py test_gello_stiffness.py
cat config/xarm7_gello_local.yaml
```

Previously observed FTDI by-id device: `/dev/serial/by-id/usb-FTDI_USB__-__Serial_Converter_FTBIN9YP-if00-port0` -> `../../ttyUSB0`. The by-id device path should be rechecked each session. Close competing serial-port applications first.

The **actual local configuration inspected on October 15** specified `robot_mode: 6`, speed `20` deg/s, acceleration `100` deg/s², gripper type `2`, GELLO IDs `[1,2,3,4,5,6,7]`, **joint signs `[1,-1,1,1,1,1,1]`**, and gripper ID `8`. The earlier draft PDF's all-positive joint-sign assumption is superseded by the inspected YAML. Start angles (radians, for inspection only): `[-0.383293, -0.351749, -0.116091, 0.794706, 0.067219, 1.041443, 1.083854]`. Do not use these as an unplanned move command.

## 3. Controller error and status check (read only)

On October 15 the first teleop attempt failed during initialization with xArm ControllerError `1`. A later read-only check confirmed `CONNECTED: True`, error/warning `[0,0]`, and state `2` before teleoperation resumed. `get_mode()` was unavailable in the installed `XArmAPI` wrapper; the AttributeError was an SDK API mismatch, not a robot-controller error.

```bash
python - <<'PY'
from xarm.wrapper import XArmAPI
arm = XArmAPI('192.168.1.226', do_not_open=True)
try:
    arm.connect()
    print('CONNECTED:', arm.connected)
    print('ERROR/WARNING:', arm.get_err_warn_code())
    print('STATE:', arm.get_state())
    print('JOINT ANGLES:', arm.get_servo_angle(is_radian=True))
finally:
    arm.disconnect()
PY
```

This does not clear errors or enable motor motion. If the controller reports any fault, diagnose on the pendant/controller before attempting teleoperation.

## 4. Standalone supervised GELLO test (MAY MOVE ROBOT)

Do not run alongside an integrated CINAPS collector.

```bash
cd ~/ufactory_teleop/gello_teleop
source ../.venv-gello/bin/activate
touch /tmp/gello_pause
python safe_gello_with_gripper.py --config config/xarm7_gello_local.yaml
```

Wait for a confirmed connection and successful synchronization, and follow the on-screen pose/clearance prompts. The launcher starts paused by creating `/tmp/gello_pause`. In a **second** terminal, resume only when the area is clear and the operator is ready:

```bash
rm -f /tmp/gello_pause  # RESUME — supervised motion possible
touch /tmp/gello_pause  # PAUSE
```

To stop the foreground program, use its documented handler (normally `Ctrl+C`); verify motor and port shutdown. A clutch file does not substitute for the physical emergency stop.

## 5. Observed GELLO tracking, October 15

The supplied log shows seven joint readouts, repeated `arm send_action = 0` returns, and J1–J6 displayed tracking-lag values of approximately `0.00`–`0.28` degrees in the shown interval. A later `GELLO PAUSED` message confirms the clutch transition. These observations support command acceptance and close joint tracking **during this trace**, not validated grasp success, collision safety, or long-term reliability.

## 6. Known safety / documentation limitations

- The working arm script defines a 20-degree J1–J6 lag threshold but does **not** enforce a hard stop on accumulated lag. Its original `safety stop` print line was misleading.
- The main script's Dynamixel `GELLO_CURRENT` register values and its old status message disagree; see `gello_stiffness.md`.
- The public YAML is a **sanitized template** using placeholders for robot IP and FTDI port; do not execute until configured for the actual local machine.
- The public script imports `gello.dynamixel.driver` and `ufactory_devices.robot` from upstream/local dependencies that have not been included in this repository. A fresh clone is not a self-contained robot-control installation.

## Sources

Consolidated from the October 13 implementation guide and checklist and October 15 terminal outputs. Raw PDFs should remain in a local/private archive pending laboratory publication approval.
