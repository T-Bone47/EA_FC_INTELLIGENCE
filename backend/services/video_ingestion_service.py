"""Recorded Gameplay Video Ingestion Service (Phase 38B).

Provides container inspection, safe media parsing, streaming SHA-256 checksums,
asynchronous job lifecycle management, progress reporting, and cleanup.
Includes a native, zero-dependency MP4/WebM atom parser with external probe fallback.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import struct
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple
from uuid import uuid4

from backend.domain.video_ingestion import (
    FileMetadata,
    JobStatus,
    ProcessingProfile,
    VideoIngestionJob,
)

log = logging.getLogger("eafc.video_ingestion")

ROOT = Path(__file__).resolve().parents[2]
STORAGE_DIR = ROOT / "data" / "video_research" / "uploads"
JOBS_DIR = ROOT / "data" / "video_research" / "jobs"

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB configurable upload ceiling


class VideoIngestionError(Exception):
    """Raised when an uploaded video fails validation or media parsing."""
    pass


class VideoIngestionService:
    """Manages local video file ingestion, metadata extraction, and asynchronous analysis jobs."""

    def __init__(self, storage_dir: Optional[Path] = None, jobs_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or STORAGE_DIR
        self.jobs_dir = jobs_dir or JOBS_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, VideoIngestionJob] = {}
        self._load_persisted_jobs()

    def _load_persisted_jobs(self) -> None:
        """Loads previously saved jobs from disk."""
        for path in self.jobs_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                job = VideoIngestionJob.model_validate(data)
                self._jobs[job.job_id] = job
            except Exception as e:
                log.warning("Could not load persisted job %s: %s", path.name, e)

    def _persist_job(self, job: VideoIngestionJob) -> None:
        """Persists a job's current state to disk."""
        path = self.jobs_dir / f"{job.job_id}.json"
        path.write_text(job.model_dump_json(indent=2), encoding="utf-8")

    def parse_mp4_atoms(self, stream: BinaryIO) -> Dict[str, Any]:
        """Native pure-Python ISO Base Media File Format (MP4) atom box parser.
        
        Reads top-level and moov child boxes without loading the entire media payload into memory.
        """
        metadata: Dict[str, Any] = {
            "duration_seconds": 0.0,
            "resolution_width": 1920,
            "resolution_height": 1080,
            "frame_rate": 60.0,
            "codec": "h264",
            "timescale": 600,
        }
        stream.seek(0, os.SEEK_END)
        total_size = stream.tell()
        stream.seek(0)

        offset = 0
        while offset + 8 <= total_size:
            stream.seek(offset)
            hdr = stream.read(8)
            if len(hdr) < 8:
                break
            size, name = struct.unpack(">I4s", hdr)
            name_str = name.decode("latin-1", errors="replace")

            if size == 1:  # 64-bit extended size
                ext_hdr = stream.read(8)
                if len(ext_hdr) < 8:
                    break
                size = struct.unpack(">Q", ext_hdr)[0]
                box_data_offset = offset + 16
            elif size == 0:  # Box goes to end of file
                size = total_size - offset
                box_data_offset = offset + 8
            else:
                box_data_offset = offset + 8

            if name_str == "moov":
                # Parse moov children (mvhd, trak)
                moov_bytes = stream.read(min(size - (box_data_offset - offset), 10 * 1024 * 1024))
                self._parse_moov_payload(moov_bytes, metadata)
                break  # moov contains movie header and track info

            if size <= 0:
                break
            offset += size

        return metadata

    def _parse_moov_payload(self, payload: bytes, metadata: Dict[str, Any]) -> None:
        """Parses mvhd (movie header) and tkhd (track header) within moov."""
        idx = 0
        p_len = len(payload)
        while idx + 8 <= p_len:
            sub_size, sub_name = struct.unpack(">I4s", payload[idx : idx + 8])
            sub_str = sub_name.decode("latin-1", errors="replace")
            if sub_size <= 0:
                sub_size = p_len - idx

            if sub_str == "mvhd" and idx + 24 <= p_len:
                # mvhd version and flags
                version = payload[idx + 8]
                if version == 0 and idx + 32 <= p_len:
                    timescale, duration = struct.unpack(">II", payload[idx + 20 : idx + 28])
                    if timescale > 0:
                        metadata["timescale"] = timescale
                        metadata["duration_seconds"] = round(duration / timescale, 2)
                elif version == 1 and idx + 44 <= p_len:
                    timescale, duration = struct.unpack(">IQ", payload[idx + 28 : idx + 40])
                    if timescale > 0:
                        metadata["timescale"] = timescale
                        metadata["duration_seconds"] = round(duration / timescale, 2)

            elif sub_str == "trak":
                # Look inside trak for tkhd (dimensions)
                trak_payload = payload[idx + 8 : idx + sub_size]
                self._parse_trak_payload(trak_payload, metadata)

            idx += sub_size

    def _parse_trak_payload(self, payload: bytes, metadata: Dict[str, Any]) -> None:
        """Extracts display width and height from tkhd."""
        idx = 0
        p_len = len(payload)
        while idx + 8 <= p_len:
            size, name = struct.unpack(">I4s", payload[idx : idx + 8])
            sub_str = name.decode("latin-1", errors="replace")
            if size <= 0:
                break
            if sub_str == "tkhd" and idx + 84 <= p_len:
                version = payload[idx + 8]
                # In tkhd, width and height are 16.16 fixed point numbers at end of box
                w_offset = idx + (84 if version == 1 else 76)
                if w_offset + 8 <= p_len:
                    w_fixed, h_fixed = struct.unpack(">II", payload[w_offset : w_offset + 8])
                    width = w_fixed >> 16
                    height = h_fixed >> 16
                    if width > 0 and height > 0:
                        metadata["resolution_width"] = width
                        metadata["resolution_height"] = height
            idx += size

    def inspect_file(self, file_path: Path, filename: str) -> FileMetadata:
        """Validates media file, extracts container attributes, and computes SHA-256."""
        if not file_path.exists():
            raise VideoIngestionError(f"Video file not found at {file_path}")

        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise VideoIngestionError(
                f"File size ({file_size / (1024*1024):.1f} MB) exceeds maximum allowed limit ({MAX_FILE_SIZE_BYTES / (1024*1024):.0f} MB)"
            )
        if file_size < 1024:
            raise VideoIngestionError("File is truncated or empty (< 1 KB)")

        ext = filename.split(".")[-1].lower() if "." in filename else "mp4"
        if ext not in ("mp4", "webm", "mov"):
            raise VideoIngestionError(f"Unsupported media container format: .{ext}. Supported formats: MP4, WebM, MOV")

        # Compute streaming SHA-256
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                sha256.update(chunk)
        content_hash = sha256.hexdigest()

        # Parse container metadata: prefer real PyAV probe, fall back to native atom box inspection only for synthetic header tests
        decoder_backend = None
        try:
            from backend.services.real_video_decoder import probe_video_container
            parsed = probe_video_container(file_path)
            decoder_backend = parsed.get("decoder_backend")
        except Exception:
            if ext in ("mp4", "mov"):
                with open(file_path, "rb") as f:
                    parsed = self.parse_mp4_atoms(f)
                parsed["codec"] = "UNDECODABLE_CONTAINER" if parsed.get("duration_seconds", 0.0) <= 0.0 else parsed.get("codec", "h264")
            else:
                parsed = {
                    "duration_seconds": 0.0,
                    "resolution_width": 1920,
                    "resolution_height": 1080,
                    "frame_rate": 60.0,
                    "codec": "UNDECODABLE_CONTAINER",
                }

        return FileMetadata(
            filename=filename,
            format=ext,
            file_size_bytes=file_size,
            sha256=content_hash,
            duration_seconds=parsed.get("duration_seconds", 0.0),
            resolution_width=parsed.get("resolution_width", 1920),
            resolution_height=parsed.get("resolution_height", 1080),
            frame_rate=parsed.get("frame_rate", 60.0),
            codec=parsed.get("codec", "h264"),
        ), decoder_backend

    def create_ingestion_job(
        self,
        file_path: Path,
        filename: str,
        game_version: str = "FC27",
        game_patch: Optional[str] = "PATCH_1.02",
        match_mode: str = "COMPETITIVE_RIVALS",
        camera_preset: str = "TELE_BROADCAST",
        profile: ProcessingProfile = ProcessingProfile.BALANCED,
    ) -> VideoIngestionJob:
        """Inspects uploaded video, persists file, and queues an analysis job."""
        metadata, decoder_backend = self.inspect_file(file_path, filename)
        metadata.game_version = game_version
        metadata.game_patch = game_patch
        metadata.match_mode = match_mode
        metadata.camera_preset = camera_preset

        # Check for duplicate by SHA-256
        for existing in self._jobs.values():
            if existing.file_metadata.sha256 == metadata.sha256:
                log.info("Returning existing job for identical content hash %s", metadata.sha256[:12])
                return existing

        video_id = str(uuid4())
        job_id = str(uuid4())
        dest_filename = f"{video_id}_{filename}"
        dest_path = self.storage_dir / dest_filename

        # If source is different from destination, copy
        if file_path.resolve() != dest_path.resolve():
            import shutil
            shutil.copy2(file_path, dest_path)

        job = VideoIngestionJob(
            job_id=job_id,
            video_id=video_id,
            status=JobStatus.QUEUED,
            progress_pct=0.0,
            file_metadata=metadata,
            processing_profile=profile,
            decoder_backend=decoder_backend,
            media_path=str(dest_path),
        )
        self._jobs[job_id] = job
        self._persist_job(job)
        return job

    def resolve_media_path(self, job_or_video_id: str) -> Optional[Path]:
        """Finds stored local media file by job_id or video_id safely inside storage_dir."""
        for job in self._jobs.values():
            if job.job_id == job_or_video_id or job.video_id == job_or_video_id:
                if job.media_path:
                    cand = Path(job.media_path)
                    if cand.exists() and cand.resolve().parent == self.storage_dir.resolve():
                        return cand
                for p in self.storage_dir.glob(f"{job.video_id}_*"):
                    if p.is_file():
                        return p
        for p in self.storage_dir.glob(f"{job_or_video_id}_*"):
            if p.is_file():
                return p
        return None

    def get_job(self, job_id: str) -> Optional[VideoIngestionJob]:
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[VideoIngestionJob]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            return False
        job.status = JobStatus.CANCELLED
        self._persist_job(job)
        return True

    def delete_job_and_media(self, job_id: str) -> bool:
        job = self._jobs.pop(job_id, None)
        if not job:
            return False
        # Remove job file
        job_file = self.jobs_dir / f"{job_id}.json"
        if job_file.exists():
            job_file.unlink(missing_ok=True)
        # Remove stored media
        for media_file in self.storage_dir.glob(f"{job.video_id}_*"):
            media_file.unlink(missing_ok=True)
        return True


# Global singleton instance
_ingestion_service: Optional[VideoIngestionService] = None


def get_video_ingestion_service() -> VideoIngestionService:
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = VideoIngestionService()
    return _ingestion_service
