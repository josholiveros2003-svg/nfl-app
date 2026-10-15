import type { UnitId } from './types';

// Used to pre-build one web page per team/unit/category at export time.
// These match the ids written by pipeline/build_data.py.
export const TEAM_IDS = [
  'ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE', 'DAL', 'DEN', 'DET',
  'GB', 'HOU', 'IND', 'JAX', 'KC', 'LA', 'LAC', 'LV', 'MIA', 'MIN', 'NE', 'NO',
  'NYG', 'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB', 'TEN', 'WAS',
];

export const UNITS: { id: UnitId; label: string; short: string }[] = [
  { id: 'offense', label: 'Offense', short: 'OFF' },
  { id: 'defense', label: 'Defense', short: 'DEF' },
  { id: 'special', label: 'Special Teams', short: 'ST' },
];

export const CATEGORY_IDS: Record<UnitId, string[]> = {
  offense: ['overview', 'passing', 'rushing', 'receiving', 'situational'],
  defense: ['overview', 'pass_defense', 'run_defense', 'situational'],
  special: ['kicking', 'punting', 'returns', 'coverage'],
};

export const unitLabel = (id: string) => UNITS.find((u) => u.id === id)?.label ?? id;

// Every category a player page can have (see pipeline/players.py).
export const PLAYER_CATEGORY_IDS = [
  'passing', 'rushing', 'receiving', 'pass_rush', 'tackling', 'coverage',
  'kicking', 'punting', 'returns', 'playing_time', 'pass_pro', 'run_block',
];

// Position lists in the power rankings.
export const POSITIONS: { id: string; label: string }[] = [
  { id: 'QB', label: 'Quarterbacks' }, { id: 'RB', label: 'Running Backs' }, { id: 'WR', label: 'Wide Receivers' },
  { id: 'TE', label: 'Tight Ends' }, { id: 'OL', label: 'Offensive Linemen' }, { id: 'DL', label: 'Defensive Linemen' },
  { id: 'LB', label: 'Linebackers' }, { id: 'DB', label: 'Defensive Backs' }, { id: 'K', label: 'Kickers' }, { id: 'P', label: 'Punters' },
];
