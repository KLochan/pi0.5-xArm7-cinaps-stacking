# CINAPS 1–50 grasp-event report: public-safe summary

Source: local 84-page *CINAPS 1-50 Grasp Report*, dated October 13, 2026. The report identifies dataset `xarm_demos_cinaps_staged_50_corrected` and shows frames around the **first detected gripper closing** for numbered demonstrations `episode_0001` through `episode_0050`.

The report displays gripper measurements, gripper-action values, J1–J7 values, and corresponding **external RGB / wrist RGB** views. Example selected frames include episode 0001 at frame 98, episode 0002 at frame 140, episode 0003 at frame 93 and episode 0050 at frame 78. These are reported grasp-event frames, **not proof of a successful physical grasp**.

## What is supported

- A 50-episode *numbered* report exists, derived from the corrected staged dataset.
- External and wrist-camera pictures accompany per-frame motion/gripper data at the reported grasp events.
- Gripper changes can be inspected alongside joint observations to check the timing of attempted grasps.

## What is not established

- That every episode has synchronized valid sensor data throughout the entire trajectory.
- That each gripper closing led to successful object acquisition or placement.
- That six letters were correctly arranged or vertically stacked in each episode.
- A measured success rate, trained pi0.5 checkpoint, or autonomous policy performance.

## Next analysis

Review all 50 recordings for task completion, missing frames, camera alignment, out-of-range joints, gripper closures, timestamps, and labels; publish an aggregate, permission-cleared metrics table. Store the full report and image-rich source data privately until lab permission is confirmed. The 127 MB PDF is **not included** in this GitHub documentation bundle.
