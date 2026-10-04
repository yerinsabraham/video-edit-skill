#!/usr/bin/env python3
"""Face boxes and person masks with MediaPipe, for Linux and Windows.

Used by vision.py when Apple Vision is not available (or VIDEO_EDIT_VISION=mediapipe).
Needs `python3 -m pip install mediapipe opencv-python-headless` (Apache-2.0);
setup.py --install offers it. Current MediaPipe releases only ship the Tasks
API, which loads small .tflite models; they are downloaded once into
~/.cache/video-edit/models/mediapipe. Older releases with the legacy
`solutions` API are used directly. Same outputs as the Swift helper:
normalised face boxes, and a white-on-black H.264 mask video.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from _common import SkillError, download, find_exe, tool_home

MODELS = {
    "face": "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
    "selfie": "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite",
}


def _libs():
    try:
        import cv2
        import mediapipe as mp
    except ImportError as exc:
        raise SkillError("Person masks on this system need MediaPipe: python3 -m pip install mediapipe opencv-python-headless") from exc
    return cv2, mp


def _model(name: str) -> str:
    path = tool_home() / "models" / "mediapipe" / Path(MODELS[name]).name
    if not path.exists():
        download(MODELS[name], path, timeout=120)
    return str(path)


def _legacy(mp) -> bool:
    return hasattr(mp, "solutions") and hasattr(getattr(mp, "solutions"), "selfie_segmentation")


def available() -> bool:
    try:
        _libs()
        return True
    except SkillError:
        return False


class _FaceDetector:
    def __init__(self, mp):
        self.mp = mp
        if _legacy(mp):
            self.impl = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
            self.legacy = True
        else:
            from mediapipe.tasks import python as mpt
            from mediapipe.tasks.python import vision as mpv

            options = mpv.FaceDetectorOptions(base_options=mpt.BaseOptions(model_asset_path=_model("face")), min_detection_confidence=0.5)
            self.impl = mpv.FaceDetector.create_from_options(options)
            self.legacy = False

    def detect(self, rgb) -> tuple[float, float, float, float] | None:
        h, w = rgb.shape[:2]
        if self.legacy:
            result = self.impl.process(rgb)
            if not result.detections:
                return None
            b = max(result.detections, key=lambda d: d.location_data.relative_bounding_box.width).location_data.relative_bounding_box
            return max(0.0, b.xmin), max(0.0, b.ymin), b.width, b.height
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        result = self.impl.detect(image)
        if not result.detections:
            return None
        b = max(result.detections, key=lambda d: d.bounding_box.width).bounding_box
        return max(0.0, b.origin_x / w), max(0.0, b.origin_y / h), b.width / w, b.height / h

    def close(self) -> None:
        self.impl.close()


class _Segmenter:
    def __init__(self, mp):
        self.mp = mp
        if _legacy(mp):
            self.impl = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=0)
            self.legacy = True
        else:
            from mediapipe.tasks import python as mpt
            from mediapipe.tasks.python import vision as mpv

            options = mpv.ImageSegmenterOptions(base_options=mpt.BaseOptions(model_asset_path=_model("selfie")), output_confidence_masks=True)
            self.impl = mpv.ImageSegmenter.create_from_options(options)
            self.legacy = False

    def matte(self, rgb):
        if self.legacy:
            return self.impl.process(rgb).segmentation_mask
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        masks = self.impl.segment(image).confidence_masks
        return masks[-1].numpy_view()  # the selfie model's last mask is the person

    def close(self) -> None:
        self.impl.close()


def faces(video: Path, samples: int) -> list[dict]:
    cv2, mp = _libs()
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    detector = _FaceDetector(mp)
    out = []
    try:
        for i in range(max(1, samples)):
            frame_no = int(total * (i + 0.5) / max(1, samples))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ok, frame = cap.read()
            if not ok:
                continue
            box = detector.detect(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if box:
                x, y, w, h = box
                out.append({"t": round(frame_no / fps, 2), "x": round(x, 4), "y": round(y, 4), "w": round(w, 4), "h": round(h, 4)})
    finally:
        detector.close()
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
    segmenter = _Segmenter(mp)
    try:
        for _ in range(frames):
            ok, frame = cap.read()
            if not ok:
                break
            matte = segmenter.matte(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            matte = (matte * 255).clip(0, 255).astype("uint8")
            if matte.shape[:2] != (height, width):
                matte = cv2.resize(matte, (width, height))
            writer.stdin.write(cv2.GaussianBlur(matte, (5, 5), 0).tobytes())
    finally:
        segmenter.close()
        writer.stdin.close()
        writer.wait()
        cap.release()
    if writer.returncode != 0 or not out.exists():
        raise SkillError("Person mask (MediaPipe) failed to write")
