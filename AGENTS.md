# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Japanese Daily News is a podcast for Japanese learners, hosted at `podcast.jpnotes.dev`. Each episode covers a real Japanese news story with four speaker roles. Episodes are defined as JSON scripts and converted to MP3 audio using Edge TTS + ffmpeg. The site is built with Astro and deployed on Cloudflare Pages.

## Full Pipeline for a New Episode

```bash
# 1. Write the script
#    Create scripts/epNNN.json following the format below

# 2. Add furigana + vocab highlights
.venv/bin/python tools/add-furigana.py epNNN

# 3. Validate the script (schema + content rules)
python3 tools/validate-episode.py epNNN

# 4. Generate audio + timing data
.venv/bin/python tools/gen-episode.py epNNN

# 5. Generate subtitles (VTT + SRT)
python3 tools/gen-subtitles.py epNNN

# 6. Copy assets to site
cp audio/epNNN.mp3 site/public/audio/
cp subtitles/epNNN.* site/public/subtitles/

# 7. Build and preview
cd site && npm run dev

# 8. Deploy (push to GitHub, Cloudflare auto-deploys)
git add . && git commit && git push
```

Requires: `ffmpeg`, `ffprobe` on PATH. Python deps in `.venv/` (edge-tts, pykakasi).

## Script Format (`scripts/epNNN.json`)

Four speaker roles:
- `host` (Maya) — English explanations only, ZERO Japanese characters, ZERO romaji (en-US-AvaNeural)
- `news` — Japanese news reading at moderate speed (ja-JP-NanamiNeural, -25%)
- `slow` — Slow Japanese repeat of key sentences (ja-JP-NanamiNeural, -30%)
- `vocab` — Individual Japanese vocabulary words (ja-JP-NanamiNeural, -30%)

Episode structure:
1. Host intro (short — one or two sentences of context, then "Let's listen.")
2. Full news (9-10 `news` segments — longer article with more detail)
3. Breakdown: `slow` sentence → `host` translation → `vocab` word → `host` explanation (1-2 sentences max, no verbose transitions)
4. Full news replay (same `news` segments)
5. Quiz: `slow` question → `host` English answer
6. Host closing + `news` "また明日。"

Target duration: ~7:30–8:00. Prioritize Japanese content over host commentary.

Critical rules:
- `host` segments must contain ZERO Japanese characters AND ZERO romaji — no 'Takusan', 'Nedan', etc.
- All Japanese pronunciation goes in `vocab`/`slow`/`news` segments, read by Japanese TTS
- Host refers to meanings only: "It means price" NOT "'Nedan' means price"
- No comparing polite vs rude forms (don't mention offensive alternatives)
- Host name is Maya: "Welcome to Japanese Daily News. I'm Maya."
- Each JSON also includes `vocabulary` (with `zh` field), `grammar` (with `meaningZh`/`noteZh`), `practiceZh`, and `level` fields

## Site Architecture (`site/`)

Astro 5 static site. Key files:
- `src/lib/episodes.ts` — loads episode JSONs, builds timing, types
- `src/pages/ep/[id].astro` — episode page with player, transcript, practice mode
- `src/pages/index.astro` — landing page
- `src/pages/rss.xml.ts` — podcast RSS feed
- `src/pages/sitemap.xml.ts` — sitemap
- `src/layouts/Layout.astro` — base layout with GA4, theme/lang toggle

Features: synced transcript, furigana, vocab click tooltips, practice mode (精听), playback speed control, dark mode, EN/中文 toggle, font size toggle (S/M/L), localStorage progress tracking, collapsible vocab/grammar section, keyboard shortcuts.

## Versioning

`PAGE_VERSION` in `Layout.astro` head script. When episode content changes, bump this version (format: YYYYMMDDNN). On mismatch, all `jdn-ep*` localStorage entries are cleared automatically.

## Tools

- `tools/gen-episode.py` — TTS audio generation + timing manifest
- `tools/add-furigana.py` — adds ruby HTML + vocab highlights to Japanese segments (uses pykakasi)
- `tools/gen-subtitles.py` — generates VTT/SRT from timing data
- `tools/validate-episode.py` — schema + content-rule check (host has no Japanese, vocab has `zh`, ja-segments have `ruby`, etc.). Run with `epNNN`, no args (all), or `--staged` (git pre-commit).
- `tools/cover.html` — podcast cover image template (screenshot at 3000x3000)

## Git hooks

`.githooks/pre-commit` runs `validate-episode.py --staged` on any staged `scripts/ep*.json`. Enabled for this repo via `git config core.hooksPath .githooks` — re-run that command after a fresh clone.

## Deployment

- Site: Cloudflare Pages (`podcast.jpnotes.dev`)
- Build: `cd site && npm install && npm run build` → output `site/dist`
- Audio/subtitles committed to git, copied to `site/public/` during build
- GA4: `G-7W59Y18KC8`

## Conventions

- Episode IDs: zero-padded `ep001`, `ep002`, etc.
- Dates in intro text: written out ("May twenty-fourth"), no year
- Difficulty levels: `N5-N4` (beginner) or `N4-N3` (intermediate) in `level` field
- Scripts self-contained — each JSON includes all voice/rate config
- Companion site: `jpnotes.dev` (grammar notes, cross-linked from grammar cards)
- Fonts: Fraunces (display), Noto Sans JP (JP), Outfit (body)
- Light mode: warm yellow paper (#F3EDDA); Dark mode: #1A1A1E
- Apple Podcasts: https://podcasts.apple.com/podcast/id1896815841
- Spotify: https://open.spotify.com/show/033nVZrL6xnSJDxcXc9PMQ
- YouTube: https://www.youtube.com/playlist?list=PLFPcxHB9z1CRXO7aEgo5qE_jP_E3cXwKb
- RSS: `https://podcast.jpnotes.dev/rss.xml`
