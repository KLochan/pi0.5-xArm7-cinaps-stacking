
# π0.5 xArm7 CINAPS Letter Stacking

**GELLO Teleoperation and Vision-Language-Action Robotic Manipulation on UFactory xArm7**

## Overview

This repository documents the development of a real-robot CINAPS letter manipulation system using a UFactory xArm7, UF G2 gripper, GELLO teleoperation, and dual Intel RealSense cameras.

The project covers robot setup, teleoperation, demonstration collection, letter placement, and planned integration with the π0.5 Vision-Language-Action policy.

## Hardware and Software

| Component | Details |
|---|---|
| Robot | UFactory xArm7 |
| Gripper | UF G2 |
| Teleoperation | GELLO with Dynamixel motors |
| Cameras | External and wrist-mounted Intel RealSense |
| Middleware | ROS 2 Jazzy |
| Planned VLA policy | π0.5 / OpenPI |
| Planned dataset format | LeRobot |

## Task Definition

The target task involves picking and placing the letters of CINAPS using the xArm7 robot.

Initial instruction:
"Pick up the blue letter C and place it in the marked C position."

## Development Status

- [x] xArm7 network and gripper setup
- [x] GELLO teleoperation integration and tuning
- [ ] Verify and publish demonstration recording scripts
- [ ] Verify CINAPS letter placement execution
- [ ] Prepare and validate the CINAPS dataset
- [ ] Integrate π0.5 training and inference
- [ ] Evaluate complete CINAPS letter stacking

## Repository Contents

Implementation scripts, setup instructions, demonstration workflows, tests, and evaluation materials will be added as they are verified.

Large datasets, trained checkpoints, ROS bags, and third-party repositories will be excluded.

## Acknowledgements

Developed at CINAPS Lab, Graduate School of System Informatics, Kobe University, Japan.

This project uses or plans to integrate GELLO, UFactory xArm7, Intel RealSense, ROS 2, LeRobot, and OpenPI, subject to their respective licenses.
  
