// Shapes of the JSON files written by pipeline/build_data.py.

/** Rating ingredients from the pipeline (see src/lib/ratings.ts and pipeline/ratings.py).
 *  m = Madden baseline; g = the five versions of the stat-based adjustment (points added to
 *  the baseline); s = how much stats count here (0-1); ltd = limited sample;
 *  nm = no Madden rating (estimated baseline); k = how much a roll-up was re-spread. */
export type Rt = {
  m: number;
  g: (number | null)[];
  s?: number;
  ltd?: boolean;
  nm?: boolean;
  k?: number;
};

/** "Why" text for the opponent / injury / recent-form factors. */
export type RatingContext = { opp?: string; inj?: string; recent?: string };

export type UnitId = 'offense' | 'defense' | 'special';

export type Team = {
  abbr: string;
  name: string;
  nickname: string;
  conference: string;
  division: string;
  color: string;
  color2: string;
  logo: string;
  record: string;
  rt?: Rt | null;
  /** Madden-based team baseline. */
  madden?: number;
};

export type Stat = {
  id: string;
  label: string;
  value: number | null;
  display: string;
  better: 'high' | 'low' | null;
  rank: number | null;
  /** How many were ranked (32 for teams; varies for players). */
  of?: number | null;
  leagueAvg: string | null;
  hint: string | null;
  rt?: Rt | null;
  /** Weight inside its category's rating. */
  w?: number;
};

export type Player = {
  id: string;
  name: string;
  pos: string | null;
  jersey: number | null;
  headshot: string | null;
  line: string;
  value: number;
  rt?: Rt | null;
};

export type Category = {
  id: string;
  label: string;
  blurb: string;
  stats: Stat[];
  leaders: { title: string; players: Player[] }[];
  rt?: Rt | null;
  /** Weight inside its unit's rating. */
  w?: number;
};

export type Game = {
  week: number;
  date: string;
  opp: string;
  home: boolean;
  pf: number | null;
  pa: number | null;
  result: 'W' | 'L' | 'T' | null;
};

export type RosterPlayer = {
  id: string;
  name: string;
  pos: string | null;
  jersey: number | null;
  headshot: string | null;
  depth: string | null;
  starter: boolean;
  tag: string | null;
  line: string | null;
  rt?: Rt | null;
};

export type RosterSection = { id: string; label: string; players: RosterPlayer[] };

export type TeamDoc = {
  season: number;
  throughWeek: number;
  updated: string;
  team: Team;
  games: Game[];
  units: Record<UnitId, Category[]>;
  roster: RosterSection[];
  unitRatings: Record<UnitId, { rt: Rt | null; w: number }>;
  context: Record<UnitId, RatingContext>;
};

export type PlayerCategory = {
  id: string;
  label: string;
  blurb: string;
  qualified: boolean;
  qualNote: string | null;
  /** Ids of the stats to show on the summary card. */
  key: string[];
  /** Offensive line categories that use team numbers. */
  teamBased?: boolean;
  stats: Stat[];
  rt?: Rt | null;
  /** Weight inside the player's overall rating. */
  w?: number;
};

export type PlayerDoc = {
  season: number;
  throughWeek: number;
  updated: string;
  id: string;
  name: string;
  group: string;
  pos: string | null;
  posName: string | null;
  team: string | null;
  teamName: string | null;
  teamColor: string;
  teamColor2: string;
  teamLogo: string | null;
  jersey: number | null;
  headshot: string | null;
  height: string | null;
  weight: number | null;
  college: string | null;
  experience: number | null;
  age: number | null;
  status: string | null;
  depth: string | null;
  starter: boolean;
  rankGroup: string;
  rankGroupPlural: string;
  categories: PlayerCategory[];
  rt?: Rt | null;
  /** His Madden NFL 27 launch rating (null if he isn't in the Madden file). */
  madden?: number | null;
  context: RatingContext | null;
};

export type TeamsIndex = {
  season: number;
  throughWeek: number;
  updated: string;
  teams: Team[];
};
