#!/usr/bin/env python3
"""Generate podcast episode from JSON script using Edge TTS.

Before speaking, Japanese text goes through tools/tts_readings.py (words the
voice misreads, rewritten into kana); a segment's own "tts" field overrides
that. The transcript, furigana and subtitles keep "text". After generating,
tools/qa-audio.py listens to the result and reports misreadings.

(A Gemini TTS variant was tried on 2026-11-03 and reverted: per-line requests
drift in timbre, and cutting a multi-line request back into lines is not
reliable without Whisper alignment, which the 1 GB server can't run.)
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile

import edge_tts

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts_readings import apply_readings  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(__file__))
SCRIPT_DIR = os.path.join(ROOT, "scripts")
OUT_DIR = os.path.join(ROOT, "audio")

DEFAULT_RATES = {
    "en": "-5%",
    "ja": "-10%",
}

PAUSE_AFTER = {
    "host": 600,
    "guide": 700,
    "news": 700,
    "slow": 800,
    "vocab": 400,
}


def pause_ms_after(seg):
    """A segment's own "pause" (ms) wins, e.g. thinking time after a quiz question."""
    return seg.get("pause", PAUSE_AFTER.get(seg["speaker"], 500))


def tts_text(seg):
    """What the voice is given (the transcript keeps seg["text"])."""
    if seg.get("tts"):
        return seg["tts"]
    if seg["speaker"] == "host":
        return seg["text"]
    return apply_readings(seg["text"])


def _use_new_edge_endpoint():
    """Since 2026-10 Microsoft refuses the old readaloud endpoint (403) in some
    regions, Japan included; Edge itself now uses api.msedgeservices.com with
    the same client key (fix from jpnotes.dev's build-audio.py). Only switched
    to after a 403, so hosts where the old endpoint works keep using it."""
    import edge_tts.communicate
    from edge_tts.constants import TRUSTED_CLIENT_TOKEN
    edge_tts.communicate.WSS_URL = (
        "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
        f"?Ocp-Apim-Subscription-Key={TRUSTED_CLIENT_TOKEN}")


async def generate_segment(text, voice, rate, output_path):
    for attempt in range(6):
        try:
            await edge_tts.Communicate(text, voice, rate=rate).save(output_path)
            return
        except Exception as e:
            msg = str(e)
            if "403" in msg and attempt == 0:
                print("  (Edge returned 403 — switching to the new endpoint)")
                _use_new_edge_endpoint()
            elif "429" in msg and attempt < 5:   # the new endpoint rate-limits bursts
                await asyncio.sleep(2 * (attempt + 1))
            else:
                raise


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

    seg_timings = []
    current_time = 1.5  # initial 1500ms silence

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, seg in enumerate(segments):
            speaker = seg["speaker"]
            text = seg["text"]
            char = characters[speaker]
            voice = char["voice"]
            rate = char.get("rate", DEFAULT_RATES.get(char["lang"], "+0%"))

            path = os.path.join(tmpdir, f"seg_{i:03d}.mp3")
            try:
                await generate_segment(tts_text(seg), voice, rate, path)
                label = f"{speaker}({char['lang']})"
                print(f"  [{i+1}/{len(segments)}] {label:20s} {text[:55]}...")
            except Exception as e:
                print(f"  [{i+1}/{len(segments)}] FAILED {speaker}: {e}")
                subprocess.run([
                    "ffmpeg", "-y", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", "1",
                    "-c:a", "libmp3lame", "-b:a", "48k", path
                ], capture_output=True)

            dur_result = subprocess.run([
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1", path
            ], capture_output=True, text=True)
            seg_dur = float(dur_result.stdout.strip())
            seg_timings.append({
                "index": i,
                "start": round(current_time, 3),
                "end": round(current_time + seg_dur, 3),
            })
            current_time += seg_dur
            pause_ms = pause_ms_after(seg)
            current_time += pause_ms / 1000

        print("\nGenerating pauses...")
        all_pauses = set(PAUSE_AFTER.values()) | {pause_ms_after(s) for s in segments}
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
                pause = pause_ms_after(seg)
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

        timing_path = os.path.join(SCRIPT_DIR, f"{ep}.timing.json")
        timing_data = {
            "episode": script["episode"],
            "totalDuration": round(duration_s, 3),
            "segments": seg_timings,
        }
        with open(timing_path, "w", encoding="utf-8") as f:
            json.dump(timing_data, f, indent=2, ensure_ascii=False)

        print(f"\nDone!")
        print(f"  Output: {out_path}")
        print(f"  Timing: {timing_path}")
        print(f"  Duration: {int(duration_s // 60)}:{int(duration_s % 60):02d}")
        print(f"  Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    asyncio.run(main())
