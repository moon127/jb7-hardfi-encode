from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import mutagen

from hardfi_encode.models import (
    SUPPORTED_EXTENSIONS,
    AudioFile,
    CodecType,
    ScanResult,
)


def _detect_codec(mutagen_file: mutagen.FileType, extension: str) -> CodecType:
    ext_codec = CodecType.from_extension(extension)
    if ext_codec == CodecType.ALAC:
        codec_name = getattr(mutagen_file.info, "codec", "").lower()
        if "alac" in codec_name:
            return CodecType.ALAC
        if "aac" in codec_name or "mp4a" in codec_name:
            return CodecType.AAC
        return CodecType.AAC
    return ext_codec


def get_audio_info(file_path: Path) -> AudioFile:
    try:
        mf = mutagen.File(str(file_path))
    except Exception:
        mf = None
    if mf is None:
        return AudioFile(
            path=str(file_path),
            relative_path="",
            codec=CodecType.UNKNOWN,
            bitrate=0,
            sample_rate=0,
            channels=0,
        )
    codec = _detect_codec(mf, file_path.suffix)
    info = mf.info
    bitrate = getattr(info, "bitrate", 0) or 0
    sample_rate = getattr(info, "sample_rate", 0) or 0
    channels = getattr(info, "channels", 0) or 0
    bit_depth = 0
    if codec == CodecType.WAV:
        bit_depth = getattr(info, "bit_depth", 16) or 16
    elif codec == CodecType.FLAC:
        bit_depth = getattr(info, "bits_per_sample", 16) or 16

    return AudioFile(
        path=str(file_path),
        relative_path="",
        codec=codec,
        bitrate=bitrate,
        sample_rate=sample_rate,
        channels=channels,
        bit_depth=bit_depth,
    )


def find_search_root(root_path: Path) -> Path:
    hardfi_path = root_path / "hardfi"
    if hardfi_path.is_dir():
        return hardfi_path
    return root_path


def scan_directory(root_path: Path, progress_callback=None) -> ScanResult:
    search_root = find_search_root(root_path)
    result = ScanResult(search_root=str(search_root))
    audio_files: List[AudioFile] = []

    all_files = sorted(search_root.rglob("*"))
    total = len(all_files)

    for idx, file_path in enumerate(all_files):
        if progress_callback and total > 0:
            progress_callback(int((idx + 1) / total * 100))

        if not file_path.is_file():
            continue
        ext = file_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        try:
            info = get_audio_info(file_path)
        except Exception:
            info = AudioFile(
                path=str(file_path),
                relative_path="",
                codec=CodecType.UNKNOWN,
                bitrate=0,
                sample_rate=0,
                channels=0,
            )

        info.relative_path = str(file_path.relative_to(search_root))
        audio_files.append(info)

    result.files = audio_files
    result.total_files = len(audio_files)
    for f in audio_files:
        result.by_codec.setdefault(f.codec, []).append(f)

    return result


def get_bitrate_range(files: List[AudioFile]) -> str:
    if not files:
        return ""
    bitrates = [f.bitrate for f in files if f.bitrate > 0]
    if not bitrates:
        return "lossless"
    min_b = min(bitrates) // 1000
    max_b = max(bitrates) // 1000
    if min_b == max_b:
        return f"{min_b}k"
    return f"{min_b}-{max_b}k"


def get_summary_lines(result: ScanResult) -> List[str]:
    lines = [f"Total audio files found: {result.total_files}", ""]
    header = f"{'Codec':<8} {'Count':<8} {'Bitrate':<16} {'Compressible':<12}"
    lines.append(header)
    lines.append("-" * len(header))

    from hardfi_encode.models import is_lossless

    for codec in CodecType:
        files = result.by_codec.get(codec, [])
        if not files:
            continue
        br = get_bitrate_range(files)
        comp = "Yes" if is_lossless(codec) else "No"
        lines.append(f"{codec.value:<8} {len(files):<8} {br:<16} {comp:<12}")

    return lines
