#!/usr/bin/env python3
"""Face boxes and person masks with MediaPipe, for Linux and Windows.

Used by vision.py when Apple Vision is not available (or VIDEO_EDIT_VISION=mediapipe).
Needs `python3 -m pip install mediapipe opencv-python` (Apache-2.0); setup.py
--install offers it. Same outputs as the Swift helper: normalised face boxes,
and a white-on-black H.264 mask video.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from _common import SkillError, find_exe


def _libs():
    try:
        import cv2  # noqa: F401
        import mediapipe as mp  # noqa: F401
    except ImportError as exc:
        raise SkillError("Person masks on this system need MediaPipe: python3 -m pip install mediapipe opencv-python") from exc
    import cv2
    import mediapipe as mp

    return cv2, mp


def available() -> bool:
    try:
        _libs()
        return True
    except SkillError:
        return False


def faces(video: Path, samples: int) -> list[dict]:
    cv2, mp = _libs()
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    out = []
    with mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as detector:
        for i in range(max(1, samples)):
            frame_no = int(total * (i + 0.5) / max(1, samples))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ok, frame = cap.read()
            if not ok:
                continue
            result = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if not result.detections:
                continue
            best = max(result.detections, key=lambda d: d.location_data.relative_bounding_box.width)
            b = best.location_data.relative_bounding_box
            out.append({"t": round(frame_no / fps, 2), "x": round(max(0.0, b.xmin), 4), "y": round(max(0.0, b.ymin), 4),
                        "w": round(b.width, 4), "h": round(b.height, 4)})
    cap.release()
    return out


def mask(video: Path, out: Path, start: float, duration: float) -> None:
    cv2, mp = _libs()
    ffmpeg = find_exe("ffmpeg")
    if not ffmpeg:
        raise SkillError("ffmpeg is missing")
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    frames = int(round(duration * fps))
    writer = subprocess.Popen(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{width}x{height}",
         "-r", f"{fps:.3f}", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(out)],
        stdin=subprocess.PIPE,
    )
    with mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=0) as seg:
        for _ in range(frames):
            ok, frame = cap.read()
            if not ok:
                break
            result = seg.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            matte = (result.segmentation_mask * 255).clip(0, 255).astype("uint8")
            matte = cv2.GaussianBlur(matte, (5, 5), 0)
            writer.stdin.write(matte.tobytes())
    writer.stdin.close()
    writer.wait()
    cap.release()
    if writer.returncode != 0 or not out.exists():
        raise SkillError("Person mask (MediaPipe) failed to write")
