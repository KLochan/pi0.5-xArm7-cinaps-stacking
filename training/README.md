# π0.5 CINAPS Corrected LoRA Training

This document records the **configuration observed in the original OpenPI training source** and checkpoint directories from the CINAPS workstation. It does not re-run training or certify checkpoint quality.

## Configuration

The `TrainConfig` named `pi05_xarm_cinaps_staged_50_corrected_lora` is defined in the developer's local `~/openpi/src/openpi/training/config.py`.

| Setting | Recorded configuration |
|---|---|
| Model | `Pi0Config(pi05=True)` |
| Data | `LeRobotXArmDataConfig` |
| Dataset repository ID | `lochan/xarm_cinaps_staged_50_corrected` |
| Action dimension | 32 |
| Action horizon | 15 |
| Discrete state input | False |
| PaliGemma variant | `gemma_2b_lora` |
| Action expert variant | `gemma_300m_lora` |
| Initial weights | `gs://openpi-assets/checkpoints/pi05_base/params` |
| Optimizer | AdamW |
| Gradient clipping norm | 1.0 |
| Learning-rate schedule | Cosine decay |
| Warmup | 1,000 steps |
| Peak learning rate | 2.5e-5 |
| Final learning rate | 2.5e-6 |
| Decay steps | 30,000 |
| Batch size | 1 |
| Configured training steps | 30,000 |
| Logging interval | 10 |
| Save interval | 1,000 |
| Keep period | 5,000 |
| EMA | None |
| Weights & Biases logging | Disabled |
| Prompt-from-task | False |

The inspected configuration also specifies `freeze_filter=Pi0Config(...).get_freeze_filter()` with the above LoRA variants.

The architecture's `action_dim=32` should not be confused with the **8-component xArm7 action representation** (seven joint values + normalized gripper) used by the local inference scripts.

## Checkpoints found

The corrected checkpoint root on the workstation is:

```text
/data/lochan/openpi/checkpoints/pi05_xarm_cinaps_staged_50_corrected_lora/
├── xarm_cinaps_staged_50_corrected_run1/
└── xarm_cinaps_staged_50_corrected_delta_run1/
```

Both run directories were observed with checkpoints at steps **5000, 10000, 15000, 20000, 25000, and 29999**. The full corrected checkpoint directory occupies approximately **107 GB** locally. At step 29999 the directories `assets/`, `params/`, and `train_state/` are present.

`_CHECKPOINT_METADATA` identifies OpenPI callback handling for assets and Orbax PyTree checkpoint handlers for parameters and train state. The displayed `metrics` and `performance_metrics` objects were empty, so neither loss nor physical success should be inferred from this metadata alone.

## Data conversion

The corresponding historical conversion source is `xarm_to_lerobot_cinaps_50_corrected.py`, which reads 50 staged episode folders from `~/xarm_demos_cinaps_staged_50_corrected`.

Its inspected feature definitions are:

| Feature | Shape / type |
|---|---|
| `external_image` | (720, 1280, 3), image |
| `wrist_image` | (720, 1280, 3), image |
| `joint_position` | (7,), float32 |
| `gripper_position` | (1,), float32 |
| `actions` | (8,), float32 |
| Conversion FPS | 6 |

**Destructive operation warning:** The historical converter includes `shutil.rmtree(output_path)` when an existing converted dataset is found. It deletes and rebuilds the previous *converted LeRobot output* without confirmation. It should not be run again before adding explicit protection and creating a backup.

**Status:** Training configuration and checkpoint directories observed; the remaining converter lines and training/runtime logs have not yet been fully audited. No checkpoint tensors, raw datasets, or logs are bundled with this document.
