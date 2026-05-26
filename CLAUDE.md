# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Japanese Daily News is a podcast for Japanese learners. Each episode covers a real Japanese news story with three speakers: an English host who explains vocabulary/grammar, a Japanese news reader at natural speed, and a slow-repeat reader for key sentences. Episodes are defined as JSON scripts and converted to MP3 audio using Edge TTS + ffmpeg.

## Generate an Episode

```bash
pip install edge-tts   # one-time dependency
python tools/gen-episode.py ep002
```

Requires `ffmpeg` and `ffprobe` on PATH. Output goes to `audio/<episode>.mp3`.

## Architecture

**Script format** (`scripts/epNNN.json`): Each script defines `characters` (voice config per speaker role), and `segments` (ordered list of `{speaker, text}` entries). Three speaker roles:
- `host` — English explanations (en-US-AvaNeural)
- `news` — Japanese news reading at moderate speed (ja-JP-NanamiNeural, -20%)
- `slow` — Slow Japanese repeat of key sentences (ja-JP-NanamiNeural, -35%)

**Generator** (`tools/gen-episode.py`): Async pipeline that TTS-renders each segment, generates silence gaps (duration varies by speaker role via `PAUSE_AFTER`), concatenates everything with ffmpeg, and outputs a single MP3. On TTS failure, inserts 1s of silence as a placeholder.

## Conventions

- Episode IDs use zero-padded format: `ep001`, `ep002`, etc.
- Scripts are self-contained — each JSON file includes all voice/rate config, so episodes can use different voices if needed.
- Audio files (mp3/wav) are gitignored; `audio/.gitkeep` preserves the directory.
