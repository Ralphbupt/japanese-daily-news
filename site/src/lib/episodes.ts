import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

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
  jpnotesLink?: string;
}

export interface RawEpisode {
  episode: number;
  title: string;
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
  description: string;
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
function buildDescription(raw: RawEpisode): string {
  const intro = raw.segments.find(s => s.speaker === 'host')?.text || '';
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
  const base = summary || raw.title;
  const level = raw.level ? ` Level ${raw.level}.` : '';
  return `${base} Learn Japanese with native audio, furigana, vocabulary and grammar.${level}`;
}

const PAUSE_AFTER: Record<string, number> = {
  host: 0.6,
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

function processEpisode(raw: RawEpisode): ProcessedEpisode {
  const paddedNum = padNum(raw.episode);
  const id = `ep${paddedNum}`;
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

  const description = buildDescription(raw);

  return {
    ...raw,
    id,
    paddedNum,
    timedSegments,
    vocabulary: raw.vocabulary ?? [],
    grammar: raw.grammar ?? [],
    practiceZh: raw.practiceZh ?? [],
    level: raw.level ?? '',
    description,
    hasTimingData,
  };
}

export function getAllEpisodes(): ProcessedEpisode[] {
  return fs.readdirSync(SCRIPTS_DIR)
    .filter(f => /^ep\d+\.json$/.test(f))
    .sort()
    .reverse()
    .map(f => processEpisode(
      JSON.parse(fs.readFileSync(path.join(SCRIPTS_DIR, f), 'utf-8'))
    ));
}

export function getEpisode(paddedNum: string): ProcessedEpisode | undefined {
  const fp = path.join(SCRIPTS_DIR, `ep${paddedNum}.json`);
  if (!fs.existsSync(fp)) return undefined;
  return processEpisode(JSON.parse(fs.readFileSync(fp, 'utf-8')));
}
