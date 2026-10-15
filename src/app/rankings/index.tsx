import { Stack } from 'expo-router';
import { Text, View } from 'react-native';
import { LinkCard, Loading, Screen, SectionTitle, styles as ui } from '@/components/ui';
import { useRankings } from '@/lib/data';
import { POSITIONS } from '@/lib/constants';
import { colors } from '@/lib/theme';

// Menu of every ranking: the league, team units, and players by position.
export default function RankingsMenu() {
  const { data, error } = useRankings();
  if (!data) return <Loading error={error} />;
  return (
    <>
      <Stack.Screen options={{ title: 'Power Rankings' }} />
      <Screen>
        <LinkCard href={{ pathname: '/rankings/list', params: { type: 'league' } }} accent={colors.good}>
          <Text style={ui.title}>League</Text>
          <Text style={ui.muted}>All 32 teams, 1 to 32: wins and losses in context, team rating and recent form.</Text>
        </LinkCard>

        <SectionTitle>Team units</SectionTitle>
        <View style={{ gap: 8 }}>
          {data.units.map((u) => (
            <LinkCard key={u.id} href={{ pathname: '/rankings/list', params: { type: 'unit', id: u.id } }}>
              <Text style={ui.title}>{u.label}</Text>
              <Text style={ui.muted}>{u.description}</Text>
            </LinkCard>
          ))}
        </View>

        <SectionTitle>Players by position</SectionTitle>
        <View style={{ gap: 8 }}>
          {POSITIONS.map((p) => (
            <LinkCard key={p.id} href={{ pathname: '/rankings/list', params: { type: 'position', id: p.id } }}>
              <Text style={ui.title}>{p.label}</Text>
            </LinkCard>
          ))}
        </View>
      </Screen>
    </>
  );
}
