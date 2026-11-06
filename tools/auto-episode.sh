#!/usr/bin/env bash
# Autonomous daily-episode generator for cron.
#   Usage: tools/auto-episode.sh n5|n4|nh   (nh = the all-Japanese show, nhNNN)
#   Env:   JDN_DRY=1  -> generate everything but do NOT commit/push (for testing)
#
# Drives a headless Claude Code (Fable 5) session that finds real Japanese
# news, writes scripts/epNNN.json, runs the full pipeline (furigana, validate,
# audit, audio, subtitles, copy assets) and pushes -> Cloudflare auto-deploys.
#
# Toolchain set up in userspace (no sudo): static ffmpeg/ffprobe in ~/.local/bin,
# .venv built via uv (python 3.11) with edge-tts + pykakasi.
set -euo pipefail

export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
REPO="/home/work/japanese-daily-news"
cd "$REPO"

LEVEL="${1:-n5}"
case "$LEVEL" in
  n5) LEVELFIELD="N5-N4"; LEVELDESC="a BEGINNER-friendly, lighter/simpler real news story (morning N5)"
      STYLE="Target duration ~7:30-8:00 with 9-10 news segments, per CLAUDE.md.";;
  n4) LEVELFIELD="N4-N3"; LEVELDESC="a more substantial INTERMEDIATE real news story (evening N4)"
      STYLE="EVENING STYLE (overrides CLAUDE.md defaults): make this episode LONGER and DENSER in Japanese. Target ~9:00-10:00. Use 13-15 news segments and more breakdown sentences so there is MORE Japanese listening. Keep host (Maya) commentary MINIMAL: one short line per intro/translation, no verbose transitions or extra explanation. Prioritize Japanese volume over English commentary.";;
  nh) LEVELFIELD="N3-N2"; LEVELDESC=""; STYLE="";;
  *)  echo "usage: $0 n5|n4|nh" >&2; exit 2;;
esac

mkdir -p "$REPO/logs"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$REPO/logs/auto-$STAMP-$LEVEL.log"

# Stamp episodes with the Beijing calendar date. Cron is pinned to Asia/Shanghai
# (CRON_TZ), but the machine's local TZ is America/New_York — the morning Beijing
# run fires in the NY evening, one calendar day behind. Without this the headless
# session would read "today" as the NY date and label the episode a day early.
TODAY_BJ="$(TZ=Asia/Shanghai date +%Y-%m-%d)"
VER_BJ="$(TZ=Asia/Shanghai date +%Y%m%d)01"

# Keep local main in sync before generating (cron may run while you also work).
git pull --rebase --autostash origin main >>"$LOG" 2>&1 || true

DRYLINE=""
if [ "${JDN_DRY:-0}" = "1" ]; then
  DRYLINE='DRY RUN: do everything through step 5, but DO NOT run step 6 (no git add/commit/push). Instead print "DRY RUN COMPLETE" and list every file you created or changed.'
fi

read -r -d '' PROMPT <<EOF || true
You are an autonomous content generator for the "Japanese Daily News" podcast.
Work in the repo at $REPO. FIRST read CLAUDE.md in full and follow its
"Full Pipeline for a New Episode", "Script Format", and "Critical rules"
sections EXACTLY. Then produce ONE brand-new episode for today.

This run's level: $LEVELDESC. The episode JSON "level" field MUST be "$LEVELFIELD".

Steps:
1. Next id: list scripts/ep*.json, take the highest NNN, add 1, zero-pad (e.g. ep039).
2. Find a REAL, recent (last few days) Japanese news story with WebSearch
   (fall back to WebFetch of NHK / NHK NEWS WEB EASY / major outlets). Pick one
   suitable for the level. Then dedupe against ALL past episodes: run
     grep -h '"title"' scripts/ep*.json
   to list every previous title (they are short one-line headlines) and AVOID
   any story already covered in ANY earlier episode, not just recent ones —
   e.g. the same event, festival, launch, or announcement under different
   wording. NEVER fabricate news.
3. Write scripts/epNNN.json per the Script Format and ALL Critical rules:
   host (Maya) has ZERO Japanese characters and ZERO romaji; 9-10 news segments;
   breakdown; full replay; quiz; closing. Follow CLAUDE.md's "Vocab selection"
   rules: no proper nouns, numbers or too-basic words, and a sentence with
   nothing worth teaching gets no vocab segment — never pad to a quota.
   Follow "Writing for the ear" (no long lists of names; uncommon place/person
   names get a "tts" kana field) and do the "Self-check" (level, natural
   Japanese, every quiz answer clearly stated in the news) before step 4.
   Include titleZh and titleEn (the headline in Chinese / English — see
   CLAUDE.md), "zh" (Chinese) and "en" (English) translations on every news segment, vocabulary
   (with zh), grammar (with meaningZh/noteZh), practiceZh, level="$LEVELFIELD". The "date" field MUST
   be exactly "$TODAY_BJ" (today's Beijing date — do NOT use your own notion of
   today), and contentVersion MUST be exactly "$VER_BJ".
   The "title" field MUST be a SHORT Japanese headline, max ~40 characters,
   ONE clause, NO date, NO details (e.g. 「高級ぶどう「ルビーロマン」が金沢で初競り、一房100万円」).
   It appears as the episode title in podcast apps and the site — put the full
   story details in the news segments, NEVER in the title.
   STYLE FOR THIS RUN: $STYLE
4. Run the pipeline. Use .venv/bin/python for ALL python tools (system python3 is
   too old). ffmpeg/ffprobe are already on PATH:
     .venv/bin/python tools/add-furigana.py epNNN
     .venv/bin/python tools/validate-episode.py epNNN      # must pass; fix until clean
     .venv/bin/python tools/audit-furigana.py epNNN        # hand-fix any SUSPECT readings in the JSON
     .venv/bin/python tools/gen-episode.py epNNN
     .venv/bin/python tools/gen-subtitles.py epNNN
     cp audio/epNNN.mp3 site/public/audio/
     cp subtitles/epNNN.* site/public/subtitles/
5. Re-run validate-episode.py epNNN to confirm it is clean.
6. Commit and push:
     git add -A
     git commit -m "Add epNNN: <short English summary of the story>"
     git push origin main
   (Cloudflare Pages auto-deploys on push.)

Only ADD the new episode. Do NOT modify other episodes or bump their
contentVersion. Keep host commentary concise. If validate fails, fix and re-run
until it passes before committing.
$DRYLINE
EOF

if [ "$LEVEL" = "nh" ]; then
  read -r -d '' PROMPT <<EOF || true
You are an autonomous content generator for the all-Japanese podcast
「日本語で聞くニュース」. Work in the repo at $REPO. FIRST read CLAUDE.md in full,
especially the section "日本語で聞くニュース", and read scripts/nh001.json as the
model of the format. Then produce ONE brand-new episode for today.

Steps:
1. Next id: list scripts/nh*.json (not *.timing.json), take the highest NNN, add 1, zero-pad (e.g. nh002).
   The "episode" field is that number.
2. Find a REAL Japanese news story from the last 1-2 days with WebSearch (fall back
   to WebFetch of NHK / major outlets), and confirm its facts in at least two
   sources. Choose the story listeners would most want to tap on and talk about:
   daily life, money, work, food, travel, society, a surprising number. Avoid
   stories that are only a list of officials or companies. Dedupe against all
   past episodes of both shows:
     grep -h '"title"' scripts/ep*.json scripts/nh*.json
   NEVER fabricate news, and never exaggerate beyond the sources.
3. Write scripts/nhNNN.json exactly as CLAUDE.md describes for this show:
   level="$LEVELFIELD", date exactly "$TODAY_BJ", contentVersion exactly "$VER_BJ",
   source naming the outlets used, titleZh, titleEn, characters copied from nh001.
   The title, hook and closing question must earn the click while staying faithful.
   Open exactly as CLAUDE.md says: greeting, hook, then the news itself. The talk must explain why the news matters, in
   easy spoken Japanese, and must not be a vocabulary or grammar lesson. Facts in
   the talk must come from the sources. Do the "Self-check" in CLAUDE.md first.
4. Run the pipeline. Use .venv/bin/python for ALL python tools:
     .venv/bin/python tools/add-furigana.py nhNNN
     .venv/bin/python tools/validate-episode.py nhNNN      # must pass; fix until clean
     .venv/bin/python tools/audit-furigana.py nhNNN        # hand-fix any SUSPECT readings in the JSON
     .venv/bin/python tools/gen-nihongo.py nhNNN
   If gen-nihongo prints CHECK for a line, read what it heard. If the voice misread
   something, add a "tts" kana field to that segment and run gen-nihongo again.
   If the audio or timing fails, stop and report the error: never publish an
   episode without audio.
     .venv/bin/python tools/gen-subtitles.py nhNNN
     cp audio/nhNNN.mp3 site/public/audio/
     cp subtitles/nhNNN.* site/public/subtitles/
5. Re-run validate-episode.py nhNNN to confirm it is clean.
6. Commit and push only the new episode's files:
     git add scripts/nhNNN.json scripts/nhNNN.timing.json audio/nhNNN.mp3 subtitles/nhNNN.vtt subtitles/nhNNN.srt
     git commit -m "Add nhNNN: <short English summary of the story>"
     git push origin main
   (Cloudflare Pages auto-deploys on push.)

Only ADD the new episode. Do NOT modify other episodes.
$DRYLINE
EOF
fi

echo "[$STAMP] level=$LEVEL dry=${JDN_DRY:-0} -> $LOG"
claude -p "$PROMPT" \
  --model claude-opus-5-5 \
  --dangerously-skip-permissions \
  >>"$LOG" 2>&1

echo "[$(date -u +%Y%m%dT%H%M%SZ)] done. tail of log:"
tail -n 20 "$LOG"
