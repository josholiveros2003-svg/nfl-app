import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useWinProbReport } from '@/lib/data';
import { colors, readableTeamColor } from '@/lib/theme';
import type { GameDoc, MissingPlayer, Team } from '@/lib/types';

type Teams = { home: Team; away: Team };
const pct = (p: number) => `${Math.round(p * 100)}%`;

/** Top of a game screen: win chances before kickoff, or the final score + what the model said. */
export function GameHeader({ game, teams }: { game: GameDoc; teams: Teams }) {
  const [open, setOpen] = useState(false);
  const { home, away } = teams;
  const favorite = game.prob.home >= game.prob.away ? home : away;
  const date = new Date(`${game.date}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });

  return (
    <View style={s.card}>
      <Text style={s.kicker}>
        Week {game.week} · {date}
        {game.neutral ? ' · Neutral site' : ''}
      </Text>

      {game.played ? (
        <View style={s.scoreRow}>
          <Score team={away} points={game.awayScore} won={(game.awayScore ?? 0) > (game.homeScore ?? 0)} />
          <Text style={s.final}>FINAL</Text>
          <Score team={home} points={game.homeScore} won={(game.homeScore ?? 0) > (game.awayScore ?? 0)} />
        </View>
      ) : null}

      <Text style={s.caption}>{game.played ? 'What the model gave each team before kickoff' : 'Chance to win'}</Text>
      <View style={s.probRow}>
        <Text style={[s.prob, { textAlign: 'left' }]}>
          {away.abbr} {pct(game.prob.away)}
        </Text>
        <Text style={[s.prob, { textAlign: 'right' }]}>
          {pct(game.prob.home)} {home.abbr}
        </Text>
      </View>
      <View style={s.bar}>
        <View style={{ flex: game.prob.away, backgroundColor: readableTeamColor(away.color, away.color2) }} />
        <View style={{ width: 2, backgroundColor: colors.bg }} />
        <View style={{ flex: game.prob.home, backgroundColor: readableTeamColor(home.color, home.color2) }} />
      </View>
      <Text style={s.sub}>
        {Math.abs(game.margin) < 0.5
          ? 'Expected to be a toss-up'
          : `${favorite.nickname} expected to win by about ${Math.abs(game.margin).toFixed(1)} points`}
        {game.played && game.correct != null ? (game.correct ? ' · ✓ the model picked the winner' : ' · ✗ the model picked the loser') : ''}
      </Text>

      <Pressable onPress={() => setOpen(true)} style={({ pressed }) => [s.whyBtn, pressed && { opacity: 0.7 }]} accessibilityRole="button">
        <Text style={s.whyText}>Why this probability?</Text>
      </Pressable>
      {open ? <WhyProbSheet game={game} teams={teams} onClose={() => setOpen(false)} /> : null}
    </View>
  );
}

function Score({ team, points, won }: { team: Team; points: number | null; won: boolean }) {
  return (
    <View style={{ alignItems: 'center', flex: 1 }}>
      <Text style={s.scoreTeam}>{team.abbr}</Text>
      <Text style={[s.score, !won && { color: colors.muted }]}>{points ?? '—'}</Text>
    </View>
  );
}

/** Which factors helped each team most, and how much injuries mattered. */
function WhyProbSheet({ game, teams, onClose }: { game: GameDoc; teams: Teams; onClose: () => void }) {
  const { data: report } = useWinProbReport();
  const { home, away } = teams;
  const helped = (points: number) => (points > 0.05 ? home : points < -0.05 ? away : null);
  const homeHelps = game.factors.filter((f) => f.points > 0.05);
  const awayHelps = game.factors.filter((f) => f.points < -0.05);
  const none = game.factors.filter((f) => Math.abs(f.points) <= 0.05);
  const all = report?.all?.model;
  const seventy = all?.calibration.find((b) => b.band.startsWith('70'));
  const injuryFactor = game.factors.find((f) => f.id === 'injuries');
  const injuryTeam = injuryFactor ? helped(injuryFactor.points) : null;
  const injuryPoints = Math.abs(injuryFactor?.points ?? 0);

  return (
    <Modal transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={s.backdrop} onPress={onClose} accessibilityLabel="Close">
        <Pressable style={s.sheet} onPress={() => {}}>
          <ScrollView contentContainerStyle={{ padding: 18, gap: 12 }}>
            <View style={s.sheetHead}>
              <View style={{ flex: 1 }}>
                <Text style={s.sheetTitle}>
                  {away.abbr} {pct(game.prob.away)} · {home.abbr} {pct(game.prob.home)}
                </Text>
                <Text style={s.sheetSub}>Why this probability</Text>
              </View>
              <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button" accessibilityLabel="Close">
                <Text style={s.close}>✕</Text>
              </Pressable>
            </View>

            <Text style={s.note}>
              Every factor is worth some points on the scoreboard. Added up, they give an expected margin of{' '}
              {Math.abs(game.margin).toFixed(1)} points for {game.margin >= 0 ? home.nickname : away.nickname}, which
              becomes the percentages above (NFL games vary by about 14 points around what’s expected).
            </Text>

            {[
              { team: home, list: homeHelps },
              { team: away, list: awayHelps },
            ].map(({ team, list }) => (
              <View key={team.abbr} style={{ gap: 6 }}>
                <Text style={s.section}>Helped {team.nickname}</Text>
                <View style={s.box}>
                  {list.length ? (
                    list
                      .sort((x, y) => Math.abs(y.points) - Math.abs(x.points))
                      .map((f, i) => (
                        <View key={f.id} style={[s.row, i < list.length - 1 && s.divider]}>
                          <View style={{ flex: 1 }}>
                            <Text style={s.rowLabel}>{f.label}</Text>
                            <Text style={s.rowDetail}>{f.detail}</Text>
                          </View>
                          <Text style={[s.rowValue, { color: colors.good }]}>+{Math.abs(f.points).toFixed(1)} pts</Text>
                        </View>
                      ))
                  ) : (
                    <Text style={[s.rowDetail, { paddingVertical: 10 }]}>Nothing significant.</Text>
                  )}
                </View>
              </View>
            ))}
            {none.length ? (
              <Text style={s.note}>No real effect: {none.map((f) => f.label.toLowerCase()).join(', ')}.</Text>
            ) : null}
            <Text style={s.note}>
              The ratings used here leave out the opponent and injury adjustments, because the model counts opponents
              (through record & schedule) and this week’s injuries separately. That’s why they can differ a little from
              the ratings shown below.
            </Text>

            <Text style={s.section}>Injuries this week</Text>
            <View style={s.box}>
              <InjuryList team={home} players={game.injuries.home} />
              <InjuryList team={away} players={game.injuries.away} last />
            </View>
            <Text style={s.note}>
              Points = how much a team loses without that player. A starting QB is worth about 5.5 points (more for a
              star); most other starters well under 1. Out and injured reserve count fully, doubtful 75%.
              {injuryTeam ? ` Net effect here: ${injuryPoints.toFixed(1)} points toward ${injuryTeam.nickname}.` : ' Net effect here: about even.'}
            </Text>

            {all ? (
              <Text style={s.note}>
                How good is this? Tested on {all.games} past games (2025 and 2026), it picked the winner{' '}
                {all.accuracy}% of the time (betting favorites: {report?.all?.vegas.accuracy}%; always picking the home
                team: {report?.all?.homeTeam.accuracy}%).{' '}
                {seventy ? `When it gave a team about ${Math.round(seventy.predicted)}%, that team won ${Math.round(seventy.actual)}% of the time.` : ''}
              </Text>
            ) : null}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function InjuryList({ team, players, last }: { team: Team; players: MissingPlayer[]; last?: boolean }) {
  const total = players.reduce((a, p) => a + p.points, 0);
  return (
    <View style={[{ paddingVertical: 10, gap: 4 }, !last && s.divider]}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        <Text style={s.rowLabel}>{team.nickname}</Text>
        <Text style={[s.rowValue, { color: total > 0.05 ? colors.bad : colors.muted }]}>
          {total > 0.05 ? `−${total.toFixed(1)} pts` : 'none'}
        </Text>
      </View>
      {players.slice(0, 6).map((p) => (
        <Text key={p.id} style={s.rowDetail}>
          {p.name} ({p.pos}) · {p.status === 'IR' ? 'injured reserve' : p.status.toLowerCase()} · −{p.points.toFixed(1)}
        </Text>
      ))}
      {players.length > 6 ? <Text style={s.rowDetail}>+{players.length - 6} more minor</Text> : null}
    </View>
  );
}

const s = StyleSheet.create({
  card: { backgroundColor: colors.card, borderRadius: 14, padding: 14, gap: 8, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  kicker: { color: colors.muted, fontSize: 13, fontWeight: '600', textAlign: 'center' },
  scoreRow: { flexDirection: 'row', alignItems: 'center' },
  scoreTeam: { color: colors.muted, fontSize: 14, fontWeight: '700' },
  score: { color: colors.text, fontSize: 36, fontWeight: '800', fontVariant: ['tabular-nums'] },
  final: { color: colors.muted, fontSize: 12, fontWeight: '800', letterSpacing: 0.8 },
  caption: { color: colors.muted, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.6, textAlign: 'center', marginTop: 4 },
  probRow: { flexDirection: 'row', justifyContent: 'space-between' },
  prob: { color: colors.text, fontSize: 20, fontWeight: '800', flex: 1, fontVariant: ['tabular-nums'] },
  bar: { flexDirection: 'row', height: 12, borderRadius: 6, overflow: 'hidden', backgroundColor: colors.border },
  sub: { color: colors.muted, fontSize: 13, textAlign: 'center' },
  whyBtn: { alignSelf: 'center', paddingVertical: 6 },
  whyText: { color: '#7FB2FF', fontWeight: '700', fontSize: 14 },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end', alignItems: 'center' },
  sheet: {
    width: '100%', maxWidth: 640, maxHeight: '88%', backgroundColor: colors.bg, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  sheetHead: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  sheetTitle: { color: colors.text, fontSize: 18, fontWeight: '800' },
  sheetSub: { color: colors.muted, fontSize: 13, marginTop: 2 },
  close: { color: colors.muted, fontSize: 20, padding: 4 },
  section: { color: colors.muted, fontSize: 13, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 4 },
  box: { backgroundColor: colors.card, borderRadius: 14, paddingHorizontal: 14, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 },
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rowLabel: { color: colors.text, fontSize: 15, fontWeight: '600' },
  rowDetail: { color: colors.muted, fontSize: 12, marginTop: 2 },
  rowValue: { fontSize: 15, fontWeight: '800', fontVariant: ['tabular-nums'] },
  note: { color: colors.muted, fontSize: 12, lineHeight: 17 },
});
