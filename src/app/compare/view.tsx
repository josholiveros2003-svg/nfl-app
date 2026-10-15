import { Link, Stack, useLocalSearchParams, type Href } from 'expo-router';
import { Text } from 'react-native';
import { Comparison } from '@/components/Comparison';
import { Loading, Screen, styles as ui } from '@/components/ui';
import { playerSide, teamSide } from '@/lib/compare';
import { usePlayer, useTeam } from '@/lib/data';
import { useIsClient } from '@/lib/useIsClient';

// Side-by-side comparison of two teams or two players.
// Address: /compare/view?kind=teams&a=KC&b=BUF&path=offense.passing
export default function CompareViewScreen() {
  const params = useLocalSearchParams<{ kind?: string; a?: string; b?: string; path?: string }>();
  const kind = params.kind === 'players' ? 'players' : 'teams';
  const isClient = useIsClient();
  const path = params.path ? params.path.split('.').filter(Boolean) : [];

  const teamA = useTeam(kind === 'teams' ? params.a : undefined);
  const teamB = useTeam(kind === 'teams' ? params.b : undefined);
  const playerA = usePlayer(kind === 'players' ? params.a : undefined);
  const playerB = usePlayer(kind === 'players' ? params.b : undefined);

  const a = kind === 'teams' ? (teamA.data ? teamSide(teamA.data) : null) : playerA.data ? playerSide(playerA.data) : null;
  const b = kind === 'teams' ? (teamB.data ? teamSide(teamB.data) : null) : playerB.data ? playerSide(playerB.data) : null;
  const error = teamA.error ?? teamB.error ?? playerA.error ?? playerB.error;

  const hrefFor = (p: string[]): Href => ({
    pathname: '/compare/view',
    params: { kind, a: params.a ?? '', b: params.b ?? '', ...(p.length ? { path: p.join('.') } : {}) },
  });

  return (
    <>
      <Stack.Screen options={{ title: 'Compare' }} />
      {isClient && (!params.a || !params.b) ? (
        <Loading error="Pick two teams or two players to compare." />
      ) : !a || !b ? (
        <Loading error={error} />
      ) : (
        <Screen>
          <Comparison a={a} b={b} path={path} hrefFor={hrefFor} />
          <Link href={{ pathname: '/compare', params: { kind } }} style={[ui.muted, { color: '#7FB2FF', fontWeight: '700', marginTop: 8 }]}>
            Compare something else
          </Link>
          <Text style={ui.muted}>
            Ratings use your Settings. Stat colors compare league ranks, so “lower is better” stats like interceptions
            count the right way.
          </Text>
        </Screen>
      )}
    </>
  );
}
