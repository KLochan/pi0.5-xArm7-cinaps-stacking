# CINAPS letter demonstration collection: workflow and validation

**Task:** Arrange letters C, I, N, A, P, S into designated places to form CINAPS. Example initial task instruction: "Pick up the blue letter C and place it in the marked C position." Do not equate placement into designated slots with vertical stacking unless the experiment genuinely uses stacked letters.

## Stage A — verify hardware / image sources (read only)

```bash
hostname
ip -4 addr show enp130s0
ping -c 4 192.168.1.226
ls -l /dev/serial/by-id/
rs-enumerate-devices
source /opt/ros/jazzy/setup.bash
ros2 topic list
```

Previous camera configuration: external and wrist RealSense. The October 13 notes propose `640x480 @ 15 FPS` for CINAPS; live frame rate was **not established by those notes**. Earlier handwash demonstrations used 6 FPS. Inspect camera assignment/serial numbers and ensure one process owns each device.

If ROS topics exist, check:

```bash
ros2 topic hz /external/external/color/image_raw
ros2 topic hz /wrist/wrist/color/image_raw
```

`ros2 topic hz` continues until interrupted; direct camera collectors may not expose ROS topics. Do not launch parallel camera drivers if the collector opens the cameras itself.

## Stage B — inspect the actual collection implementation first

The October 13 PDF proposes `~/cinaps_collection/run_cinaps_50.sh` and `collect_cinaps_50.py`, but their presence and content were **not verified by that PDF**. The October 15 supplied grasp report indicates a separate `xarm_demos_cinaps_staged_50_corrected` dataset; the correct active collector and path still need live inspection.

```bash
ls -lah ~/cinaps_collection
ls -l ~/cinaps_collection/run_cinaps_50.sh \
      ~/cinaps_collection/collect_cinaps_50.py
sed -n '1,240p' ~/cinaps_collection/run_cinaps_50.sh
python3 -m py_compile ~/cinaps_collection/collect_cinaps_50.py
ps -ef | grep -E 'gello|collect_cinaps|realsense|ros2' | grep -v grep
```

If the named files do not exist, **stop** and locate the actual collector rather than running guessed commands. Review: camera ownership, robot ownership, reset, pause/stop behavior, recording frequency, saved schema, label ordering, and episode output directory.

## Stage C — supervised episode procedure

1. Clear the xArm workspace, confirm accessible physical E-stop, and confirm one owner of robot and GELLO serial.
2. Place the letters for the intended task and verify visibility from external and wrist cameras.
3. Record task text, timestamps, robot joint readings, gripper position/action, and camera observations.
4. Teleoperate approach, grasp, lift, transfer, and release into the target position.
5. Finish/save using the **actual collector's documented** mechanism; do not assume key bindings.
6. Inspect the episode before beginning a batch. Repeat only after a safe workspace reset.

An integrated launch command such as `./run_cinaps_50.sh` is **conditional**, not a verified safe-to-run instruction. Never launch it alongside standalone GELLO teleoperation unless the collection architecture has explicitly been verified to support that arrangement.

## Stage D — audit episodes, then back up

First establish the actual output directory from the collector. The following path was proposed in the older guide but may differ from the corrected dataset named in the grasp report:

```bash
ls -lah ~/xarm_demos_cinaps_50
find ~/xarm_demos_cinaps_50 -maxdepth 1 -type d -name 'episode_*' | wc -l
du -sh ~/xarm_demos_cinaps_50
find ~/xarm_demos_cinaps_50 -type f -empty
```

Verify **for every episode**: readable external/wrist RGB frames, synchronized timestamps, 7 joint values, G2 observations/actions, task labels, and complete trajectory. Counted files or closing events are not task success. Backup using `rsync` only after confirming source/destination and available disk space:

```bash
mkdir -p /data/lochan/cinaps_backup
rsync -avh --progress ~/xarm_demos_cinaps_50/ /data/lochan/cinaps_backup/
```

Do not delete originals after copying without separately validating backup completeness.

## Stage E — next research phase

Following dataset validation: implement a CINAPS-specific LeRobot converter; validate observation/action fields and visual samples; fine-tune pi0.5; run inference-only and dry-run checks; then test bounded real-robot operation with direct supervision. Neither training nor autonomous stacking success is demonstrated by the reference PDFs.
