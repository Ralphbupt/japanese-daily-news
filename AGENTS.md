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

Misread words: `tools/tts_readings.py` rewrites words the voice gets wrong into kana before speaking (regex rules, shared by all episodes — add one when a word recurs). For a one-off, give the segment a `"tts"` field with the misread word in kana (e.g. `"text": "…網走…"`, `"tts": "…あばしり…"`); the transcript, furigana and subtitles keep `text`.

Episode structure:
1. Host intro (short — one or two sentences of context, then "Let's listen.")
2. Full news (9-10 `news` segments — longer article with more detail)
3. Breakdown: `slow` sentence → `host` translation → (optional) `vocab` word → `host` explanation (1-2 sentences max, no verbose transitions)

Vocab selection — quality over quantity. A sentence with nothing worth teaching gets NO vocab (just `slow` → `host` translation). Never pad to fill a quota; 4-8 good words per episode beats 14 filler ones.
- DO pick: verbs, adjectives, adverbs, set expressions and common nouns a learner at this episode's `level` doesn't know yet but will meet again (e.g. 降る, 急に, 気温, みぞれ, いつもの年).
- DON'T pick: proper nouns — place, person, company or event names (北海道, 本州, 札幌, トヨタ); plain numbers/counters/dates (7つ, 10月28日); katakana loanwords whose meaning is obvious (ニュース); words clearly below the level (山, 白い, 早い, 同じ in an N4-N3 episode — and the most basic ones like 山 even at N5-N4).
- The top-level `vocabulary` list holds exactly the words that get a `vocab` segment.

Writing for the ear (listeners can't re-read):
- No long strings of proper nouns. Seven town names in one sentence is unlistenable (and the voice misread 網走 in ep253): summarize — 「北海道と青森の7つの町」 — and name at most one or two.
- Names with uncommon readings (place / person names like 網走, 帯広, 細野豪志) get a `"tts"` field with the name in kana, on every segment that contains it (news, slow, quiz). Common ones (東京, 札幌, 大阪) don't need it.
- One idea per sentence; split long sentences rather than stacking clauses.

Self-check before running the pipeline (as jpnotes.dev reviews its listening items):
- Level: vocabulary and grammar fit the episode's `level`; a word clearly above it is either replaced with a simpler one or taught as vocab.
- Natural Japanese, the way NHK NEWS WEB EASY / a Japanese newsreader would say it — no word-for-word translation from English.
- Quiz: each question is answered clearly in the news (a learner who followed the story can answer), has exactly one right answer, and uses words from the episode.
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
- Each JSON also includes `titleZh` / `titleEn` (the headline translated: a natural Chinese news headline ≤ 30 chars and a short English one ≤ 70 chars, sentence case — they become the /zh/ and English page titles, "<titleZh>｜日语新闻听力 第N集" / "<titleEn> | Easy Japanese News EP NNN"), `vocabulary` (with `zh` field), `grammar` (with `meaningZh`/`noteZh`), `practiceZh` (one entry per breakdown sentence: Japanese line, Chinese translation line, notes — the Chinese line is also shown under that sentence on /zh/ pages), and `level` fields. Every `news` segment also gets a `zh` field with its Chinese translation (same text in the replay); /zh/ pages show it under the sentence, and validate-episode fails a news sentence with neither `zh` nor a practiceZh entry

## Site Architecture (`site/`)

Astro 5 static site. Key files:
- `src/lib/episodes.ts` — loads episode JSONs, builds timing, types
- `src/pages/[...lang]/ep/[id].astro` — episode page with player, transcript, practice mode
- `src/pages/[...lang]/index.astro`, `about.astro` — landing / about page
- `src/lib/i18n.ts` — one page per language, like jpnotes.dev: English at `/…/`, Chinese at `/zh/…/` (`[...lang]` = undefined | `zh`). Write UI text with both `class="i18n-en"` / `class="i18n-zh"` siblings; after the build `astro.config.mjs` (`stripOtherLang`) keeps only the page's own language. `Layout.astro` sets `lang`, hreflang/x-default, and redirects to the reader's saved language (`jdn-lang`; a zh browser with none saved only from the English home page). Internal links go through `lp(path, lang)`
- `src/pages/rss.xml.ts` — podcast RSS feed
- `src/pages/sitemap.xml.ts` — sitemap
- `src/layouts/Layout.astro` — base layout with GA4, theme/lang toggle

Features: synced transcript, furigana, vocab click tooltips, Japanese-only mode (纯日语: just the first news reading, auto-play continues in it), practice mode (精听), lock-screen title = current sentence (Media Session), playback speed control, dark mode, EN/中文 toggle, font size toggle (S/M/L), localStorage progress tracking (global preferences: theme, language, font size, speed `jdn-speed`, mode `jdn-mode` (full text / Japanese only — practice is never saved), vocab/grammar section open `jdn-review-open`, auto-play; per episode: position `jdn-epNNN`, listened/practiced), collapsible vocab/grammar section, keyboard shortcuts.

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
- Fonts: Fraunces (display), Outfit (body, PingFang SC for Chinese); Japanese uses system fonts first — Mincho (Hiragino Mincho / Yu Mincho, Noto Serif JP fallback) for transcript/practice/examples, Gothic (Hiragino Kaku Gothic, Noto Sans JP fallback) for titles and UI; furigana stays Gothic
- Themes (header button cycles light → warm → dark, saved in `theme`): light = jpnotes.dev "paper" #f6f4ef with deep red #b8283f (default); warm = the original yellow paper #F3EDDA with #C23B22; dark = #14141e with #e94560. Tokens at the top of `site/src/styles/global.css`.
- Apple Podcasts: https://podcasts.apple.com/podcast/id1896815841
- Spotify: https://open.spotify.com/show/033nVZrL6xnSJDxcXc9PMQ
- YouTube: https://www.youtube.com/playlist?list=PLFPcxHB9z1CRXO7aEgo5qE_jP_E3cXwKb
- RSS: `https://podcast.jpnotes.dev/rss.xml`
