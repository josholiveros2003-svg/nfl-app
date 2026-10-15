import { createContext, createElement, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import rankingSettings from '../../config/rankings.json';
import settings from '../../config/ratings.json';
import type { Rt } from './types';

// How the app turns the pipeline's rating ingredients into a 0-100 number.
//
// Every rating = Madden baseline + a stat-based adjustment. The adjustment comes in five
// versions (this season's stats, opponent-adjusted, injury-adjusted, analyst opinion,
// last 3 games); the Settings sliders decide how they're blended. Factors that aren't
// available (analyst opinion, for now) are skipped, so their share is spread across the
// others. A sixth slider ("stats influence") scales how far stats can move ratings at all.

export type Factor = {
  id: 'performance' | 'opponents' | 'injuries' | 'analyst' | 'recent';
  label: string;
  weight: number;
  available?: boolean;
  explain: string;
};

export const FACTORS = settings.context.factors as Factor[];
export const DEFAULT_WEIGHTS = FACTORS.map((f) => f.weight);
export const INFLUENCE = settings.context.statsInfluence;
const STORAGE_KEY = 'nfl-stats:rating-weights-v3';

const isAvailable = (i: number) => FACTORS[i].available !== false;

/** Weights as shares adding up to 1, using only factors that are available. */
export function effectiveWeights(weights: number[]) {
  const usable = weights.map((w, i) => (isAvailable(i) ? Math.max(0, w) : 0));
  const total = usable.reduce((a, b) => a + b, 0);
  if (!total) return FACTORS.map((_, i) => (i === 0 ? 1 : 0)); // everything at 0: fall back to this season's stats
  return usable.map((w) => w / total);
}

export type Breakdown = {
  rating: number;
  /** Madden baseline. */
  baseline: number;
  /** How far this season's stats move it (before the other factors). */
  stats: number;
  /** How much each other factor moved it (null = not available). */
  moves: { factor: Factor; share: number; move: number | null }[];
  /** How much stats count here (0-1), after the influence slider. */
  statShare: number;
  limited: boolean;
  estimatedBaseline: boolean;
  respread: number | null;
  /** Teams: points from wins and losses in context (null for players). */
  results: number | null;
};

const clamp = (x: number) => Math.max(1, Math.min(99, x));

export function breakdown(rt: Rt | null | undefined, weights: number[], influence = 1): Breakdown | null {
  if (!rt || rt.m == null || !rt.g) return null;
  const w = effectiveWeights(weights);
  const perf = (rt.g[0] ?? 0) * influence;
  const moves = FACTORS.slice(1).map((factor, j) => {
    const i = j + 1;
    const usable = isAvailable(i) && rt.g[i] != null;
    return { factor, share: w[i], move: usable ? w[i] * ((rt.g[i] as number) * influence - perf) : null };
  });
  const results = rt.res != null ? rt.res * influence : null;
  const total = rt.m + perf + moves.reduce((a, m) => a + (m.move ?? 0), 0) + (results ?? 0);
  return {
    rating: Math.round(clamp(total)),
    baseline: rt.m,
    stats: perf,
    moves,
    statShare: Math.min(1, (rt.s ?? 0) * influence),
    limited: !!rt.ltd,
    estimatedBaseline: !!rt.nm,
    respread: rt.k ?? null,
    results,
  };
}

// ---- Slider settings, shared by every screen ----

/** League power-ranking weights (see config/rankings.json). */
export type RankWeights = { results: number; rating: number; form: number; injuries: number };
export const DEFAULT_RANK_WEIGHTS: RankWeights = { ...rankingSettings.weights, injuries: 1 };

type Saved = { weights: number[]; influence: number; rank: RankWeights };

function loadSaved(): Saved | null {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && Array.isArray(parsed.weights) && parsed.weights.length === FACTORS.length) {
      return {
        weights: parsed.weights.map(Number),
        influence: Number(parsed.influence ?? INFLUENCE.default),
        rank: { ...DEFAULT_RANK_WEIGHTS, ...(parsed.rank ?? {}) },
      };
    }
  } catch {
    // ignore: fall back to defaults
  }
  return null;
}

function save(v: Saved) {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(v));
  } catch {
    // Private browsing etc.: settings still work for this visit.
  }
}

type WeightsState = Saved & {
  setWeight: (i: number, v: number) => void;
  setInfluence: (v: number) => void;
  setRank: (key: keyof RankWeights, v: number) => void;
  reset: () => void;
};
const DEFAULTS: Saved = { weights: DEFAULT_WEIGHTS, influence: INFLUENCE.default, rank: DEFAULT_RANK_WEIGHTS };
const WeightsContext = createContext<WeightsState>({
  ...DEFAULTS, setWeight: () => {}, setInfluence: () => {}, setRank: () => {}, reset: () => {},
});

export function RatingWeightsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Saved>(() => loadSaved() ?? DEFAULTS);
  const update = useCallback((fn: (prev: Saved) => Saved) => {
    setState((prev) => {
      const next = fn(prev);
      save(next);
      return next;
    });
  }, []);
  const setWeight = useCallback(
    (i: number, v: number) => update((p) => ({ ...p, weights: p.weights.map((x, j) => (j === i ? v : x)) })),
    [update],
  );
  const setInfluence = useCallback((v: number) => update((p) => ({ ...p, influence: v })), [update]);
  const setRank = useCallback(
    (key: keyof RankWeights, v: number) => update((p) => ({ ...p, rank: { ...p.rank, [key]: v } })),
    [update],
  );
  const reset = useCallback(() => update(() => DEFAULTS), [update]);
  const value = useMemo(
    () => ({ ...state, setWeight, setInfluence, setRank, reset }),
    [state, setWeight, setInfluence, setRank, reset],
  );
  return createElement(WeightsContext.Provider, { value }, children);
}

export const useRatingWeights = () => useContext(WeightsContext);

/** The 0-100 rating (or null) for one item, using the current slider settings. */
export function useRating(rt: Rt | null | undefined) {
  const { weights, influence } = useRatingWeights();
  return useMemo(() => breakdown(rt, weights, influence), [rt, weights, influence]);
}
