import rankingSettings from '../../config/rankings.json';
import type { RankWeights } from './ratings';
import type { LeagueParts, LeagueTeam } from './types';

// League power rankings, computed in the app so the Settings sliders apply instantly.
// Each part (results, team rating minus injuries, recent form) is compared across all 32
// teams (how many standard deviations above average), blended with the slider weights,
// and put on a 0-100 scale (average team = 77).

type Part = 'results' | 'rating' | 'form';
const PARTS: Part[] = ['results', 'rating', 'form'];
const { mean: SCALE_MEAN, sd: SCALE_SD } = rankingSettings.scale;
const INJURY_COST = rankingSettings.injuries.ratingPointsPerInjuryPoint;

export type PowerRow = {
  team: string;
  score: number;
  rank: number;
  prevRank: number;
  /** Points above/below average that each part contributed to the score. */
  parts: Record<Part, number>;
  /** Team rating after the current-injury penalty. */
  effectiveRating: number;
  injuryCost: number;
  data: LeagueTeam;
};

type Yardstick = { parts: Record<Part, { mu: number; sd: number }>; comb: { mu: number; sd: number } };

const valueOf = (teams: Record<string, LeagueTeam>, t: string, which: 'now' | 'prev', p: Part, w: RankWeights) => {
  const x: LeagueParts = teams[t][which];
  return p === 'rating' ? x.rating - w.injuries * INJURY_COST * x.injuryPoints : x[p];
};

const spread = (xs: number[]) => {
  const mu = xs.reduce((a, b) => a + b, 0) / xs.length;
  return { mu, sd: Math.sqrt(xs.reduce((a, b) => a + (b - mu) ** 2, 0) / xs.length) || 1 };
};

/** Scores for one week. Both weeks are measured against the same yardstick (this week's league),
 *  so a team that didn't play (bye) keeps exactly the same score. */
function scoreAll(teams: Record<string, LeagueTeam>, which: 'now' | 'prev', w: RankWeights, yard?: Yardstick) {
  const ids = Object.keys(teams);
  const total = PARTS.reduce((a, p) => a + Math.max(0, w[p]), 0) || 1;
  const partStats =
    yard?.parts ?? (Object.fromEntries(PARTS.map((p) => [p, spread(ids.map((t) => valueOf(teams, t, which, p, w)))])) as Yardstick['parts']);
  const z = (t: string, p: Part) => (valueOf(teams, t, which, p, w) - partStats[p].mu) / partStats[p].sd;
  const comb = Object.fromEntries(ids.map((t) => [t, PARTS.reduce((a, p) => a + (Math.max(0, w[p]) / total) * z(t, p), 0)]));
  const combStats = yard?.comb ?? spread(Object.values(comb));
  const score = Object.fromEntries(ids.map((t) => [t, SCALE_MEAN + (SCALE_SD * (comb[t] - combStats.mu)) / combStats.sd]));
  const parts = Object.fromEntries(
    ids.map((t) => [t, Object.fromEntries(PARTS.map((p) => [p, (SCALE_SD * (Math.max(0, w[p]) / total) * z(t, p)) / combStats.sd]))]),
  ) as Record<string, Record<Part, number>>;
  const order = [...ids].sort((a, b) => score[b] - score[a]);
  const rank = Object.fromEntries(order.map((t, i) => [t, i + 1]));
  return { score, parts, rank, order, yard: { parts: partStats, comb: combStats } as Yardstick };
}

export function powerRankings(teams: Record<string, LeagueTeam>, w: RankWeights): PowerRow[] {
  const now = scoreAll(teams, 'now', w);
  const prev = scoreAll(teams, 'prev', w, now.yard);
  return now.order.map((t) => ({
    team: t,
    score: now.score[t],
    rank: now.rank[t],
    prevRank: prev.rank[t],
    parts: now.parts[t],
    effectiveRating: valueOf(teams, t, 'now', 'rating', w),
    injuryCost: w.injuries * INJURY_COST * teams[t].now.injuryPoints,
    data: teams[t],
  }));
}

/** Plain-language label for one game's result vs. what an average team would do. */
export function gameVerdict(quality: number) {
  if (quality >= 0.3) return 'Big win';
  if (quality >= 0.1) return 'Good result';
  if (quality > -0.1) return 'About as expected';
  if (quality > -0.3) return 'Disappointing';
  return 'Bad loss';
}
