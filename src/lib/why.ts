import type { WhyInfo } from '@/components/Rating';
import { UNITS, unitLabel } from './constants';
import type { Category, PlayerCategory, PlayerDoc, TeamDoc, UnitId } from './types';

// Builds what each "why this rating" sheet shows, following the same drill-down as the
// screens: team → unit → category → stat, and player → category → stat.

export function teamWhy(doc: TeamDoc): WhyInfo {
  const join = (key: 'opp' | 'inj') =>
    UNITS.slice(0, 2)
      .map((u) => `${u.label}: ${doc.context?.[u.id]?.[key] ?? ''}`)
      .join(' ');
  return {
    title: `${doc.team.name}`,
    team: true,
    rt: doc.team.rt,
    context: { opp: join('opp'), inj: join('inj'), recent: doc.context?.offense?.recent },
    parts: UNITS.map((u) => ({ label: u.label, w: doc.unitRatings?.[u.id]?.w, rt: doc.unitRatings?.[u.id]?.rt })),
  };
}

export function unitWhy(doc: TeamDoc, unit: UnitId): WhyInfo {
  return {
    title: `${doc.team.nickname} ${unitLabel(unit)}`,
    team: true,
    rt: doc.unitRatings?.[unit]?.rt,
    context: doc.context?.[unit],
    parts: doc.units[unit].map((c) => ({ label: c.label, w: c.w, rt: c.rt })),
  };
}

export function categoryWhy(doc: TeamDoc, unit: UnitId, cat: Category): WhyInfo {
  return {
    title: `${doc.team.nickname} ${cat.label === 'Overview' ? `${unitLabel(unit)} Overview` : cat.label}`,
    team: true,
    rt: cat.rt,
    context: doc.context?.[unit],
    parts: cat.stats.map((st) => ({ label: st.label, w: st.w, rt: st.rt })),
  };
}

export function playerWhy(p: PlayerDoc): WhyInfo {
  return {
    title: p.name,
    rt: p.rt,
    context: p.context,
    parts: p.categories.map((c) => ({ label: c.label, w: c.w, rt: c.rt })),
  };
}

export function playerCategoryWhy(p: PlayerDoc, cat: PlayerCategory): WhyInfo {
  return {
    title: `${p.name} · ${cat.label}`,
    rt: cat.rt,
    context: p.context,
    parts: cat.stats.map((st) => ({ label: st.label, w: st.w, rt: st.rt })),
  };
}
