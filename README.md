# Japanese Daily News

A daily podcast for Japanese learners, **produced end-to-end by an autonomous AI pipeline**.
Twice a day, a headless Claude Code agent picks a real Japanese news story, writes the episode,
runs it through deterministic validators, generates audio and subtitles, and ships it — no human
in the loop.

**Listen:** [podcast.jpnotes.dev](https://podcast.jpnotes.dev) ·
[Apple Podcasts](https://podcasts.apple.com/podcast/id1896815841) ·
[Spotify](https://open.spotify.com/show/033nVZrL6xnSJDxcXc9PMQ) ·
[YouTube](https://www.youtube.com/playlist?list=PLFPcxHB9z1CRXO7aEgo5qE_jP_E3cXwKb) ·
[RSS](https://podcast.jpnotes.dev/rss.xml)

140+ episodes since May 2026 · morning (N5–N4) and evening (N4–N3) editions

## Pipeline

```
cron (2×/day)
  └─ tools/auto-episode.sh ── headless Claude Code agent
        1. find a real news story, write scripts/epNNN.json      (LLM)
        2. add-furigana.py      ruby readings + vocab highlights  (pykakasi)
        3. validate-episode.py  schema + content rules            (deterministic gate)
        4. audit-furigana.py    flag suspicious kanji readings    (deterministic gate)
        5. gen-episode.py       multi-voice TTS + timing manifest (Edge TTS, ffmpeg)
        6. gen-subtitles.py     VTT / SRT from timing data
        7. git push ──────────► Cloudflare Pages auto-deploy
```

The LLM does the creative part; everything it produces has to pass deterministic checks before
it can ship. A git pre-commit hook runs the same validator, so a bad script can't be committed
even by hand.

## Guardrails against LLM mistakes

- **Role separation is enforced, not requested.** The English host must contain zero Japanese
  characters and zero romaji, so every Japanese word is spoken by the Japanese voice.
  `validate-episode.py` rejects any violation.
- **Furigana auditing.** pykakasi mislabels multi-reading kanji (日 / 時 / 人 / 間, date readings
  like ついたち〜とおか, rendaku). `audit-furigana.py` flags suspect readings for correction instead
  of trusting the tokenizer.
- **Per-episode cache versioning.** Each script carries a `contentVersion`; when an episode's audio
  or timing changes, only that episode's saved playback position is reset on listeners' devices.

## Episode format

Each episode is a self-contained JSON script with four TTS roles — English host, news reading,
slow repeat, vocabulary — structured as: intro → full news → sentence-by-sentence breakdown →
replay → quiz. Scripts also carry vocabulary, grammar notes and Chinese translations for the site.

## Site

Astro 5 static site: synced transcript with furigana, tap-to-define vocabulary, practice mode
(精听), playback speed, EN / 中文 toggle, dark mode, and local progress tracking.

## Stack

Claude Code (headless) · Python · Edge TTS · ffmpeg · pykakasi · Astro · Cloudflare Pages

## Repo layout

```
scripts/   episode JSON scripts + timing manifests
tools/     pipeline: generation, furigana, validation, audio, subtitles, cron driver
site/      Astro website
audio/     generated MP3s (served from the site)
subtitles/ generated VTT / SRT
```

Companion project: [jpnotes.dev](https://jpnotes.dev) — Japanese grammar notes, N5 → N2.
