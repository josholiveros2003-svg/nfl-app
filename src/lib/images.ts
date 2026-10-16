// Player photos and team logos come from the NFL's and ESPN's image servers at full size
// (NFL headshots are 3400 x 2450 pixels, about 5 MB each, ~33 MB in memory once loaded).
// A roster of 65 of those is enough to crash Safari on an iPhone. Both servers can resize
// on the fly, so we ask for a copy sized for where it's shown (2x for sharp screens).

const NFL_UPLOAD = '/image/upload/';

/** A small copy of a player photo or team logo, `points` wide on screen. */
export function sized(url: string | null | undefined, points: number): string | undefined {
  if (!url) return undefined;
  const px = Math.round(points * 2);
  // NFL headshots: .../image/upload/f_auto,q_auto/league/<id> -> face-centered square thumbnail.
  const i = url.indexOf(NFL_UPLOAD);
  if (url.includes('static.www.nfl.com') && i >= 0) {
    const rest = url.slice(i + NFL_UPLOAD.length);
    const slash = rest.indexOf('/');
    const hasTransform = slash > 0 && rest.slice(0, slash).includes('_');
    const path = hasTransform ? rest.slice(slash + 1) : rest;
    return `${url.slice(0, i + NFL_UPLOAD.length)}c_thumb,g_face,w_${px},h_${px},f_auto,q_auto/${path}`;
  }
  // ESPN team logos: https://a.espncdn.com/i/teamlogos/nfl/500/gb.png -> resized copy.
  const espn = url.match(/^https:\/\/a\.espncdn\.com(\/i\/teamlogos\/.+)$/);
  if (espn) return `https://a.espncdn.com/combiner/i?img=${espn[1]}&w=${px}&h=${px}`;
  return url;
}
