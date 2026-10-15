// Small fixes after `expo export` so the site works on GitHub Pages.
import { copyFileSync, existsSync, writeFileSync } from 'node:fs';

// GitHub Pages hides folders starting with "_" (like Expo's "_expo") unless this file exists.
writeFileSync('dist/.nojekyll', '');

// GitHub Pages shows 404.html for unknown addresses.
if (existsSync('dist/+not-found.html')) copyFileSync('dist/+not-found.html', 'dist/404.html');

// Pages whose address carries ?id=... (player, game) or other options (compare) also get a
// <name>.html copy, so GitHub Pages serves /player?id=... directly instead of redirecting
// /player -> /player/ first.
const copies = ['player', 'game', 'compare', 'rankings'].filter((name) => existsSync(`dist/${name}/index.html`));
for (const name of copies) copyFileSync(`dist/${name}/index.html`, `dist/${name}.html`);

console.log(`postexport: added .nojekyll, 404.html and ${copies.map((n) => `${n}.html`).join(', ')}`);
