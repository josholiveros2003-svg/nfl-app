import { Image, StyleSheet, Text, View } from 'react-native';
import type { Team } from '@/lib/types';
import { RatingButton, type WhyInfo } from './Rating';


/** Banner in the team's colors, shown at the top of every team screen. */
export function TeamHeader({ team, subtitle, rating }: { team: Team; subtitle?: string; rating?: WhyInfo }) {
  return (
    <View style={[s.wrap, { backgroundColor: team.color, borderBottomColor: team.color2 }]}>
      <View style={s.logoBg}>
        <Image source={{ uri: team.logo }} style={s.logo} accessibilityLabel={`${team.name} logo`} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={s.name}>{team.name}</Text>
        <Text style={s.sub}>
          {team.record} · {team.division}
          {subtitle ? ` · ${subtitle}` : ''}
        </Text>
      </View>
      {rating ? (
        <View style={s.ratingWrap}>
          <RatingButton info={rating} size="md" />
          <Text style={s.ratingLabel}>OVR</Text>
        </View>
      ) : null}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, borderRadius: 16, borderBottomWidth: 4 },
  logoBg: { width: 60, height: 60, borderRadius: 30, backgroundColor: 'rgba(255,255,255,0.92)', alignItems: 'center', justifyContent: 'center' },
  logo: { width: 46, height: 46 },
  name: { color: '#fff', fontSize: 21, fontWeight: '800' },
  sub: { color: 'rgba(255,255,255,0.85)', fontSize: 14, marginTop: 2 },
  ratingWrap: { alignItems: 'center', gap: 4, backgroundColor: 'rgba(0,0,0,0.35)', borderRadius: 12, padding: 6 },
  ratingLabel: { color: 'rgba(255,255,255,0.85)', fontSize: 10, fontWeight: '800', letterSpacing: 0.6 },
});

