# CINAPS Corrected Dataset — Initial Structural Validation

**Dataset:** `xarm_demos_cinaps_staged_50_corrected` (local workstation; not included in GitHub)

**Validation source:** Terminal output from October 15, 2026. The earlier one-off script checked row/image counts, image readability with OpenCV, and finite joint/action numbers. This document records that output; the new reusable validator is a **different, more stringent script**. Its actual results are documented below.

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

## Reusable validator results — October 15, 2026

The user executed `data_processing/validate_cinaps_dataset.py` against the corrected dataset using the default 100 ms camera callback skew warning threshold.

| Result | Value |
|---|---:|
| Episodes analyzed | 50 |
| Total CSV rows | 11,520 |
| Structural failures (`FAIL`) | **0** |
| Episodes with callback-skew warnings (`WARN`) | **50** |
| Highest recorded camera callback skew | **1,614.69 ms**, episode 0012 |
| Another high maximum | **1,557.8 ms**, episode 0046 |
| Lowest per-episode maximum | **166.0 ms**, episode 0026 |
| Validation report path on workstation | `/tmp/cinaps_validation.csv` |

**Meaning:** All episodes passed the validator's structural checks; none passed the strict 100 ms per-episode maximum callback-skew threshold. These are **warnings**, not demonstrated grasp or placement failures. The reported values are per-episode **maxima**, not means or medians. The actual per-frame timing distribution remains unknown from the summary log alone.

The validator currently checks JPEG headers and dimensions, not complete pixel decoding. The earlier OpenCV script performed readability checks. Successful runs do not prove that camera capture was synchronized, the arm trajectory was optimal, or every letter was correctly placed.

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
  --dataset ~/xarm_demos_cinaps_staged_50_corrected \
  --report /tmp/cinaps_validation.csv
```

The validator reports missing/misnumbered images, CSV field/finite-value issues, stage labels, timestamp monotonicity and callback skew warnings. It checks JPEG **headers**, not a full pixel decode; follow up with full image decoding where required.

## Follow-up required

1. Run and inspect the new validator report. Record per-episode timestamp skew distributions, not only the maximum.
2. Visually review grasp, lift, transport and placement outcomes and mark failures.
3. Confirm camera timebase/synchronization and decide whether resampling is needed.
4. Create a clean, labeled dataset and only then convert to LeRobot.
5. Do not commit the raw 4.3 GB dataset or full internal grasp PDF to the public repository without explicit lab authorization.


## Frame-level camera callback skew distribution — October 15, 2026

A read-only analysis of all `external_timestamp` and `wrist_timestamp` values in the 50 corrected episode CSV files produced:

| Metric | Result |
|---|---:|
| Frame pairs | **11,520** |
| Median absolute callback timestamp skew | **26.23 ms** |
| 95th percentile absolute callback skew | **144.70 ms** |
| Maximum skew | **1,614.69 ms** |
| Skew > 50 ms | **3,391 (29.44%)** |
| Skew > 100 ms | **1,557 (13.52%)** |
| Skew > 200 ms | **381 (3.31%)** |
| Skew > 500 ms | **61 (0.53%)** |
| Skew > 1000 ms | **11 (0.10%)** |

**Interpretation:** 86.48% of frame pairs are at or below the 100 ms callback skew threshold, although all 50 episodes contain at least one sample above it. These are callback-reception timestamps, not necessarily camera sensor timestamps, so they are not a direct measurement of physical capture synchronization. Before training, examine outliers and camera freshness/possible frame reuse; avoid changing or dropping the original data without an explicit preprocessing strategy and evaluation.

## Camera Synchronization Visualization

![CINAPS camera synchronization analysis](cinaps_camera_synchronization.png)

The median camera callback timestamp difference is 26.23 ms across
11,520 frame pairs. A total of 1,557 pairs (13.52%) exceed 100 ms.
These are callback timestamps, not verified sensor capture timestamps.
