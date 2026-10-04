#!/usr/bin/env python3
"""Run basic QA checks on a rendered video."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import SkillError, ensure_project, fail, ffprobe, find_exe, read_json, run_cmd


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a QA report for the current render.")
    parser.add_argument("project", help="Project directory.")
    parser.add_argument("--render", help="Render path. Defaults to recipe final output.")
    args = parser.parse_args()

    try:
        project = ensure_project(Path(args.project))
        recipe = read_json(project / "recipe.json")
        render = Path(args.render) if args.render else project / recipe["output"]["final"]
        if not render.exists():
            fail(f"Missing render: {render}")
        probe = ffprobe(render)
        fmt = probe.get("format", {})
        duration = float(fmt.get("duration") or 0)
        expected = sum(float(s["out"]) - float(s["in"]) for s in recipe["segments"])
        findings: list[str] = []
        if abs(duration - expected) > 0.35:
            findings.append(f"duration mismatch: expected {expected:.2f}s, got {duration:.2f}s")
        if int(fmt.get("size") or 0) <= 0:
            findings.append("render has zero size")

        ffmpeg = find_exe("ffmpeg")
        sheet = project / "qa" / "cut-check.jpg"
        if ffmpeg:
            try:
                run_cmd(
                    [
                        ffmpeg,
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(render),
                        "-vf",
                        "fps=1/2,scale=240:-1,tile=5x5",
                        "-frames:v",
                        "1",
                        str(sheet),
                    ]
                )
            except SkillError as exc:
                findings.append(f"could not create contact sheet: {exc}")

        status = "PASS" if not findings else "REVIEW"
        report = project / "qa" / "report.md"
        lines = [
            "# QA Report",
            "",
            f"Render: `{render}`",
            f"Status: **{status}**",
            f"Duration: {duration:.2f}s",
            f"Expected: {expected:.2f}s",
            "",
            "## Findings",
            "",
        ]
        if findings:
            lines.extend(f"- {item}" for item in findings)
        else:
            lines.append("- No blocking findings from automated checks.")
        lines.extend(["", "## Artifacts", "", f"- Contact sheet: `{sheet}`"])
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{status}: wrote {report}")
        return 0 if not findings else 2
    except SkillError as exc:
        fail(str(exc))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

