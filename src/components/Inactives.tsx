import { Text, View } from 'react-native';
import { colors } from '@/lib/theme';
import type { GameDoc, InactivePlayer, RosterPlayer, TeamDoc } from '@/lib/types';
import { PlayerRow } from './PlayerRow';
import { Card, SectionTitle } from './ui';

/** starter is unknown (undefined) in older data files. */
type Row = Omit<InactivePlayer, 'starter'> & { starter?: boolean };

const STATUS: Record<string, string> = { IR: 'IR', Out: 'Out', Doubtful: 'Doubtful' };

/** Who each team is missing for a game: position, overall rating and starter or backup. */
export function Inactives({ game, away, home }: { game: GameDoc; away: TeamDoc; home: TeamDoc }) {
  // Older data files only have the weighted injury list (no starter flag, minor players left out).
  const list = (side: 'home' | 'away'): Row[] => game.inactive?.[side] ?? game.injuries[side];

  return (
    <View style={{ gap: 6 }}>
      <SectionTitle>Inactive players</SectionTitle>
      {[
        { doc: away, players: list('away') },
        { doc: home, players: list('home') },
      ].map(({ doc, players }) => (
        <TeamInactives key={doc.team.abbr} doc={doc} players={players} />
      ))}
      <Text style={{ color: colors.muted, fontSize: 12, lineHeight: 17 }}>
        From the injury report (out or doubtful) and injured reserve. “Starter” means the player was on the first string of
        the depth chart at the start of the season.
        {game.played ? '' : ' Before the week’s injury report comes out, only injured reserve is known.'}
      </Text>
    </View>
  );
}

function TeamInactives({ doc, players }: { doc: TeamDoc; players: Row[] }) {
  const roster = new Map<string, RosterPlayer>(doc.roster.flatMap((sec) => sec.players.map((p) => [p.id, p] as const)));
  const starters = players.filter((p) => p.starter).length;
  return (
    <Card style={{ paddingVertical: 0, paddingHorizontal: 0, overflow: 'hidden' }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 14, paddingVertical: 10, borderBottomWidth: players.length ? 0.5 : 0, borderBottomColor: colors.border }}>
        <Text style={{ color: colors.text, fontSize: 15, fontWeight: '700' }}>{doc.team.nickname}</Text>
        <Text style={{ color: colors.muted, fontSize: 13 }}>
          {players.length ? `${players.length} out${starters ? ` · ${starters} starter${starters === 1 ? '' : 's'}` : ''}` : 'Nobody out'}
        </Text>
      </View>
      {players.map((p, i) => {
        const r = roster.get(p.id);
        return (
          <PlayerRow
            key={p.id}
            id={p.id}
            name={p.name}
            headshot={r?.headshot ?? null}
            tagline={[r?.jersey != null ? `#${r.jersey}` : null, p.pos, STATUS[p.status] ?? p.status].filter(Boolean).join(' · ')}
            rt={r?.rt ?? null}
            badge={
              p.starter === undefined ? null : p.starter ? { text: 'Starter', color: colors.good } : { text: 'Backup', color: colors.muted }
            }
            last={i === players.length - 1}
          />
        );
      })}
    </Card>
  );
}
