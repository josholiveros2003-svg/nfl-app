import { Stack, useLocalSearchParams } from 'expo-router';
import { Text } from 'react-native';
import { Leaders } from '@/components/Leaders';
import { RatingSummary } from '@/components/Rating';
import { StatRow } from '@/components/StatRow';
import { TeamHeader } from '@/components/TeamHeader';
import { Card, Loading, Screen, SectionTitle, styles as ui } from '@/components/ui';
import { CATEGORY_IDS, TEAM_IDS, UNITS, unitLabel } from '@/lib/constants';
import { useTeam } from '@/lib/data';
import type { UnitId } from '@/lib/types';
import { categoryWhy, teamWhy } from '@/lib/why';

// Pre-build a page for every team × unit × category when exporting the website.
export async function generateStaticParams() {
  return TEAM_IDS.flatMap((t) =>
    UNITS.flatMap((u) => CATEGORY_IDS[u.id].map((category) => ({ team: t.toLowerCase(), unit: u.id, category }))),
  );
}

// The detail screen: every stat in the category, plus the team's top players.
export default function CategoryScreen() {
  const params = useLocalSearchParams<{ team: string; unit: UnitId; category: string }>();
  const { team, unit } = params;
  const category = params.category?.replace(/\.html$/, ''); // some hosts keep ".html" in the address
  const { data, error } = useTeam(team);
  const cat = data?.units[unit]?.find((c) => c.id === category);

  return (
    <>
      <Stack.Screen options={{ title: cat?.label ?? '' }} />
      {!data || !cat ? (
        <Loading error={error ?? (data ? 'Unknown category' : undefined)} />
      ) : (
        <Screen>
          <TeamHeader team={data.team} subtitle={`${unitLabel(unit)} › ${cat.label}`} rating={teamWhy(data)} />
          <RatingSummary info={categoryWhy(data, unit, cat)} caption={`${cat.label} rating`} />
          <Text style={ui.muted}>
            {cat.blurb} Tap a stat with ⓘ to see what it means, or a colored rating to see why. Rank is out of 32
            teams.
          </Text>
          <Card style={{ paddingVertical: 2 }}>
            {cat.stats.map((st, i) => (
              <StatRow
                key={st.id}
                stat={st}
                last={i === cat.stats.length - 1}
                ratingTitle={`${data.team.nickname} · ${st.label}`}
                context={data.context?.[unit]}
                team
              />
            ))}
          </Card>
          {cat.leaders.map((l) => (
            <Leaders key={l.title} title={l.title} players={l.players} />
          ))}
          <SectionTitle> </SectionTitle>
        </Screen>
      )}
    </>
  );
}
