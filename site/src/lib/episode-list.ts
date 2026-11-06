import { getAllEpisodes } from './episodes';
import type { Channel } from './i18n';

// Episode list for the player's playlist panel and for auto-play's "next"
// (order and level filter are the listener's choice). Oldest first; one small
// file fetched on demand instead of embedding 260+ titles in every page.
export function episodeList(channel: Channel): Response {
  const list = getAllEpisodes(channel)
    .sort((a, b) => a.episode - b.episode)
    .map(ep => ({
      n: ep.paddedNum,
      t: ep.title,
      en: ep.titleEn || '',
      zh: ep.titleZh || '',
      lv: ep.level,
      d: ep.date,
    }));
  return new Response(JSON.stringify(list), {
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}
