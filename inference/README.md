# CINAPS π0.5 Inference Experiments

This directory contains experimental inference implementations
for the UFactory xArm7 using the CINAPS-trained π0.5 policy.

## Scripts

- xarm_pi05_cinaps_one_shot.py
  Single predicted action with limited joint movement.

- xarm_pi05_cinaps_chunk5.py
  Five predicted actions (A1-A5), intermediate trajectory
  checks, and manual operator approval.

## Observations

- External RGB camera
- Wrist RGB camera
- Seven robot joint positions
- Normalized gripper observation
- Natural-language CINAPS instruction

## Checkpoints

Corrected CINAPS LoRA checkpoints were saved at steps
5000, 10000, 15000, 20000, 25000, and 29999.

Checkpoint weights are not included in this repository.

## Safety and Limitations

These scripts can command physical robot movement.
They are experimental research code, not validated
collision-free or safety-certified robot controllers.

The gripper is not commanded in these experiments.
Physical task success and execution logs have not yet
been independently verified.

Do not execute on hardware without reviewing motion
constraints, joint limits, error responses, emergency
stop access, and the current robot configuration.
