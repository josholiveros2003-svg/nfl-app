import { Link } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { sized } from '@/lib/images';
import { colors, pctColor } from '@/lib/theme';
import type { BoxCell, BoxScore as Box, BoxSection, Team } from '@/lib/types';
import { Segmented } from './ui';

type Teams = { home: Team; away: Team };

/** Both teams' stats for one game, side by side, each colored against every team's games
 *  this season, with the league average under each label. */
export function TeamStats({ box, teams }: { box: Box; teams: Teams }) {
  const { home, away } = teams;
  return (
    <View style={{ gap: 8 }}>
      <View style={s.card}>
        <View style={[s.tsRow, s.tsHead]}>
          <TeamTag team={away} />
          <Text style={s.tsHeadLabel}>Team stats</Text>
          <TeamTag team={home} right />
        </View>
        {box.teams.map((st, i) => (
          <View key={st.id} style={[s.tsRow, i < box.teams.length - 1 && s.divider]}>
            <Value cell={st.away} />
            <View style={s.tsLabelBox}>
              <Text style={s.tsLabel}>{st.label}</Text>
              <Text style={s.avg}>NFL avg {st.avg}{st.better === 'low' ? ' · lower is better' : ''}</Text>
            </View>
            <Value cell={st.home} />
          </View>
        ))}
      </View>
      <Legend what="every team's games this season" />
    </View>
  );
}

/** Player stats for one team at a time: passing, rushing, receiving, defense, kicking, punting. */
export function BoxScore({ box, teams }: { box: Box; teams: Teams }) {
  const [side, setSide] = useState<'away' | 'home'>('away');
  const sections = box.players[side];
  return (
    <View style={{ gap: 10 }}>
      <Segmented
        options={[
          { id: 'away', label: teams.away.nickname },
          { id: 'home', label: teams.home.nickname },
        ]}
        value={side}
        onChange={setSide}
      />
      {sections.length ? (
        sections.map((sec) => <Section key={sec.id} sec={sec} />)
      ) : (
        <Text style={s.note}>No player stats for this game yet.</Text>
      )}
      <Legend what="games this season by players at the same position" />
    </View>
  );
}

function Section({ sec }: { sec: BoxSection }) {
  // Narrower columns when there are five, so names still have room.
  const col = { width: sec.cols.length > 4 ? 44 : 50 };
  const avgKeys = Object.keys(sec.avgs).sort((a, b) => (a === '*' ? 1 : b === '*' ? -1 : a.localeCompare(b)));
  return (
    <View style={s.card}>
      <View style={[s.row, s.headRow]}>
        <Text style={[s.nameCol, s.secTitle]}>{sec.label}</Text>
        {sec.cols.map((c) => (
          <Text key={c.id} style={[s.statCol, col, s.colHead]}>
            {c.label}
          </Text>
        ))}
      </View>
      {sec.rows.map((r) => {
        const content = (pressed: boolean) => (
          <View style={[s.row, s.divider, pressed && s.pressed]}>
            <View style={s.nameCol}>
              <Text style={s.name} numberOfLines={2}>
                {r.name}
              </Text>
              {r.pos ? <Text style={s.pos}>{r.pos}</Text> : null}
            </View>
            {r.cells.map((c, i) => (
              <Text key={sec.cols[i].id} style={[s.statCol, col, s.cell, { color: pctColor(c.p) }]} numberOfLines={1} adjustsFontSizeToFit>
                {c.d}
              </Text>
            ))}
          </View>
        );
        return r.link ? (
          <Link key={r.id} href={{ pathname: '/player', params: { id: r.id } }} asChild>
            <Pressable accessibilityRole="link" accessibilityLabel={`${r.name}, open player page`}>
              {({ pressed }) => content(pressed)}
            </Pressable>
          </Link>
        ) : (
          <View key={r.id}>{content(false)}</View>
        );
      })}
      {avgKeys.map((k, i) => (
        <View key={k} style={[s.row, s.avgRow, i === 0 && s.avgFirst]}>
          <Text style={[s.nameCol, s.avgLabel]} numberOfLines={1}>
            {k === '*' ? 'NFL avg' : `${k} avg`}
          </Text>
          {sec.avgs[k].map((a, j) => (
            <Text key={sec.cols[j].id} style={[s.statCol, col, s.avgCell]} numberOfLines={1} adjustsFontSizeToFit>
              {a}
            </Text>
          ))}
        </View>
      ))}
    </View>
  );
}

function Value({ cell }: { cell: BoxCell }) {
  const c = pctColor(cell.p);
  return (
    <View style={[s.valueBox, cell.p != null && { backgroundColor: `${c}1F` }]}>
      <Text style={[s.value, { color: c }]} numberOfLines={1} adjustsFontSizeToFit>
        {cell.d}
      </Text>
    </View>
  );
}

function TeamTag({ team, right }: { team: Team; right?: boolean }) {
  return (
    <View style={[s.tag, right && { justifyContent: 'flex-end' }]}>
      {!right ? <Logo team={team} /> : null}
      <Text style={s.tagText}>{team.abbr}</Text>
      {right ? <Logo team={team} /> : null}
    </View>
  );
}

function Logo({ team }: { team: Team }) {
  return (
    <View style={s.logoBg}>
      <Image source={{ uri: sized(team.logo, 22) }} style={s.logo} />
    </View>
  );
}

function Legend({ what }: { what: string }) {
  return (
    <View style={{ gap: 4 }}>
      <View style={s.legend}>
        {[
          { c: colors.good, t: 'Top third' },
          { c: colors.mid, t: 'Middle' },
          { c: colors.bad, t: 'Bottom third' },
        ].map((x) => (
          <View key={x.t} style={s.legendItem}>
            <View style={[s.swatch, { backgroundColor: x.c }]} />
            <Text style={s.legendText}>{x.t}</Text>
          </View>
        ))}
      </View>
      <Text style={[s.note, { textAlign: 'center' }]}>Colors compare each number with {what}.</Text>
    </View>
  );
}

const s = StyleSheet.create({
  card: { backgroundColor: colors.card, borderRadius: 14, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border, overflow: 'hidden' },
  divider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
  pressed: { backgroundColor: colors.cardPressed },
  // Team stats
  tsRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 8, gap: 8 },
  tsHead: { paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  tsHeadLabel: { flex: 1, textAlign: 'center', color: colors.muted, fontSize: 12, fontWeight: '700', letterSpacing: 0.6, textTransform: 'uppercase' },
  tsLabelBox: { flex: 1, alignItems: 'center' },
  tsLabel: { color: colors.text, fontSize: 14, fontWeight: '600', textAlign: 'center' },
  valueBox: { width: 96, paddingVertical: 7, paddingHorizontal: 4, borderRadius: 9, alignItems: 'center' },
  value: { fontSize: 15, fontWeight: '800', fontVariant: ['tabular-nums'] },
  tag: { width: 96, flexDirection: 'row', alignItems: 'center', gap: 6 },
  tagText: { color: colors.text, fontSize: 15, fontWeight: '800' },
  logoBg: { width: 26, height: 26, borderRadius: 13, backgroundColor: 'rgba(255,255,255,0.92)', alignItems: 'center', justifyContent: 'center' },
  logo: { width: 22, height: 22 },
  // Player tables
  row: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 8 },
  headRow: { paddingVertical: 10 },
  secTitle: { color: colors.text, fontSize: 15, fontWeight: '800' },
  colHead: { color: colors.muted, fontSize: 11, fontWeight: '700', letterSpacing: 0.4 },
  nameCol: { flex: 1, paddingRight: 6 },
  statCol: { width: 50, textAlign: 'center' },
  name: { color: colors.text, fontSize: 14, fontWeight: '600' },
  pos: { color: colors.muted, fontSize: 11, marginTop: 1 },
  cell: { fontSize: 14, fontWeight: '700', fontVariant: ['tabular-nums'] },
  avgRow: { paddingVertical: 6, backgroundColor: 'rgba(255,255,255,0.03)' },
  avgFirst: { borderTopWidth: 1, borderTopColor: colors.border },
  avgLabel: { color: colors.muted, fontSize: 12, fontWeight: '700' },
  avgCell: { color: colors.muted, fontSize: 12, fontWeight: '600', fontVariant: ['tabular-nums'] },
  avg: { color: colors.muted, fontSize: 11, marginTop: 2, textAlign: 'center' },
  note: { color: colors.muted, fontSize: 12, lineHeight: 17 },
  legend: { flexDirection: 'row', justifyContent: 'center', gap: 14 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  swatch: { width: 12, height: 12, borderRadius: 3 },
  legendText: { color: colors.muted, fontSize: 12 },
});
