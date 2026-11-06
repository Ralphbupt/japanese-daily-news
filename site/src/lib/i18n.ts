// One page per language, like jpnotes.dev: English at /page/, Chinese at
// /zh/page/. Pages live under src/pages/[...lang]/ (lang undefined = English).
// Each built page keeps only its own language (see stripOtherLang in
// astro.config.mjs); hreflang ties the two copies together.

export type Lang = 'en' | 'zh';

/** getStaticPaths params for the two languages. */
export const LANG_PARAMS: { lang: string | undefined }[] = [{ lang: undefined }, { lang: 'zh' }];

export function langOf(param: string | undefined): Lang {
  return param === 'zh' || param?.startsWith('zh/') ? 'zh' : 'en';
}

// Two shows on one site: the English-explained 'main' one at /…/, the
// all-Japanese one at /nihongo/… . Pages shared by both take these params in
// [...lang] (undefined | zh | nihongo | zh/nihongo).
export type Channel = 'main' | 'nihongo';
export const CHANNEL_PARAMS: { lang: string | undefined; channel: Channel }[] = [
  { lang: undefined, channel: 'main' },
  { lang: 'zh', channel: 'main' },
  { lang: 'nihongo', channel: 'nihongo' },
  { lang: 'zh/nihongo', channel: 'nihongo' },
];

export function channelOf(param: string | undefined): Channel {
  return param?.endsWith('nihongo') ? 'nihongo' : 'main';
}

export const COVER: Record<Channel, string> = { main: '/cover.jpg', nihongo: '/cover-nihongo.jpg' };

export const SHOW_NAME: Record<Channel, string> = {
  main: 'Japanese Daily News',
  nihongo: '日本語で聞くニュース',
};

export const RSS_PATH: Record<Channel, string> = { main: '/rss.xml', nihongo: '/nihongo/rss.xml' };

/** Site path in a language and channel: chp('/ep/001/', 'zh', 'nihongo') → '/zh/nihongo/ep/001/'. */
export function chp(path: string, lang: Lang, channel: Channel): string {
  return lp((channel === 'nihongo' ? '/nihongo' : '') + path, lang);
}

/** Site path in a language: lp('/ep/001/', 'zh') → '/zh/ep/001/'. */
export function lp(path: string, lang: Lang): string {
  return lang === 'zh' ? '/zh' + path : path;
}

/** Both language copies of the current page path. */
export function altPaths(pathname: string): Record<Lang, string> {
  let base = pathname.replace(/^\/zh(?=\/|$)/, '') || '/';
  if (!base.endsWith('/')) base += '/';
  return { en: base, zh: '/zh' + base };
}

export const HTML_LANG: Record<Lang, string> = { en: 'en', zh: 'zh-CN' };
export const HREFLANG: Record<Lang, string> = { en: 'en', zh: 'zh-Hans' };
export const OG_LOCALE: Record<Lang, string> = { en: 'en_US', zh: 'zh_CN' };
