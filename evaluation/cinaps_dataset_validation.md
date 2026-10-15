# CINAPS Corrected Dataset — Initial Structural Validation

**Dataset:** `xarm_demos_cinaps_staged_50_corrected` (local workstation; not included in GitHub)

**Validation source:** Terminal output from October 15, 2026. The earlier one-off script checked row/image counts, image readability with OpenCV, and finite joint/action numbers. This document records that output; the new reusable validator is a **different, more stringent script** and its results must be generated separately.

| Measure | Observed result |
|---|---:|
| Episode directories | 50 |
| Total CSV records | 11,520 |
| External JPEG frames (matched per episode) | 11,520 |
| Wrist JPEG frames (matched per episode) | 11,520 |
| Episodes with structural issues in initial check | 0 |
| Largest external/wrist callback timestamp difference | **1,614.69 ms** |
| Sample image resolution (both cameras, episode_0001 frame 000000) | **1280 × 720** |
| Corrected dataset local disk usage | **4.3 GB** |
| OpenCV installed in system Python | 4.6.0 |

## Interpretation

All 50 episodes passed the **initial structural script**, which checked image counts and matched them with CSV row counts, parsed finite joint/action numbers, and attempted decoding JPEGs using OpenCV. It did *not* rigorously check per-frame filename correspondence, stage consistency, time monotonicity, or physical task success.

The **1,614.69 ms maximum camera timestamp offset warrants investigation** before training. These are recorder callback timestamps, not necessarily synchronized hardware capture timestamps; the maximum also does not describe typical/median offset. Do not label the camera streams synchronized based on these results.

The recorded `gripper_position` and `action_gripper` fields reflect the GELLO state-export representation; they should not be interpreted as independently verified physical G2 opening measurements.

The accompanying 84-page *CINAPS 1–50 Grasp Report* shows frames around identified gripper-closing events with external/wrist images and joint values. This is **not** evidence that every episode successfully grasped and placed its letter.

## Reproduce a stricter read-only validation

From the cloned repository on the workstation:

```bash
cd ~/pi0.5-xArm7-cinaps-stacking
/usr/bin/python3 data_processing/validate_cinaps_dataset.py \\
  --dataset ~/xarm_demos_cinaps_staged_50_corrected \\
  --report /tmp/cinaps_validation.csv
```

The validator reports missing/misnumbered images, CSV field/finite-value issues, stage labels, timestamp monotonicity and callback skew warnings. It checks JPEG **headers**, not a full pixel decode; follow up with full image decoding where required.

## Follow-up required

1. Run and inspect the new validator report. Record per-episode timestamp skew distributions, not only the maximum.
2. Visually review grasp, lift, transport and placement outcomes and mark failures.
3. Confirm camera timebase/synchronization and decide whether resampling is needed.
4. Create a clean, labeled dataset and only then convert to LeRobot.
5. Do not commit the raw 4.3 GB dataset or full internal grasp PDF to the public repository without explicit lab authorization.
