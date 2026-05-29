# JB7 HardFi Encode

A cross-platform desktop tool for scanning and converting audio files from a Brennan JB7 media player's `hardfi` directory structure. Converts lossless formats (WAV, FLAC, ALAC) to more space-efficient formats.

<img width="953" height="723" alt="Screenshot 2026-05-29 at 09 52 27" src="https://github.com/user-attachments/assets/26744f19-5849-4f5a-acfa-3bfd529a0ebf" />

## Features

- Scans a source directory for audio files (WAV, FLAC, ALAC, AAC, MP3)
- Auto-detects Brennan JB7 `hardfi/` directory structure
- Displays a summary of files by codec type and bitrate
- Converts lossless files to a chosen target format:
  - WAV → FLAC (lossless compression)
  - WAV / FLAC / ALAC → AAC (lossy, specify bitrate: 128k–320k)
  - WAV / FLAC / ALAC → MP3 (lossy, specify bitrate: 128k–320k)
- Preserves directory structure (Artist/Album/track)
- Optionally deletes original files after successful conversion
- Skips already-compressed formats (AAC, MP3) — no re-encoding

## Requirements

- **Python 3.10+**
- **ffmpeg** (for audio conversion)

### Installing ffmpeg

- **macOS:** `brew install ffmpeg`
- **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/) or `choco install ffmpeg`
- **Linux:** `sudo apt install ffmpeg` (Debian/Ubuntu) or equivalent

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd jb7-hardfi-encode

# Create virtual environment and install dependencies
make venv
```

### Windows (without Make)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

```bash
# Activate virtual environment and run
make run
```

Or manually:

```bash
source venv/bin/activate    # macOS/Linux
# venv\Scripts\activate     # Windows
python -m hardfi_encode
```

1. Click **Select Source** and choose a directory containing your music files (or a `hardfi/` subdirectory).
2. Review the audio summary (codec types, counts, bitrates).
3. Choose a target format and bitrate (if applicable).
4. Check **Delete original files** if desired.
5. Click **Start Conversion**.

## Source Directory Structure

The tool accepts either:

- A directory containing `Artist/Album/track` subdirectories, or
- A directory containing a `hardfi/` subdirectory with the Brennan JB7 structure: `hardfi/Artist/Album/01 Track 1.ext`

## Supported Formats

| Format | Codec | Compressible |
|--------|-------|-------------|
| WAV    | Lossless | Yes → FLAC/AAC/MP3 |
| FLAC   | Lossless | Yes → AAC/MP3 |
| ALAC   | Lossless | Yes → AAC/MP3 |
| AAC    | Lossy  | No |
| MP3    | Lossy  | No |

## Development

```bash
# Run tests with coverage
make test

# Generate HTML coverage report
make test-html

# Clean up
make clean
```
