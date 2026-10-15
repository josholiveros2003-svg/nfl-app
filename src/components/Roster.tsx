import { View } from 'react-native';
import type { RosterSection } from '@/lib/types';
import { colors } from '@/lib/theme';
import { PlayerRow } from './PlayerRow';
import { Card, SectionTitle } from './ui';

/** The team's players by position group, in depth chart order (starters first). */
export function Roster({ sections }: { sections: RosterSection[] }) {
  return (
    <>
      {sections
        .filter((sec) => sec.players.length)
        .map((sec) => (
          <View key={sec.id}>
            <SectionTitle>
              {sec.label} ({sec.players.length})
            </SectionTitle>
            <Card style={{ paddingVertical: 0, paddingHorizontal: 0, overflow: 'hidden', marginTop: 6 }}>
              {sec.players.map((p, i) => (
                <PlayerRow
                  key={p.id}
                  id={p.id}
                  name={p.name}
                  headshot={p.headshot}
                  tagline={[p.jersey != null ? `#${p.jersey}` : null, p.depth?.replace('Starter · ', '') ?? p.pos].filter(Boolean).join(' · ')}
                  line={p.line}
                  rt={p.rt ?? null}
                  badge={
                    p.tag
                      ? { text: p.tag, color: colors.bad }
                      : p.starter
                        ? { text: 'Starter', color: colors.good }
                        : null
                  }
                  last={i === sec.players.length - 1}
                />
              ))}
            </Card>
          </View>
        ))}
    </>
  );
}
