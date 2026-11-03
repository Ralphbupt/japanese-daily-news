#!/usr/bin/env python3
"""Generate podcast episode from JSON script.

TTS engine: Gemini TTS by default (key from $GEMINI_API_KEY or
~/.config/storyanim/gemini_key). Any segment Gemini fails on (it is flaky on
very short single words) falls back to Edge TTS using the voice/rate in the
script's `characters`. Set TTS_ENGINE=edge to use Edge for everything.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave

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
    "vocab": 400,
}


GEMINI_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_VOICES = {"host": "Aoede", "news": "Kore", "slow": "Kore", "vocab": "Kore"}
# Gemini speaks faster than the old Edge rates (-25%/-30%); slow it down with
# ffmpeg atempo (pitch-preserving). Override all with GEMINI_TEMPO_SCALE.
GEMINI_TEMPO = {"host": 0.95, "news": 0.88, "slow": 0.80, "vocab": 0.85}
GEMINI_STYLE = {
    "host": "Read this as a warm, friendly podcast host, at a relaxed pace: ",
    "news": "日本語のニュースキャスターとして、落ち着いた自然な速さで読んでください：",
    "slow": "日本語学習者のために、ゆっくり、はっきり読んでください：",
    "vocab": "ゆっくり読んでください：",
}


def gemini_key():
    key = os.environ.get("GEMINI_API_KEY")
    path = os.path.expanduser("~/.config/storyanim/gemini_key")
    if not key and os.path.exists(path):
        key = open(path).read().strip()
    return key


_gemini_client = None


def gemini_tts(speaker, text, reading, wav_path):
    """Return True on success. Tries several prompt phrasings."""
    global _gemini_client
    from google import genai
    from google.genai import types
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=gemini_key())
    style = GEMINI_STYLE.get(speaker, "")
    variants = [style + text, style + text + "。" if speaker != "host" else style + text + "."]
    variants.append(f'Read this aloud exactly: "{text}"' if speaker == "host"
                    else f"次の文をそのまま読み上げてください：「{text}」。")
    if reading:
        variants.append(style + reading + "。")
    variants.append(variants[0])
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name=GEMINI_VOICES.get(speaker, "Kore")))),
    )
    for prompt in variants:
        try:
            r = _gemini_client.models.generate_content(
                model=GEMINI_MODEL, contents=prompt, config=config)
            cand = r.candidates[0]
            if not (cand.content and cand.content.parts):
                raise RuntimeError(f"empty audio ({cand.finish_reason})")
            pcm = cand.content.parts[0].inline_data.data
            with wave.open(wav_path, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(pcm)
            return True
        except Exception as e:
            msg = str(e)
            print(f"      gemini retry: {msg[:100]}")
            time.sleep(30 if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) else 2)
    return False


async def generate_segment(text, voice, rate, output_path):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)


async def synth(seg, char, output_path, tmpdir, use_gemini):
    """Write an mp3 for one segment. Returns the engine actually used."""
    speaker, text = seg["speaker"], seg["text"]
    if use_gemini:
        import re
        m = re.search(r'data-reading="([^"]+)"', seg.get("ruby", ""))
        reading = m.group(1) if (m and speaker == "vocab") else None
        wav = output_path + ".wav"
        cache_dir = os.environ.get("TTS_CACHE")  # optional: reuse raw audio while tuning
        cached = None
        if cache_dir:
            import hashlib
            os.makedirs(cache_dir, exist_ok=True)
            h = hashlib.md5(f"{GEMINI_MODEL}|{speaker}|{text}".encode()).hexdigest()
            cached = os.path.join(cache_dir, h + ".wav")
            if os.path.exists(cached):
                shutil.copy(cached, wav)
        ok = os.path.exists(wav) or gemini_tts(speaker, text, reading, wav)
        if ok and cached and not os.path.exists(cached):
            shutil.copy(wav, cached)
        if ok:
            tempo = GEMINI_TEMPO.get(speaker, 1.0) * float(os.environ.get("GEMINI_TEMPO_SCALE", "1"))
            subprocess.run(["ffmpeg", "-y", "-i", wav, "-filter:a", f"atempo={tempo:.3f}",
                            "-ar", "24000", "-ac", "1",
                            "-c:a", "libmp3lame", "-b:a", "48k", output_path],
                           capture_output=True, check=True)
            return "gemini"
    rate = char.get("rate", DEFAULT_RATES.get(char["lang"], "+0%"))
    await generate_segment(text, char["voice"], rate, output_path)
    return "edge"


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
    use_gemini = os.environ.get("TTS_ENGINE", "gemini") == "gemini" and bool(gemini_key())
    print(f"TTS engine: {'gemini (' + GEMINI_MODEL + ')' if use_gemini else 'edge'}\n")
    done = {}       # (speaker, text) -> mp3 path, so the news replay is not re-billed
    fallbacks = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, seg in enumerate(segments):
            speaker = seg["speaker"]
            text = seg["text"]
            char = characters[speaker]

            path = os.path.join(tmpdir, f"seg_{i:03d}.mp3")
            try:
                key = (speaker, text)
                if key in done:
                    shutil.copy(done[key], path)
                    engine = "reuse"
                else:
                    engine = await synth(seg, char, path, tmpdir, use_gemini)
                    done[key] = path
                    if use_gemini and engine == "edge":
                        fallbacks.append(i + 1)
                label = f"{speaker}({engine})"
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
            pause_ms = PAUSE_AFTER.get(speaker, 500)
            current_time += pause_ms / 1000

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
        if fallbacks:
            print(f"  Edge fallback segments: {fallbacks}")


if __name__ == "__main__":
    asyncio.run(main())
