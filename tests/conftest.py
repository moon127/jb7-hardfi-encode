from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import Generator

import pytest


def create_test_wav(path: Path, sample_rate: int = 44100, channels: int = 2, duration: float = 0.05) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(sample_rate * duration)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for _ in range(n_samples):
            wf.writeframes(struct.pack("<h", 0))
    return path


@pytest.fixture
def tmp_audio_dir(tmp_path: Path) -> Path:
    return tmp_path / "music"


@pytest.fixture
def flat_album_dir(tmp_audio_dir: Path) -> Path:
    album_dir = tmp_audio_dir / "Test Artist" / "Test Album"
    create_test_wav(album_dir / "01 Track 1.wav")
    create_test_wav(album_dir / "02 Track 2.wav")
    create_test_wav(album_dir / "03 Track 3.wav")
    return tmp_audio_dir


@pytest.fixture
def hardfi_dir(tmp_audio_dir: Path) -> Path:
    hardfi = tmp_audio_dir / "hardfi"
    artist_album = hardfi / "Test Artist" / "Test Album"
    create_test_wav(artist_album / "01 Track 1.wav")
    create_test_wav(artist_album / "02 Track 2.wav")

    other = hardfi / "Other Artist" / "Greatest Hits"
    create_test_wav(other / "01 Song A.flac")
    create_test_wav(other / "02 Song B.flac")
    return tmp_audio_dir


@pytest.fixture
def mixed_codec_dir(tmp_audio_dir: Path) -> Path:
    album = tmp_audio_dir / "Various" / "Compilation"
    create_test_wav(album / "track1.wav")
    create_test_wav(album / "track2.flac")
    (album / "track3.mp3").write_text("fake mp3")
    (album / "track4.m4a").write_text("fake m4a")
    (album / "notes.txt").write_text("not an audio file")
    return tmp_audio_dir


@pytest.fixture
def empty_audio_dir(tmp_audio_dir: Path) -> Path:
    tmp_audio_dir.mkdir(parents=True, exist_ok=True)
    (tmp_audio_dir / "readme.txt").write_text("no audio here")
    return tmp_audio_dir
