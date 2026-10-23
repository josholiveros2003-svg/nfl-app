import { Stack, useLocalSearchParams, type Href } from 'expo-router';
import { Comparison } from '@/components/Comparison';
import { Inactives } from '@/components/Inactives';
import { Loading, Screen } from '@/components/ui';
import { GameHeader } from '@/components/WinProb';
import { teamSide } from '@/lib/compare';
import { useGame, useTeam } from '@/lib/data';
import { useIsClient } from '@/lib/useIsClient';

// One game: win chances (or the final score), then the two teams side by side using the
// same Compare screen. Address: /game?id=2026_06_SEA_DEN (&path=offense.passing to drill down).
export default function GameScreen() {
  const params = useLocalSearchParams<{ id?: string; path?: string }>();
  const isClient = useIsClient();
  const path = params.path ? params.path.split('.').filter(Boolean) : [];
  const game = useGame(params.id);
  const away = useTeam(game.data?.away);
  const home = useTeam(game.data?.home);
  const error = game.error ?? away.error ?? home.error;

  const hrefFor = (p: string[]): Href => ({
    pathname: '/game',
    params: { id: params.id ?? '', ...(p.length ? { path: p.join('.') } : {}) },
  });

  return (
    <>
      <Stack.Screen options={{ title: game.data ? `${game.data.away} @ ${game.data.home}` : 'Game' }} />
      {!game.data || !away.data || !home.data ? (
        <Loading error={isClient && !params.id ? 'No game picked' : error} />
      ) : (
        <Screen>
          <GameHeader game={game.data} teams={{ home: home.data.team, away: away.data.team }} />
          <Comparison a={teamSide(away.data)} b={teamSide(home.data)} path={path} hrefFor={hrefFor} />
          {path.length === 0 ? <Inactives game={game.data} away={away.data} home={home.data} /> : null}
        </Screen>
      )}
    </>
  );
}
