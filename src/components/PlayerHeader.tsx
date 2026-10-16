import { Link } from 'expo-router';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';
import { ordinal } from '@/lib/theme';
import type { PlayerDoc } from '@/lib/types';
import { playerWhy } from '@/lib/why';
import { RatingButton } from './Rating';
import { sized } from '@/lib/images';

/** Banner at the top of every player screen, in his team's colors. */
export function PlayerHeader({ player, subtitle }: { player: PlayerDoc; subtitle?: string }) {
  const bio = [
    player.age != null ? `Age ${player.age}` : null,
    player.height,
    player.weight ? `${player.weight} lb` : null,
    // years_exp counts completed seasons, so this season is one more.
    player.experience == null ? null : player.experience === 0 ? 'Rookie' : `${ordinal(player.experience + 1)} season`,
    player.college,
  ].filter(Boolean);

  return (
    <View style={[s.wrap, { backgroundColor: player.teamColor, borderBottomColor: player.teamColor2 }]}>
      <View style={s.top}>
        {player.headshot ? (
          <Image source={{ uri: sized(player.headshot, 84) }} style={s.photo} accessibilityLabel={`Photo of ${player.name}`} />
        ) : (
          <View style={[s.photo, s.placeholder]}>
            <Text style={s.initial}>{player.name.charAt(0)}</Text>
          </View>
        )}
        <View style={{ flex: 1 }}>
          <Text style={s.name}>{player.name}</Text>
          <Text style={s.sub}>
            {[player.jersey != null ? `#${player.jersey}` : null, player.posName].filter(Boolean).join(' · ')}
            {subtitle ? ` · ${subtitle}` : ''}
          </Text>
          {player.depth || player.status === 'RES' ? (
            <View style={s.tags}>
              {player.depth ? <Text style={s.tag}>{player.depth}</Text> : null}
              {player.status === 'RES' ? <Text style={s.tag}>Injured reserve</Text> : null}
            </View>
          ) : null}
        </View>
        <View style={s.ratingWrap}>
          <RatingButton info={playerWhy(player)} size="md" />
          <Text style={s.ratingLabel}>OVR</Text>
        </View>
      </View>

      {player.team && player.teamName ? (
        <Link href={`/team/${player.team.toLowerCase()}`} asChild>
          <Pressable style={s.teamRow} accessibilityRole="link">
            {player.teamLogo ? (
              <View style={s.logoBg}>
                <Image source={{ uri: sized(player.teamLogo, 20) }} style={s.logo} />
              </View>
            ) : null}
            <Text style={s.team}>{player.teamName}</Text>
            <Text style={s.teamArrow}>›</Text>
          </Pressable>
        </Link>
      ) : null}

      {bio.length ? <Text style={s.bio}>{bio.join(' · ')}</Text> : null}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { padding: 14, borderRadius: 16, borderBottomWidth: 4, gap: 10 },
  top: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  photo: { width: 84, height: 84, borderRadius: 42, backgroundColor: 'rgba(255,255,255,0.9)' },
  placeholder: { alignItems: 'center', justifyContent: 'center' },
  initial: { fontSize: 28, fontWeight: '800', color: '#333' },
  name: { color: '#fff', fontSize: 22, fontWeight: '800' },
  sub: { color: 'rgba(255,255,255,0.88)', fontSize: 14, marginTop: 2 },
  tags: { flexDirection: 'row', gap: 6, marginTop: 6, flexWrap: 'wrap' },
  tag: {
    color: '#fff', fontSize: 12, fontWeight: '700', backgroundColor: 'rgba(0,0,0,0.28)',
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999, overflow: 'hidden',
  },
  teamRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: 'rgba(0,0,0,0.22)',
    borderRadius: 10, paddingVertical: 6, paddingHorizontal: 8,
  },
  logoBg: { width: 26, height: 26, borderRadius: 13, backgroundColor: 'rgba(255,255,255,0.92)', alignItems: 'center', justifyContent: 'center' },
  logo: { width: 20, height: 20 },
  team: { color: '#fff', fontSize: 14, fontWeight: '600', flex: 1 },
  teamArrow: { color: 'rgba(255,255,255,0.8)', fontSize: 20, marginTop: -2 },
  bio: { color: 'rgba(255,255,255,0.85)', fontSize: 13 },
  ratingWrap: { alignItems: 'center', gap: 4, backgroundColor: 'rgba(0,0,0,0.35)', borderRadius: 12, padding: 6, alignSelf: 'flex-start' },
  ratingLabel: { color: 'rgba(255,255,255,0.85)', fontSize: 10, fontWeight: '800', letterSpacing: 0.6 },
});
