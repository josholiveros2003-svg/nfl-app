import { StyleSheet, Text, View } from 'react-native';
import type { Stat } from '@/lib/types';
import { colors, ordinal, rankColor } from '@/lib/theme';

/** A small row of 2–3 headline numbers used on summary cards. */
export function KeyStats({ stats }: { stats: (Stat | undefined)[] }) {
  return (
    <View style={s.row}>
      {stats.filter(Boolean).map((st) => (
        <View key={st!.id} style={s.cell}>
          <Text style={s.value}>{st!.display.split(/  | \(/)[0]}</Text>
          <Text style={s.label} numberOfLines={2}>
            {st!.label}
          </Text>
          {st!.rank != null && <Text style={[s.rank, { color: rankColor(st!.rank, st!.of) }]}>{ordinal(st!.rank)}{st!.of ? ` of ${st!.of}` : ''}</Text>}
        </View>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', gap: 8, marginTop: 10 },
  cell: { flex: 1, backgroundColor: colors.bg, borderRadius: 10, padding: 8 },
  value: { color: colors.text, fontSize: 17, fontWeight: '700', fontVariant: ['tabular-nums'] },
  label: { color: colors.muted, fontSize: 11, marginTop: 2 },
  rank: { fontSize: 12, fontWeight: '700', marginTop: 4 },
});
