// Links an episode's grammar points to the matching section of a jpnotes.dev
// lesson. The index is jpnotes.dev/search-index.json (one entry per grammar
// point: lesson id, section anchor, title, level), copied into
// src/data/jpnotes-index.json by tools/update-jpnotes-index.sh.
//
// A point is matched by its pattern: the Japanese form at the start of a
// jpnotes title has to start the episode's pattern (〜として → 〜として（作为）),
// polite forms are folded to plain ones first, and a few common patterns whose
// wording differs go through ALIASES. Nothing matched → the level's grammar
// checklist, so every point still gets a useful link.
import index from '../data/jpnotes-index.json';

const SITE = 'https://jpnotes.dev';
const SKIP = new Set(['lesson00', 'lesson75', 'lesson92']);   // kana chart, review lessons
const LEVELS = ['N1', 'N2', 'N3', 'N4', 'N5'];

interface Entry { id: string; s: string; t: string; l: string }
export interface JpnotesLink { url: string; title: string; matched: boolean }

// The index stores titles and anchors HTML-escaped (&quot; …); the page's id attribute is the decoded text.
const unescape = (x: string) => x.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&');
const entries = (index as Entry[])
  .filter(p => p.s && p.id.startsWith('lesson') && !SKIP.has(p.id))
  .map(p => ({ ...p, s: unescape(p.s), t: unescape(p.t) }));
const HIRA = /[぀-ゟ]/;

// Each title's Japanese forms: 「〜せいで / 〜せいか（都怪…）」 → せいで, せいか.
const terms: { tok: string; p: Entry }[] = [];
for (const p of entries) {
  const head = p.t.split(/[（(]/)[0];
  for (const raw of head.split(/\s*[/／・、]\s*|\s+vs\s+|\s+—\s+/)) {
    const tok = raw.replace(/[〜~\s「」]/g, '');
    if (tok.length >= 2 && HIRA.test(tok) && !/[a-zA-Z]/.test(tok)) terms.push({ tok, p });
  }
}

const POLITE: [string, string][] = [
  ['なければなりません', 'なければならない'], ['かもしれません', 'かもしれない'],
  ['てはいけません', 'てはいけない'], ['ませんでした', 'なかった'],
  ['ています', 'ている'], ['ていました', 'ていた'], ['でしょう', 'だろう'],
  ['ことができます', 'ことができる'], ['によりますと', 'によると'],
];

function norm(s: string): string {
  let out = (s || '').replace(/（[^）]*）|\([^)]*\)|\+.*$/g, '').replace(/[〜~\s「」・…。、]/g, '');
  for (const [a, b] of POLITE) out = out.split(a).join(b);
  return out;
}

// Patterns the title match misses: [test on the raw pattern, title fragment].
const ALIASES: [RegExp, string][] = [
  [/と呼ばれ|と言われ|と期待され|られ(る|て|た)|され(る|て|た)/, '受身形详解'],
  [/様態/, '〜そうだ ①'],
  [/伝聞/, '〜そうだ ②'],
  [/^〜?と（条件）|^〜?と\(条件\)/, '〜と（自然'],
  [/^〜?ば$|〜ば（/, '〜ば（假定'],
  [/^〜?たら/, '〜たら（完成'],
  [/より(?!ほか)/, '比较表达'],
  [/^〜?ため(に|の)?$/, '〜ために（目的'],
  [/予定/, '〜予定だ'],
  [/^〜?ぶり/, '〜ぶりに'],
  [/以来/, '〜て以来'],
  [/^〜?て(くる|きた|きます|きました)|^〜?ていく/, '〜ていく / 〜てくる'],
  [/^〜?うち/, '〜うちに'],
  [/^〜?らしい/, '〜らしい'],
];

const levelNo = (l?: string) => (l && LEVELS.includes(l) ? LEVELS.indexOf(l) : -1);   // N1 → 0 … N5 → 4
const urlOf = (p: Entry) => `${SITE}/${p.id}/#${encodeURI(p.s)}`;

function byTitle(fragment: string): Entry | undefined {
  return entries.find(p => p.t.startsWith(fragment) || p.t.includes(fragment));
}

// Lexicographic: does score a beat score b?
function better(a: number[], b: number[]): boolean {
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] > b[i];
  return false;
}

const cache = new Map<string, JpnotesLink>();

export function jpnotesLink(pattern: string, level?: string): JpnotesLink {
  const key = pattern + '|' + (level || '');
  const hit = cache.get(key);
  if (hit) return hit;
  let found: Entry | undefined;
  for (const [re, frag] of ALIASES) if (re.test(pattern)) { found = byTitle(frag); if (found) break; }
  if (!found) {
    const pat = norm(pattern), lv = levelNo(level);
    let best: { score: number[]; p: Entry } | undefined;
    for (const { tok, p } of terms) {
      const starts = pat.startsWith(tok) || (pat.length >= 2 && tok.startsWith(pat) && tok.length - pat.length <= 1);
      if (!starts && !(tok.length >= 4 && pat.includes(tok))) continue;
      // Not a lesson two or more levels harder than the episode's point (〜とは at N4 ≠ the N1 lesson).
      if (lv >= 0 && levelNo(p.l) >= 0 && lv - levelNo(p.l) >= 2) continue;
      const score = [starts ? 1 : 0, tok.length, p.l === level ? 1 : 0];
      if (!best || better(score, best.score)) best = { score, p };
    }
    found = best?.p;
  }
  const link: JpnotesLink = found
    ? { url: urlOf(found), title: found.t, matched: true }
    : { url: level && LEVELS.includes(level) ? `${SITE}/${level}_grammar_list/` : `${SITE}/grammar/`, title: '', matched: false };
  cache.set(key, link);
  return link;
}

// Tags a jpnotes URL with where the click came from (kept ahead of the #anchor).
export function withUtm(url: string, medium: string): string {
  const [base, hash] = url.split('#');
  return `${base}?utm_source=podcast&utm_medium=${medium}${hash ? '#' + hash : ''}`;
}
