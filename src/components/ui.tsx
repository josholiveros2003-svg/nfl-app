import { Link, type Href } from 'expo-router';
import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View, type ViewStyle } from 'react-native';
import { colors, ordinal, rankColor } from '@/lib/theme';

/** Scrolling page body, kept to phone width on big screens. */
export function Screen({ children }: { children: ReactNode }) {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={styles.screen}>
      <View style={styles.inner}>{children}</View>
    </ScrollView>
  );
}

export function Loading({ error }: { error?: string }) {
  return (
    <View style={styles.center}>
      {error ? (
        <Text style={styles.muted}>Couldn’t load stats. Check your connection and try again.{'\n'}({error})</Text>
      ) : (
        <ActivityIndicator color={colors.muted} />
      )}
    </View>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <Text style={styles.section}>{children}</Text>;
}

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

/** A card you can tap to go to another screen. */
export function LinkCard({ href, children, accent }: { href: Href; children: ReactNode; accent?: string }) {
  return (
    <Link href={href} asChild>
      <Pressable>
        {({ pressed }) => (
          <View
            style={[
              styles.card,
              accent ? { borderLeftWidth: 4, borderLeftColor: accent } : null,
              pressed && { backgroundColor: colors.cardPressed },
            ]}
          >
            <View style={styles.row}>
              <View style={{ flex: 1 }}>{children}</View>
              <Text style={styles.chevron}>›</Text>
            </View>
          </View>
        )}
      </Pressable>
    </Link>
  );
}

/** "5th" in green/amber/red depending on how good the rank is. */
export function RankChip({ rank, of }: { rank: number | null; of?: number | null }) {
  if (rank == null) return null;
  const c = rankColor(rank, of);
  return (
    <View style={[styles.chip, { borderColor: c }]}>
      <Text style={[styles.chipText, { color: c }]}>{ordinal(rank)}</Text>
    </View>
  );
}

/** A row of buttons where one is selected (like iPhone's segmented control). */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <View style={styles.segWrap} accessibilityRole="tablist">
      {options.map((o) => {
        const active = o.id === value;
        return (
          <Pressable
            key={o.id}
            onPress={() => onChange(o.id)}
            style={[styles.segItem, active && styles.segActive]}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
          >
            <Text style={[styles.segText, active && styles.segTextActive]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export const styles = StyleSheet.create({
  segWrap: { flexDirection: 'row', backgroundColor: colors.card, borderRadius: 12, padding: 3, marginTop: 6 },
  segItem: { flex: 1, paddingVertical: 9, borderRadius: 9, alignItems: 'center' },
  segActive: { backgroundColor: colors.border },
  segText: { color: colors.muted, fontSize: 14, fontWeight: '600' },
  segTextActive: { color: colors.text },
  screen: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 48 },
  inner: { width: '100%', maxWidth: 640, alignSelf: 'center', gap: 10 },
  center: { flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center', padding: 24 },
  card: {
    backgroundColor: colors.card,
    borderRadius: 14,
    padding: 14,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  chevron: { color: colors.muted, fontSize: 26, fontWeight: '300', marginTop: -2 },
  section: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
    marginTop: 14,
    marginBottom: 2,
  },
  title: { color: colors.text, fontSize: 17, fontWeight: '700' },
  body: { color: colors.text, fontSize: 15 },
  muted: { color: colors.muted, fontSize: 13, textAlign: 'left' },
  chip: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2, minWidth: 44, alignItems: 'center' },
  chipText: { fontSize: 12, fontWeight: '700' },
});
