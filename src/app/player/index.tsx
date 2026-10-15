import { Stack, useLocalSearchParams } from 'expo-router';
import { Text, View } from 'react-native';
import { KeyStats } from '@/components/KeyStats';
import { PlayerHeader } from '@/components/PlayerHeader';
import { RatingBadge } from '@/components/Rating';
import { LinkCard, Loading, Screen, styles as ui } from '@/components/ui';
import { usePlayer } from '@/lib/data';
import { useIsClient } from '@/lib/useIsClient';
import { readableTeamColor } from '@/lib/theme';

// A player's page: header, then one card per stat category that fits his position.
// The address looks like /player?id=00-0033873 (his NFL player id).
export default function PlayerScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const isClient = useIsClient();
  const { data, error } = usePlayer(id);

  return (
    <>
      <Stack.Screen options={{ title: data?.name ?? 'Player' }} />
      {!data ? (
        <Loading error={error ?? (isClient && !id ? 'No player picked' : undefined)} />
      ) : (
        <Screen>
          <PlayerHeader player={data} />
          <Text style={ui.muted}>
            {data.season} regular season through Week {data.throughWeek}. Ranks and ratings compare him with other{' '}
            {data.rankGroupPlural}. Tap the OVR rating to see how it was built.
          </Text>
          {data.categories.map((c) => {
            const preview = (c.key ?? []).map((k) => c.stats.find((st) => st.id === k));
            return (
              <LinkCard
                key={c.id}
                href={{ pathname: '/player/[category]', params: { category: c.id, id: data.id } }}
                accent={readableTeamColor(data.teamColor, data.teamColor2)}
              >
                <View style={ui.row}>
                  <Text style={[ui.title, { flex: 1 }]}>{c.label}</Text>
                  <RatingBadge rt={c.rt} size="sm" />
                </View>
                <Text style={ui.muted}>{c.qualified ? c.blurb : c.qualNote}</Text>
                <KeyStats stats={preview} />
              </LinkCard>
            );
          })}
        </Screen>
      )}
    </>
  );
}
