export const colors = {
  bg: '#0B0F17',
  card: '#151B26',
  cardPressed: '#1C2433',
  border: '#232C3B',
  text: '#F2F4F8',
  muted: '#8A94A6',
  good: '#34C77B',
  mid: '#D9A441',
  bad: '#F25F5C',
};

/** Green for the top ~third, amber for the middle, red for the bottom ~third.
 *  Out of 32 teams that's 1–10 green, 11–22 amber, 23–32 red. */
export function rankColor(rank: number | null, of: number | null = 32) {
  if (rank == null) return colors.muted;
  const total = of ?? 32;
  if (rank <= Math.round((total * 10) / 32)) return colors.good;
  if (rank <= Math.round((total * 22) / 32)) return colors.mid;
  return colors.bad;
}

/** How full the rank bar is: 1st = full, last = nearly empty. */
export function rankFill(rank: number | null, of: number | null = 32) {
  if (rank == null) return 0;
  const total = of ?? 32;
  return (total + 1 - rank) / total;
}

export function ordinal(n: number) {
  const s = ['th', 'st', 'nd', 'rd'];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

/** Some team colors are too dark to read on our dark background. */
export function readableTeamColor(primary: string, secondary: string) {
  const lum = (hex: string) => {
    const h = hex.replace('#', '');
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  return lum(primary) > 0.12 ? primary : secondary;
}

/** Madden-style rating colors: 85+ green, 75+ light green, 65+ amber, 55+ orange, below that red. */
export function ratingColor(rating: number | null | undefined) {
  if (rating == null) return colors.muted;
  if (rating >= 85) return colors.good;
  if (rating >= 75) return '#8FD16B';
  if (rating >= 65) return colors.mid;
  if (rating >= 55) return '#F0883E';
  return colors.bad;
}
