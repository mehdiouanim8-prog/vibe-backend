"""
Element backend liveness verification.

Uses DeepFace's built-in face anti-spoofing model on multiple sampled
video frames. This is a passive anti-spoofing check; it is NOT a
regulated KYC provider and should not be represented as one.

The caller should still require human/admin KYC review after this check.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import cv2
from deepface import DeepFace


class LivenessVerificationError(Exception):
    """Raised when a liveness submission cannot be verified safely."""


@dataclass(frozen=True)
class LivenessResult:
    passed: bool
    frames_checked: int
    real_frames: int
    duration_seconds: float
    reason: str


MIN_DURATION_SECONDS = 3.0
MAX_DURATION_SECONDS = 35.0
MIN_FRAMES_TO_CHECK = 5
MAX_FRAMES_TO_CHECK = 12
REAL_FRAME_RATIO = 0.75


def _sample_frame_indexes(frame_count: int, fps: float) -> list[int]:
    if frame_count <= 0 or fps <= 0:
        raise LivenessVerificationError("The uploaded video has no readable frames.")

    duration = frame_count / fps
    if duration < MIN_DURATION_SECONDS:
        raise LivenessVerificationError(
            f"Liveness video is too short. Record at least {MIN_DURATION_SECONDS:.0f} seconds."
        )

    if duration > MAX_DURATION_SECONDS:
        raise LivenessVerificationError(
            f"Liveness video is too long. Maximum is {MAX_DURATION_SECONDS:.0f} seconds."
        )

    count = min(MAX_FRAMES_TO_CHECK, max(MIN_FRAMES_TO_CHECK, int(duration * 2)))
    count = min(count, frame_count)

    # Evenly distributed samples reduce the chance that only one easy frame
    # is evaluated.
    return [
        min(frame_count - 1, int(i * (frame_count - 1) / max(1, count - 1)))
        for i in range(count)
    ]


def verify_liveness_video(video_path: str | Path) -> LivenessResult:
    path = Path(video_path)

    if not path.is_file():
        raise LivenessVerificationError("The liveness video could not be found.")

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise LivenessVerificationError("The liveness video could not be decoded.")

    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))

        indexes = _sample_frame_indexes(frame_count, fps)
        real_frames = 0
        checked = 0

        for frame_index in indexes:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()

            if not ok or frame is None:
                continue

            checked += 1

            try:
                faces = DeepFace.extract_faces(
                    img_path=frame,
                    detector_backend="opencv",
                    enforce_detection=True,
                    align=True,
                    anti_spoofing=True,
                    max_faces=2,
                )
            except Exception:
                # A frame that cannot be safely verified does not count as real.
                continue

            # Exactly one face must be present. Multiple faces are rejected
            # because the server must know which person is being verified.
            if len(faces) != 1:
                continue

            face = faces[0]
            if bool(face.get("is_real", False)):
                real_frames += 1

        duration = frame_count / fps

        if checked < MIN_FRAMES_TO_CHECK:
            return LivenessResult(
                passed=False,
                frames_checked=checked,
                real_frames=real_frames,
                duration_seconds=duration,
                reason="Not enough readable frames were available for verification.",
            )

        ratio = real_frames / checked
        passed = ratio >= REAL_FRAME_RATIO

        return LivenessResult(
            passed=passed,
            frames_checked=checked,
            real_frames=real_frames,
            duration_seconds=duration,
            reason=(
                "Liveness verification passed."
                if passed
                else "The liveness check could not verify a live person."
            ),
        )
    finally:
        capture.release()
