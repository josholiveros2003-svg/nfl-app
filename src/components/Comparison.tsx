import { Link, type Href } from 'expo-router';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import {
  nodeAt,
  pairChildren,
  ratingAdvantage,
  shade,
  statAdvantage,
  type Advantage,
  type CompareNode,
  type CompareSide,
} from '@/lib/compare';
import { useRating } from '@/lib/ratings';
import { colors, ordinal } from '@/lib/theme';

type Props = {
  a: CompareSide;
  b: CompareSide;
  /** Where we are in the drill-down, e.g. ["offense", "passing"]. */
  path: string[];
  /** Address for one level deeper (the screen decides how links look). */
  hrefFor: (path: string[]) => Href;
};

/** Side-by-side comparison of any two things that can be turned into a CompareNode tree
 *  (teams, players, and later the two teams in a game). Every row is shaded to show who has
 *  the advantage and by how much. */
export function Comparison({ a, b, path, hrefFor }: Props) {
  const nodeA = nodeAt(a.tree, path);
  const nodeB = nodeAt(b.tree, path);
  const rows = pairChildren(nodeA, nodeB);
  const ratingA = useRating(a.tree.rt)?.rating;
  const ratingB = useRating(b.tree.rt)?.rating;
  const overall = ratingAdvantage(ratingA, ratingB);
  const crumbs = ['Overall', ...path.map((_, i) => (nodeAt(a.tree, path.slice(0, i + 1)) ?? nodeAt(b.tree, path.slice(0, i + 1)))?.label ?? '')];

  return (
    <View style={{ gap: 10 }}>
      {/* Header: who's being compared, with their overall ratings. */}
      <View style={s.header}>
        <SideHeader side={a} rating={ratingA} adv={overall} which="a" />
        <Text style={s.vs}>vs</Text>
        <SideHeader side={b} rating={ratingB} adv={overall} which="b" />
      </View>

      {/* Breadcrumb: Overall › Offense › Passing (each step tappable). */}
      <View style={s.crumbs}>
        {crumbs.map((label, i) => (
          <View key={i} style={s.crumbItem}>
            {i > 0 ? <Text style={s.crumbSep}>›</Text> : null}
            {i < crumbs.length - 1 ? (
              <Link href={hrefFor(path.slice(0, i))} style={s.crumbLink}>
                {label}
              </Link>
            ) : (
              <Text style={s.crumbHere}>{label}</Text>
            )}
          </View>
        ))}
      </View>

      {path.length > 0 ? <RatingRow label={`${crumbs[crumbs.length - 1]} rating`} a={nodeA} b={nodeB} strong /> : null}

      <View style={s.table}>
        {rows.map((row, i) => {
          const deeper = !!(row.a?.children?.length || row.b?.children?.length);
          const content = (row.a?.stat || row.b?.stat) && !deeper
            ? <StatRow label={(row.a ?? row.b)!.label} a={row.a} b={row.b} />
            : <RatingRow label={(row.a ?? row.b)!.label} a={row.a} b={row.b} chevron={deeper} />;
          return (
            <View key={row.key} style={i < rows.length - 1 ? s.divider : null}>
              {deeper ? (
                <Link href={hrefFor([...path, row.key])} asChild>
                  <Pressable accessibilityRole="link">{({ pressed }) => <View style={pressed && s.pressed}>{content}</View>}</Pressable>
                </Link>
              ) : (
                content
              )}
            </View>
          );
        })}
      </View>

      <Legend />
    </View>
  );
}

function SideHeader({ side, rating, adv, which }: { side: CompareSide; rating?: number; adv: Advantage; which: 'a' | 'b' }) {
  const sh = shade(adv, which);
  return (
    <Link href={side.href as Href} asChild>
      <Pressable style={StyleSheet.flatten([s.side, { backgroundColor: sh.backgroundColor }])} accessibilityRole="link">
        <View style={s.imageWrap}>
          {side.image ? <Image source={{ uri: side.image }} style={s.image} /> : <Text style={s.initial}>{side.name[0]}</Text>}
        </View>
        <Text style={[s.sideName, sh.dark && s.darkText]} numberOfLines={2}>
          {side.name}
        </Text>
        <Text style={[s.sideSub, sh.dark && s.darkSub]} numberOfLines={1}>
          {side.subtitle}
        </Text>
        <Text style={[s.sideRating, sh.dark && s.darkText]}>{rating ?? '—'}</Text>
        <Text style={[s.sideLabel, sh.dark && s.darkSub]}>OVERALL</Text>
      </Pressable>
    </Link>
  );
}

/** A row comparing two 0-100 ratings (overall, unit or category). */
function RatingRow({ label, a, b, chevron, strong }: { label: string; a: CompareNode | null; b: CompareNode | null; chevron?: boolean; strong?: boolean }) {
  const ra = useRating(a?.rt);
  const rb = useRating(b?.rt);
  const adv = ratingAdvantage(ra?.rating, rb?.rating);
  return (
    <View style={[s.row, strong && s.strongRow]}>
      <Cell adv={adv} which="a" main={ra?.rating != null ? String(ra.rating) : '—'} sub={ra?.limited ? 'LTD' : undefined} />
      <View style={s.labelBox}>
        <Text style={[s.label, strong && { fontWeight: '800' }]} numberOfLines={2}>
          {label}
        </Text>
        {chevron ? <Text style={s.more}>Tap for details ›</Text> : null}
      </View>
      <Cell adv={adv} which="b" main={rb?.rating != null ? String(rb.rating) : '—'} sub={rb?.limited ? 'LTD' : undefined} />
    </View>
  );
}

/** A row comparing one stat: its value, league rank and 0-100 rating on each side. */
function StatRow({ label, a, b }: { label: string; a: CompareNode | null; b: CompareNode | null }) {
  const ra = useRating(a?.rt);
  const rb = useRating(b?.rt);
  const adv = statAdvantage(a?.stat, b?.stat);
  const sub = (n: CompareNode | null, r?: number) =>
    [n?.stat?.rank != null ? ordinal(n.stat.rank) : null, r != null ? `${r} rtg` : null].filter(Boolean).join(' · ') || undefined;
  const lowerBetter = (a?.stat ?? b?.stat)?.better === 'low';
  return (
    <View style={s.row}>
      <Cell adv={adv} which="a" main={a?.stat?.display?.split('  ')[0] ?? '—'} sub={sub(a, ra?.rating)} small />
      <View style={s.labelBox}>
        <Text style={s.label} numberOfLines={3}>
          {label}
        </Text>
        {lowerBetter ? <Text style={s.more}>lower is better</Text> : null}
        {!(a?.stat ?? b?.stat)?.better ? <Text style={s.more}>info only</Text> : null}
      </View>
      <Cell adv={adv} which="b" main={b?.stat?.display?.split('  ')[0] ?? '—'} sub={sub(b, rb?.rating)} small />
    </View>
  );
}

function Cell({ adv, which, main, sub, small }: { adv: Advantage; which: 'a' | 'b'; main: string; sub?: string; small?: boolean }) {
  const sh = shade(adv, which);
  return (
    <View style={[s.cell, { backgroundColor: sh.backgroundColor }]}>
      <Text style={[small ? s.cellMainSmall : s.cellMain, sh.dark && s.darkText]} numberOfLines={1} adjustsFontSizeToFit>
        {main}
      </Text>
      {sub ? (
        <Text style={[s.cellSub, sh.dark && s.darkSub]} numberOfLines={1}>
          {sub}
        </Text>
      ) : null}
    </View>
  );
}

function Legend() {
  const swatch = (adv: Advantage, which: 'a' | 'b') => <View style={[s.swatch, { backgroundColor: shade(adv, which).backgroundColor }]} />;
  return (
    <View style={s.legend}>
      <View style={s.legendItem}>
        {swatch({ leader: 'a', strength: 0.2 }, 'a')}
        {swatch({ leader: 'a', strength: 1 }, 'a')}
        <Text style={s.legendText}>ahead (small → big gap)</Text>
      </View>
      <View style={s.legendItem}>
        {swatch({ leader: 'b', strength: 0.2 }, 'a')}
        {swatch({ leader: 'b', strength: 1 }, 'a')}
        <Text style={s.legendText}>behind</Text>
      </View>
      <View style={s.legendItem}>
        {swatch({ leader: 'even', strength: 0 }, 'a')}
        <Text style={s.legendText}>even</Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'stretch', gap: 8 },
  vs: { color: colors.muted, fontWeight: '800', alignSelf: 'center', fontSize: 13 },
  side: {
    flex: 1, alignItems: 'center', padding: 12, borderRadius: 14, gap: 2,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, minHeight: 168,
  },
  imageWrap: { width: 56, height: 56, borderRadius: 28, backgroundColor: 'rgba(255,255,255,0.92)', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginBottom: 4 },
  image: { width: 52, height: 52, borderRadius: 26 },
  initial: { fontSize: 22, fontWeight: '800', color: '#333' },
  sideName: { color: colors.text, fontSize: 15, fontWeight: '800', textAlign: 'center' },
  sideSub: { color: colors.muted, fontSize: 12 },
  sideRating: { color: colors.text, fontSize: 30, fontWeight: '800', marginTop: 4, fontVariant: ['tabular-nums'] },
  sideLabel: { color: colors.muted, fontSize: 10, fontWeight: '800', letterSpacing: 0.6 },
  darkText: { color: '#0B0F17' },
  darkSub: { color: 'rgba(11,15,23,0.7)' },
  crumbs: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 4 },
  crumbItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  crumbSep: { color: colors.muted },
  crumbLink: { color: '#7FB2FF', fontWeight: '600', fontSize: 14 },
  crumbHere: { color: colors.text, fontWeight: '700', fontSize: 14 },
  table: { backgroundColor: colors.card, borderRadius: 14, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, overflow: 'hidden' },
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  pressed: { opacity: 0.7 },
  row: { flexDirection: 'row', alignItems: 'stretch', minHeight: 56 },
  strongRow: { backgroundColor: colors.card, borderRadius: 14, overflow: 'hidden', borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  cell: { width: '30%', alignItems: 'center', justifyContent: 'center', paddingVertical: 8, paddingHorizontal: 4 },
  cellMain: { color: colors.text, fontSize: 20, fontWeight: '800', fontVariant: ['tabular-nums'] },
  cellMainSmall: { color: colors.text, fontSize: 16, fontWeight: '700', fontVariant: ['tabular-nums'] },
  cellSub: { color: colors.muted, fontSize: 11, marginTop: 2 },
  labelBox: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6, paddingVertical: 8 },
  label: { color: colors.text, fontSize: 14, fontWeight: '600', textAlign: 'center' },
  more: { color: colors.muted, fontSize: 11, marginTop: 2 },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, justifyContent: 'center', marginTop: 4 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  swatch: { width: 14, height: 14, borderRadius: 3 },
  legendText: { color: colors.muted, fontSize: 12 },
});
