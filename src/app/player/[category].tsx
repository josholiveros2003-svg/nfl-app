import { Stack, useLocalSearchParams } from 'expo-router';
import { Text } from 'react-native';
import { PlayerHeader } from '@/components/PlayerHeader';
import { RatingSummary } from '@/components/Rating';
import { StatRow } from '@/components/StatRow';
import { Card, Loading, Screen, styles as ui } from '@/components/ui';
import { PLAYER_CATEGORY_IDS } from '@/lib/constants';
import { usePlayer } from '@/lib/data';
import { colors } from '@/lib/theme';
import { playerCategoryWhy } from '@/lib/why';

// Pre-build one page per category; which player to show comes from ?id= in the address.
export async function generateStaticParams() {
  return PLAYER_CATEGORY_IDS.map((category) => ({ category }));
}

export default function PlayerCategoryScreen() {
  const params = useLocalSearchParams<{ id: string; category: string }>();
  const category = params.category?.replace(/\.html$/, '');
  const { data, error } = usePlayer(params.id);
  const cat = data?.categories.find((c) => c.id === category);

  return (
    <>
      <Stack.Screen options={{ title: cat?.label ?? '' }} />
      {!data || !cat ? (
        <Loading error={error ?? (data ? 'Unknown category' : undefined)} />
      ) : (
        <Screen>
          <PlayerHeader player={data} subtitle={cat.label} />
          <RatingSummary info={playerCategoryWhy(data, cat)} caption={`${cat.label} rating`} />
          <Text style={ui.muted}>
            {cat.blurb}{' '}
            {cat.teamBased
              ? 'Ranks compare his team with the other 31.'
              : `Ranks and ratings compare him with other ${data.rankGroupPlural}.`}{' '}
            Tap a stat with ⓘ to see what it means, or a colored rating to see why.
          </Text>
          {cat.qualNote ? (
            <Card style={{ borderColor: colors.mid }}>
              <Text style={[ui.body, { fontSize: 14 }]}>{cat.qualNote}</Text>
            </Card>
          ) : null}
          <Card style={{ paddingVertical: 2 }}>
            {cat.stats.map((st, i) => (
              <StatRow
                key={st.id}
                stat={st}
                last={i === cat.stats.length - 1}
                avgLabel={cat.teamBased ? 'League avg' : `${data.rankGroup} avg`}
                rankedAmong={cat.teamBased ? 'teams' : data.rankGroupPlural}
                ratingTitle={`${data.name} · ${st.label}`}
                context={data.context}
              />
            ))}
          </Card>
        </Screen>
      )}
    </>
  );
}
