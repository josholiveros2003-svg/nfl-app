import { Link, Stack } from 'expo-router';
import { useMemo, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { Loading, Screen, SectionTitle, Segmented, styles as ui } from '@/components/ui';
import { useSchedule, useTeams } from '@/lib/data';
import { buildStandings, compareStandings, conferenceSeeds, recordText, type Standing } from '@/lib/standings';
import { colors } from '@/lib/theme';
import { sized } from '@/lib/images';

type View_ = 'divisions' | 'conferences';
const VIEWS: { id: View_; label: string }[] = [
  { id: 'divisions', label: 'Divisions' },
  { id: 'conferences', label: 'Playoff picture' },
];
const DIVS = ['East', 'North', 'South', 'West'];

export default function StandingsScreen() {
  const [view, setView] = useState<View_>('divisions');
  const schedule = useSchedule();
  const teams = useTeams();
  const rows = useMemo(
    () => (schedule.data && teams.data ? buildStandings(schedule.data, teams.data.teams) : null),
    [schedule.data, teams.data],
  );

  return (
    <>
      <Stack.Screen options={{ title: 'Standings' }} />
      {!rows ? (
        <Loading error={schedule.error ?? teams.error} />
      ) : (
        <Screen>
          <Segmented options={VIEWS} value={view} onChange={setView} />
          {view === 'divisions'
            ? ['AFC', 'NFC'].flatMap((conf) =>
                DIVS.map((d) => {
                  const name = `${conf} ${d}`;
                  const list = rows.filter((r) => r.team.division === name).sort(compareStandings);
                  return (
                    <View key={name}>
                      <SectionTitle>{name}</SectionTitle>
                      <Table rows={list} />
                    </View>
                  );
                }),
              )
            : ['AFC', 'NFC'].map((conf) => {
                const { seeded, others } = conferenceSeeds(rows, conf);
                return (
                  <View key={conf} style={{ gap: 8 }}>
                    <SectionTitle>{conf} playoff picture</SectionTitle>
                    <Table rows={seeded} seeds />
                    <Text style={ui.muted}>Seeds 1–4 are division leaders; 5–7 are wild cards.</Text>
                    <Table rows={others} startAt={8} />
                  </View>
                );
              })}
          <Text style={ui.muted}>
            Ties are broken by win %, then division record (same division only), conference record and point differential (simplified; the
            NFL’s official tiebreakers have more steps). Tap a team to open it.
          </Text>
        </Screen>
      )}
    </>
  );
}

function Table({ rows, seeds, startAt }: { rows: Standing[]; seeds?: boolean; startAt?: number }) {
  return (
    <View style={s.table}>
      <View style={[s.row, s.head]}>
        <Text style={[s.hText, { flex: 1 }]}>{seeds ? 'SEED' : startAt ? '' : 'TEAM'}</Text>
        <Text style={[s.hText, s.col]}>W-L</Text>
        <Text style={[s.hText, s.col]}>PCT</Text>
        <Text style={[s.hText, s.col]}>DIFF</Text>
        <Text style={[s.hText, s.colS]}>STRK</Text>
      </View>
      {rows.map((r, i) => (
        <Link key={r.team.abbr} href={`/team/${r.team.abbr.toLowerCase()}`} asChild>
          <Pressable accessibilityRole="link" accessibilityLabel={`${r.team.name}, ${recordText([r.w, r.l, r.t])}`}>
            {({ pressed }) => (
              <View style={[s.row, i < rows.length - 1 && s.divider, pressed && { backgroundColor: colors.cardPressed }]}>
                {seeds || startAt ? <Text style={s.seed}>{(startAt ?? 1) + i}</Text> : null}
                <View style={s.logoBg}>
                  <Image source={{ uri: sized(r.team.logo, 22) }} style={s.logo} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.name} numberOfLines={1}>{r.team.nickname}</Text>
                  <Text style={s.sub}>
                    Div {recordText(r.div)} · Conf {recordText(r.conf)}
                  </Text>
                </View>
                <Text style={[s.cell, s.col]}>{recordText([r.w, r.l, r.t])}</Text>
                <Text style={[s.cell, s.col]}>{r.pct.toFixed(3).replace(/^0/, '')}</Text>
                <Text style={[s.cell, s.col, { color: r.diff > 0 ? colors.good : r.diff < 0 ? colors.bad : colors.muted }]}>
                  {r.diff > 0 ? `+${r.diff}` : r.diff}
                </Text>
                <Text style={[s.cell, s.colS]}>{r.streak}</Text>
              </View>
            )}
          </Pressable>
        </Link>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  table: { backgroundColor: colors.card, borderRadius: 14, overflow: 'hidden', borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, marginTop: 6 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 9, paddingHorizontal: 12 },
  head: { paddingVertical: 6, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  hText: { color: colors.muted, fontSize: 11, fontWeight: '800', letterSpacing: 0.5 },
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  seed: { color: colors.muted, width: 18, textAlign: 'right', fontWeight: '800', fontVariant: ['tabular-nums'] },
  logoBg: { width: 28, height: 28, borderRadius: 14, backgroundColor: 'rgba(255,255,255,0.92)', alignItems: 'center', justifyContent: 'center' },
  logo: { width: 22, height: 22 },
  name: { color: colors.text, fontSize: 15, fontWeight: '700' },
  sub: { color: colors.muted, fontSize: 11, marginTop: 1 },
  col: { width: 42, textAlign: 'right' },
  colS: { width: 34, textAlign: 'right' },
  cell: { color: colors.text, fontSize: 13, fontWeight: '600', fontVariant: ['tabular-nums'] },
});
