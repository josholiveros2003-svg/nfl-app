import { Link, Stack, useLocalSearchParams, type Href } from 'expo-router';
import { Text } from 'react-native';
import { Comparison } from '@/components/Comparison';
import { Loading, Screen, styles as ui } from '@/components/ui';
import { playerSide, teamSide } from '@/lib/compare';
import { usePositionRank, useTeamRanks } from '@/lib/compareRanks';
import { usePlayer, usePlayersIndex, useRankings, useTeam } from '@/lib/data';
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

  // Rankings: power-ranking spot and league rank at every level for teams; position rank for players.
  const ranks = useTeamRanks(useRankings().data);
  const players = usePlayersIndex(kind === 'players');
  const posA = usePositionRank(players.data, kind === 'players' ? params.a : undefined);
  const posB = usePositionRank(players.data, kind === 'players' ? params.b : undefined);
  const teamBadge = (t: string) => {
    const power = ranks?.power(t);
    return power ? `#${power} in power rankings` : null;
  };
  const playerBadge = (r: ReturnType<typeof usePositionRank>) =>
    !r ? null : r.rank ? `#${r.rank} of ${r.of} ${r.group}s` : `${r.group} · not ranked yet (limited sample)`;

  const a = kind === 'teams'
    ? teamA.data ? teamSide(teamA.data, ranks?.groups(teamA.data.team.abbr), teamBadge(teamA.data.team.abbr)) : null
    : playerA.data ? playerSide(playerA.data, playerBadge(posA)) : null;
  const b = kind === 'teams'
    ? teamB.data ? teamSide(teamB.data, ranks?.groups(teamB.data.team.abbr), teamBadge(teamB.data.team.abbr)) : null
    : playerB.data ? playerSide(playerB.data, playerBadge(posB)) : null;
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
          <Comparison a={a} b={b} path={path} hrefFor={hrefFor} rankOf={kind === 'teams' ? ranks?.rankOf : undefined} />
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
