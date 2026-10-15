import { Stack, useLocalSearchParams } from 'expo-router';
import { Text, View } from 'react-native';
import { KeyStats } from '@/components/KeyStats';
import { RatingBadge, RatingSummary } from '@/components/Rating';
import { TeamHeader } from '@/components/TeamHeader';
import { LinkCard, Loading, Screen, styles as ui } from '@/components/ui';
import { TEAM_IDS, UNITS, unitLabel } from '@/lib/constants';
import { useTeam } from '@/lib/data';
import { readableTeamColor } from '@/lib/theme';
import type { UnitId } from '@/lib/types';
import { teamWhy, unitWhy } from '@/lib/why';

// Pre-build a page for every team × unit when exporting the website.
export async function generateStaticParams() {
  return TEAM_IDS.flatMap((t) => UNITS.map((u) => ({ team: t.toLowerCase(), unit: u.id })));
}

// Offense / Defense / Special Teams: a card for each category.
export default function UnitScreen() {
  const { team, unit } = useLocalSearchParams<{ team: string; unit: UnitId }>();
  const { data, error } = useTeam(team);
  const categories = data?.units[unit];

  return (
    <>
      <Stack.Screen options={{ title: unitLabel(unit) }} />
      {!data || !categories ? (
        <Loading error={error ?? (data ? 'Unknown section' : undefined)} />
      ) : (
        <Screen>
          <TeamHeader team={data.team} subtitle={unitLabel(unit)} rating={teamWhy(data)} />
          <RatingSummary info={unitWhy(data, unit)} caption={`${unitLabel(unit)} rating`} />
          {categories.map((c) => (
            <LinkCard
              key={c.id}
              href={`/team/${team}/${unit}/${c.id}`}
              accent={readableTeamColor(data.team.color, data.team.color2)}
            >
              <View style={ui.row}>
                <Text style={[ui.title, { flex: 1 }]}>{c.label}</Text>
                <RatingBadge rt={c.rt} size="sm" />
              </View>
              <Text style={ui.muted}>{c.blurb}</Text>
              <KeyStats stats={c.stats.filter((st) => st.rank != null).slice(0, 3)} />
            </LinkCard>
          ))}
        </Screen>
      )}
    </>
  );
}
