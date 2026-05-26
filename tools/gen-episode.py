#!/usr/bin/env python3
"""Generate podcast episode from JSON script using Edge TTS."""

import asyncio
import json
import os
import subprocess
import sys
import tempfile

import edge_tts

ROOT = os.path.dirname(os.path.dirname(__file__))
SCRIPT_DIR = os.path.join(ROOT, "scripts")
OUT_DIR = os.path.join(ROOT, "audio")

DEFAULT_RATES = {
    "en": "-5%",
    "ja": "-10%",
}

PAUSE_AFTER = {
    "host": 600,
    "news": 700,
    "slow": 800,
}


async def generate_segment(text, voice, rate, output_path):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)


async def main():
    ep = sys.argv[1] if len(sys.argv) > 1 else "ep001"
    script_path = os.path.join(SCRIPT_DIR, f"{ep}.json")

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    characters = script["characters"]
    segments = script["segments"]
    print(f"Episode {script['episode']}: {script['title']}")
    print(f"Generating {len(segments)} segments...\n")

    os.makedirs(OUT_DIR, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, seg in enumerate(segments):
            speaker = seg["speaker"]
            text = seg["text"]
            char = characters[speaker]
            voice = char["voice"]
            rate = char.get("rate", DEFAULT_RATES.get(char["lang"], "+0%"))

            path = os.path.join(tmpdir, f"seg_{i:03d}.mp3")
            try:
                await generate_segment(text, voice, rate, path)
                label = f"{speaker}({char['lang']})"
                print(f"  [{i+1}/{len(segments)}] {label:20s} {text[:55]}...")
            except Exception as e:
                print(f"  [{i+1}/{len(segments)}] FAILED {speaker}: {e}")
                subprocess.run([
                    "ffmpeg", "-y", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", "1",
                    "-c:a", "libmp3lame", "-b:a", "48k", path
                ], capture_output=True)

        print("\nGenerating pauses...")
        all_pauses = set(PAUSE_AFTER.values())
        all_pauses.add(1000)
        all_pauses.add(1500)
        all_pauses.add(2000)
        for ms in all_pauses:
            path = os.path.join(tmpdir, f"silence_{ms}.mp3")
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                f"anullsrc=r=24000:cl=mono", "-t", f"{ms/1000:.2f}",
                "-c:a", "libmp3lame", "-b:a", "48k", path
            ], capture_output=True)

        print("Concatenating...")
        concat_path = os.path.join(tmpdir, "concat.txt")
        with open(concat_path, "w") as f:
            f.write("file 'silence_1500.mp3'\n")
            for i, seg in enumerate(segments):
                f.write(f"file 'seg_{i:03d}.mp3'\n")
                pause = PAUSE_AFTER.get(seg["speaker"], 500)
                f.write(f"file 'silence_{pause}.mp3'\n")
            f.write("file 'silence_2000.mp3'\n")

        out_path = os.path.join(OUT_DIR, f"{ep}.mp3")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_path, "-c:a", "libmp3lame", "-b:a", "128k",
            out_path
        ], capture_output=True)

        size_mb = os.path.getsize(out_path) / (1024 * 1024)
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            out_path
        ], capture_output=True, text=True)
        duration_s = float(result.stdout.strip())
        print(f"\nDone!")
        print(f"  Output: {out_path}")
        print(f"  Duration: {int(duration_s // 60)}:{int(duration_s % 60):02d}")
        print(f"  Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    asyncio.run(main())
