#!/usr/bin/env python3
"""Generate an all-Japanese episode (scripts/nhNNN.json) with Gemini TTS.

Unlike tools/gen-episode.py (Edge, one request per line), this reads each run of
same-speaker segments in ONE request, which keeps the voice stable, and reuses
the audio of a repeated block (the news replay). Sentence timing comes from
gemini-3.5-transcribe word timestamps aligned to the script, so no Whisper is
needed. The same comparison reports lines that may be misread or skipped.

  python3 tools/gen-nihongo.py nh001 [--cache DIR]

Give the model ONLY the text to read: a style instruction in the prompt gets
read aloud (lite) or causes very long pauses (2.5).
Key: $GEMINI_API_KEY or ~/.config/storyanim/gemini_key.
"""

import base64
import difflib
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts_readings import apply_readings  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_DIR = os.path.join(ROOT, "scripts")
OUT_DIR = os.path.join(ROOT, "audio")
API = "https://generativelanguage.googleapis.com/v1beta/models"
TTS_MODEL = os.environ.get("NH_TTS_MODEL", "gemini-3.8-flash-lite-tts")
ASR_MODEL = "gemini-3.5-transcribe"
RATE = 24000
LEAD_MS = 1000
TAIL_MS = 1500
PAUSE_BEFORE_NEWS_MS = 1000
PAUSE_BETWEEN_BLOCKS_MS = 1500
MIN_MATCH = 0.85


def api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key.strip()
    with open(os.path.expanduser("~/.config/storyanim/gemini_key")) as f:
        return f.read().strip()


def post(model, body, timeout=280):
    req = urllib.request.Request(
        f"{API}/{model}:generateContent", json.dumps(body).encode(),
        {"Content-Type": "application/json", "x-goog-api-key": api_key()})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if attempt == 4 or e.code not in (429, 500, 503):
                raise
        except (TimeoutError, urllib.error.URLError):
            if attempt == 4:
                raise
        time.sleep(15 * (attempt + 1))


def pcm_from_response(data):
    """2.5 returns raw PCM; 3.8 returns a whole WAV file. Treating the WAV as
    raw plays its header and 6 KB trailer as a loud click at each block's ends."""
    if data[:4] != b"RIFF":
        return data
    i = 12
    while i + 8 <= len(data):
        cid, size = data[i:i + 4], struct.unpack("<I", data[i + 4:i + 8])[0]
        if cid == b"data":
            return data[i + 8:i + 8 + size]
        i += 8 + size + (size & 1)
    raise ValueError("WAV response without a data chunk")


def block_key(voice, lines):
    return hashlib.md5(f"{TTS_MODEL}|{voice}|{chr(10).join(lines)}".encode()).hexdigest()[:16]


def synthesize(voice, lines, cache):
    path = os.path.join(cache, block_key(voice, lines) + ".pcm")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    r = post(TTS_MODEL, {
        "contents": [{"parts": [{"text": "\n".join(lines)}]}],
        "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}})
    data = base64.b64decode(r["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    pcm = pcm_from_response(data)
    with open(path, "wb") as f:
        f.write(pcm)
    return pcm


def write_wav(path, pcm):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)


def transcribe(pcm, cache, key):
    path = os.path.join(cache, key + ".words.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with tempfile.TemporaryDirectory() as tmp:
        wav, mp3 = os.path.join(tmp, "a.wav"), os.path.join(tmp, "a.mp3")
        write_wav(wav, pcm)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-b:a", "64k", mp3], check=True)
        with open(mp3, "rb") as f:
            audio = base64.b64encode(f.read()).decode()
    r = post(ASR_MODEL, {
        "contents": [{"parts": [{"inlineData": {"mimeType": "audio/mpeg", "data": audio}}]}],
        "generationConfig": {"audioTranscriptionConfig": {"wordTimestamp": True}}})
    words = [{"w": w["word"], "s": float(w["startOffset"].rstrip("s")),
              "e": float(w["endOffset"].rstrip("s"))}
             for w in r["candidates"][0]["content"]["parts"][0]["audioTranscription"]["words"]]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False)
    return words


def norm(s):
    s = unicodedata.normalize("NFKC", s).replace("ヶ", "か").replace("ヵ", "か")
    return re.sub(r"[\s、。,.，．!?！？「」『』…・]", "", s)


def align(lines, words):
    """Each line → (start, end, match ratio) in the block, from word times."""
    said, owner = "", []
    for i, w in enumerate(words):
        n = norm(w["w"])
        said += n
        owner += [i] * len(n)
    script, line_of = "", []
    for i, line in enumerate(lines):
        n = norm(line)
        script += n
        line_of += [i] * len(n)
    hits = [[] for _ in lines]
    sm = difflib.SequenceMatcher(None, script, said, autojunk=False)
    for b in sm.get_matching_blocks():
        for k in range(b.size):
            hits[line_of[b.a + k]].append(owner[b.b + k])
    out = []
    for i, h in enumerate(hits):
        ratio = len(h) / max(1, len(norm(lines[i])))
        if h:
            out.append([words[min(h)]["s"], words[max(h)]["e"], ratio])
        else:
            out.append([None, None, 0.0])
    for i, o in enumerate(out):      # a line nothing matched sits between neighbours
        if o[0] is None:
            o[0] = out[i - 1][1] if i else 0.0
            o[1] = next((x[0] for x in out[i + 1:] if x[0] is not None), o[0])
    return out


def make_blocks(segments):
    """Runs of one speaker; a segment with "break": true starts a new block."""
    blocks = []
    for i, seg in enumerate(segments):
        if blocks and blocks[-1]["speaker"] == seg["speaker"] and not seg.get("break"):
            blocks[-1]["idx"].append(i)
        else:
            blocks.append({"speaker": seg["speaker"], "idx": [i]})
    return blocks


def spoken(seg):
    return apply_readings(seg.get("tts") or seg["text"])


def main():
    args = sys.argv[1:]
    ep = args[0]
    cache = args[args.index("--cache") + 1] if "--cache" in args else os.path.join(
        tempfile.gettempdir(), f"jdn-{ep}")
    os.makedirs(cache, exist_ok=True)
    with open(os.path.join(SCRIPT_DIR, f"{ep}.json"), encoding="utf-8") as f:
        script = json.load(f)
    segments, chars = script["segments"], script["characters"]
    blocks = make_blocks(segments)

    done, pieces, timings, warned = {}, [], [None] * len(segments), 0
    t = LEAD_MS / 1000
    pieces.append(b"\0\0" * (RATE * LEAD_MS // 1000))
    for n, b in enumerate(blocks):
        lines = [spoken(segments[i]) for i in b["idx"]]
        voice = chars[b["speaker"]]["voice"]
        key = block_key(voice, lines)
        if key not in done:
            pcm = synthesize(voice, lines, cache)
            # Align to the transcript's own spelling: "text" (kanji), not the kana in "tts".
            done[key] = (pcm, align([segments[i]["text"] for i in b["idx"]], transcribe(pcm, cache, key)))
            print(f"  block {n}: {b['speaker']} x{len(lines)}  {len(pcm) / 2 / RATE:.1f}s")
            for line, a in zip(lines, done[key][1]):
                if a[2] < MIN_MATCH:
                    warned += 1
                    print(f"    CHECK {a[2]:.0%}: {line[:50]}")
        pcm, aligned = done[key]
        for i, a in zip(b["idx"], aligned):
            timings[i] = {"index": i, "start": round(t + a[0], 3), "end": round(t + a[1], 3)}
        t += len(pcm) / 2 / RATE
        pieces.append(pcm)
        if n + 1 < len(blocks):
            ms = PAUSE_BEFORE_NEWS_MS if blocks[n + 1]["speaker"] == "news" else PAUSE_BETWEEN_BLOCKS_MS
            pieces.append(b"\0\0" * (RATE * ms // 1000))
            t += ms / 1000
    pieces.append(b"\0\0" * (RATE * TAIL_MS // 1000))
    t += TAIL_MS / 1000

    out = os.path.join(OUT_DIR, f"{ep}.mp3")
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "all.wav")
        write_wav(wav, b"".join(pieces))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-c:a", "libmp3lame",
                        "-b:a", "128k", out], check=True)
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                         "-of", "csv=p=0", out]).decode())
    with open(os.path.join(SCRIPT_DIR, f"{ep}.timing.json"), "w", encoding="utf-8") as f:
        json.dump({"episode": script["episode"], "totalDuration": round(dur, 3),
                   "segments": timings}, f, indent=2, ensure_ascii=False)
    print(f"Done: {out}  {int(dur // 60)}:{int(dur % 60):02d}  {warned} line(s) to check")


if __name__ == "__main__":
    main()
