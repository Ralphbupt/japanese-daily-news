import type { APIRoute } from 'astro';
import { getAllEpisodes } from '../lib/episodes';
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

function rfcDate(d: string): string {
  return new Date(d + 'T12:00:00Z').toUTCString();
}

export const GET: APIRoute = async () => {
  const episodes = getAllEpisodes();

  const items = episodes.map(ep => {
    const audioUrl = `${SITE}/audio/${ep.id}.mp3`;
    const link = `${SITE}/ep/${ep.paddedNum}`;

    let length = 0;
    const audioPath = path.join(AUDIO_DIR, `${ep.id}.mp3`);
    try { length = fs.statSync(audioPath).size; } catch { /* ok */ }

    const lastSeg = ep.timedSegments[ep.timedSegments.length - 1];
    const durationSec = lastSeg ? Math.round(lastSeg.end + 2) : 0;

    return `    <item>
      <title>${escapeXml(`EP ${ep.paddedNum}: ${ep.title}`)}</title>
      <link>${link}</link>
      <guid isPermaLink="true">${link}</guid>
      <pubDate>${rfcDate(ep.date)}</pubDate>
      <description>${escapeXml(ep.description)}</description>
      <enclosure url="${audioUrl}" length="${length}" type="audio/mpeg"/>
      <itunes:duration>${durationSec}</itunes:duration>
      <itunes:episode>${ep.episode}</itunes:episode>
      <podcast:transcript url="${SITE}/subtitles/${ep.id}.vtt" type="text/vtt" language="ja"/>
    </item>`;
  }).join('\n');

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Japanese Daily News</title>
    <link>${SITE}</link>
    <description>Learn Japanese through real news stories. Daily episodes with native audio, vocabulary breakdown, and grammar review.</description>
    <language>ja</language>
    <atom:link href="${SITE}/rss.xml" rel="self" type="application/rss+xml"/>
    <itunes:author>Japanese Daily News</itunes:author>
    <itunes:owner>
      <itunes:name>Japanese Daily News</itunes:name>
      <itunes:email>pengcheng199@gmail.com</itunes:email>
    </itunes:owner>
    <itunes:image href="${SITE}/cover.jpg"/>
    <itunes:category text="Education">
      <itunes:category text="Language Learning"/>
    </itunes:category>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
