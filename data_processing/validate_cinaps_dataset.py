#!/usr/bin/env python3
"""Read-only audit of corrected xArm7 CINAPS staged recordings.

Usage:
    /usr/bin/python3 data_processing/validate_cinaps_dataset.py
    /usr/bin/python3 data_processing/validate_cinaps_dataset.py --dataset ~/xarm_demos_cinaps_staged_50_corrected --report /tmp/cinaps_validation.csv

A PASS means structural checks passed, NOT successful grasp/placement.
Camera skew is measured from callback timestamps in the CSV (not image sensor capture timestamps).
"""
import argparse
import csv
import math
from pathlib import Path

STAGES = [
    (1, 8, "C"), (9, 16, "I"), (17, 24, "N"),
    (25, 32, "A"), (33, 40, "P"), (41, 48, "S"),
    (49, 50, "FULL"),
]
REQUIRED = (
    ["frame", "timestamp", "state_timestamp", "external_timestamp", "wrist_timestamp"]
    + [f"joint{i}" for i in range(1, 8)]
    + ["gripper_position"]
    + [f"action_joint{i}" for i in range(1, 8)]
    + ["action_gripper", "g2_target_mm", "stage_letter", "demo_in_stage"]
)
FINITE_COLS = [
    "timestamp", "state_timestamp", "external_timestamp", "wrist_timestamp",
    *[f"joint{i}" for i in range(1, 8)],
    "gripper_position",
    *[f"action_joint{i}" for i in range(1, 8)],
    "action_gripper", "g2_target_mm",
]


def expected_stage(number):
    for start, end, stage in STAGES:
        if start <= number <= end:
            return stage, number - start + 1
    return None, None


def jpeg_resolution(path):
    """Read JPEG dimensions with standard library only; no image decode."""
    with path.open("rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise ValueError("not JPEG")
        while True:
            marker_start = f.read(1)
            if not marker_start:
                raise ValueError("no JPEG SOF marker")
            if marker_start != b"\xff":
                continue
            marker = f.read(1)
            while marker == b"\xff":
                marker = f.read(1)
            if not marker:
                raise ValueError("truncated JPEG")
            code = marker[0]
            if code in (0xD8, 0xD9) or 0xD0 <= code <= 0xD7 or code == 0x01:
                continue
            length_b = f.read(2)
            if len(length_b) != 2:
                raise ValueError("truncated marker")
            length = int.from_bytes(length_b, "big")
            if length < 2:
                raise ValueError("bad marker length")
            if code in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                hdr = f.read(5)
                if len(hdr) != 5:
                    raise ValueError("truncated SOF")
                height = int.from_bytes(hdr[1:3], "big")
                width = int.from_bytes(hdr[3:5], "big")
                return width, height
            f.seek(length - 2, 1)


def inspect_episode(folder, expected_resolution, warn_skew_ms):
    errors = []
    warnings = []
    csv_path = folder / "robot_data.csv"
    try:
        episode_id = int(folder.name.split("_", 1)[1])
    except (IndexError, ValueError):
        return dict(episode=folder.name, frames=0, external=0, wrist=0, max_skew_ms=0,
                    status="FAIL", errors="Invalid episode name", warnings="")
    stage, stage_index = expected_stage(episode_id)
    if stage is None:
        errors.append("episode number outside 1..50")
    rows = []
    if not csv_path.is_file():
        errors.append("missing robot_data.csv")
    else:
        with csv_path.open(newline="") as stream:
            reader = csv.DictReader(stream)
            missing = set(REQUIRED) - set(reader.fieldnames or [])
            if missing:
                errors.append("missing CSV columns: " + ",".join(sorted(missing)))
            else:
                rows = list(reader)
    n = len(rows)
    if n == 0:
        errors.append("no CSV records")
    filenames = {f"{i:06d}.jpg" for i in range(n)}
    camera_counts = {}
    for camera in ("external", "wrist"):
        camera_dir = folder / camera
        images = sorted(camera_dir.glob("*.jpg")) if camera_dir.is_dir() else []
        camera_counts[camera] = len(images)
        names = {p.name for p in images}
        if names != filenames:
            errors.append(f"{camera} filenames disagree with CSV row indices")
        for photo in images:
            try:
                wh = jpeg_resolution(photo)
                if wh != expected_resolution:
                    errors.append(f"{camera}/{photo.name} size {wh} expected {expected_resolution}")
                    break
            except (OSError, ValueError) as exc:
                errors.append(f"{camera}/{photo.name} malformed JPEG header: {exc}")
                break
    max_skew = 0.0
    prev_time = None
    if rows:
        for idx, row in enumerate(rows):
            try:
                if int(row["frame"]) != idx:
                    errors.append(f"frame index mismatch at row {idx}")
                    break
                if stage is not None and (row["stage_letter"] != stage or
                                          int(row["demo_in_stage"]) != stage_index):
                    errors.append(f"stage label mismatch at row {idx}")
                    break
                values = {name: float(row[name]) for name in FINITE_COLS}
                if not all(math.isfinite(v) for v in values.values()):
                    errors.append(f"non-finite CSV data at row {idx}")
                    break
                for name in ("gripper_position", "action_gripper"):
                    if not 0 <= values[name] <= 1:
                        warnings.append(f"{name} outside [0,1] at row {idx}")
                t = values["timestamp"]
                if prev_time is not None and t <= prev_time:
                    errors.append(f"non-increasing CSV timestamp at row {idx}")
                    break
                prev_time = t
                skew = abs(values["external_timestamp"] - values["wrist_timestamp"]) * 1000.0
                max_skew = max(max_skew, skew)
            except (KeyError, ValueError, TypeError) as exc:
                errors.append(f"invalid CSV row {idx}: {exc}")
                break
    if max_skew > warn_skew_ms:
        warnings.append(f"camera callback skew {max_skew:.1f} ms > {warn_skew_ms:g} ms")
    return dict(episode=folder.name, frames=n, external=camera_counts["external"],
                wrist=camera_counts["wrist"], max_skew_ms=round(max_skew, 2),
                status="FAIL" if errors else ("WARN" if warnings else "PASS"),
                errors="; ".join(errors), warnings="; ".join(dict.fromkeys(warnings)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path,
                        default=Path.home() / "xarm_demos_cinaps_staged_50_corrected")
    parser.add_argument("--report", type=Path, help="Optional CSV report output path")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--warn-skew-ms", type=float, default=100)
    args = parser.parse_args()
    if not args.dataset.is_dir():
        parser.error(f"Dataset directory does not exist: {args.dataset}")
    episodes = sorted(p for p in args.dataset.glob("episode_*") if p.is_dir())
    results = [inspect_episode(p, (args.width, args.height), args.warn_skew_ms)
               for p in episodes]
    present = {r["episode"] for r in results}
    missing = {f"episode_{i:04d}" for i in range(1, 51)} - present
    for r in results:
        print(f'{r["episode"]}: {r["status"]} | rows={r["frames"]} | '
              f'external={r["external"]} | wrist={r["wrist"]} | '
              f'max skew={r["max_skew_ms"]:.1f}ms')
    print(f'Folders: {len(results)} | Frames: {sum(r["frames"] for r in results)} | '
          f'FAIL: {sum(r["status"] == "FAIL" for r in results)} | '
          f'WARN: {sum(r["status"] == "WARN" for r in results)}')
    print(f'Max callback skew: {max((r["max_skew_ms"] for r in results), default=0):.2f} ms')
    if missing:
        print("Missing episodes:", ", ".join(sorted(missing)))
    for r in results:
        if r["errors"] or r["warnings"]:
            print(f'{r["episode"]}: {r["errors"] or r["warnings"]}')
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(results[0]) if results else
                                    ["episode", "frames", "external", "wrist",
                                     "max_skew_ms", "status", "errors", "warnings"])
            writer.writeheader()
            writer.writerows(results)
        print("Report:", args.report)
    if missing or any(r["status"] == "FAIL" for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
