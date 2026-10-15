# GELLO Dynamixel stiffness: settings and inspection

This documents configuration history; it is **not** a recommendation to apply motor settings without hardware verification. The GELLO XL330 control-table addresses used in the Python scripts are operating mode `11`, torque enable `64`, goal current `102`, goal position `116`, and (in the standalone test) present position `132`.

## Read-only inspection

```bash
cd ~/ufactory_teleop/gello_teleop
source ../.venv-gello/bin/activate
ls -l /dev/serial/by-id/
grep -nEi 'GELLO_CURRENT|CURRENT_MA|torque|current|stiff|pwm' \
  safe_gello_with_gripper.py test_gello_stiffness.py
python3 -m py_compile safe_gello_with_gripper.py test_gello_stiffness.py
```

Syntax compilation does not test motor limits, safe physical behavior, or correct current units.

## Distinguish THREE sets of values

| Joint ID | Historical proposed (Oct 13 PDFs) | Standalone `test_gello_stiffness.py` | Main `safe_gello_with_gripper.py` |
|---|---:|---:|---:|
| 1 | 15 | 30 | 8 |
| 2 | 30 | 60 | 15 |
| 3 | 30 | 60 | 15 |
| 4 | 20 | 40 | 15 |
| 5 | 15 | 30 | 15 |
| 6 | 25 | 25 | 15 |
| 7 | 20 | 20 | 15 |

These are **numeric values passed to the GOAL_CURRENT register**, not independently measured currents. In the standalone script, the dictionary is misleadingly called `CURRENT_MA`, but values are passed directly to `write2ByteTxRx`; confirm the exact motor model and register scale before interpreting as mA.

The main script's earlier console message printed `J1=30 J2=60 J3=60 J4=40 J5=30 J6=25 J7=20` despite writing the **main-script values** above. The GitHub-reviewed version corrected the message; the untouched operational script on the workstation may still print the misleading line.

## Standalone stiffness test — movement/torque possible

The actual `test_gello_stiffness.py` disables torque for IDs 1–7, changes to current-based position mode 5, reads the present position, sets that as the goal, writes goal-current registers, and finally enables torque. Its `finally` block attempts to disable torque and close the port.

**Do not run concurrently with teleoperation or a collection process.** Confirm that no other process owns GELLO serial, check the motor-specific allowable current and mode, prevent contact with the robot/workspace, test with robot-side teleoperation disabled, and have a supervised stop plan. Historical problems included tight J1, a failure disabling ID 1 torque, and Dynamixel communication errors.

Source: October 13 *GELLO Stiffness Adjustment* reference PDF, inspected October 15 Python scripts and terminal session.
