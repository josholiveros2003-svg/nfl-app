import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { RatingBadge } from '@/components/Rating';
import { Card, Loading, Screen, SectionTitle, Segmented, styles as ui } from '@/components/ui';
import { usePlayersIndex, useTeams } from '@/lib/data';
import { colors } from '@/lib/theme';
import type { PlayerIndexEntry, Team } from '@/lib/types';
import { useIsClient } from '@/lib/useIsClient';

type Kind = 'teams' | 'players';
const KINDS: { id: Kind; label: string }[] = [
  { id: 'teams', label: 'Teams' },
  { id: 'players', label: 'Players' },
];

const GROUP_NAME: Record<string, string> = {
  QB: 'quarterbacks', RB: 'running backs', WR: 'wide receivers', TE: 'tight ends', OL: 'offensive linemen',
  DL: 'defensive linemen', LB: 'linebackers', DB: 'defensive backs', K: 'kickers', P: 'punters', LS: 'long snappers',
};

// Pick any two teams, or any two players at the same position, then compare them.
export default function ComparePickerScreen() {
  const params = useLocalSearchParams<{ kind?: string }>();
  const isClient = useIsClient();
  // The address can ask for ?kind=players; only follow it once in the browser (see useIsClient).
  const [chosen, setKind] = useState<Kind | null>(null);
  const kind: Kind = chosen ?? (isClient && params.kind === 'players' ? 'players' : 'teams');

  return (
    <>
      <Stack.Screen options={{ title: 'Compare' }} />
      <Screen>
        <Text style={ui.muted}>
          Compare any two teams, or two players at the same position, side by side, whether or not they play each
          other.
        </Text>
        <Segmented options={KINDS} value={kind} onChange={setKind} />
        {kind === 'teams' ? <TeamPicker /> : <PlayerPicker />}
      </Screen>
    </>
  );
}

function go(kind: Kind, a: string, b: string) {
  router.push({ pathname: '/compare/view', params: { kind, a, b } });
}

// ---- Teams ----

function TeamPicker() {
  const { data, error } = useTeams();
  const [a, setA] = useState<Team | null>(null);
  const [b, setB] = useState<Team | null>(null);
  if (!data) return <Loading error={error} />;

  const pick = (t: Team) => {
    if (!a) setA(t);
    else if (!b && t.abbr !== a.abbr) setB(t);
  };

  return (
    <>
      <Slots
        a={a ? { name: a.name, sub: a.record, image: a.logo, rt: a.rt } : null}
        b={b ? { name: b.name, sub: b.record, image: b.logo, rt: b.rt } : null}
        clearA={() => {
          setA(b);
          setB(null);
        }}
        clearB={() => setB(null)}
        onCompare={a && b ? () => go('teams', a.abbr.toLowerCase(), b.abbr.toLowerCase()) : undefined}
        prompt={!a ? 'Tap the first team' : !b ? 'Now tap the second team' : null}
      />
      {!b ? (
        <Card style={{ paddingVertical: 4, paddingHorizontal: 0, overflow: 'hidden' }}>
          {[...data.teams]
            .sort((x, y) => x.name.localeCompare(y.name))
            .filter((t) => t.abbr !== a?.abbr)
            .map((t, i, list) => (
              <Pressable key={t.abbr} onPress={() => pick(t)} style={({ pressed }) => [s.pickRow, i < list.length - 1 && s.divider, pressed && s.pressed]}>
                <View style={s.logoBg}>
                  <Image source={{ uri: t.logo }} style={s.logo} />
                </View>
                <Text style={s.pickName}>{t.name}</Text>
                <Text style={s.pickSub}>{t.record}</Text>
                <RatingBadge rt={t.rt} size="sm" />
              </Pressable>
            ))}
        </Card>
      ) : null}
    </>
  );
}

// ---- Players ----

const norm = (x: string) => x.toLowerCase().normalize('NFD').replace(/[^a-z ]/g, '');

function PlayerPicker() {
  const { data, error } = usePlayersIndex();
  const [a, setA] = useState<PlayerIndexEntry | null>(null);
  const [b, setB] = useState<PlayerIndexEntry | null>(null);
  const [query, setQuery] = useState('');

  const results = useMemo(() => {
    if (!data) return [];
    const q = norm(query.trim());
    const pool = data.filter((p) => p.team && (!a || (p.group === a.group && p.id !== a.id)));
    const hits = q ? pool.filter((p) => norm(p.name).includes(q)) : pool.filter((p) => p.starter);
    // Starters first, then by name.
    return hits.sort((x, y) => Number(y.starter) - Number(x.starter) || x.name.localeCompare(y.name)).slice(0, 25);
  }, [data, query, a]);

  if (!data) return <Loading error={error} />;

  const pick = (p: PlayerIndexEntry) => {
    if (!a) setA(p);
    else setB(p);
    setQuery('');
  };
  const slot = (p: PlayerIndexEntry | null) =>
    p ? { name: p.name, sub: [p.pos, p.team].filter(Boolean).join(' · '), image: null, rt: p.rt } : null;

  return (
    <>
      <Slots
        a={slot(a)}
        b={slot(b)}
        clearA={() => {
          setA(b);
          setB(null);
        }}
        clearB={() => setB(null)}
        onCompare={a && b ? () => go('players', a.id, b.id) : undefined}
        prompt={!a ? 'Search for the first player' : !b ? `Now pick another of the ${GROUP_NAME[a.group] ?? a.group}` : null}
      />
      {!b ? (
        <>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder={a ? `Search ${GROUP_NAME[a.group] ?? 'players'}…` : 'Search any player…'}
            placeholderTextColor={colors.muted}
            style={s.search}
            autoCorrect={false}
            autoCapitalize="words"
            accessibilityLabel="Search players"
          />
          <SectionTitle>{query ? 'Matches' : a ? `Starting ${GROUP_NAME[a.group] ?? ''}` : 'Starters'}</SectionTitle>
          <Card style={{ paddingVertical: 4, paddingHorizontal: 0, overflow: 'hidden' }}>
            {results.length ? (
              results.map((p, i) => (
                <Pressable key={p.id} onPress={() => pick(p)} style={({ pressed }) => [s.pickRow, i < results.length - 1 && s.divider, pressed && s.pressed]}>
                  <View style={{ flex: 1 }}>
                    <Text style={s.pickName}>{p.name}</Text>
                    <Text style={s.pickSub}>{[p.jersey != null ? `#${p.jersey}` : null, p.pos, p.team].filter(Boolean).join(' · ')}</Text>
                  </View>
                  <RatingBadge rt={p.rt} size="sm" />
                </Pressable>
              ))
            ) : (
              <Text style={[ui.muted, { padding: 14 }]}>No players match “{query}”.</Text>
            )}
          </Card>
        </>
      ) : null}
    </>
  );
}

// ---- The two slots + Compare button ----

type SlotInfo = { name: string; sub: string; image: string | null; rt?: PlayerIndexEntry['rt'] } | null;

function Slots({ a, b, clearA, clearB, onCompare, prompt }: {
  a: SlotInfo; b: SlotInfo; clearA: () => void; clearB: () => void; onCompare?: () => void; prompt: string | null;
}) {
  return (
    <View style={{ gap: 8 }}>
      <View style={s.slots}>
        <Slot info={a} label="First" onClear={clearA} />
        <Text style={s.vs}>vs</Text>
        <Slot info={b} label="Second" onClear={clearB} />
      </View>
      {prompt ? <Text style={[ui.muted, { textAlign: 'center' }]}>{prompt}</Text> : null}
      {onCompare ? (
        <Pressable onPress={onCompare} style={({ pressed }) => [s.compareBtn, pressed && s.pressed]} accessibilityRole="button">
          <Text style={s.compareText}>Compare</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function Slot({ info, label, onClear }: { info: SlotInfo; label: string; onClear: () => void }) {
  return (
    <View style={[s.slot, !info && s.slotEmpty]}>
      {info ? (
        <>
          {info.image ? (
            <View style={s.logoBg}>
              <Image source={{ uri: info.image }} style={s.logo} />
            </View>
          ) : null}
          <Text style={s.slotName} numberOfLines={2}>
            {info.name}
          </Text>
          <Text style={s.pickSub}>{info.sub}</Text>
          <RatingBadge rt={info.rt} size="sm" />
          <Pressable onPress={onClear} hitSlop={8} accessibilityRole="button" accessibilityLabel={`Remove ${info.name}`}>
            <Text style={s.change}>Change</Text>
          </Pressable>
        </>
      ) : (
        <Text style={s.slotLabel}>{label}</Text>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  slots: { flexDirection: 'row', alignItems: 'stretch', gap: 8, marginTop: 4 },
  vs: { color: colors.muted, fontWeight: '800', alignSelf: 'center' },
  slot: {
    flex: 1, alignItems: 'center', justifyContent: 'center', gap: 4, padding: 12, minHeight: 130, borderRadius: 14,
    backgroundColor: colors.card, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  slotEmpty: { borderStyle: 'dashed', borderWidth: 1.5, backgroundColor: 'transparent' },
  slotLabel: { color: colors.muted, fontWeight: '700' },
  slotName: { color: colors.text, fontWeight: '800', fontSize: 15, textAlign: 'center' },
  change: { color: '#7FB2FF', fontWeight: '700', fontSize: 13, marginTop: 2 },
  compareBtn: { backgroundColor: colors.good, borderRadius: 12, paddingVertical: 13, alignItems: 'center' },
  compareText: { color: '#0B0F17', fontWeight: '800', fontSize: 16 },
  search: {
    backgroundColor: colors.card, color: colors.text, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12,
    fontSize: 16, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  pickRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, paddingHorizontal: 14 },
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  pressed: { opacity: 0.7 },
  logoBg: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.92)', alignItems: 'center', justifyContent: 'center' },
  logo: { width: 28, height: 28 },
  pickName: { color: colors.text, fontSize: 15, fontWeight: '600', flex: 1 },
  pickSub: { color: colors.muted, fontSize: 12 },
});
