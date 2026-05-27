import type { APIRoute } from 'astro';
import { getAllEpisodes } from '../lib/episodes';

const SITE = 'https://podcast.jpnotes.dev';

export const GET: APIRoute = async () => {
  const episodes = getAllEpisodes();

  const urls = [
    { loc: '/', priority: '1.0', changefreq: 'daily' },
    ...episodes.map(ep => ({
      loc: `/ep/${ep.paddedNum}/`,
      lastmod: ep.date,
      priority: '0.8',
      changefreq: 'monthly',
    })),
  ];

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map(u => `  <url>
    <loc>${SITE}${u.loc}</loc>${u.lastmod ? `\n    <lastmod>${u.lastmod}</lastmod>` : ''}
    <changefreq>${u.changefreq}</changefreq>
    <priority>${u.priority}</priority>
  </url>`).join('\n')}
</urlset>`;

  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
