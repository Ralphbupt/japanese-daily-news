import type { APIRoute } from 'astro';
import { getAllEpisodes } from '../lib/episodes';
import { lp, HREFLANG, type Lang } from '../lib/i18n';

const SITE = 'https://podcast.jpnotes.dev';
const LANGS: Lang[] = ['en', 'zh'];

export const GET: APIRoute = async () => {
  const episodes = getAllEpisodes();

  // Each page once per language; every copy lists all copies as alternates.
  const pages = [
    { path: '/', priority: '1.0', changefreq: 'daily' },
    { path: '/about/', priority: '0.5', changefreq: 'monthly' },
    ...episodes.map(ep => ({
      path: `/ep/${ep.paddedNum}/`,
      lastmod: ep.date,
      priority: '0.8',
      changefreq: 'monthly',
    })),
  ];

  const alternates = (path: string) => [
    ...LANGS.map(l => `    <xhtml:link rel="alternate" hreflang="${HREFLANG[l]}" href="${SITE}${lp(path, l)}"/>`),
    `    <xhtml:link rel="alternate" hreflang="x-default" href="${SITE}${path}"/>`,
  ].join('\n');

  const entries = pages.flatMap(p => LANGS.map(l => `  <url>
    <loc>${SITE}${lp(p.path, l)}</loc>${p.lastmod ? `\n    <lastmod>${p.lastmod}</lastmod>` : ''}
    <changefreq>${p.changefreq}</changefreq>
    <priority>${p.priority}</priority>
${alternates(p.path)}
  </url>`));

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${entries.join('\n')}
</urlset>`;

  return new Response(xml, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
};
