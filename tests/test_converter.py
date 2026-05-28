from __future__ import annotations

from pathlib import Path

import pytest

from hardfi_encode.converter import (
    CODEC_TO_EXT,
    CODEC_TO_FFMPEG,
    build_output_path,
    convert_single_file,
    plan_conversion,
    run_conversion,
    verify_ffmpeg,
)
from hardfi_encode.models import (
    CodecType,
    ConversionPlan,
    AudioFile,
)


class TestCodecMaps:
    def test_codec_to_ext(self):
        assert CODEC_TO_EXT[CodecType.WAV] == ".wav"
        assert CODEC_TO_EXT[CodecType.FLAC] == ".flac"
        assert CODEC_TO_EXT[CodecType.AAC] == ".m4a"
        assert CODEC_TO_EXT[CodecType.MP3] == ".mp3"

    def test_codec_to_ffmpeg(self):
        assert CODEC_TO_FFMPEG[CodecType.WAV] == "pcm_s16le"
        assert CODEC_TO_FFMPEG[CodecType.FLAC] == "flac"
        assert CODEC_TO_FFMPEG[CodecType.AAC] == "aac"
        assert CODEC_TO_FFMPEG[CodecType.MP3] == "libmp3lame"


class TestBuildOutputPath:
    def test_wav_output(self):
        result = build_output_path("Artist/Album/track.flac", Path("/music"), CodecType.WAV)
        assert result == Path("/music/Artist/Album/track.wav")

    def test_flac_output(self):
        result = build_output_path("Artist/Album/track.wav", Path("/music"), CodecType.FLAC)
        assert result == Path("/music/Artist/Album/track.flac")

    def test_aac_output(self):
        result = build_output_path("Artist/Album/track.wav", Path("/music"), CodecType.AAC)
        assert result == Path("/music/Artist/Album/track.m4a")

    def test_mp3_output(self):
        result = build_output_path("Artist/Album/track.wav", Path("/music"), CodecType.MP3)
        assert result == Path("/music/Artist/Album/track.mp3")

    def test_flac_to_aac(self):
        result = build_output_path("Album/song.flac", Path("/root"), CodecType.AAC)
        assert result == Path("/root/Album/song.m4a")

    def test_target_dir_output(self):
        result = build_output_path("Artist/Album/track.flac", Path("/music"), CodecType.WAV, target_dir=Path("/output"))
        assert result == Path("/output/Artist/Album/track.wav")

    def test_target_dir_empty(self):
        result = build_output_path("Artist/Album/track.flac", Path("/music"), CodecType.WAV, target_dir=None)
        assert result == Path("/music/Artist/Album/track.wav")


class TestPlanConversion:
    def test_plan_flac_to_wav(self):
        files = [
            AudioFile(
                path="/m/a.flac", relative_path="a.flac", codec=CodecType.FLAC,
                bitrate=500000, sample_rate=44100, channels=2,
            ),
        ]
        plan = plan_conversion(files, CodecType.WAV)
        assert len(plan.files_to_convert) == 1
        assert plan.target_codec == CodecType.WAV

    def test_plan_wav_to_flac(self):
        files = [
            AudioFile(
                path="/m/a.wav", relative_path="a.wav", codec=CodecType.WAV,
                bitrate=1411000, sample_rate=44100, channels=2,
            ),
        ]
        plan = plan_conversion(files, CodecType.FLAC, delete_originals=True)
        assert len(plan.files_to_convert) == 1
        assert plan.target_codec == CodecType.FLAC
        assert plan.delete_originals is True

    def test_plan_skips_same_codec(self):
        files = [
            AudioFile(
                path="/m/a.flac", relative_path="a.flac", codec=CodecType.FLAC,
                bitrate=500000, sample_rate=44100, channels=2,
            ),
        ]
        plan = plan_conversion(files, CodecType.FLAC)
        assert len(plan.files_to_convert) == 0

    def test_plan_skips_lossy(self):
        files = [
            AudioFile(
                path="/m/a.mp3", relative_path="a.mp3", codec=CodecType.MP3,
                bitrate=192000, sample_rate=44100, channels=2,
            ),
            AudioFile(
                path="/m/b.aac", relative_path="b.m4a", codec=CodecType.AAC,
                bitrate=256000, sample_rate=44100, channels=2,
            ),
        ]
        plan = plan_conversion(files, CodecType.AAC, bitrate=128000)
        assert len(plan.files_to_convert) == 0

    def test_plan_mixed(self):
        files = [
            AudioFile(
                path="/m/a.wav", relative_path="a.wav", codec=CodecType.WAV,
                bitrate=1411000, sample_rate=44100, channels=2,
            ),
            AudioFile(
                path="/m/b.flac", relative_path="b.flac", codec=CodecType.FLAC,
                bitrate=500000, sample_rate=44100, channels=2,
            ),
            AudioFile(
                path="/m/c.mp3", relative_path="c.mp3", codec=CodecType.MP3,
                bitrate=192000, sample_rate=44100, channels=2,
            ),
        ]
        plan = plan_conversion(files, CodecType.AAC, bitrate=192000)
        assert len(plan.files_to_convert) == 2
        assert plan.bitrate == 192000

    def test_plan_bitrate_passthrough(self):
        files = [
            AudioFile(
                path="/m/a.wav", relative_path="a.wav", codec=CodecType.WAV,
                bitrate=1411000, sample_rate=44100, channels=2,
            ),
        ]
        plan = plan_conversion(files, CodecType.MP3, bitrate=320000)
        assert plan.bitrate == 320000


class TestConvertSingleFile:
    def test_converts_wav_to_flac(self, tmp_path, mocker):
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""

        input_path = tmp_path / "test.wav"
        output_path = tmp_path / "test.flac"
        input_path.write_text("fake wav content")

        convert_single_file(input_path, output_path, CodecType.FLAC)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd
        assert "-c:a" in cmd
        assert "flac" in cmd
        assert str(input_path) in cmd
        assert str(output_path) in cmd

    def test_converts_flac_to_wav(self, tmp_path, mocker):
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""

        input_path = tmp_path / "test.flac"
        output_path = tmp_path / "test.wav"
        input_path.write_text("fake flac content")

        convert_single_file(input_path, output_path, CodecType.WAV)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd
        assert "-c:a" in cmd
        assert "pcm_s16le" in cmd
        assert "-b:a" not in cmd

    def test_converts_wav_to_aac_with_bitrate(self, tmp_path, mocker):
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""

        input_path = tmp_path / "test.wav"
        output_path = tmp_path / "test.m4a"
        input_path.write_text("fake wav content")

        convert_single_file(input_path, output_path, CodecType.AAC, bitrate=192000)

        cmd = mock_run.call_args[0][0]
        assert "-b:a" in cmd
        assert "192k" in cmd
        assert "-movflags" in cmd
        assert "+faststart" in cmd

    def test_converts_flac_to_mp3_with_bitrate(self, tmp_path, mocker):
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""

        input_path = tmp_path / "test.flac"
        output_path = tmp_path / "test.mp3"
        input_path.write_text("fake flac content")

        convert_single_file(input_path, output_path, CodecType.MP3, bitrate=256000)

        cmd = mock_run.call_args[0][0]
        assert "libmp3lame" in cmd
        assert "-b:a" in cmd
        assert "256k" in cmd

    def test_ffmpeg_failure_raises(self, tmp_path, mocker):
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "some error"

        input_path = tmp_path / "test.wav"
        output_path = tmp_path / "test.flac"
        input_path.write_text("fake")

        with pytest.raises(RuntimeError, match="ffmpeg failed"):
            convert_single_file(input_path, output_path, CodecType.FLAC)

    def test_creates_output_directory(self, tmp_path, mocker):
        mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""

        input_path = tmp_path / "sub" / "test.wav"
        output_path = tmp_path / "sub" / "deep" / "test.flac"
        input_path.parent.mkdir(parents=True)

        convert_single_file(input_path, output_path, CodecType.FLAC)
        assert output_path.parent.exists()


class TestVerifyFFmpeg:
    def test_ffmpeg_found(self, mocker):
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0
        assert verify_ffmpeg() is True

    def test_ffmpeg_not_found(self, mocker):
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.side_effect = FileNotFoundError()
        assert verify_ffmpeg() is False

    def test_ffmpeg_fails(self, mocker):
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 1
        assert verify_ffmpeg() is False


class TestRunConversion:
    def test_successful_conversion(self, tmp_path, mocker):
        mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""

        search_root = tmp_path / "music"
        (search_root / "Artist" / "Album").mkdir(parents=True)
        wav_path = search_root / "Artist" / "Album" / "01 track.wav"
        wav_path.write_text("fake wav")

        af = AudioFile(
            path=str(wav_path),
            relative_path="Artist/Album/01 track.wav",
            codec=CodecType.WAV,
            bitrate=1411000,
            sample_rate=44100,
            channels=2,
        )
        plan = ConversionPlan(
            target_codec=CodecType.FLAC,
            bitrate=None,
            delete_originals=False,
            files_to_convert=[af],
        )

        results = run_conversion(plan, str(search_root))
        assert results["converted"] == 1
        assert results["skipped"] == 0
        assert results["errors"] == 0

    def test_skips_existing_output(self, tmp_path, mocker):
        mocker.patch("hardfi_encode.converter.subprocess.run")

        search_root = tmp_path / "music"
        (search_root / "Artist" / "Album").mkdir(parents=True)
        wav_path = search_root / "Artist" / "Album" / "01 track.wav"
        wav_path.write_text("fake wav")
        flac_path = search_root / "Artist" / "Album" / "01 track.flac"
        flac_path.write_text("already exists")

        af = AudioFile(
            path=str(wav_path),
            relative_path="Artist/Album/01 track.wav",
            codec=CodecType.WAV,
            bitrate=1411000,
            sample_rate=44100,
            channels=2,
        )
        plan = ConversionPlan(
            target_codec=CodecType.FLAC,
            bitrate=None,
            delete_originals=False,
            files_to_convert=[af],
        )

        results = run_conversion(plan, str(search_root))
        assert results["converted"] == 0
        assert results["skipped"] == 1

    def test_handles_conversion_error(self, tmp_path, mocker):
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.side_effect = RuntimeError("ffmpeg crashed")

        search_root = tmp_path / "music"
        (search_root / "Artist").mkdir(parents=True)
        wav_path = search_root / "Artist" / "track.wav"
        wav_path.write_text("fake")

        af = AudioFile(
            path=str(wav_path),
            relative_path="Artist/track.wav",
            codec=CodecType.WAV,
            bitrate=1411000,
            sample_rate=44100,
            channels=2,
        )
        plan = ConversionPlan(
            target_codec=CodecType.FLAC, bitrate=None,
            delete_originals=False, files_to_convert=[af],
        )

        results = run_conversion(plan, str(search_root))
        assert results["converted"] == 0
        assert results["errors"] == 1

    def test_delete_originals(self, tmp_path, mocker):
        mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""

        search_root = tmp_path / "music"
        (search_root / "Album").mkdir(parents=True)
        wav_path = search_root / "Album" / "track.wav"
        wav_path.write_text("fake wav")

        af = AudioFile(
            path=str(wav_path),
            relative_path="Album/track.wav",
            codec=CodecType.WAV,
            bitrate=1411000,
            sample_rate=44100,
            channels=2,
        )
        plan = ConversionPlan(
            target_codec=CodecType.FLAC, bitrate=None,
            delete_originals=True, files_to_convert=[af],
        )

        results = run_conversion(plan, str(search_root))
        assert results["converted"] == 1
        assert not wav_path.exists()

    def test_cancelled_before_start(self, tmp_path, mocker):
        mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0

        search_root = tmp_path / "music"
        (search_root / "A").mkdir(parents=True)
        wav_path = search_root / "A" / "t.wav"
        wav_path.write_text("fake")

        af = AudioFile(
            path=str(wav_path), relative_path="A/t.wav",
            codec=CodecType.WAV, bitrate=1411000,
            sample_rate=44100, channels=2,
        )
        plan = ConversionPlan(
            target_codec=CodecType.FLAC, bitrate=None,
            delete_originals=False, files_to_convert=[af, af],
        )

        results = run_conversion(plan, str(search_root), cancel_check=lambda: True)
        assert results["cancelled"] is True
        assert results["converted"] == 0
        mock_run.assert_not_called()

    def test_cancelled_mid_conversion(self, tmp_path, mocker):
        mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""

        search_root = tmp_path / "music"
        (search_root / "A").mkdir(parents=True)
        wav_path = search_root / "A" / "t.wav"
        wav_path.write_text("fake")
        wav_path2 = search_root / "A" / "u.wav"
        wav_path2.write_text("fake")

        files = [
            AudioFile(path=str(wav_path), relative_path="A/t.wav", codec=CodecType.WAV, bitrate=1411000, sample_rate=44100, channels=2),
            AudioFile(path=str(wav_path2), relative_path="A/u.wav", codec=CodecType.WAV, bitrate=1411000, sample_rate=44100, channels=2),
        ]
        plan = ConversionPlan(
            target_codec=CodecType.FLAC, bitrate=None,
            delete_originals=False, files_to_convert=files,
        )

        calls = []
        def cb(pct, msg):
            calls.append((pct, msg))

        cancel_count = 0
        def cancel_check():
            nonlocal cancel_count
            cancel_count += 1
            return cancel_count >= 3

        results = run_conversion(plan, str(search_root), progress_callback=cb, cancel_check=cancel_check)
        assert results["cancelled"] is True
        assert results["converted"] == 1
        assert results["errors"] == 0
        assert any("Cancelling" in msg for _, msg in calls)

    def test_progress_callback_invoked(self, tmp_path, mocker):
        mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""

        search_root = tmp_path / "music"
        (search_root / "A").mkdir(parents=True)
        wav_path = search_root / "A" / "t.wav"
        wav_path.write_text("fake")

        af = AudioFile(
            path=str(wav_path), relative_path="A/t.wav",
            codec=CodecType.WAV, bitrate=1411000,
            sample_rate=44100, channels=2,
        )
        plan = ConversionPlan(
            target_codec=CodecType.FLAC, bitrate=None,
            delete_originals=False, files_to_convert=[af],
        )

        calls = []

        def cb(pct, msg):
            calls.append((pct, msg))

        run_conversion(plan, str(search_root), progress_callback=cb)
        assert len(calls) == 1
        assert calls[0][0] == 100

    def test_target_dir_output(self, tmp_path, mocker):
        mock_run = mocker.patch("hardfi_encode.converter.subprocess.run")
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""

        search_root = tmp_path / "music"
        target_dir = tmp_path / "output"
        (search_root / "A").mkdir(parents=True)
        wav_path = search_root / "A" / "t.wav"
        wav_path.write_text("fake")

        af = AudioFile(
            path=str(wav_path), relative_path="A/t.wav",
            codec=CodecType.WAV, bitrate=1411000,
            sample_rate=44100, channels=2,
        )
        plan = ConversionPlan(
            target_codec=CodecType.FLAC, bitrate=None,
            delete_originals=False, files_to_convert=[af],
        )

        results = run_conversion(plan, str(search_root), target_dir=str(target_dir))
        assert results["converted"] == 1
        cmd = mock_run.call_args[0][0]
        assert str(target_dir / "A" / "t.flac") in cmd
        assert wav_path.exists()
