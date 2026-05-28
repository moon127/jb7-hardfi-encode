from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Callable, Optional

from hardfi_encode.models import (
    LOSSLESS_CODECS,
    AudioFile,
    CodecType,
    ConversionPlan,
    is_lossless,
)

logger = logging.getLogger(__name__)

CODEC_TO_FFMPEG = {
    CodecType.WAV: "pcm_s16le",
    CodecType.FLAC: "flac",
    CodecType.AAC: "aac",
    CodecType.MP3: "libmp3lame",
}

CODEC_TO_EXT = {
    CodecType.WAV: ".wav",
    CodecType.FLAC: ".flac",
    CodecType.AAC: ".m4a",
    CodecType.MP3: ".mp3",
}


def build_output_path(input_rel: str, search_root: Path, target_codec: CodecType, target_dir: Path | None = None) -> Path:
    rel = Path(input_rel)
    new_ext = CODEC_TO_EXT[target_codec]
    output_rel = rel.with_suffix(new_ext)
    base = target_dir if target_dir else search_root
    return base / output_rel


def convert_single_file(
    input_path: Path,
    output_path: Path,
    target_codec: CodecType,
    bitrate: Optional[int] = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["ffmpeg", "-y", "-i", str(input_path)]
    cmd.extend(["-c:a", CODEC_TO_FFMPEG[target_codec]])

    if target_codec in (CodecType.AAC, CodecType.MP3) and bitrate:
        cmd.extend(["-b:a", f"{bitrate // 1000}k"])

    if target_codec == CodecType.AAC:
        cmd.extend(["-movflags", "+faststart"])

    cmd.append(str(output_path))

    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (return code {result.returncode}): {result.stderr}")


def verify_ffmpeg() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def run_conversion(
    plan: ConversionPlan,
    search_root: str,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    target_dir: str | None = None,
) -> dict:
    results: dict = {"converted": 0, "skipped": 0, "errors": 0, "details": [], "cancelled": False}
    search_path = Path(search_root)
    target_path = Path(target_dir) if target_dir else None
    total = len(plan.files_to_convert)

    if cancel_check and cancel_check():
        results["cancelled"] = True
        return results

    for i, af in enumerate(plan.files_to_convert):
        if cancel_check and cancel_check():
            results["cancelled"] = True
            if progress_callback:
                progress_callback(int((i + 1) / total * 100), "Cancelling...")
            break
        try:
            input_path = Path(af.path)
            output_path = build_output_path(af.relative_path, search_path, plan.target_codec, target_dir=target_path)

            if output_path.exists():
                logger.info("Skipping %s — output already exists", output_path)
                results["skipped"] += 1
                results["details"].append((af.relative_path, "skipped", "output exists"))
                if progress_callback:
                    progress_callback(int((i + 1) / total * 100), f"Skipped: {af.relative_path}")
                continue

            convert_single_file(input_path, output_path, plan.target_codec, plan.bitrate)

            if plan.delete_originals:
                os.remove(input_path)
                parent = input_path.parent
                try:
                    while parent != search_path and not any(parent.iterdir()):
                        parent.rmdir()
                        parent = parent.parent
                except OSError:
                    pass

            results["converted"] += 1
            results["details"].append((af.relative_path, "converted", str(output_path)))
            if progress_callback:
                progress_callback(int((i + 1) / total * 100), f"Converted: {af.relative_path}")

        except Exception as e:
            logger.error("Failed to convert %s: %s", af.path, e)
            results["errors"] += 1
            results["details"].append((af.relative_path, "error", str(e)))
            if progress_callback:
                progress_callback(int((i + 1) / total * 100), f"Error: {af.relative_path}")

    return results


def plan_conversion(
    files: list[AudioFile],
    target_codec: CodecType,
    bitrate: Optional[int] = None,
    delete_originals: bool = False,
) -> ConversionPlan:
    files_to_convert = [f for f in files if is_lossless(f.codec) and f.codec != target_codec]
    return ConversionPlan(
        target_codec=target_codec,
        bitrate=bitrate,
        delete_originals=delete_originals,
        files_to_convert=files_to_convert,
    )
