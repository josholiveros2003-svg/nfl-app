import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { RatingContext, Stat } from '@/lib/types';
import { RatingButton } from './Rating';
import { colors, ordinal, rankColor, rankFill } from '@/lib/theme';
import { RankChip } from './ui';

type Props = {
  stat: Stat;
  last?: boolean;
  /** "League avg" for teams, "QB avg" etc. for players. */
  avgLabel?: string;
  /** For players: who he's ranked against, e.g. "QBs" → "5th of 31 QBs". */
  rankedAmong?: string;
  /** Title for the "why this rating" sheet, e.g. "Bills · Net yards per attempt". */
  ratingTitle?: string;
  context?: RatingContext | null;
  /** A team stat (its baseline comes from the team's Madden roster rating). */
  team?: boolean;
};

/** One stat: name, value, rank, a bar showing where he/the team sits among the
 *  rest, and (tap to open) a plain-language explanation. */
export function StatRow({ stat, last, avgLabel = 'League avg', rankedAmong, ratingTitle, context, team }: Props) {
  const [open, setOpen] = useState(false);
  const hasHint = !!stat.hint;
  const fill = rankFill(stat.rank, stat.of);
  const color = rankColor(stat.rank, stat.of);

  // Two separate tap targets side by side (web doesn't allow a button inside a button):
  // the stat itself (shows the ⓘ explanation) and the rating badge (shows "why").
  return (
    <View style={[s.row, !last && s.divider]}>
      <Pressable
        disabled={!hasHint}
        onPress={() => setOpen((o) => !o)}
        style={s.main}
        accessibilityRole={hasHint ? 'button' : undefined}
        accessibilityHint={hasHint ? 'Shows what this stat means' : undefined}
      >
        <View style={s.top}>
          <Text style={s.label}>
            {stat.label}
            {hasHint ? <Text style={s.info}>  ⓘ</Text> : null}
          </Text>
          <Text style={s.value}>{stat.display}</Text>
          <RankChip rank={stat.rank} of={stat.of} />
        </View>

        {stat.rank != null && (
          <View style={s.track}>
            <View style={[s.fill, { width: `${fill * 100}%`, backgroundColor: color }]} />
          </View>
        )}

        <Text style={s.avg}>
          {avgLabel}: {stat.leagueAvg ?? '—'}
          {rankedAmong && stat.rank != null && stat.of ? `  ·  ${ordinal(stat.rank)} of ${stat.of} ${rankedAmong}` : ''}
          {stat.better === 'low' ? '  ·  lower is better' : ''}
        </Text>

        {open && stat.hint ? <Text style={s.hint}>{stat.hint}</Text> : null}
      </Pressable>

      {stat.better ? (
        <RatingButton size="sm" info={{ title: ratingTitle ?? stat.label, rt: stat.rt, context, team }} />
      ) : (
        <View style={s.noRating}>
          <Text style={s.noRatingText}>info{'\n'}only</Text>
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  row: { paddingVertical: 12, flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  main: { flex: 1, gap: 6 },
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  top: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  label: { flex: 1, color: colors.text, fontSize: 15 },
  info: { color: colors.muted, fontSize: 13 },
  value: { color: colors.text, fontSize: 16, fontWeight: '700', fontVariant: ['tabular-nums'] },
  track: { height: 4, borderRadius: 2, backgroundColor: colors.border, overflow: 'hidden' },
  fill: { height: 4, borderRadius: 2 },
  avg: { color: colors.muted, fontSize: 12 },
  hint: { color: colors.text, opacity: 0.85, fontSize: 13, lineHeight: 18, marginTop: 2 },
  noRating: { width: 34, alignItems: 'center', paddingTop: 4 },
  noRatingText: { color: colors.muted, fontSize: 9, fontWeight: '700', textTransform: 'uppercase', textAlign: 'center' },
});
