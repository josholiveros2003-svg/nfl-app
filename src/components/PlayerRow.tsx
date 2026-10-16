import { Link } from 'expo-router';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { colors } from '@/lib/theme';
import type { Rt } from '@/lib/types';
import { RatingBadge } from './Rating';
import { sized } from '@/lib/images';

type Props = {
  id: string;
  name: string;
  headshot: string | null;
  /** Small grey text under the name, e.g. "#15 · Starter · QB". */
  tagline?: string | null;
  /** Second line, e.g. a stat summary. */
  line?: string | null;
  /** Little colored label on the right, e.g. "Starter" or "IR". */
  badge?: { text: string; color: string } | null;
  /** His overall 0-100 rating. */
  rt?: Rt | null;
  last?: boolean;
};

/** One tappable player, used anywhere players are listed. Opens his player page. */
export function PlayerRow({ id, name, headshot, tagline, line, badge, rt, last }: Props) {
  return (
    <Link href={{ pathname: '/player', params: { id } }} asChild>
      <Pressable accessibilityRole="link" accessibilityLabel={`${name}, open player page`}>
        {({ pressed }) => (
          <View style={[s.row, !last && s.divider, pressed && s.pressed]}>
            {headshot ? (
              <Image source={{ uri: sized(headshot, 44) }} style={s.photo} />
            ) : (
              <View style={[s.photo, s.placeholder]}>
                <Text style={s.initial}>{name.charAt(0)}</Text>
              </View>
            )}
            <View style={{ flex: 1 }}>
              <Text style={s.name} numberOfLines={1}>
                {name}
              </Text>
              {tagline ? <Text style={s.tagline}>{tagline}</Text> : null}
              {line ? <Text style={s.line}>{line}</Text> : null}
            </View>
            {badge ? (
              <View style={[s.badge, { borderColor: badge.color }]}>
                <Text style={[s.badgeText, { color: badge.color }]}>{badge.text}</Text>
              </View>
            ) : null}
            {rt !== undefined ? <RatingBadge rt={rt} size="sm" /> : null}
            <Text style={s.chevron}>›</Text>
          </View>
        )}
      </Pressable>
    </Link>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, paddingHorizontal: 14 },
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  pressed: { backgroundColor: colors.cardPressed },
  photo: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.border },
  placeholder: { alignItems: 'center', justifyContent: 'center' },
  initial: { color: colors.muted, fontWeight: '700' },
  name: { color: colors.text, fontSize: 15, fontWeight: '600' },
  tagline: { color: colors.muted, fontSize: 12, marginTop: 1 },
  line: { color: '#C9D1DE', fontSize: 13, marginTop: 2 },
  badge: { borderWidth: 1, borderRadius: 999, paddingHorizontal: 7, paddingVertical: 1 },
  badgeText: { fontSize: 11, fontWeight: '700' },
  chevron: { color: colors.muted, fontSize: 22, fontWeight: '300', marginTop: -2 },
});
