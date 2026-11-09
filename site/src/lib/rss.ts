import { getAllEpisodes } from './episodes';
import { withUtm } from './jpnotes';
import { COVER, RSS_PATH, SHOW_NAME, chp, type Channel } from './i18n';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SITE = 'https://podcast.jpnotes.dev';
const AUDIO_DIR = fileURLToPath(new URL('../../public/audio', import.meta.url));

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
function showNotes(ep: ReturnType<typeof getAllEpisodes>[number]): string {
  let html = `<p>${esc(ep.description)}</p>`;
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
  let html = `<p>${esc(hookJa(ep))}</p>`;
  if (ep.grammar.length) {
    html += '<p>今回の文法：</p><ul>' + ep.grammar.map(g =>
      `<li><a href="${esc(withUtm(g.jpnotes!.url, 'rss'))}">${esc(g.pattern)}</a></li>`).join('') + '</ul>';
  }
  html += `<p>難しいと感じたら、英語の解説つきの番組もあります：<a href="${SITE}/?utm_source=podcast&amp;utm_medium=rss">${SHOW_NAME.main}</a></p>`;
  html += `<p>ふりがな、翻訳、単語と文法はウェブサイトで：<a href="${SITE}/nihongo/ep/${ep.paddedNum}/">podcast.jpnotes.dev</a></p>`;
  return html.replace(/]]>/g, ']]&gt;');
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
    description: 'Learn Japanese through real news stories. Daily episodes with native audio, vocabulary breakdown, and grammar review.',
    summary: 'A daily Japanese news podcast for learners. Each episode covers a real news story with vocabulary breakdowns, grammar notes, and practice quizzes. Hosted by Maya.',
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
    const audioUrl = `${SITE}/audio/${ep.id}.mp3`;
    const link = `${SITE}${chp(`/ep/${ep.paddedNum}`, 'en', channel)}`;

    let length = 0;
    const audioPath = path.join(AUDIO_DIR, `${ep.id}.mp3`);
    try { length = fs.statSync(audioPath).size; } catch { /* ok */ }

    const lastSeg = ep.timedSegments[ep.timedSegments.length - 1];
    const durationSec = lastSeg ? Math.round(lastSeg.end + 2) : 0;

    return `    <item>
      <title>${escapeXml(channel === 'nihongo' ? ep.title : `EP ${ep.paddedNum}: ${ep.title}`)}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      <pubDate>${rfcDate(ep.date, ep.level)}</pubDate>
      <description><![CDATA[${channel === 'nihongo' ? showNotesJa(ep) : showNotes(ep)}]]></description>
      <enclosure url="${audioUrl}" length="${length}" type="audio/mpeg"/>
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
