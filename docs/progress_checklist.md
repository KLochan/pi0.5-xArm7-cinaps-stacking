# CINAPS implementation progress checklist

**Evidence cutoff:** October 15, 2026. A check means evidence for the stated narrow claim, not broad motion safety or finished autonomous behavior.

| Status | Milestone | Evidence / remaining action |
|---|---|---|
| [x] | xArm7 Ethernet | 4/4 ping replies on Oct 15; controller reachability confirmed |
| [x] | FTDI GELLO USB | by-id adapter seen pointing to `ttyUSB0` |
| [x] | GELLO configuration identified | Local YAML inspected; J2 joint sign is `-1` |
| [x] | GELLO arm command/feedback trace | Oct 15 trace: `send_action = 0`; close 7-joint tracking; pause state observed |
| [x] | Stiffness scripts identified | Main and standalone Python source inspected; syntax of standalone test passed |
| [ ] | Verified physical safety limits | Lag limit in main script is informational, not an enforced hard stop |
| [ ] | Verified current unit/limits and motor readback | Three historical/script parameter sets disagree; inspect actual motors |
| [ ] | Both cameras live in CINAPS collection | Inspect actual image streams and synchronization |
| [ ] | Integrated collector source verified | Identify and inspect actual scripts and process ownership |
| [x] | Grasp report covering episodes 0001–0050 provided | 84-page report for `xarm_demos_cinaps_staged_50_corrected` with camera frames and grasp-event selections |
| [ ] | 50 valid completed placement/stacking episodes | Requires episode-wide QA; grasp-closing frames alone are insufficient |
| [ ] | CINAPS LeRobot dataset validated | Not established by supplied PDFs |
| [ ] | CINAPS pi0.5 training/inference validated | Not established by supplied PDFs |

## Historical notes

The earlier Oct 13 checklist marked GELLO teleoperation only "previously done"; the Oct 15 supplied trace provides newer evidence of commanded arm tracking. The original PDF also labels 50 episodes a future target; the subsequently supplied grasp report provides evidence of **50 numbered episodes in a corrected staged dataset**. Neither contradicts the need for per-episode validation.

See `gello_setup.md`, `gello_stiffness.md`, `cinaps_collection.md`, and `cinaps_grasp_report.md`.
