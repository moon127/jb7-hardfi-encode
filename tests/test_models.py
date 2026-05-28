from hardfi_encode.models import (
    LOSSLESS_CODECS,
    LOSSY_CODECS,
    SUPPORTED_EXTENSIONS,
    CodecType,
    is_lossless,
    is_lossy,
)


class TestCodecType:
    def test_from_extension_wav(self):
        assert CodecType.from_extension(".wav") == CodecType.WAV
        assert CodecType.from_extension(".WAV") == CodecType.WAV
        assert CodecType.from_extension(".wave") == CodecType.WAV

    def test_from_extension_flac(self):
        assert CodecType.from_extension(".flac") == CodecType.FLAC
        assert CodecType.from_extension(".FLAC") == CodecType.FLAC

    def test_from_extension_m4a(self):
        assert CodecType.from_extension(".m4a") == CodecType.ALAC

    def test_from_extension_aac(self):
        assert CodecType.from_extension(".aac") == CodecType.AAC
        assert CodecType.from_extension(".mp4") == CodecType.AAC

    def test_from_extension_mp3(self):
        assert CodecType.from_extension(".mp3") == CodecType.MP3

    def test_from_extension_unknown(self):
        assert CodecType.from_extension(".ogg") == CodecType.UNKNOWN
        assert CodecType.from_extension(".txt") == CodecType.UNKNOWN
        assert CodecType.from_extension("") == CodecType.UNKNOWN

    def test_supported_extensions_contains_all_codec_exts(self):
        assert ".wav" in SUPPORTED_EXTENSIONS
        assert ".wave" in SUPPORTED_EXTENSIONS
        assert ".flac" in SUPPORTED_EXTENSIONS
        assert ".m4a" in SUPPORTED_EXTENSIONS
        assert ".aac" in SUPPORTED_EXTENSIONS
        assert ".mp4" in SUPPORTED_EXTENSIONS
        assert ".mp3" in SUPPORTED_EXTENSIONS


class TestIsLossless:
    def test_lossless_codecs(self):
        for c in LOSSLESS_CODECS:
            assert is_lossless(c), f"{c} should be lossless"

    def test_lossy_not_lossless(self):
        for c in LOSSY_CODECS:
            assert not is_lossless(c), f"{c} should not be lossless"


class TestIsLossy:
    def test_lossy_codecs(self):
        for c in LOSSY_CODECS:
            assert is_lossy(c), f"{c} should be lossy"

    def test_lossless_not_lossy(self):
        for c in LOSSLESS_CODECS:
            assert not is_lossy(c), f"{c} should not be lossy"
