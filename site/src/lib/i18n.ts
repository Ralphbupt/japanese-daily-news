// One page per language, like jpnotes.dev: English at /page/, Chinese at
// /zh/page/. Pages live under src/pages/[...lang]/ (lang undefined = English).
// Each built page keeps only its own language (see stripOtherLang in
// astro.config.mjs); hreflang ties the two copies together.

export type Lang = 'en' | 'zh';

/** getStaticPaths params for the two languages. */
export const LANG_PARAMS: { lang: string | undefined }[] = [{ lang: undefined }, { lang: 'zh' }];

export function langOf(param: string | undefined): Lang {
  return param === 'zh' ? 'zh' : 'en';
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
