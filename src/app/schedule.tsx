import { Link, router, Stack, useLocalSearchParams } from 'expo-router';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Loading, Screen, SectionTitle, styles as ui } from '@/components/ui';
import { useSchedule, useTeams } from '@/lib/data';
import { colors, readableTeamColor } from '@/lib/theme';
import type { ScheduleGame, Team } from '@/lib/types';

// This week's games (or any week), grouped by day. Tapping a game opens the game screen.
// Address: /schedule (current week) or /schedule?week=7
export default function ScheduleScreen() {
  const params = useLocalSearchParams<{ week?: string }>();
  const { data, error } = useSchedule();
  const teams = useTeams();
  if (!data || !teams.data) return <Loading error={error ?? teams.error} />;

  const weeks = Object.keys(data.weeks).map(Number).sort((a, b) => a - b);
  const asked = Number(params.week);
  const week = weeks.includes(asked) ? asked : data.currentWeek;
  const games = data.weeks[String(week)] ?? [];
  const byTeam = Object.fromEntries(teams.data.teams.map((t) => [t.abbr, t]));
  const setWeek = (w: number) => router.setParams({ week: String(w) });

  // Group by day, in order.
  const days: { key: string; label: string; games: ScheduleGame[] }[] = [];
  for (const g of games) {
    let day = days.find((d) => d.key === g.date);
    if (!day) {
      const label = new Date(`${g.date}T12:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
      day = { key: g.date, label, games: [] };
      days.push(day);
    }
    day.games.push(g);
  }

  return (
    <>
      <Stack.Screen options={{ title: 'Schedule' }} />
      <Screen>
        <View style={s.weekBar}>
          <Pressable disabled={week <= weeks[0]} onPress={() => setWeek(week - 1)} hitSlop={10} accessibilityLabel="Previous week">
            <Text style={[s.arrow, week <= weeks[0] && s.disabled]}>‹</Text>
          </Pressable>
          <View style={{ alignItems: 'center' }}>
            <Text style={s.weekTitle}>Week {week}</Text>
            <Text style={ui.muted}>{week === data.currentWeek ? 'This week' : week < data.currentWeek ? 'Played' : 'Upcoming'}</Text>
          </View>
          <Pressable disabled={week >= weeks[weeks.length - 1]} onPress={() => setWeek(week + 1)} hitSlop={10} accessibilityLabel="Next week">
            <Text style={[s.arrow, week >= weeks[weeks.length - 1] && s.disabled]}>›</Text>
          </Pressable>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
          {weeks.map((w) => (
            <Pressable key={w} onPress={() => setWeek(w)} style={[s.chip, w === week && s.chipOn]} accessibilityLabel={`Week ${w}`}>
              <Text style={[s.chipText, w === week && s.chipTextOn]}>{w}</Text>
            </Pressable>
          ))}
        </ScrollView>

        {days.map((d) => (
          <View key={d.key} style={{ gap: 8 }}>
            <SectionTitle>{d.label}</SectionTitle>
            {d.games.map((g) => (
              <GameCard key={g.id} game={g} away={byTeam[g.away]} home={byTeam[g.home]} />
            ))}
          </View>
        ))}
        <Text style={ui.muted}>Kickoff times are Mountain Time (Utah). Win chances are the model’s call before kickoff.</Text>
      </Screen>
    </>
  );
}

/** Kickoff in Mountain Time (Utah). The schedule lists Eastern times; Mountain is always
 *  2 hours behind, since both switch to and from daylight saving time on the same dates. */
function kickoff(time: string) {
  const [h, m] = time.split(':').map(Number);
  if (Number.isNaN(h)) return time;
  const mt = (h - 2 + 24) % 24;
  return `${((mt + 11) % 12) + 1}:${String(m).padStart(2, '0')} ${mt >= 12 ? 'PM' : 'AM'} MT`;
}

function GameCard({ game, away, home }: { game: ScheduleGame; away?: Team; home?: Team }) {
  const played = game.homeScore != null && game.awayScore != null;
  return (
    <Link href={{ pathname: '/game', params: { id: game.id } }} asChild>
      <Pressable accessibilityRole="link" accessibilityLabel={`${game.away} at ${game.home}`}>
        {({ pressed }) => (
          <View style={[s.card, pressed && { backgroundColor: colors.cardPressed }]}>
            <View style={{ flex: 1, gap: 8 }}>
              <TeamLine team={away} abbr={game.away} record={game.awayRecord} score={game.awayScore} won={played && game.awayScore! > game.homeScore!} prob={game.prob?.away} />
              <TeamLine team={home} abbr={game.home} record={game.homeRecord} score={game.homeScore} won={played && game.homeScore! > game.awayScore!} prob={game.prob?.home} home />
              {game.prob && away && home ? (
                <View style={s.bar}>
                  <View style={{ flex: game.prob.away, backgroundColor: readableTeamColor(away.color, away.color2) }} />
                  <View style={{ width: 2, backgroundColor: colors.card }} />
                  <View style={{ flex: game.prob.home, backgroundColor: readableTeamColor(home.color, home.color2) }} />
                </View>
              ) : null}
            </View>
            <View style={s.side}>
              {played ? (
                <>
                  <Text style={s.final}>FINAL</Text>
                  {game.correct != null ? <Text style={s.verdict}>{game.correct ? 'Model ✓' : 'Model ✗'}</Text> : null}
                </>
              ) : (
                <Text style={s.time}>{kickoff(game.time)}</Text>
              )}
              {game.neutral ? <Text style={s.verdict}>Neutral</Text> : null}
            </View>
          </View>
        )}
      </Pressable>
    </Link>
  );
}

function TeamLine({ team, abbr, record, score, won, prob, home }: {
  team?: Team; abbr: string; record: string; score: number | null; won: boolean; prob?: number; home?: boolean;
}) {
  return (
    <View style={s.line}>
      <View style={s.logoBg}>{team ? <Image source={{ uri: team.logo }} style={s.logo} /> : null}</View>
      <Text style={s.name} numberOfLines={1}>
        {home ? '@ ' : ''}
        {team?.nickname ?? abbr}
      </Text>
      <Text style={s.record}>{record}</Text>
      {score != null ? (
        <Text style={[s.score, !won && { color: colors.muted }]}>{score}</Text>
      ) : prob != null ? (
        <Text style={s.prob}>{Math.round(prob * 100)}%</Text>
      ) : null}
    </View>
  );
}

const s = StyleSheet.create({
  weekBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 8 },
  arrow: { color: colors.text, fontSize: 34, fontWeight: '300', paddingHorizontal: 12 },
  disabled: { color: colors.border },
  weekTitle: { color: colors.text, fontSize: 20, fontWeight: '800' },
  chip: { minWidth: 34, paddingVertical: 6, paddingHorizontal: 8, borderRadius: 999, backgroundColor: colors.card, alignItems: 'center' },
  chipOn: { backgroundColor: colors.text },
  chipText: { color: colors.muted, fontWeight: '700', fontSize: 13 },
  chipTextOn: { color: colors.bg },
  card: {
    flexDirection: 'row', gap: 12, backgroundColor: colors.card, borderRadius: 14, padding: 12,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  line: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  logoBg: { width: 30, height: 30, borderRadius: 15, backgroundColor: 'rgba(255,255,255,0.92)', alignItems: 'center', justifyContent: 'center' },
  logo: { width: 24, height: 24 },
  name: { color: colors.text, fontSize: 15, fontWeight: '700', flex: 1 },
  record: { color: colors.muted, fontSize: 13, fontVariant: ['tabular-nums'] },
  score: { color: colors.text, fontSize: 18, fontWeight: '800', width: 34, textAlign: 'right', fontVariant: ['tabular-nums'] },
  prob: { color: colors.text, fontSize: 15, fontWeight: '700', width: 42, textAlign: 'right', fontVariant: ['tabular-nums'] },
  bar: { flexDirection: 'row', height: 6, borderRadius: 3, overflow: 'hidden' },
  side: { width: 74, alignItems: 'flex-end', justifyContent: 'center', gap: 4 },
  time: { color: colors.text, fontSize: 13, fontWeight: '700', textAlign: 'right' },
  final: { color: colors.muted, fontSize: 12, fontWeight: '800', letterSpacing: 0.6 },
  verdict: { color: colors.muted, fontSize: 11 },
});
