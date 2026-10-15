import { Link, router, Stack, useLocalSearchParams } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { KeyStats } from '@/components/KeyStats';
import { TeamHeader } from '@/components/TeamHeader';
import { RatingBadge } from '@/components/Rating';
import { Roster } from '@/components/Roster';
import { Card, LinkCard, Loading, Screen, Segmented, styles as ui } from '@/components/ui';
import { TEAM_IDS, UNITS } from '@/lib/constants';
import { useTeam } from '@/lib/data';
import { colors, readableTeamColor } from '@/lib/theme';
import type { TeamDoc, UnitId } from '@/lib/types';
import { teamWhy } from '@/lib/why';

// Pre-build a page for every team when exporting the website.
export async function generateStaticParams() {
  return TEAM_IDS.map((t) => ({ team: t.toLowerCase() }));
}

// The headline numbers shown on each unit's card: [category id, stat id].
const HEADLINES: Record<UnitId, [string, string][]> = {
  offense: [['overview', 'ppg'], ['overview', 'ypg'], ['overview', 'epa']],
  defense: [['overview', 'papg'], ['overview', 'yapg'], ['overview', 'takeaways']],
  special: [['kicking', 'fg_pct'], ['punting', 'net'], ['returns', 'kr_avg']],
};

const findStat = (doc: TeamDoc, unit: UnitId, cat: string, stat: string) =>
  doc.units[unit].find((c) => c.id === cat)?.stats.find((s) => s.id === stat);

type Tab = 'stats' | 'schedule' | 'roster';
const TABS: { id: Tab; label: string }[] = [
  { id: 'stats', label: 'Team Stats' },
  { id: 'schedule', label: 'Schedule' },
  { id: 'roster', label: 'Roster' },
];

export default function TeamScreen() {
  const params = useLocalSearchParams<{ team: string; tab?: Tab }>();
  const team = params.team;
  const tab: Tab = TABS.some((t) => t.id === params.tab) ? (params.tab as Tab) : 'stats';
  const { data, error } = useTeam(team);
  // The chosen tab goes in the address (?tab=roster) so "back" from a player returns here.
  const setTab = (t: Tab) => router.setParams({ tab: t === 'stats' ? undefined : t });

  return (
    <>
      <Stack.Screen options={{ title: data?.team.nickname ?? team?.toUpperCase() ?? '' }} />
      {!data ? (
        <Loading error={error} />
      ) : (
        <Screen>
          <TeamHeader team={data.team} rating={teamWhy(data)} />

          <Segmented options={TABS} value={tab} onChange={setTab} />

          {tab === 'stats' && (
            <>
              {UNITS.map((u) => (
                <LinkCard
                  key={u.id}
                  href={`/team/${team}/${u.id}`}
                  accent={readableTeamColor(data.team.color, data.team.color2)}
                >
                  <View style={ui.row}>
                    <Text style={[ui.title, { flex: 1 }]}>{u.label}</Text>
                    <RatingBadge rt={data.unitRatings?.[u.id]?.rt} size="sm" />
                  </View>
                  <Text style={ui.muted}>{data.units[u.id].map((c) => c.label).join(' · ')}</Text>
                  <KeyStats stats={HEADLINES[u.id].map(([c, st]) => findStat(data, u.id, c, st))} />
                </LinkCard>
              ))}
            </>
          )}

          {tab === 'schedule' && (
            <Card style={{ paddingVertical: 0, paddingHorizontal: 0, overflow: 'hidden' }}>
              {data.games.map((g, i) => {
                const row = (pressed: boolean) => (
                  <View style={[s.game, i < data.games.length - 1 && s.divider, pressed && { backgroundColor: colors.cardPressed }]}>
                    <Text style={s.week}>Wk {g.week}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={s.opp}>
                        {g.home ? 'vs' : '@'} {g.opp}
                      </Text>
                      {g.wp != null ? (
                        <Text style={s.wp}>
                          {g.result ? 'Model gave them' : 'Chance to win'} {Math.round(g.wp * 100)}%
                          {g.result && g.result !== 'T' ? ((g.wp > 0.5) === (g.result === 'W') ? ' · ✓' : ' · ✗') : ''}
                        </Text>
                      ) : null}
                    </View>
                    {g.result ? (
                      <Text style={[s.score, { color: g.result === 'W' ? colors.good : g.result === 'L' ? colors.bad : colors.mid }]}>
                        {g.result} {g.pf}–{g.pa}
                      </Text>
                    ) : (
                      <Text style={s.date}>{formatDate(g.date)}</Text>
                    )}
                    {g.id ? <Text style={s.chev}>›</Text> : null}
                  </View>
                );
                return g.id ? (
                  <Link key={g.week} href={{ pathname: '/game', params: { id: g.id } }} asChild>
                    <Pressable accessibilityRole="link" accessibilityLabel={`Week ${g.week} game details`}>
                      {({ pressed }) => row(pressed)}
                    </Pressable>
                  </Link>
                ) : (
                  <View key={g.week}>{row(false)}</View>
                );
              })}
            </Card>
          )}

          {tab === 'roster' && <Roster sections={data.roster} />}

          <Text style={[ui.muted, { marginTop: 8 }]}>
            {data.season} regular season through Week {data.throughWeek}. Ranks are out of 32 teams. Data: nflverse, updated{' '}
            {new Date(data.updated).toLocaleString()}.
          </Text>
        </Screen>
      )}
    </>
  );
}

function formatDate(iso: string) {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

const s = StyleSheet.create({
  game: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, paddingHorizontal: 14, gap: 12 },
  wp: { color: colors.muted, fontSize: 12, marginTop: 2 },
  chev: { color: colors.muted, fontSize: 20, marginTop: -2 },
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  week: { color: colors.muted, width: 44, fontSize: 13 },
  opp: { color: colors.text, flex: 1, fontSize: 15 },
  score: { fontWeight: '700', fontSize: 15, fontVariant: ['tabular-nums'] },
  date: { color: colors.muted, fontSize: 14 },
});
