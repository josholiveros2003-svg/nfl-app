import { useMemo } from 'react';
import { powerRankings } from './powerRankings';
import { breakdown, useRatingWeights } from './ratings';
import type { PlayerIndexEntry, RankingsDoc, Rt } from './types';

/** League ranks (1-32) for every team at every level, using the current Settings sliders,
 *  plus power-ranking spots and the Offensive/Defensive Line ratings. */
export function useTeamRanks(rankings?: RankingsDoc) {
  const { weights, influence, rank } = useRatingWeights();
  return useMemo(() => {
    if (!rankings) return null;
    const lists: Record<string, Record<string, Rt | null>> = { ...rankings.nodes };
    for (const u of rankings.units) {
      if (u.kind === 'group') lists[u.id] = Object.fromEntries(Object.entries(u.teams).map(([t, v]) => [t, v.rt]));
    }
    const ranks: Record<string, Record<string, number>> = {};
    for (const [key, teams] of Object.entries(lists)) {
      const scored = Object.entries(teams)
        .map(([t, rt]) => [t, breakdown(rt, weights, influence)?.rating ?? -1] as const)
        .sort((a, b) => b[1] - a[1]);
      ranks[key] = {};
      let prev: number | null = null;
      let place = 0;
      scored.forEach(([t, v], i) => {
        if (v !== prev) {
          place = i + 1;
          prev = v;
        }
        ranks[key][t] = place; // ties share a rank
      });
    }
    const power = Object.fromEntries(powerRankings(rankings.league.teams, rank).map((p) => [p.team, p.rank]));
    return {
      rankOf: (key: string, team: string) => ranks[key]?.[team] ?? null,
      power: (team: string) => (power[team] as number | undefined) ?? null,
      groups: (team: string) => ({
        offensive_line: lists.offensive_line?.[team] ?? null,
        defensive_line: lists.defensive_line?.[team] ?? null,
      }),
    };
  }, [rankings, weights, influence, rank]);
}

/** A player's rank at his position (full-sample players only), with the current sliders. */
export function usePositionRank(players: PlayerIndexEntry[] | undefined, id: string | undefined) {
  const { weights, influence } = useRatingWeights();
  return useMemo(() => {
    const me = players?.find((p) => p.id === id);
    if (!players || !me) return null;
    const pool = players
      .filter((p) => p.group === me.group && p.team && p.rt)
      .map((p) => ({ id: p.id, b: breakdown(p.rt, weights, influence) }))
      .filter((x) => x.b && !x.b.limited)
      .sort((a, b) => b.b!.rating - a.b!.rating);
    const i = pool.findIndex((x) => x.id === id);
    return { rank: i >= 0 ? i + 1 : null, of: pool.length, group: me.group };
  }, [players, id, weights, influence]);
}
