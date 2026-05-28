from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List


class CodecType(Enum):
    WAV = "WAV"
    FLAC = "FLAC"
    ALAC = "ALAC"
    AAC = "AAC"
    MP3 = "MP3"
    UNKNOWN = "Unknown"

    @classmethod
    def from_extension(cls, ext: str) -> CodecType:
        mapping = {
            ".wav": cls.WAV,
            ".wave": cls.WAV,
            ".flac": cls.FLAC,
            ".m4a": cls.ALAC,
            ".aac": cls.AAC,
            ".mp4": cls.AAC,
            ".mp3": cls.MP3,
        }
        return mapping.get(ext.lower(), cls.UNKNOWN)


LOSSLESS_CODECS = {CodecType.WAV, CodecType.FLAC, CodecType.ALAC}
LOSSY_CODECS = {CodecType.AAC, CodecType.MP3}
SUPPORTED_EXTENSIONS = {".wav", ".wave", ".flac", ".m4a", ".aac", ".mp4", ".mp3"}


def is_lossless(codec: CodecType) -> bool:
    return codec in LOSSLESS_CODECS


def is_lossy(codec: CodecType) -> bool:
    return codec in LOSSY_CODECS


@dataclass
class AudioFile:
    path: str
    relative_path: str
    codec: CodecType
    bitrate: int
    sample_rate: int
    channels: int
    bit_depth: int = 0


@dataclass
class ScanResult:
    total_files: int = 0
    by_codec: Dict[CodecType, List[AudioFile]] = field(default_factory=dict)
    files: List[AudioFile] = field(default_factory=list)
    search_root: str = ""


@dataclass
class ConversionPlan:
    target_codec: CodecType
    bitrate: int | None
    delete_originals: bool
    files_to_convert: List[AudioFile]
