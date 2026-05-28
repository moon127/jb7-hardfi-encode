from __future__ import annotations

from pathlib import Path

import pytest

from hardfi_encode.models import CodecType
from hardfi_encode.scanner import (
    _detect_codec,
    find_search_root,
    get_audio_info,
    get_bitrate_range,
    get_summary_lines,
    scan_directory,
)


class TestFindSearchRoot:
    def test_hardfi_subdir_found(self, hardfi_dir: Path):
        root = find_search_root(hardfi_dir)
        assert root == hardfi_dir / "hardfi"

    def test_no_hardfi_subdir(self, flat_album_dir: Path):
        root = find_search_root(flat_album_dir)
        assert root == flat_album_dir

    def test_hardfi_is_file_not_dir(self, tmp_path: Path):
        (tmp_path / "hardfi").write_text("not a dir")
        root = find_search_root(tmp_path)
        assert root == tmp_path


class TestGetAudioInfo:
    def test_wav_file(self, tmp_path: Path):
        from tests.conftest import create_test_wav
        wav_path = create_test_wav(tmp_path / "test.wav")
        info = get_audio_info(wav_path)
        assert info.codec == CodecType.WAV
        assert info.bitrate > 0
        assert info.sample_rate == 44100
        assert info.channels == 2
        assert info.bit_depth == 16

    def test_unknown_format(self, tmp_path: Path):
        f = tmp_path / "test.xyz"
        f.write_text("fake data")
        info = get_audio_info(f)
        assert info.codec == CodecType.UNKNOWN
        assert info.bitrate == 0

    def test_missing_file(self, tmp_path: Path):
        info = get_audio_info(tmp_path / "nonexistent.wav")
        assert info.codec == CodecType.UNKNOWN


class TestDetectCodec:
    def test_wav_detected(self):
        class FakeInfo:
            codec = ""
            bitrate = 1411200
            sample_rate = 44100
            channels = 2

        class FakeMutagen:
            info = FakeInfo()

        assert _detect_codec(FakeMutagen(), ".wav") == CodecType.WAV

    def test_flac_detected(self):
        class FakeInfo:
            codec = ""
            bitrate = 500000
            sample_rate = 44100
            channels = 2

        class FakeMutagen:
            info = FakeInfo()

        assert _detect_codec(FakeMutagen(), ".flac") == CodecType.FLAC

    def test_mp3_detected(self):
        class FakeInfo:
            codec = ""
            bitrate = 192000
            sample_rate = 44100
            channels = 2

        class FakeMutagen:
            info = FakeInfo()

        assert _detect_codec(FakeMutagen(), ".mp3") == CodecType.MP3

    def test_alac_m4a_detected(self):
        class FakeInfo:
            codec = "alac"
            bitrate = 0
            sample_rate = 44100
            channels = 2

        class FakeMutagen:
            info = FakeInfo()

        assert _detect_codec(FakeMutagen(), ".m4a") == CodecType.ALAC

    def test_aac_m4a_detected(self):
        class FakeInfo:
            codec = "mp4a"
            bitrate = 256000
            sample_rate = 44100
            channels = 2

        class FakeMutagen:
            info = FakeInfo()

        assert _detect_codec(FakeMutagen(), ".m4a") == CodecType.AAC


class TestScanDirectory:
    def test_flat_album_structure(self, flat_album_dir: Path):
        result = scan_directory(flat_album_dir)
        assert result.total_files == 3
        assert len(result.by_codec.get(CodecType.WAV, [])) == 3
        assert result.search_root == str(flat_album_dir)

    def test_hardfi_structure(self, hardfi_dir: Path, mocker):
        mock_file = mocker.patch("hardfi_encode.scanner.mutagen.File")
        wav_info = type("Info", (), {"bitrate": 1411200, "sample_rate": 44100, "channels": 2, "bit_depth": 16})()
        flac_info = type("Info", (), {"bitrate": 500000, "sample_rate": 44100, "channels": 2, "bits_per_sample": 16})()

        def side_effect(path):
            if path.endswith(".wav"):
                return type("WAV", (), {"info": wav_info})()
            elif path.endswith(".flac"):
                return type("FLAC", (), {"info": flac_info})()
            return None

        mock_file.side_effect = side_effect
        result = scan_directory(hardfi_dir)
        assert result.total_files == 4
        wavs = result.by_codec.get(CodecType.WAV, [])
        flacs = result.by_codec.get(CodecType.FLAC, [])
        assert len(wavs) == 2
        assert len(flacs) == 2
        assert result.search_root.endswith("hardfi")
        for f in result.files:
            assert "hardfi" not in f.relative_path

    def test_relative_paths(self, flat_album_dir: Path):
        result = scan_directory(flat_album_dir)
        for f in result.files:
            rel = Path(f.relative_path)
            assert not rel.is_absolute()
            assert rel.parts[0] == "Test Artist"

    def test_empty_directory(self, empty_audio_dir: Path):
        result = scan_directory(empty_audio_dir)
        assert result.total_files == 0

    def test_mixed_codec_directory(self, mixed_codec_dir: Path, mocker):
        mocker.patch(
            "hardfi_encode.scanner.get_audio_info",
            side_effect=lambda p: type(
                "AudioFile",
                (),
                {
                    "path": str(p),
                    "relative_path": "",
                    "codec": CodecType.WAV if p.suffix == ".wav"
                    else CodecType.FLAC if p.suffix == ".flac"
                    else CodecType.MP3 if p.suffix == ".mp3"
                    else CodecType.AAC,
                    "bitrate": 1411000 if p.suffix == ".wav" else 0,
                    "sample_rate": 44100,
                    "channels": 2,
                },
            )(),
        )
        result = scan_directory(mixed_codec_dir)
        assert result.total_files == 4
        assert ".txt" not in [Path(f.path).suffix for f in result.files]

    def test_get_summary_lines(self, flat_album_dir: Path):
        result = scan_directory(flat_album_dir)
        lines = get_summary_lines(result)
        assert any("Total audio files found: 3" in l for l in lines)
        assert any("WAV" in l for l in lines)
        assert any("Yes" in l for l in lines)

    def test_scan_with_progress(self, flat_album_dir: Path):
        progress_values = []

        def cb(pct):
            progress_values.append(pct)

        result = scan_directory(flat_album_dir, progress_callback=cb)
        assert result.total_files == 3
        assert len(progress_values) > 0
        assert all(0 <= v <= 100 for v in progress_values)


class TestGetBitrateRange:
    def test_single_bitrate(self):
        from hardfi_encode.models import AudioFile
        files = [
            AudioFile(path="a", relative_path="a", codec=CodecType.MP3, bitrate=192000, sample_rate=44100, channels=2),
            AudioFile(path="b", relative_path="b", codec=CodecType.MP3, bitrate=192000, sample_rate=44100, channels=2),
        ]
        assert get_bitrate_range(files) == "192k"

    def test_range(self):
        from hardfi_encode.models import AudioFile
        files = [
            AudioFile(path="a", relative_path="a", codec=CodecType.MP3, bitrate=128000, sample_rate=44100, channels=2),
            AudioFile(path="b", relative_path="b", codec=CodecType.MP3, bitrate=320000, sample_rate=44100, channels=2),
        ]
        assert get_bitrate_range(files) == "128-320k"

    def test_no_bitrates(self):
        from hardfi_encode.models import AudioFile
        files = [
            AudioFile(path="a", relative_path="a", codec=CodecType.FLAC, bitrate=0, sample_rate=44100, channels=2),
        ]
        assert get_bitrate_range(files) == "lossless"

    def test_empty_list(self):
        assert get_bitrate_range([]) == ""
