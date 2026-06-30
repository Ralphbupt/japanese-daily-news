#!/usr/bin/env bash
# Autonomous daily-episode generator for cron.
#   Usage: tools/auto-episode.sh n5|n4
#   Env:   JDN_DRY=1  -> generate everything but do NOT commit/push (for testing)
#
# Drives a headless Claude Code (Opus 4.8) session that finds real Japanese
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
  *)  echo "usage: $0 n5|n4" >&2; exit 2;;
esac

mkdir -p "$REPO/logs"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$REPO/logs/auto-$STAMP-$LEVEL.log"

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
   suitable for the level. Read the titles/topics of the last ~10 episodes and
   AVOID repeating a story already covered. NEVER fabricate news.
3. Write scripts/epNNN.json per the Script Format and ALL Critical rules:
   host (Maya) has ZERO Japanese characters and ZERO romaji; 9-10 news segments;
   breakdown; full replay; quiz; closing. Include vocabulary (with zh), grammar
   (with meaningZh/noteZh), practiceZh, level="$LEVELFIELD", and contentVersion
   = today's date YYYYMMDD followed by "01".
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

echo "[$STAMP] level=$LEVEL dry=${JDN_DRY:-0} -> $LOG"
claude -p "$PROMPT" \
  --model claude-opus-4-8 \
  --dangerously-skip-permissions \
  >>"$LOG" 2>&1

echo "[$(date -u +%Y%m%dT%H%M%SZ)] done. tail of log:"
tail -n 20 "$LOG"
