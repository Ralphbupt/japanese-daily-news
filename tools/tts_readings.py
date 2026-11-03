"""Words the TTS voice misreads, rewritten into kana before speaking.

Applied by gen-episode.py to every Japanese segment (news / slow) unless the
segment has its own "tts" field. Transcript, furigana and subtitles keep the
written form. Add a rule when tools/qa-audio.py reports a misreading that can
recur in future episodes (common words, place names that come up often);
one-off fixes go in the segment's "tts" field instead.

Seeded from jpnotes.dev's build-audio.py TTS_READINGS (rules checked there by
transcribing every mp3 with Whisper, 2026-10-30), keeping the general ones.
"""

import re

KANJI = r"一-鿿々"

TTS_READINGS = [
    (r"何時(?!間|でも|か(?!ら)|も)", "なんじ"),        # not いつ
    (r"九時間", "きゅうじかん"),                        # not くじかん
    (rf"(?<![{KANJI}])町(?![{KANJI}])", "まち"),        # standalone 町
    (r"(?<=[ぁ-ん])気味", "ぎみ"),                      # 遅れ気味, not きみ
    (r"(?<=て)来(?=な)", "こ"),                         # 持って来なければ
    (r"気を遣", "気をつか"),
    (r"寒気(?=[もが]する)", "さむけ"),
    (r"間違", "まちが"),
    (r"小さな", "ちいさな"),
    (r"平仮名", "ひらがな"),
    (r"半年", "はんとし"),
    (r"(?<=暑い)日", "ひ"),
    (r"人が少ない", "ひとが少ない"),
    (r"辛(?=い|く)", "から"),                           # news: spicy, not つらい
    # Place names found misread in this podcast (tools/qa-audio.py)
    (r"網走", "あばしり"),                              # ep253: read あまぼし
]

_COMPILED = [(re.compile(p), r) for p, r in TTS_READINGS]


def apply_readings(text):
    for pat, rep in _COMPILED:
        text = pat.sub(rep, text)
    return text
