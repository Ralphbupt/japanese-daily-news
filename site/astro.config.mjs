import { defineConfig } from 'astro/config';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// One page per language (see src/lib/i18n.ts): pages are written with both
// languages side by side (class="i18n-en" / "i18n-zh"), and after the build
// each page keeps only its own, so /ep/NNN/ is English-only HTML and
// /zh/ep/NNN/ Chinese-only — what search engines see matches the hreflang.
// Pages without data-force-lang (404) keep both and switch with CSS.

/** Remove every element whose class list includes `cls`, with its content. */
function stripClass(html, cls) {
  const open = new RegExp(`<([a-zA-Z][a-zA-Z0-9]*)\\b[^>]*\\bclass="[^"]*\\b${cls}\\b[^"]*"[^>]*>`, 'g');
  let out = '';
  let pos = 0;
  let m;
  while ((m = open.exec(html))) {
    const tag = m[1].toLowerCase();
    // Find the matching close tag, counting nested same-name tags.
    const re = new RegExp(`<(/?)${tag}\\b[^>]*>`, 'gi');
    re.lastIndex = m.index + m[0].length;
    let depth = 1;
    let t;
    while (depth > 0 && (t = re.exec(html))) depth += t[1] ? -1 : 1;
    if (depth !== 0) continue; // unbalanced: leave it alone
    out += html.slice(pos, m.index);
    pos = re.lastIndex;
    open.lastIndex = pos;
  }
  return out + html.slice(pos);
}

function stripOtherLang() {
  return {
    name: 'strip-other-language',
    hooks: {
      'astro:build:done': ({ dir }) => {
        const root = fileURLToPath(dir);
        let n = 0;
        const walk = d => {
          for (const e of fs.readdirSync(d, { withFileTypes: true })) {
            const p = path.join(d, e.name);
            if (e.isDirectory()) walk(p);
            else if (e.name.endsWith('.html')) {
              const html = fs.readFileSync(p, 'utf8');
              const lang = (html.match(/<html[^>]*\bdata-force-lang="(en|zh)"/) || [])[1];
              if (!lang) continue;
              fs.writeFileSync(p, stripClass(html, lang === 'zh' ? 'i18n-en' : 'i18n-zh'));
              n++;
            }
          }
        };
        walk(root);
        console.log(`[strip-other-language] ${n} pages reduced to one language`);
      },
    },
  };
}

export default defineConfig({
  site: 'https://podcast.jpnotes.dev',
  integrations: [stripOtherLang()],
});
