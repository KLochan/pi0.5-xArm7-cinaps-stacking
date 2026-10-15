# CINAPS real-robot benchmark protocol (planned)

**Status:** Evaluation protocol, **not a completed benchmark**. Do not interpret a structurally valid recording, detected gripper closing, or a successful policy inference call as a successful manipulation.

## Tasks and endpoints

| Endpoint | Proposed pass criterion | Report |
|---|---|---|
| Grasp success | Target letter is lifted and remains held for a pre-declared hold interval | successes / attempts and rate |
| Placement success | Target letter is released in its designated marked region, with pre-declared position/orientation tolerance | successes / attempts and rate |
| Full CINAPS success | All six letters are placed in the correct C-I-N-A-P-S order within the trial time limit | successes / full-sequence trials and rate |
| Policy inference latency | Time for policy call, after input has been assembled; report median, p95 and sample count | milliseconds |
| End-to-end control latency | Time from identified observation availability through action delivery (explicit start/stop boundaries required) | milliseconds |
| Camera timing | Difference of camera message capture timestamps if available; report callback receipt skew separately | median, p95, outlier fractions |

## Experiment design to specify before running

1. Fix the robot calibration, initial letter poses, gripper settings, camera configuration, checkpoint, action chunk size and timeout.
2. Record each episode's letter, start condition, predicted action details, outcome label, intervention and failure reason. Distinguish manual demonstrations from autonomous policy rollouts.
3. Use repeated trials per letter and full-sequence runs. Report the exact denominator and confidence intervals; do not conflate partial and full-task successes.
4. Log inference-only time separately from total camera-to-robot latency; include hardware, checkpoint and code commit details.
5. Audit visual recordings independently for successful grasps and placements. A closing event is not proof of grasp.
6. Note all safety-related stops and interventions, and do not claim collision avoidance without dedicated validation.

## Currently supported evidence

- **50** corrected staged episode folders; **11,520** paired camera records passed structural checks.
- Camera **callback-reception** timestamp skew: median **26.23 ms**, p95 **144.7 ms**, **13.52%** greater than 100 ms. These are not sensor exposure timestamps.
- Eight preliminary policy-call latency values are shown in the main README; exact task/checkpoint attribution is unverified and therefore they are **not** an autonomous CINAPS benchmark.
- Grasp, placement and full-sequence success rates are **not yet quantified**.

See [dataset validation](cinaps_dataset_validation.md) and the [README](../README.md).
