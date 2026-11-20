import { getAllEpisodes } from './episodes';
import { withUtm } from './jpnotes';
import { COVER, RSS_PATH, SHOW_NAME, chp, type Channel } from './i18n';
import { audioUrl, audioBytes } from './audio';

const SITE = 'https://podcast.jpnotes.dev';

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

// Show notes: the summary, then this episode's grammar points, each linked to
// its jpnotes.dev lesson section (podcast apps render this HTML subset).
// Chapters as timestamps in the show notes ("00:00 Intro", one per line), which Spotify
// and other apps turn into chapters. Every episode has the same shape, so the starts come
// from its timing: the main show is intro, news, breakdown, news again, quiz; the
// all-Japanese one is opening, news, talk, news again. A chapter starts at the line that
// introduces it. Fewer than three chapters (an odd old episode) gives none.
type Ep = ReturnType<typeof getAllEpisodes>[number];
function stamp(sec: number): string {
  const s = Math.floor(sec), h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, r = s % 60;
  const mm = String(m).padStart(2, '0'), ss = String(r).padStart(2, '0');
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}
function chapters(ep: Ep, channel: Channel): string {
  const seg = ep.timedSegments;
  const isNews = (i: number) => seg[i]?.speaker === 'news';
  const after = (from: number, ok: (i: number) => boolean) => {
    for (let i = Math.max(from, 0); i < seg.length; i++) if (ok(i)) return i;
    return -1;
  };
  const news1 = after(0, isNews);
  const talk = news1 < 0 ? -1 : after(news1, i => !isNews(i));
  const news2 = talk < 0 ? -1 : after(talk, isNews);
  const lead = (i: number) => (i > 0 && !isNews(i - 1) ? i - 1 : i);   // the line announcing it
  const quiz = news2 < 0 ? -1 : after(news2, i => !isNews(i) && i < seg.length - 2);
  const labels = channel === 'nihongo'
    ? ['オープニング', 'ニュース', 'ニュースについて', 'もう一度ニュース']
    : ['Intro', 'The news in Japanese', 'Sentence by sentence', 'The news again', 'Quiz'];
  const starts = channel === 'nihongo'
    ? [0, news1, talk, news2 < 0 ? -1 : lead(news2)]
    : [0, news1, talk, news2 < 0 ? -1 : lead(news2), quiz];
  const list: [number, string][] = [];
  starts.forEach((i, k) => {
    if (i < 0) return;
    const t = k === 0 ? 0 : seg[i].start;
    if (list.length && t - list[list.length - 1][0] < 10) return;   // apps want chapters of 10 s or more
    list.push([t, labels[k]]);
  });
  if (list.length < 3) return '';
  return '<p>' + list.map(([t, l]) => `${stamp(t)} ${esc(l)}`).join('<br>') + '</p>';
}

function showNotes(ep: ReturnType<typeof getAllEpisodes>[number]): string {
  let html = `<p>${esc(ep.description)}</p>` + chapters(ep, 'main');
  if (ep.grammar.length) {
    html += '<p>Grammar in this episode:</p><ul>' + ep.grammar.map(g =>
      `<li><a href="${esc(withUtm(g.jpnotes!.url, 'rss'))}">${esc(g.pattern)}</a> — ${esc(g.meaning)}</li>`).join('') + '</ul>';
  }
  if (ep.level === 'N4-N3') {
    html += `<p>Ready for more Japanese? Try our all-Japanese daily show for N3–N2 learners: <a href="${SITE}/nihongo/?utm_source=podcast&amp;utm_medium=rss">${SHOW_NAME.nihongo}</a></p>`;
  }
  html += `<p>Free grammar notes, practice questions and Anki decks for JLPT N5–N1: <a href="${esc(withUtm('https://jpnotes.dev/', 'rss'))}">jpnotes.dev</a></p>`;
  return html.replace(/]]>/g, ']]&gt;');
}

// The all-Japanese show: notes in Japanese too, opening with the episode's hook.
function showNotesJa(ep: ReturnType<typeof getAllEpisodes>[number]): string {
  let html = `<p>${esc(hookJa(ep))}</p>` + chapters(ep, 'nihongo');
  if (ep.grammar.length) {
    html += '<p>今回の文法：</p><ul>' + ep.grammar.map(g =>
      `<li><a href="${esc(withUtm(g.jpnotes!.url, 'rss'))}">${esc(g.pattern)}</a></li>`).join('') + '</ul>';
  }
  html += `<p>難しいと感じたら、英語の解説つきの番組もあります：<a href="${SITE}/?utm_source=podcast&amp;utm_medium=rss">${SHOW_NAME.main}</a></p>`;
  html += `<p>ふりがな、翻訳、単語と文法はウェブサイトで：<a href="${SITE}/nihongo/ep/${ep.paddedNum}/">podcast.jpnotes.dev</a></p>`;
  return html.replace(/]]>/g, ']]&gt;');
}

// Main-show item title: the Japanese headline, then the English one and the level, so
// listeners who search in English ("easy Japanese news N4") find the episode on Spotify,
// where search is the largest source of impressions (2026-11).
function mainTitle(ep: ReturnType<typeof getAllEpisodes>[number]): string {
  let t = `EP ${ep.paddedNum}: ${ep.title}`;
  if (ep.titleEn) t += ` | ${ep.titleEn}`;
  if (ep.level) t += ` (JLPT ${ep.level})`;
  return t;
}

function hookJa(ep: ReturnType<typeof getAllEpisodes>[number]): string {
  return ep.summary.replace(/\.$/, '');
}

// When the daily cron (tools/auto-episode.sh, CRON_TZ=Asia/Shanghai) publishes
// each kind of episode: n5 at 07:00, nh at 10:00, n4 at 19:00 Beijing time. The
// push lands ~5 min later and Cloudflare deploys a few minutes after that.
// `date` is the Beijing calendar date.
const PUBLISH_TIME_BJ: Record<string, string> = {
  'N5-N4': '07:10',
  'N3-N2': '10:10',
  'N4-N3': '19:10',
};

function rfcDate(d: string, level: string): string {
  const time = PUBLISH_TIME_BJ[level] ?? '12:00';
  return new Date(`${d}T${time}:00+08:00`).toUTCString();
}

const SHOW_TEXT: Record<Channel, { description: string; summary: string }> = {
  main: {
    description: 'Easy Japanese listening practice with real news, every day. Two short episodes a day for JLPT N5–N3 learners: Japanese news read by a native voice, a slow sentence-by-sentence breakdown in English, key vocabulary and grammar, and a quick quiz. Learn Japanese on your commute. Ready for more? Try our sister show 日本語で聞くニュース: daily news all in Japanese for N3–N2 learners.',
    summary: 'Easy Japanese listening practice with real news, every day. Two short episodes a day for JLPT N5–N3 learners: Japanese news read by a native voice, a slow sentence-by-sentence breakdown in English, key vocabulary and grammar, and a quick quiz. Hosted by Maya. Transcripts with furigana at podcast.jpnotes.dev. Ready for more? Try our sister show 日本語で聞くニュース: daily news all in Japanese for N3–N2 learners.',
  },
  nihongo: {
    description: 'JLPT N3〜N2の学習者のための、全部日本語のニュース番組です。本物のニュースを聞いて、やさしい日本語の解説を聞いて、もう一度ニュースを聞きます。',
    summary: 'JLPT N3〜N2の学習者のための、全部日本語のニュース番組です。本物のニュースを聞いて、やさしい日本語の解説を聞いて、もう一度ニュースを聞きます。',
  },
};

/** The podcast feed of one show. */
export function buildRss(channel: Channel): Response {
  const episodes = getAllEpisodes(channel);
  const text = SHOW_TEXT[channel];
  const home = `${SITE}${chp('/', 'en', channel)}`.replace(/\/$/, '') || SITE;

  const items = episodes.map(ep => {
    const enclosure = audioUrl(ep.id);
    // <link> ends in a slash, as the pages are served (the slashless address 308-redirects: Search Console listed 181
    // episodes as "Page with redirect", found through this feed, 2026-11-09). <guid> keeps the old address: podcast
    // apps know each episode by it, and a changed guid would show every episode as new.
    const link = `${SITE}${chp(`/ep/${ep.paddedNum}`, 'en', channel)}`;

    const length = audioBytes(ep.id);

    const lastSeg = ep.timedSegments[ep.timedSegments.length - 1];
    const durationSec = lastSeg ? Math.round(lastSeg.end + 2) : 0;

    return `    <item>
      <title>${escapeXml(channel === 'nihongo' ? ep.title : mainTitle(ep))}</title>
      <link>${link}/</link>
      <guid isPermaLink="true">${link}</guid>
      <pubDate>${rfcDate(ep.date, ep.level)}</pubDate>
      <description><![CDATA[${channel === 'nihongo' ? showNotesJa(ep) : showNotes(ep)}]]></description>
      <enclosure url="${enclosure}" length="${length}" type="audio/mpeg"/>
      <itunes:duration>${durationSec}</itunes:duration>
      <itunes:episode>${ep.episode}</itunes:episode>
      <itunes:summary>${escapeXml(channel === 'nihongo' ? hookJa(ep) : ep.description)}</itunes:summary>
      <podcast:transcript url="${SITE}/subtitles/${ep.id}.vtt" type="text/vtt" language="ja"/>
    </item>`;
  }).join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>${SHOW_NAME[channel]}</title>
    <link>${home}</link>
    <description>${escapeXml(text.description)}</description>
    <language>ja</language>
    <copyright>© 2026 Japanese Daily News (podcast.jpnotes.dev). CC BY-NC 4.0 — https://creativecommons.org/licenses/by-nc/4.0/</copyright>
    <atom:link href="${SITE}${RSS_PATH[channel]}" rel="self" type="application/rss+xml"/>
    <itunes:author>Japanese Daily News</itunes:author>
    <itunes:owner>
      <itunes:name>Japanese Daily News</itunes:name>
      <itunes:email>pengcheng199@gmail.com</itunes:email>
    </itunes:owner>
    <itunes:image href="${SITE}${COVER[channel]}"/>
    <itunes:category text="Education">
      <itunes:category text="Language Learning"/>
    </itunes:category>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <itunes:summary>${escapeXml(text.summary)}</itunes:summary>
${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
}
