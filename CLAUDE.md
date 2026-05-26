# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Japanese Daily News is a podcast for Japanese learners, hosted at `podcast.jpnotes.dev`. Each episode covers a real Japanese news story with four speaker roles. Episodes are defined as JSON scripts and converted to MP3 audio using Edge TTS + ffmpeg. The site is built with Astro and deployed on Cloudflare Pages.

## Full Pipeline for a New Episode

```bash
# 1. Write the script
#    Create scripts/epNNN.json following the format below

# 2. Add furigana + vocab highlights
.venv/bin/python tools/add-furigana.py epNNN

# 3. Generate audio + timing data
.venv/bin/python tools/gen-episode.py epNNN

# 4. Generate subtitles (VTT + SRT)
python3 tools/gen-subtitles.py epNNN

# 5. Copy assets to site
cp audio/epNNN.mp3 site/public/audio/
cp subtitles/epNNN.* site/public/subtitles/

# 6. Build and preview
cd site && npm run dev

# 7. Deploy (push to GitHub, Cloudflare auto-deploys)
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
1. Host intro
2. Full news (6-7 `news` segments)
3. Breakdown: `host` cue → `slow` sentence → `vocab` word → `host` explanation (repeat)
4. Full news replay (same `news` segments)
5. Quiz: `slow` question → `host` English answer → `vocab` Japanese answer
6. Vocab recap: `vocab` word → `host` meaning
7. Host closing + `news` "また明日。"

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
- `tools/cover.html` — podcast cover image template (screenshot at 3000x3000)

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
- Fonts: Fraunces (display), Shippori Mincho (JP), Outfit (body)
- Light mode: warm yellow paper (#F3EDDA); Dark mode: #1A1A1E
- Apple Podcasts: submitted (podcasters.apple.com)
- RSS: `https://podcast.jpnotes.dev/rss.xml`
