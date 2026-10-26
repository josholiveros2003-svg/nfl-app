import { Stack, useLocalSearchParams, type Href } from 'expo-router';
import { useState } from 'react';
import { BoxScore, TeamStats } from '@/components/BoxScore';
import { Comparison } from '@/components/Comparison';
import { Inactives } from '@/components/Inactives';
import { Loading, Screen, Segmented } from '@/components/ui';
import { GameHeader } from '@/components/WinProb';
import { teamSide } from '@/lib/compare';
import { useGame, useTeam } from '@/lib/data';
import { useIsClient } from '@/lib/useIsClient';

type Tab = 'box' | 'team' | 'matchup';
const TABS: { id: Tab; label: string }[] = [
  { id: 'box', label: 'Box score' },
  { id: 'team', label: 'Team stats' },
  { id: 'matchup', label: 'Matchup' },
];

// One game: win chances (or the final score), then (for played games) the box score and team
// stats, and the two teams side by side using the same Compare screen.
// Address: /game?id=2026_06_SEA_DEN (&path=offense.passing to drill down into the matchup).
export default function GameScreen() {
  const params = useLocalSearchParams<{ id?: string; path?: string }>();
  const [picked, setPicked] = useState<Tab | null>(null);
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

  // Played games open on the box score; drilling into the matchup stays on the matchup.
  const box = path.length === 0 ? game.data?.box : undefined;
  const tab: Tab = !box ? 'matchup' : (picked ?? 'box');

  return (
    <>
      <Stack.Screen options={{ title: game.data ? `${game.data.away} @ ${game.data.home}` : 'Game' }} />
      {!game.data || !away.data || !home.data ? (
        <Loading error={isClient && !params.id ? 'No game picked' : error} />
      ) : (
        <Screen>
          <GameHeader game={game.data} teams={{ home: home.data.team, away: away.data.team }} />
          {box ? <Segmented options={TABS} value={tab} onChange={setPicked} /> : null}
          {box && tab === 'box' ? <BoxScore box={box} teams={{ home: home.data.team, away: away.data.team }} /> : null}
          {box && tab === 'team' ? <TeamStats box={box} teams={{ home: home.data.team, away: away.data.team }} /> : null}
          {tab === 'matchup' ? (
            <>
              <Comparison a={teamSide(away.data)} b={teamSide(home.data)} path={path} hrefFor={hrefFor} />
              {path.length === 0 ? <Inactives game={game.data} away={away.data} home={home.data} /> : null}
            </>
          ) : null}
        </Screen>
      )}
    </>
  );
}
