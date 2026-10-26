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
  /** Teams only: rating points from wins and losses in context. */
  res?: number;
  /** Peer group for the league average, e.g. "team.offense" or "pos.WR.receiving" (see averages.json). */
  a?: string;
};

/** public/data/averages.json: per peer group, the average rating ingredients of each bucket of
 *  peers that share the same available factors (n = how many). See pipeline/averages.py. */
export type AverageBucket = { n: number; m: number; g: (number | null)[]; res?: number };
export type AveragesDoc = Record<string, AverageBucket[]>;

/** "Why" text for the opponent / injury / recent-form factors. */
export type RatingContext = { opp?: string; inj?: string; recent?: string; mkt?: string };

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
  /** nflverse game id, e.g. "2026_06_SEA_DEN". */
  id?: string;
  /** This team's chance to win, as the model saw it before kickoff (0-1). */
  wp?: number | null;
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
  results?: TeamResults;
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

/** One row of public/data/players.json (used for searching players). */
export type PlayerIndexEntry = {
  id: string;
  name: string;
  team: string | null;
  pos: string | null;
  group: string;
  jersey: number | null;
  starter: boolean;
  rt?: Rt | null;
};

export type GameFactor = { id: string; label: string; points: number; detail: string };
export type MissingPlayer = { id: string; name: string; pos: string | null; status: string; points: number };
/** Everyone ruled out for a game (Out, Doubtful or injured reserve), however small the impact. */
export type InactivePlayer = { id: string; name: string; pos: string | null; status: string; starter: boolean };

/** One number in a box score: how it's shown, and its percentile among this season's games
 *  (0-100, 100 = best; null = not judged good or bad). */
export type BoxCell = { d: string; p: number | null };
export type BoxTeamStat = {
  id: string; label: string; better: 'high' | 'low' | null;
  /** League average per team per game, already formatted. */
  avg: string;
  home: BoxCell; away: BoxCell;
};
export type BoxRow = {
  id: string; name: string; pos: string | null;
  /** Which average this player is compared with: a position ("WR") or "*" (everyone in the section). */
  ag: string;
  /** Whether the player has a page in the app. */
  link: boolean;
  cells: BoxCell[];
};
export type BoxSection = {
  id: string; label: string;
  cols: { id: string; label: string; better: 'high' | 'low' | null }[];
  /** League average per game for each column, by position ("*" = everyone in the section). */
  avgs: Record<string, string[]>;
  rows: BoxRow[];
};
export type BoxScore = { teams: BoxTeamStat[]; players: { home: BoxSection[]; away: BoxSection[] } };

/** public/data/games/<id>.json: one game, with its pre-game win probability and why. */
export type GameDoc = {
  id: string;
  season: number;
  week: number;
  date: string;
  home: string;
  away: string;
  neutral: boolean;
  played: boolean;
  homeScore: number | null;
  awayScore: number | null;
  prob: { home: number; away: number };
  /** Expected home margin in points (negative = away favored). */
  margin: number;
  /** Each factor's effect in points (positive helps the home team), biggest first. */
  factors: GameFactor[];
  injuries: { home: MissingPlayer[]; away: MissingPlayer[] };
  /** Missing in older data files (before this list was added). */
  inactive?: { home: InactivePlayer[]; away: InactivePlayer[] };
  /** Played games only: team and player stats (see pipeline/boxscore.py). */
  box?: BoxScore;
  correct: boolean | null;
};

type Eval = { games: number; correct: number; accuracy: number; brier: number;
  calibration: { band: string; games: number; predicted: number; actual: number }[] };

/** public/data/winprob_report.json: how the model has done on past games. */
export type WinProbReport = Record<string, { model: Eval; homeTeam: Eval; vegas: Eval }>;

/** Wins and losses judged against each game's pre-game win chance. */
export type TeamResults = {
  points: number;
  wins: number;
  losses: number;
  expectedWins: number;
  games: { week: number; opp: string; home: boolean; pf: number; pa: number; result: 'W' | 'L' | 'T'; expected: number; points: number }[];
};

// ---- public/data/rankings.json ----
export type LeagueParts = { results: number; form: number; rating: number; injuryPoints: number };
export type RankedGame = {
  week: number; opp: string; home: boolean; neutral: boolean; pf: number; pa: number;
  result: 'W' | 'L' | 'T'; oppRecord: string; avgChance: number; quality: number;
};
export type LeagueTeam = {
  record: string; now: LeagueParts; prev: LeagueParts; injuries: MissingPlayer[]; games: RankedGame[];
};
export type UnitList = {
  id: string; label: string; kind: 'unit' | 'cat' | 'group'; description: string;
  teams: Record<string, { rt: Rt | null; starters: { id: string; name: string; pos: string | null }[]; move?: number }>;
};
export type RankingsDoc = {
  season: number; throughWeek: number; updated: string;
  league: { lastPlayedWeek: number; teams: Record<string, LeagueTeam> };
  units: UnitList[];
};

// ---- public/data/schedule.json ----
export type ScheduleGame = {
  id: string; date: string; weekday: string; time: string; away: string; home: string; neutral: boolean;
  awayRecord: string; homeRecord: string; awayScore: number | null; homeScore: number | null;
  prob: { home: number; away: number } | null; correct: boolean | null;
};
export type ScheduleDoc = { season: number; currentWeek: number; weeks: Record<string, ScheduleGame[]> };
