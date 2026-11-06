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

# 3. Validate the script (schema + content rules) and audit furigana readings
python3 tools/validate-episode.py epNNN
python3 tools/audit-furigana.py epNNN   # pykakasi mislabels multi-reading kanji; fix any SUSPECT lines in the JSON by hand

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
- Each JSON also includes `titleZh` / `titleEn` (the headline translated: a natural Chinese news headline ≤ 30 chars and a short English one ≤ 70 chars, sentence case — they become the /zh/ and English page titles, "<titleZh>｜日语新闻听力 第N集" / "<titleEn> | Easy Japanese News EP NNN"), `vocabulary` (with `zh` field), `grammar` (with `meaningZh`/`noteZh`), `practiceZh` (one entry per breakdown sentence: Japanese line, Chinese translation line, notes — the Chinese line is also shown under that sentence on /zh/ pages), and `level` fields. Every `news` segment also gets a `zh` (Chinese) and an `en` (English) field with its faithful translation — same facts and order, digits as in the source; identical in the replay. The /zh/ and English pages show them under the sentence (readers can hide them), and validate-episode fails a news sentence without `en`, or without `zh` unless practiceZh covers it

## 日本語で聞くニュース (second show, `scripts/nhNNN.json`)

An all-Japanese daily show for N3–N2 learners, on the same site at `/nihongo/` and `/zh/nihongo/`, with its own RSS (`/nihongo/rss.xml`), numbering from 1 and cover (`site/public/cover-nihongo.jpg`). Apple Podcasts: https://podcasts.apple.com/podcast/id6831520512 . Same JSON as the main show, with these differences:

- Speakers: only `guide` (voice Charon) and `news` (voice Leda), both `"lang": "ja"`, `"rate": "+0%"`. No host, slow or vocab segments, and no English or Chinese in the audio.
- Structure: `guide` greeting with the date only (「こんにちは。日本語で聞くニュースです。今日は11月6日、金曜日です。」) → `guide` hook (1 line, a question or surprise from the story) → 12-15 `news` lines → 10-14 `guide` lines talking about the story in plain, natural Japanese → `guide` transition with `"break": true` → the same `news` lines again → `guide` closing with an open question to the listener, ending 「また明日。」. Target 5:00-6:30. No line announces the news: the first `news` line starts the story itself (never 「今日のニュースです。」, never 「まずはニュースを聞いてみましょう」), and the replay starts the same way.
- Teaching lives on the page: `vocabulary` (6-8), `grammar` (4-5), top-level `quiz` (3 `{q, a}` in Japanese) and `practiceZh`; never read them out as a lesson. Every `news` line has `zh` and `en`.
- Pick stories people want to talk about, and make the title, hook and description earn the click: a concrete number, a surprise or a question that touches daily life. Every claim stays faithful to the sources; no exaggeration or invented tension. `title` is at most ~40 characters.
- Numbers and counters the voice may misread get a `tts` kana field (e.g. 「9か月」→「きゅうかげつ」).
- Audio: `.venv/bin/python tools/gen-nihongo.py nhNNN` (Gemini TTS `gemini-3.8-flash-lite-tts`, timing from `gemini-3.5-transcribe`; key in `$GEMINI_API_KEY` or `~/.config/storyanim/gemini_key`; never print it). It writes `audio/nhNNN.mp3` and `scripts/nhNNN.timing.json`, and prints `CHECK` for lines the transcript does not match. Don't add style instructions to the TTS text: the voice reads them aloud. The remaining pipeline steps are the same as the main show, with `nhNNN` in place of `epNNN`.
- Published daily by cron with `tools/auto-episode.sh nh` at 11:00 Japan time, for listeners at Japan noon.

## Site Architecture (`site/`)

Astro 5 static site. Key files:
- `src/lib/episodes.ts` — loads episode JSONs, builds timing, types
- `src/pages/[...lang]/ep/[id].astro` — episode page with player, transcript, practice mode
- `src/pages/[...lang]/index.astro`, `about.astro` — landing / about page
- `src/lib/i18n.ts` — one page per language, like jpnotes.dev: English at `/…/`, Chinese at `/zh/…/` (`[...lang]` = undefined | `zh`). Write UI text with both `class="i18n-en"` / `class="i18n-zh"` siblings; after the build `astro.config.mjs` (`stripOtherLang`) keeps only the page's own language. `Layout.astro` sets `lang`, hreflang/x-default, and redirects to the reader's saved language (`jdn-lang`; a zh browser with none saved only from the English home page). Internal links go through `lp(path, lang)`
- `src/pages/rss.xml.ts` — podcast RSS feed
- `src/pages/sitemap.xml.ts` — sitemap
- `src/layouts/Layout.astro` — base layout with GA4, theme/lang toggle

Features: synced transcript, furigana, vocab click tooltips, Japanese-only mode (纯日语: just the first news reading, auto-play continues in it), practice mode (精听), lock-screen title = the piece of the current sentence being read (Media Session; lock screens show about two lines, so long sentences are split by time, `LOCK_MAX`), playlist panel in the player (order oldest/newest first and level filter; auto-play follows it; data from `/episodes.json`; auto-play and picking from the list while playing swap the next page in place on the same `<audio>` (`swapIn`), because iOS won't start audio on a freshly loaded page without a tap), translation under each sentence (zh on /zh/, en on English pages; 译文/Translation toggle), playback speed control, dark mode, EN/中文 toggle, font size toggle (S/M/L), localStorage progress tracking (global preferences: theme, language, font size, speed `jdn-speed`, mode `jdn-mode` (full text / Japanese only — practice is never saved), vocab/grammar section open `jdn-review-open`, translation lines `jdn-tr`, playlist order `jdn-order` and level `jdn-pl-level`, auto-play; per episode: position `jdn-epNNN`, listened/practiced), collapsible vocab/grammar section, keyboard shortcuts.

## Versioning

Cache invalidation is **per-episode**, via the `contentVersion` field (format `YYYYMMDDNN`) in each `scripts/epNNN.json`. When an episode's content/timing changes, bump **only that episode's** `contentVersion`. Display-only fixes that leave audio/timing untouched (e.g. furigana corrections) do **not** need a bump — bumping would needlessly clear listeners' saved playback positions. The episode page (`[...lang]/ep/[id].astro`) stores it as `ver` alongside the saved playback position in `jdn-ep<NNN>`; on load, if the stored `ver` no longer matches, only that one episode's saved position is dropped — every other episode's progress is left intact. New episodes get a `contentVersion` at creation.

(Legacy: there used to be a single global `PAGE_VERSION` in `Layout.astro` that wiped *all* `jdn-ep*` entries on any change. It was removed in favor of the per-episode field — don't reintroduce it.)

## Tools

- `tools/gen-episode.py` — TTS audio generation + timing manifest
- `tools/add-furigana.py` — adds ruby HTML + vocab highlights to Japanese segments (uses pykakasi)
- `tools/gen-subtitles.py` — generates VTT/SRT from timing data
- `tools/validate-episode.py` — schema + content-rule check (host has no Japanese, vocab has `zh`, ja-segments have `ruby`, etc.). Run with `epNNN`, no args (all), or `--staged` (git pre-commit).
- `tools/audit-furigana.py` — flags suspicious pykakasi readings (multi-reading kanji like 日/時/人/間, special date readings ついたち〜とおか, mis-splits, rendaku). Report-only; fix flagged readings in the JSON by hand. `--readings` dumps every distinct base=reading pair.
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
- Companion site: `jpnotes.dev`. Each grammar point is linked to its jpnotes lesson section at build time (`site/src/lib/jpnotes.ts`, matching the pattern against `site/src/data/jpnotes-index.json`; unmatched → that level's `/N?_grammar_list/`). The links appear on grammar cards and in the RSS show notes ("Grammar in this episode"), tagged `utm_source=podcast&utm_medium=web|rss`. Refresh the index with `tools/update-jpnotes-index.sh` after jpnotes lessons change. The old per-script `jpnotesLink` field is unused (its URLs 404) — don't write it in new scripts.
- Fonts: Fraunces (display), Outfit (body, PingFang SC for Chinese); Japanese uses system fonts first — Mincho (Hiragino Mincho / Yu Mincho, Noto Serif JP fallback) for transcript/practice/examples, Gothic (Hiragino Kaku Gothic, Noto Sans JP fallback) for titles and UI; furigana stays Gothic
- Themes (header button cycles light → warm → dark, saved in `theme`): light = jpnotes.dev "paper" #f6f4ef with deep red #b8283f (default); warm = the original yellow paper #F3EDDA with #C23B22; dark = #14141e with #e94560. Tokens at the top of `site/src/styles/global.css`.
- Apple Podcasts: https://podcasts.apple.com/podcast/id1896815841
- Spotify: https://open.spotify.com/show/033nVZrL6xnSJDxcXc9PMQ
- YouTube: https://www.youtube.com/playlist?list=PLFPcxHB9z1CRXO7aEgo5qE_jP_E3cXwKb
- RSS: `https://podcast.jpnotes.dev/rss.xml`
