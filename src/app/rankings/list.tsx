import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Image, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { WhySheet, type WhyInfo } from '@/components/Rating';
import { Loading, Screen, SectionTitle, styles as ui } from '@/components/ui';
import { useAverages, usePlayersIndex, useRankings, useTeams } from '@/lib/data';
import { gameVerdict, powerRankings, type PowerRow } from '@/lib/powerRankings';
import { breakdown, leagueAverage, useRatingWeights, type LeagueAverage } from '@/lib/ratings';
import { colors, ratingColor } from '@/lib/theme';
import type { Team } from '@/lib/types';
import { POSITIONS } from '@/lib/constants';
import { sized } from '@/lib/images';

type Row = {
  key: string;
  rank: number | null;
  name: string;
  sub: string;
  image: string | null;
  rating: number | null;
  move?: number | null;
  limited?: boolean;
  onPress: () => void;
};

// One ranked list: /rankings/list?type=league | type=unit&id=offensive_line | type=position&id=QB
export default function RankingList() {
  const params = useLocalSearchParams<{ type?: string; id?: string }>();
  const type = params.type === 'unit' || params.type === 'position' ? params.type : 'league';
  const rankings = useRankings();
  const teams = useTeams();
  const players = usePlayersIndex(type === 'position');
  const averages = useAverages();
  const { weights, influence, rank: rankWeights } = useRatingWeights();
  const [why, setWhy] = useState<WhyInfo | null>(null);
  const [leagueWhy, setLeagueWhy] = useState<PowerRow | null>(null);

  const byTeam = useMemo(() => Object.fromEntries((teams.data?.teams ?? []).map((t) => [t.abbr, t])), [teams.data]);

  const { title, intro, rows, limitedRows, avg } = useMemo(() => {
    const empty = { title: 'Rankings', intro: '', rows: [] as Row[], limitedRows: [] as Row[], avg: null as LeagueAverage | null };
    const avgFor = (key?: string) =>
      key && averages.data?.[key] ? leagueAverage(key, averages.data[key], weights, influence) : null;
    if (!rankings.data || !teams.data) return empty;
    const league = rankings.data.league.teams;
    if (type === 'league') {
      const list = powerRankings(league, rankWeights);
      return {
        title: 'League Power Rankings',
        intro: `Through Week ${rankings.data.league.lastPlayedWeek}. Wins and losses in context, team rating and recent form, blended with your Settings. Tap a team to see why.`,
        rows: list.map((r) => ({
          key: r.team, rank: r.rank, name: byTeam[r.team]?.name ?? r.team, sub: r.data.record,
          image: byTeam[r.team]?.logo ?? null, rating: Math.round(r.score), move: r.prevRank - r.rank,
          onPress: () => setLeagueWhy(r),
        })),
        limitedRows: [],
        avg: null,
      };
    }
    if (type === 'unit') {
      const list = rankings.data.units.find((u) => u.id === params.id);
      if (!list) return empty;
      const scored = Object.entries(list.teams)
        .map(([t, v]) => ({ t, v, r: breakdown(v.rt, weights, influence)?.rating ?? null }))
        .sort((a, b) => (b.r ?? -1) - (a.r ?? -1));
      return {
        title: list.label,
        intro: `${list.description}. ${list.kind === 'group' ? 'Average of the starters’ player ratings.' : 'Team rating for this part of the game.'} Tap a team to see why.`,
        rows: scored.map(({ t, v, r }, i) => ({
          key: t, rank: i + 1, name: byTeam[t]?.name ?? t,
          sub: [league[t]?.record, v.starters.length ? v.starters.map((p) => p.name.split(' ').slice(-1)[0]).join(', ') : null].filter(Boolean).join(' · '),
          image: byTeam[t]?.logo ?? null, rating: r, move: v.move ?? null,
          onPress: () => setWhy({
            title: `${byTeam[t]?.name ?? t} · ${list.label}`, rt: v.rt, team: list.kind !== 'group',
            baseline: list.kind === 'group'
              ? { label: 'Starters’ Madden average', detail: `Average Madden rating of ${v.starters.map((p) => p.name).join(', ')}` }
              : undefined,
            link: { label: `Open ${byTeam[t]?.name ?? t}`, href: `/team/${t.toLowerCase()}` },
          }),
        })),
        limitedRows: [],
        avg: avgFor(Object.values(list.teams).find((v) => v.rt?.a)?.rt?.a),
      };
    }
    // Players by position: full-sample players first; limited-sample players listed separately below.
    const pos = POSITIONS.find((p) => p.id === params.id);
    if (!pos || !players.data) return { ...empty, title: pos?.label ?? 'Players' };
    const scored = players.data
      .filter((p) => p.group === pos.id && p.team && p.rt)
      .map((p) => ({ p, b: breakdown(p.rt, weights, influence) }))
      .filter((x) => x.b)
      .sort((a, b) => b.b!.rating - a.b!.rating);
    const toRow = (x: (typeof scored)[number], rank: number | null): Row => ({
      key: x.p.id, rank, name: x.p.name, sub: [x.p.pos, x.p.team, x.p.starter ? 'starter' : null].filter(Boolean).join(' · '),
      image: byTeam[x.p.team ?? '']?.logo ?? null, rating: x.b!.rating, limited: x.b!.limited,
      onPress: () => setWhy({ title: x.p.name, rt: x.p.rt, link: { label: `Open ${x.p.name}`, href: { pathname: '/player', params: { id: x.p.id } } } }),
    });
    const full = scored.filter((x) => !x.b!.limited);
    const limited = scored.filter((x) => x.b!.limited);
    return {
      title: pos.label,
      intro: 'Player ratings (Madden baseline moved by this season’s stats). Players who haven’t played enough yet are listed separately at the bottom. Tap a player to see why.',
      rows: full.map((x, i) => toRow(x, i + 1)),
      limitedRows: limited.slice(0, 40).map((x) => toRow(x, null)),
      avg: avgFor(`pos.${pos.id}`),
    };
  }, [rankings.data, teams.data, players.data, averages.data, type, params.id, weights, influence, rankWeights, byTeam]);

  const loading = !rankings.data || !teams.data || (type === 'position' && !players.data);
  return (
    <>
      <Stack.Screen options={{ title }} />
      {loading ? (
        <Loading error={rankings.error ?? teams.error ?? players.error} />
      ) : (
        <Screen>
          <Text style={ui.muted}>{intro}</Text>
          {avg ? (
            <Text style={s.avgLine}>
              League average ({avg.group ? `all ${avg.count} ${avg.group}s` : 'all 32 teams'}):{' '}
              <Text style={{ color: ratingColor(avg.rating), fontWeight: '800' }}>{avg.rating}</Text>
            </Text>
          ) : null}
          <List rows={rows} />
          {limitedRows.length ? (
            <>
              <SectionTitle>Limited sample (not ranked yet)</SectionTitle>
              <List rows={limitedRows} />
            </>
          ) : null}
        </Screen>
      )}
      {why ? <WhySheet info={why} onClose={() => setWhy(null)} /> : null}
      {leagueWhy ? <LeagueWhy row={leagueWhy} team={byTeam[leagueWhy.team]} byTeam={byTeam} onClose={() => setLeagueWhy(null)} /> : null}
    </>
  );
}

function List({ rows }: { rows: Row[] }) {
  return (
    <View style={s.table}>
      {rows.map((r, i) => (
        <Pressable key={r.key} onPress={r.onPress} accessibilityRole="button" accessibilityLabel={`${r.name}, see why`}>
          {({ pressed }) => (
            <View style={[s.row, i < rows.length - 1 && s.divider, pressed && { backgroundColor: colors.cardPressed }]}>
              <Text style={s.rank}>{r.rank ?? '–'}</Text>
              <View style={s.logoBg}>{r.image ? <Image source={{ uri: sized(r.image, 26) }} style={s.logo} /> : null}</View>
              <View style={{ flex: 1 }}>
                <Text style={s.name} numberOfLines={1}>{r.name}</Text>
                <Text style={s.sub} numberOfLines={1}>{r.sub}</Text>
              </View>
              {r.move !== undefined ? <Move move={r.move} /> : null}
              <View style={[s.rating, { borderColor: ratingColor(r.rating) }]}>
                <Text style={[s.ratingText, { color: ratingColor(r.rating) }]}>{r.rating ?? '—'}</Text>
                {r.limited ? <Text style={[s.ltd, { color: ratingColor(r.rating) }]}>LTD</Text> : null}
              </View>
            </View>
          )}
        </Pressable>
      ))}
    </View>
  );
}

function Move({ move }: { move: number | null }) {
  if (move == null) return <Text style={[s.move, { color: colors.muted }]}> </Text>;
  if (move === 0) return <Text style={[s.move, { color: colors.muted }]}>–</Text>;
  return <Text style={[s.move, { color: move > 0 ? colors.good : colors.bad }]}>{move > 0 ? `▲${move}` : `▼${-move}`}</Text>;
}

/** Why a team is ranked where it is in the league power rankings. */
function LeagueWhy({ row, team, byTeam, onClose }: { row: PowerRow; team?: Team; byTeam: Record<string, Team>; onClose: () => void }) {
  const name = team?.name ?? row.team;
  const pts = (x: number) => `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(1)}`;
  const tone = (x: number) => (x >= 0.05 ? colors.good : x <= -0.05 ? colors.bad : colors.muted);
  const move = row.prevRank - row.rank;
  return (
    <Modal transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={s.backdrop} onPress={onClose}>
        <Pressable style={s.sheet} onPress={() => {}}>
          <ScrollView contentContainerStyle={{ padding: 18, gap: 12 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <View style={[s.rating, { width: 54, height: 54, borderColor: ratingColor(row.score) }]}>
                <Text style={[s.ratingText, { fontSize: 22, color: ratingColor(row.score) }]}>{Math.round(row.score)}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.sheetTitle}>#{row.rank} {name}</Text>
                <Text style={s.sub}>
                  {row.data.record} · last week #{row.prevRank}
                  {move ? ` (${move > 0 ? 'up' : 'down'} ${Math.abs(move)})` : ' (no change)'}
                </Text>
              </View>
              <Pressable onPress={onClose} hitSlop={10} accessibilityLabel="Close"><Text style={s.close}>✕</Text></Pressable>
            </View>

            <View style={s.box}>
              <WhyLine label="Average team" detail="Every team starts at 77" value="77.0" />
              <WhyLine label="Wins & losses (in context)" detail="Results vs. what an average team would do against the same opponents, home or away" value={pts(row.parts.results)} color={tone(row.parts.results)} />
              <WhyLine
                label="Team rating"
                detail={`Rating ${row.data.now.rating.toFixed(0)}${row.injuryCost >= 0.5 ? `, minus ${row.injuryCost.toFixed(1)} for players out now` : ''}`}
                value={pts(row.parts.rating)}
                color={tone(row.parts.rating)}
              />
              <WhyLine label="Recent form" detail="Last 4 games, most recent counting most" value={pts(row.parts.form)} color={tone(row.parts.form)} />
              <View style={[s.whyRow, { borderBottomWidth: 0 }]}>
                <Text style={[s.name, { flex: 1 }]}>Power score</Text>
                <Text style={[s.ratingText, { fontSize: 20, color: ratingColor(row.score) }]}>{Math.round(row.score)}</Text>
              </View>
            </View>

            <Text style={s.section}>Game by game</Text>
            <View style={s.box}>
              {row.data.games.map((g) => (
                <WhyLine
                  key={g.week}
                  label={`Wk ${g.week} · ${g.result} ${g.pf}–${g.pa} ${g.home ? 'vs' : '@'} ${byTeam[g.opp]?.nickname ?? g.opp} (${g.oppRecord})`}
                  detail={`An average team would win ${Math.round(g.avgChance * 100)}% here · ${gameVerdict(g.quality)}`}
                  value={g.quality >= 0.1 ? '▲' : g.quality <= -0.1 ? '▼' : '–'}
                  color={g.quality >= 0.1 ? colors.good : g.quality <= -0.1 ? colors.bad : colors.muted}
                />
              ))}
              {!row.data.games.length ? <Text style={[s.sub, { paddingVertical: 10 }]}>No games yet.</Text> : null}
            </View>

            {row.data.injuries.length ? (
              <>
                <Text style={s.section}>Key players out now</Text>
                <View style={s.box}>
                  {row.data.injuries.map((p) => (
                    <WhyLine key={p.id} label={`${p.name} (${p.pos})`} detail={p.status === 'IR' ? 'injured reserve' : p.status.toLowerCase()} value={`−${p.points.toFixed(1)}`} color={colors.bad} />
                  ))}
                </View>
              </>
            ) : null}

            <Text style={s.sub}>
              Close games count as partial wins or losses, margins are capped at 21 points, and teams with fewer games are
              pulled toward the middle. Change the weights in Settings.
            </Text>
            <Pressable
              onPress={() => {
                onClose();
                router.push(`/team/${row.team.toLowerCase()}`);
              }}
              style={s.linkBtn}
              accessibilityRole="link"
            >
              <Text style={s.name}>Open {name} ›</Text>
            </Pressable>
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function WhyLine({ label, detail, value, color }: { label: string; detail?: string; value: string; color?: string }) {
  return (
    <View style={s.whyRow}>
      <View style={{ flex: 1 }}>
        <Text style={s.name}>{label}</Text>
        {detail ? <Text style={s.sub}>{detail}</Text> : null}
      </View>
      <Text style={[s.ratingText, { color: color ?? colors.text }]}>{value}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  avgLine: { color: colors.muted, fontSize: 13, fontWeight: '600' },
  table: { backgroundColor: colors.card, borderRadius: 14, overflow: 'hidden', borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, paddingHorizontal: 12 },
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rank: { color: colors.muted, width: 24, textAlign: 'right', fontWeight: '800', fontVariant: ['tabular-nums'] },
  logoBg: { width: 32, height: 32, borderRadius: 16, backgroundColor: 'rgba(255,255,255,0.92)', alignItems: 'center', justifyContent: 'center' },
  logo: { width: 26, height: 26 },
  name: { color: colors.text, fontSize: 15, fontWeight: '700' },
  sub: { color: colors.muted, fontSize: 12, marginTop: 1 },
  move: { width: 34, textAlign: 'right', fontSize: 12, fontWeight: '800', fontVariant: ['tabular-nums'] },
  rating: { width: 40, height: 40, borderRadius: 9, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  ratingText: { fontWeight: '800', fontSize: 16, fontVariant: ['tabular-nums'] },
  ltd: { position: 'absolute', bottom: -7, fontSize: 8, fontWeight: '800', backgroundColor: colors.bg, paddingHorizontal: 2 },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end', alignItems: 'center' },
  sheet: {
    width: '100%', maxWidth: 640, maxHeight: '88%', backgroundColor: colors.bg, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  sheetTitle: { color: colors.text, fontSize: 18, fontWeight: '800' },
  close: { color: colors.muted, fontSize: 20, padding: 4 },
  section: { color: colors.muted, fontSize: 13, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase' },
  box: { backgroundColor: colors.card, borderRadius: 14, paddingHorizontal: 14, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  whyRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  linkBtn: { backgroundColor: colors.card, borderRadius: 12, paddingVertical: 12, alignItems: 'center', borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
});
