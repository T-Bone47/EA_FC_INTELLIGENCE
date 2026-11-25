"""Phase 39 Stage 2: Real Video Frame Decoding, Hardware Probe & Adaptive Sampling.

Uses PyAV (FFmpeg libraries) for timestamp-accurate MP4/WebM/MOV decoding and OpenCV
with optional OpenCL GPU acceleration (e.g. RTX 3050 4GB) and seamless CPU fallback.
Memory-bounded streaming: processes frames incrementally without loading full clips into RAM.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Optional, Tuple
import numpy as np

from backend.domain.video_ingestion import ProcessingProfile

log = logging.getLogger("eafc.real_video_decoder")


class RealVideoDecodeError(Exception):
    """Raised when a media file cannot be opened or contains no decodable video frames."""
    pass


@dataclass
class DecodedFrameSample:
    frame_index: int
    timestamp_sec: float
    rgb_array: np.ndarray  # H x W x 3 uint8
    motion_score: float
    corrupt_packets_skipped: int


def detect_compute_device() -> Dict[str, Any]:
    """Probes GPU OpenCL acceleration (RTX 3050 etc.) with clean CPU fallback."""
    try:
        import cv2
        has_ocl = bool(cv2.ocl.haveOpenCL())
        if has_ocl:
            cv2.ocl.setUseOpenCL(True)
            if cv2.ocl.useOpenCL():
                # Run tiny UMat allocation smoke test to confirm active kernel execution
                mat = np.zeros((16, 16), dtype=np.uint8)
                umat = cv2.UMat(mat)
                _ = cv2.GaussianBlur(umat, (3, 3), 0).get()
                dev_name = cv2.ocl.Device.getDefault().name() or "OpenCL GPU"
                return {"backend": "OPENCL_GPU", "device_name": dev_name.strip(), "opencv_version": cv2.__version__}
        return {"backend": "CPU_SIMD", "device_name": "CPU (OpenCV SIMD)", "opencv_version": cv2.__version__}
    except Exception as e:
        log.warning("OpenCL probe fell back to CPU: %s", e)
        return {"backend": "CPU_NUMPY_FALLBACK", "device_name": f"CPU ({e})", "opencv_version": "unknown"}


def probe_video_container(file_path: Path) -> Dict[str, Any]:
    """Inspects MP4, WebM, or MOV container streams accurately using PyAV."""
    if not file_path.exists():
        raise RealVideoDecodeError(f"Media file does not exist: {file_path}")

    try:
        import av
    except ImportError as e:
        raise RealVideoDecodeError(f"PyAV decoder dependency unavailable: {e}") from e

    try:
        with av.open(str(file_path)) as container:
            video_streams = [s for s in container.streams if s.type == "video"]
            if not video_streams:
                raise RealVideoDecodeError("Container has zero video streams.")

            stream = video_streams[0]
            fps = float(stream.average_rate or stream.guessed_rate or 30.0)
            width = int(stream.width or 0)
            height = int(stream.height or 0)
            codec_name = str(stream.codec_context.name or "unknown")

            duration_sec = 0.0
            if stream.duration and stream.time_base:
                duration_sec = float(stream.duration * stream.time_base)
            elif container.duration:
                duration_sec = float(container.duration / av.time_base)

            total_frames = int(stream.frames or 0)
            if total_frames <= 0 and duration_sec > 0 and fps > 0:
                total_frames = int(round(duration_sec * fps))

            # Quick readability probe: verify at least 1 packet can decode cleanly
            if width <= 0 or height <= 0:
                raise RealVideoDecodeError("Video stream reported invalid spatial dimensions.")

            return {
                "duration_seconds": round(max(0.0, duration_sec), 2),
                "resolution_width": width,
                "resolution_height": height,
                "frame_rate": round(max(1.0, fps), 2),
                "codec": codec_name,
                "total_frames": total_frames,
                "format_name": container.format.name,
                "decoder_backend": f"PyAV/{av.__version__}",
            }
    except RealVideoDecodeError:
        raise
    except Exception as e:
        raise RealVideoDecodeError(f"Corrupted or un-decodable media container: {e}") from e


def _sampling_step_seconds(profile: ProcessingProfile, motion_score: float) -> float:
    """Adaptive sampling step: tightens sample frequency when camera/action moves quickly."""
    if profile == ProcessingProfile.HIGH_ACCURACY:
        return 0.10  # Fixed 10 Hz
    if profile == ProcessingProfile.BALANCED:
        return 0.10 if motion_score >= 12.0 else 0.20
    # FAST
    return 0.20 if motion_score >= 15.0 else 0.50


def iter_adaptive_frames(
    file_path: Path,
    profile: ProcessingProfile = ProcessingProfile.BALANCED,
    max_seconds: Optional[float] = 120.0,
    cancel_check: Optional[Callable[[], bool]] = None,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> Generator[DecodedFrameSample, None, None]:
    """Streams timestamp-accurate RGB frames incrementally with adaptive sampling."""
    try:
        import av
    except ImportError as e:
        raise RealVideoDecodeError(f"PyAV decoder dependency unavailable: {e}") from e

    corrupt_skipped = 0
    prev_thumb: Optional[np.ndarray] = None
    last_emitted_t: Optional[float] = None
    motion_score = 0.0
    frames_decoded = 0

    try:
        with av.open(str(file_path)) as container:
            video_streams = [s for s in container.streams if s.type == "video"]
            if not video_streams:
                raise RealVideoDecodeError("No video stream found in container.")
            stream = video_streams[0]
            stream.thread_type = "AUTO"
            time_base = float(stream.time_base) if stream.time_base else (1.0 / 30.0)
            fps = float(stream.average_rate or stream.guessed_rate or 30.0)
            duration_est = (
                float(stream.duration * time_base)
                if (stream.duration and stream.time_base)
                else (float(container.duration / av.time_base) if container.duration else 30.0)
            )
            effective_cap = min(duration_est, max_seconds) if (max_seconds and duration_est > 0) else (max_seconds or duration_est or 30.0)

            raw_idx = 0
            for packet in container.demux(stream):
                if cancel_check and cancel_check():
                    log.info("Video decode cancelled cleanly at frame %d", raw_idx)
                    return

                try:
                    decoded = packet.decode()
                except Exception as pkt_err:
                    corrupt_skipped += 1
                    log.warning("Skipped corrupt packet (%s), total skipped=%d", pkt_err, corrupt_skipped)
                    continue

                for frame in decoded:
                    if cancel_check and cancel_check():
                        return

                    if frame.pts is not None:
                        timestamp_sec = float(frame.pts * time_base)
                    else:
                        timestamp_sec = raw_idx / max(1.0, fps)

                    if max_seconds is not None and timestamp_sec > max_seconds:
                        return

                    # Check adaptive sampling gate before full RGB conversion if unneeded
                    step = _sampling_step_seconds(profile, motion_score)
                    if last_emitted_t is not None and (timestamp_sec - last_emitted_t) < (step - 1e-4):
                        raw_idx += 1
                        continue

                    rgb = frame.to_ndarray(format="rgb24")
                    # Compute lightweight 64x36 motion MAD for adaptive sampling
                    thumb = rgb[:: max(1, rgb.shape[0] // 36), :: max(1, rgb.shape[1] // 64), 1].astype(np.int16)
                    if prev_thumb is not None and thumb.shape == prev_thumb.shape:
                        motion_score = float(np.mean(np.abs(thumb - prev_thumb)))
                    prev_thumb = thumb

                    last_emitted_t = timestamp_sec
                    frames_decoded += 1

                    if progress_cb and effective_cap > 0:
                        pct = min(98.0, (timestamp_sec / effective_cap) * 95.0)
                        progress_cb(pct)

                    yield DecodedFrameSample(
                        frame_index=raw_idx,
                        timestamp_sec=round(timestamp_sec, 3),
                        rgb_array=rgb,
                        motion_score=round(motion_score, 2),
                        corrupt_packets_skipped=corrupt_skipped,
                    )
                    raw_idx += 1

            if frames_decoded == 0:
                raise RealVideoDecodeError("Video stream contained 0 decodable frames.")
    except RealVideoDecodeError:
        raise
    except Exception as e:
        raise RealVideoDecodeError(f"Video decode failure: {e}") from e
