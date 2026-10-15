import settings from '../../config/compare.json';
import { UNITS } from './constants';
import type { PlayerDoc, Rt, Stat, TeamDoc } from './types';

// The Compare screen works on a simple tree that teams and players (and, later, games)
// can all be turned into: Overall › groups › categories › stats. Each side of a
// comparison is one tree; rows are matched up by `key`.

export type CompareNode = {
  key: string;
  label: string;
  rt?: Rt | null;
  /** Present on the bottom level (individual stats). */
  stat?: Stat;
  children?: CompareNode[];
};

/** One side of a comparison: who it is, plus its tree. */
export type CompareSide = {
  id: string;
  name: string;
  subtitle: string;
  image: string | null;
  color: string;
  href: string;
  tree: CompareNode;
};

export function teamSide(doc: TeamDoc): CompareSide {
  return {
    id: doc.team.abbr,
    name: doc.team.name,
    subtitle: `${doc.team.record} · ${doc.team.division}`,
    image: doc.team.logo,
    color: doc.team.color,
    href: `/team/${doc.team.abbr.toLowerCase()}`,
    tree: {
      key: 'overall',
      label: 'Overall',
      rt: doc.team.rt,
      children: UNITS.map((u) => ({
        key: u.id,
        label: u.label,
        rt: doc.unitRatings?.[u.id]?.rt,
        children: doc.units[u.id].map((c) => ({
          key: c.id,
          label: c.label,
          rt: c.rt,
          children: c.stats.map((s) => ({ key: s.id, label: s.label, rt: s.rt, stat: s })),
        })),
      })),
    },
  };
}

export function playerSide(doc: PlayerDoc): CompareSide {
  return {
    id: doc.id,
    name: doc.name,
    subtitle: [doc.pos, doc.team].filter(Boolean).join(' · '),
    image: doc.headshot,
    color: doc.teamColor,
    href: `/player?id=${doc.id}`,
    tree: {
      key: 'overall',
      label: 'Overall',
      rt: doc.rt,
      children: doc.categories.map((c) => ({
        key: c.id,
        label: c.label,
        rt: c.rt,
        children: c.stats.map((s) => ({ key: s.id, label: s.label, rt: s.rt, stat: s })),
      })),
    },
  };
}

/** Follow a path of keys (e.g. ["offense", "passing"]) down a tree. */
export function nodeAt(tree: CompareNode, path: string[]): CompareNode | null {
  let node: CompareNode | undefined = tree;
  for (const key of path) {
    node = node?.children?.find((c) => c.key === key);
    if (!node) return null;
  }
  return node ?? null;
}

/** Line up two lists of rows by key, keeping the left side's order (then any extras on the right). */
export function pairChildren(a: CompareNode | null, b: CompareNode | null) {
  const left = a?.children ?? [];
  const right = b?.children ?? [];
  const keys = [...left.map((c) => c.key), ...right.map((c) => c.key).filter((k) => !left.some((c) => c.key === k))];
  return keys.map((key) => ({
    key,
    a: left.find((c) => c.key === key) ?? null,
    b: right.find((c) => c.key === key) ?? null,
  }));
}

// ---- Advantage colors ----

export type Advantage = {
  /** Which side is ahead: 'a', 'b', 'even', or null when the two can't be compared. */
  leader: 'a' | 'b' | 'even' | null;
  /** 0 (tiny gap) to 1 (gap at or above the "solid" setting). */
  strength: number;
};

const NONE: Advantage = { leader: null, strength: 0 };

function fromGap(gap: number, solidAt: number): Advantage {
  if (gap === 0) return { leader: 'even', strength: 0 };
  return { leader: gap > 0 ? 'a' : 'b', strength: Math.min(1, Math.abs(gap) / solidAt) };
}

/** Advantage between two 0-100 ratings (as shown, i.e. rounded). */
export function ratingAdvantage(a: number | null | undefined, b: number | null | undefined): Advantage {
  if (a == null || b == null) return NONE;
  return fromGap(a - b, settings.ratingGapForSolid);
}

/** Percentile from a rank: 1st = 100, last = 0. */
const percentile = (rank: number, of: number) => (of > 1 ? ((of - rank) / (of - 1)) * 100 : 50);

/** Advantage between two stats. Uses league rank when both have one (so "lower is better"
 *  stats work automatically); otherwise compares the raw numbers in the right direction. */
export function statAdvantage(a: Stat | undefined, b: Stat | undefined): Advantage {
  if (!a || !b || !a.better || a.value == null || b.value == null) return NONE;
  if (a.value === b.value) return { leader: 'even', strength: 0 };
  if (a.rank != null && b.rank != null) {
    const ofA = a.of ?? 32;
    const ofB = b.of ?? 32;
    const gap = percentile(a.rank, ofA) - percentile(b.rank, ofB);
    if (gap !== 0) return fromGap(gap, settings.statRankGapForSolid);
  }
  const sign = a.better === 'low' ? -1 : 1;
  const scale = Math.max(Math.abs(a.value), Math.abs(b.value)) || 1;
  return fromGap((sign * (a.value - b.value)) / scale, settings.statRelativeGapForSolid);
}

const GREEN = [52, 199, 123];
const RED = [242, 95, 92];
const YELLOW = [217, 164, 65];

/** Background + text colors for one side of a row. */
export function shade(adv: Advantage, side: 'a' | 'b') {
  if (adv.leader == null) return { backgroundColor: 'transparent', dark: false };
  const alpha =
    adv.leader === 'even'
      ? settings.lightestShade + 0.2
      : settings.lightestShade + (settings.solidShade - settings.lightestShade) * adv.strength;
  const rgb = adv.leader === 'even' ? YELLOW : adv.leader === side ? GREEN : RED;
  return { backgroundColor: `rgba(${rgb.join(',')},${alpha.toFixed(2)})`, dark: alpha > 0.6 };
}
