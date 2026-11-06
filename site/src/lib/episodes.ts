import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { jpnotesLink, type JpnotesLink } from './jpnotes';
import type { Channel } from './i18n';

const SCRIPTS_DIR = fileURLToPath(new URL('../../../scripts', import.meta.url));

export interface Character {
  voice: string;
  role: string;
  lang: string;
  rate: string;
}

export interface Segment {
  speaker: string;
  text: string;
  ruby?: string;
  /** Chinese translation of a news sentence (shown on /zh/ pages). Sentences
   *  the breakdown covers also get one from practiceZh. */
  zh?: string;
  /** English translation of a news sentence (shown on English pages). */
  en?: string;
  /** What the TTS voice is given, when it differs from text (misreadings). */
  tts?: string;
}

export interface TimedSegment extends Segment {
  start: number;
  end: number;
  index: number;
}

export interface VocabItem {
  ja: string;
  reading: string;
  en: string;
  zh?: string;
}

export interface GrammarPoint {
  pattern: string;
  meaning: string;
  meaningZh?: string;
  formation: string;
  example: string;
  translation: string;
  note?: string;
  noteZh?: string;
  level?: string;
  /** Legacy field from older scripts; the URLs are wrong, use `jpnotes`. */
  jpnotesLink?: string;
  /** The matching jpnotes.dev lesson section, worked out at build time. */
  jpnotes?: JpnotesLink;
}

export interface RawEpisode {
  episode: number;
  title: string;
  /** Headline in Chinese / English, for the /zh/ and English pages' titles. */
  titleZh?: string;
  titleEn?: string;
  date: string;
  source: string;
  characters: Record<string, Character>;
  segments: Segment[];
  vocabulary?: VocabItem[];
  grammar?: GrammarPoint[];
  level?: string;
  practiceZh?: string[];
  /** Per-episode cache key (YYYYMMDDNN). Bump only when THIS episode's
   *  content/timing changes — invalidates only this episode's saved playback
   *  position, leaving every other episode's progress intact. */
  contentVersion?: string;
}

export interface ProcessedEpisode extends RawEpisode {
  id: string;
  paddedNum: string;
  timedSegments: TimedSegment[];
  vocabulary: VocabItem[];
  grammar: GrammarPoint[];
  practiceZh: string[];
  level: string;
  /** Story summary extracted from the host intro (no boilerplate). */
  summary: string;
  description: string;
  /** Chinese meta description for /zh/ pages. */
  descriptionZh: string;
  /** Japanese sentence → its Chinese translation (from practiceZh), shown
   *  under the transcript on /zh/ pages. */
  zhLines: Record<string, string>;
  /** Japanese sentence → its English translation (segment en fields). */
  enLines: Record<string, string>;
  hasTimingData: boolean;
}

function padNum(n: number): string {
  return String(n).padStart(3, '0');
}

// Build a unique, descriptive meta description per episode. The host intro
// follows "Welcome... I'm Maya. Today is <date>. Today's story: <summary>. Let's
// listen." — we extract just the story summary so each page has a distinct,
// content-rich description (the old logic emitted the same boilerplate greeting
// for every episode, which Google treats as duplicate/thin content).
function buildSummary(raw: RawEpisode): string {
  // The all-Japanese show opens with a greeting, then the hook (its summary).
  const guide = raw.segments.filter(s => s.speaker === 'guide');
  const intro = (guide.length ? guide[1] : raw.segments.find(s => s.speaker === 'host'))?.text || '';
  let summary = '';
  const m = intro.match(/Today['’]s story\b[^.!?]*?:\s*(.+?)(?:\s*Let['’]s listen\.?\s*)?$/i);
  if (m) summary = m[1].trim();
  if (!summary) {
    const drop = /welcome to japanese daily news|i['’]m maya|your host|today is\b|let['’]s listen/i;
    summary = intro
      .split(/(?<=[.!?])\s+/)
      .filter(s => s && !drop.test(s))
      .join(' ')
      .trim();
  }
  if (summary && !/[.!?]$/.test(summary)) summary += '.';
  if (summary) summary = summary.charAt(0).toUpperCase() + summary.slice(1);
  return summary;
}

function buildDescription(raw: RawEpisode, summary: string): string {
  const base = summary || raw.title;
  const level = raw.level ? ` Level ${raw.level}.` : '';
  return `${base} Learn Japanese with native audio, furigana, vocabulary and grammar.${level}`;
}

const LEVEL_ZH: Record<string, string> = { 'N5-N4': '初级 N5–N4', 'N4-N3': '中级 N4–N3', 'N3-N2': '中高级 N3–N2' };

function buildDescriptionZh(raw: RawEpisode): string {
  const head = raw.titleZh ? `${raw.titleZh}。` : `${raw.title}。`;
  const level = raw.level ? `（${LEVEL_ZH[raw.level] || raw.level}）` : '';
  if (raw.characters.guide) return `${head}全日语新闻听力${level}：新闻朗读加日语讲解，附振假名、中文翻译、词汇和语法。`;
  return `${head}用真实日语新闻练听力${level}：自然语速朗读、逐句讲解，附振假名、中文翻译、词汇和语法。`;
}

// Lines every episode opens / closes with.
const FIXED_ZH: Record<string, string> = {
  '今日のニュースです。': '今天的新闻。',
  'また明日。': '明天见。',
};

/** Japanese sentence → Chinese: a segment's own zh field, else practiceZh
 *  ("Japanese sentence\nChinese translation\nnotes"), else the fixed lines. */
function buildZhLines(raw: RawEpisode): Record<string, string> {
  const out: Record<string, string> = { ...FIXED_ZH };
  for (const seg of raw.segments) {
    if (seg.zh) out[seg.text.trim()] = seg.zh.trim();
  }
  for (const entry of raw.practiceZh ?? []) {
    const [ja, zh] = entry.split('\n');
    if (ja && zh && !(ja.trim() in out && !(ja.trim() in FIXED_ZH))) out[ja.trim()] = zh.trim();
  }
  return out;
}

const FIXED_EN: Record<string, string> = {
  '今日のニュースです。': "Here's today's news.",
  'また明日。': 'See you tomorrow.',
};

function buildEnLines(raw: RawEpisode): Record<string, string> {
  const out: Record<string, string> = { ...FIXED_EN };
  for (const seg of raw.segments) {
    if (seg.en) out[seg.text.trim()] = seg.en.trim();
  }
  return out;
}

const PAUSE_AFTER: Record<string, number> = {
  host: 0.6,
  guide: 0.7,
  news: 0.7,
  slow: 0.8,
  vocab: 0.4,
};

function estimateDuration(text: string, lang: string, rate: string): number {
  const rateFactor = 1 + parseInt(rate) / 100;
  if (lang === 'ja') {
    return text.length / (4.5 * rateFactor);
  }
  return text.split(/\s+/).length / (2.5 * rateFactor);
}

function processEpisode(raw: RawEpisode, prefix = 'ep'): ProcessedEpisode {
  const paddedNum = padNum(raw.episode);
  const id = `${prefix}${paddedNum}`;
  let hasTimingData = false;

  let t = 1.5;
  const timedSegments: TimedSegment[] = raw.segments.map((seg, i) => {
    const char = raw.characters[seg.speaker];
    const dur = estimateDuration(seg.text, char.lang, char.rate);
    const start = t;
    const end = t + dur;
    t = end + (PAUSE_AFTER[seg.speaker] ?? 0.6);
    return {
      ...seg,
      start: Math.round(start * 1000) / 1000,
      end: Math.round(end * 1000) / 1000,
      index: i,
    };
  });

  const timingPath = path.join(SCRIPTS_DIR, `${id}.timing.json`);
  if (fs.existsSync(timingPath)) {
    try {
      const data = JSON.parse(fs.readFileSync(timingPath, 'utf-8'));
      if (Array.isArray(data.segments)) {
        data.segments.forEach((s: { start: number; end: number }, i: number) => {
          if (timedSegments[i]) {
            timedSegments[i].start = s.start;
            timedSegments[i].end = s.end;
          }
        });
        hasTimingData = true;
      }
    } catch { /* use estimates */ }
  }

  const summary = buildSummary(raw);
  const description = buildDescription(raw, summary);

  return {
    ...raw,
    id,
    paddedNum,
    timedSegments,
    vocabulary: raw.vocabulary ?? [],
    grammar: (raw.grammar ?? []).map(g => ({ ...g, jpnotes: jpnotesLink(g.pattern, g.level) })),
    practiceZh: raw.practiceZh ?? [],
    level: raw.level ?? '',
    summary,
    description,
    descriptionZh: buildDescriptionZh(raw),
    zhLines: buildZhLines(raw),
    enLines: buildEnLines(raw),
    hasTimingData,
  };
}

/** Episode files per show: scripts/epNNN.json (main), scripts/nhNNN.json (nihongo). */
export function getAllEpisodes(channel: Channel = 'main'): ProcessedEpisode[] {
  const prefix = channel === 'nihongo' ? 'nh' : 'ep';
  const file = new RegExp(`^${prefix}\\d+\\.json$`);
  return fs.readdirSync(SCRIPTS_DIR)
    .filter(f => file.test(f))
    .sort()
    .reverse()
    .map(f => processEpisode(
      JSON.parse(fs.readFileSync(path.join(SCRIPTS_DIR, f), 'utf-8')),
      prefix,
    ));
}

export function getEpisode(paddedNum: string): ProcessedEpisode | undefined {
  const fp = path.join(SCRIPTS_DIR, `ep${paddedNum}.json`);
  if (!fs.existsSync(fp)) return undefined;
  return processEpisode(JSON.parse(fs.readFileSync(fp, 'utf-8')));
}
