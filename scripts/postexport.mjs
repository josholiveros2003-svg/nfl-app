// Small fixes after `expo export` so the site works on GitHub Pages.
import { copyFileSync, existsSync, writeFileSync } from 'node:fs';

// GitHub Pages hides folders starting with "_" (like Expo's "_expo") unless this file exists.
writeFileSync('dist/.nojekyll', '');

// GitHub Pages shows 404.html for unknown addresses.
if (existsSync('dist/+not-found.html')) copyFileSync('dist/+not-found.html', 'dist/404.html');

// Player pages live at /player?id=...  Saving a player.html copy lets GitHub Pages serve
// that address directly instead of redirecting /player -> /player/ (which could drop ?id=).
if (existsSync('dist/player/index.html')) copyFileSync('dist/player/index.html', 'dist/player.html');

console.log('postexport: added .nojekyll, 404.html and player.html');
