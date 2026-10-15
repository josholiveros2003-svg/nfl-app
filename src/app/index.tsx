import { Link } from 'expo-router';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { RatingBadge } from '@/components/Rating';
import { LinkCard, Loading, Screen, SectionTitle, styles as ui } from '@/components/ui';
import { useTeams } from '@/lib/data';
import { colors, readableTeamColor } from '@/lib/theme';
import type { Team } from '@/lib/types';

const DIVISIONS = ['East', 'North', 'South', 'West'];

// Home: all 32 teams, grouped by division.
export default function TeamsScreen() {
  const { data, error } = useTeams();
  if (!data) return <Loading error={error} />;

  const groups: { name: string; teams: Team[] }[] = [];
  for (const conf of ['AFC', 'NFC']) {
    for (const d of DIVISIONS) {
      const name = `${conf} ${d}`;
      groups.push({ name, teams: data.teams.filter((t) => t.division === name) });
    }
  }

  return (
    <Screen>
      <View style={s.tiles}>
        {[
          { href: '/schedule' as const, icon: '📅', label: 'Schedule' },
          { href: '/standings' as const, icon: '📊', label: 'Standings' },
          { href: '/rankings' as const, icon: '🏆', label: 'Rankings' },
          { href: '/compare' as const, icon: '⚖️', label: 'Compare' },
        ].map((t) => (
          <Link key={t.href} href={t.href} asChild>
            <Pressable style={s.tile} accessibilityRole="link">
              <Text style={s.tileIcon}>{t.icon}</Text>
              <Text style={s.tileLabel}>{t.label}</Text>
            </Pressable>
          </Link>
        ))}
      </View>
      <Text style={ui.muted}>
        {data.season} season · through Week {data.throughWeek}. The colored number is each team’s overall
        rating: its Madden roster rating, moved by this season’s results.
      </Text>
      {groups.map((g) => (
        <View key={g.name} style={{ gap: 8 }}>
          <SectionTitle>{g.name}</SectionTitle>
          {g.teams.map((t) => (
            <LinkCard key={t.abbr} href={`/team/${t.abbr.toLowerCase()}`} accent={readableTeamColor(t.color, t.color2)}>
              <View style={ui.row}>
                <View style={s.logoBg}>
                  <Image source={{ uri: t.logo }} style={s.logo} accessibilityLabel="" />
                </View>
                <Text style={[ui.title, { flex: 1 }]}>{t.name}</Text>
                <Text style={s.record}>{t.record}</Text>
                <RatingBadge rt={t.rt} size="sm" />
              </View>
            </LinkCard>
          ))}
        </View>
      ))}
    </Screen>
  );
}

const s = StyleSheet.create({
  tiles: { flexDirection: 'row', gap: 8 },
  tile: {
    flex: 1, alignItems: 'center', gap: 4, paddingVertical: 12, borderRadius: 14, backgroundColor: colors.card,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  tileIcon: { fontSize: 24 },
  tileLabel: { color: colors.text, fontWeight: '700', fontSize: 13 },
  logoBg: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.92)', alignItems: 'center', justifyContent: 'center' },
  logo: { width: 30, height: 30 },
  record: { color: '#C9D1DE', fontSize: 15, fontWeight: '600', fontVariant: ['tabular-nums'] },
});
