import type { Player } from '@/lib/types';
import { PlayerRow } from './PlayerRow';
import { Card, SectionTitle } from './ui';

/** Top players for a team category. Each one is tappable. */
export function Leaders({ title, players }: { title: string; players: Player[] }) {
  if (!players.length) return null;
  return (
    <>
      <SectionTitle>{title}</SectionTitle>
      <Card style={{ paddingVertical: 0, paddingHorizontal: 0, overflow: 'hidden' }}>
        {players.map((p, i) => (
          <PlayerRow
            key={p.id}
            id={p.id}
            name={p.name}
            headshot={p.headshot}
            tagline={[p.pos, p.jersey != null ? `#${p.jersey}` : null].filter(Boolean).join(' · ')}
            line={p.line}
            rt={p.rt ?? null}
            last={i === players.length - 1}
          />
        ))}
      </Card>
    </>
  );
}
