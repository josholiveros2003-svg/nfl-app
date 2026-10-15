import type { ScheduleDoc, Team } from './types';

// Standings, worked out from every played game in schedule.json.
// Tiebreakers are simplified (win %, then division record within a division, conference
// record, point differential); the NFL's official list is longer.

export type Standing = {
  team: Team;
  w: number; l: number; t: number; pct: number;
  pf: number; pa: number; diff: number;
  div: [number, number, number]; conf: [number, number, number];
  home: [number, number, number]; away: [number, number, number];
  streak: string;
};

const pctOf = ([w, l, t]: [number, number, number]) => (w + l + t ? (w + t / 2) / (w + l + t) : 0);
export const recordText = ([w, l, t]: [number, number, number]) => `${w}-${l}${t ? `-${t}` : ''}`;

export function buildStandings(schedule: ScheduleDoc, teams: Team[]): Standing[] {
  const by = Object.fromEntries(teams.map((t) => [t.abbr, t]));
  const rows: Record<string, Standing> = Object.fromEntries(
    teams.map((t) => [t.abbr, {
      team: t, w: 0, l: 0, t: 0, pct: 0, pf: 0, pa: 0, diff: 0,
      div: [0, 0, 0], conf: [0, 0, 0], home: [0, 0, 0], away: [0, 0, 0], streak: '–',
    } as Standing]),
  );
  const results: Record<string, ('W' | 'L' | 'T')[]> = {};
  const weeks = Object.keys(schedule.weeks).map(Number).sort((a, b) => a - b);
  for (const wk of weeks) {
    for (const g of schedule.weeks[String(wk)]) {
      if (g.homeScore == null || g.awayScore == null) continue;
      for (const [me, opp, pf, pa, isHome] of [
        [g.home, g.away, g.homeScore, g.awayScore, true],
        [g.away, g.home, g.awayScore, g.homeScore, false],
      ] as const) {
        const r = rows[me];
        if (!r) continue;
        const i = pf > pa ? 0 : pf < pa ? 1 : 2;
        if (i === 0) r.w += 1;
        else if (i === 1) r.l += 1;
        else r.t += 1;
        r.pf += pf;
        r.pa += pa;
        (isHome ? r.home : r.away)[i] += 1;
        if (by[opp]?.conference === by[me]?.conference) r.conf[i] += 1;
        if (by[opp]?.division === by[me]?.division) r.div[i] += 1;
        (results[me] ??= []).push(i === 0 ? 'W' : i === 1 ? 'L' : 'T');
      }
    }
  }
  for (const r of Object.values(rows)) {
    r.pct = pctOf([r.w, r.l, r.t]);
    r.diff = r.pf - r.pa;
    const res = results[r.team.abbr] ?? [];
    if (res.length) {
      const last = res[res.length - 1];
      let n = 0;
      for (let k = res.length - 1; k >= 0 && res[k] === last; k--) n++;
      r.streak = `${last}${n}`;
    }
  }
  return Object.values(rows);
}

/** Best first: win %, then division record (only between teams in the same division),
 *  conference record, point differential. */
export function compareStandings(a: Standing, b: Standing) {
  const sameDivision = a.team.division === b.team.division;
  return (
    b.pct - a.pct ||
    (sameDivision ? pctOf(b.div) - pctOf(a.div) : 0) ||
    pctOf(b.conf) - pctOf(a.conf) ||
    b.diff - a.diff
  );
}

/** Playoff picture for one conference: 4 division leaders (seeds 1-4), then 3 wild cards. */
export function conferenceSeeds(rows: Standing[], conference: string) {
  const conf = rows.filter((r) => r.team.conference === conference);
  const leaders = Object.values(
    conf.reduce<Record<string, Standing[]>>((acc, r) => ((acc[r.team.division] ??= []).push(r), acc), {}),
  ).map((d) => [...d].sort(compareStandings)[0]);
  const seeded = [...leaders].sort(compareStandings);
  const rest = conf.filter((r) => !leaders.includes(r)).sort(compareStandings);
  return { seeded: [...seeded, ...rest.slice(0, 3)], others: rest.slice(3) };
}
