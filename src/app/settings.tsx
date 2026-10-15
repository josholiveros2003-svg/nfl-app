import Slider from '@react-native-community/slider';
import { Stack } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Card, Screen, SectionTitle, styles as ui } from '@/components/ui';
import rankingSettings from '../../config/rankings.json';
import { effectiveWeights, FACTORS, INFLUENCE, useRatingWeights, type RankWeights } from '@/lib/ratings';
import { colors } from '@/lib/theme';

// Sliders for how much each factor counts in every rating. Changes apply instantly
// across the app and are remembered on this device.
export default function SettingsScreen() {
  const { weights, influence, rank, setWeight, setInfluence, setRank, reset } = useRatingWeights();
  const rankTotal = (['results', 'rating', 'form'] as const).reduce((a, k) => a + Math.max(0, rank[k]), 0) || 1;
  const shares = effectiveWeights(weights);

  return (
    <>
      <Stack.Screen options={{ title: 'Settings' }} />
      <Screen>
        <SectionTitle>How far stats can move ratings</SectionTitle>
        <Text style={ui.muted}>
          Every rating starts at the player’s (or team’s) Madden NFL 27 rating and then moves with real results.
        </Text>
        <Card>
          <View style={s.factor}>
            <View style={s.top}>
              <Text style={s.label}>Stats influence</Text>
              <Text style={s.share}>{influence.toFixed(1)}×</Text>
            </View>
            <Slider
              minimumValue={INFLUENCE.min}
              maximumValue={INFLUENCE.max}
              step={0.1}
              value={influence}
              onValueChange={setInfluence}
              minimumTrackTintColor={colors.good}
              maximumTrackTintColor={colors.border}
              thumbTintColor={colors.text}
              accessibilityLabel="Stats influence"
            />
            <Text style={s.explain}>{INFLUENCE.explain}</Text>
          </View>
        </Card>

        <SectionTitle>Rating factors</SectionTitle>
        <Text style={ui.muted}>
          These decide how the stat-based adjustment is built. Slide to change how much each one counts. The
          percentages on the right are the actual shares after balancing them to 100%.
        </Text>

        <Card style={{ gap: 4 }}>
          {FACTORS.map((f, i) => {
            const available = f.available !== false;
            return (
              <View key={f.id} style={[s.factor, i < FACTORS.length - 1 && s.divider]}>
                <View style={s.top}>
                  <Text style={[s.label, !available && { color: colors.muted }]}>{f.label}</Text>
                  <Text style={s.share}>{available ? `${Math.round(shares[i] * 100)}%` : 'Not available yet'}</Text>
                </View>
                <Slider
                  minimumValue={0}
                  maximumValue={100}
                  step={1}
                  value={weights[i]}
                  onValueChange={(v) => setWeight(i, v)}
                  disabled={!available}
                  minimumTrackTintColor={available ? colors.good : colors.border}
                  maximumTrackTintColor={colors.border}
                  thumbTintColor={available ? colors.text : colors.muted}
                  accessibilityLabel={`${f.label} weight`}
                />
                <Text style={s.explain}>{f.explain}</Text>
              </View>
            );
          })}
        </Card>

        <SectionTitle>Power rankings</SectionTitle>
        <Text style={ui.muted}>How the League power rankings are built. Percentages are the actual shares after balancing.</Text>
        <Card style={{ gap: 4 }}>
          {RANK_SLIDERS.map((r, i) => (
            <View key={r.key} style={[s.factor, i < RANK_SLIDERS.length - 1 && s.divider]}>
              <View style={s.top}>
                <Text style={s.label}>{r.label}</Text>
                <Text style={s.share}>
                  {r.key === 'injuries' ? `${rank.injuries.toFixed(1)}×` : `${Math.round((Math.max(0, rank[r.key]) / rankTotal) * 100)}%`}
                </Text>
              </View>
              <Slider
                minimumValue={0}
                maximumValue={r.key === 'injuries' ? 2 : 100}
                step={r.key === 'injuries' ? 0.1 : 1}
                value={rank[r.key]}
                onValueChange={(v) => setRank(r.key, v)}
                minimumTrackTintColor={colors.good}
                maximumTrackTintColor={colors.border}
                thumbTintColor={colors.text}
                accessibilityLabel={`${r.label} weight`}
              />
              <Text style={s.explain}>{r.explain}</Text>
            </View>
          ))}
        </Card>

        <Pressable onPress={reset} style={({ pressed }) => [s.reset, pressed && { opacity: 0.7 }]} accessibilityRole="button">
          <Text style={s.resetText}>Reset everything to defaults</Text>
        </Pressable>

        <SectionTitle>Other weights</SectionTitle>
        <Text style={ui.muted}>
          How stats add up into categories, positions and teams (for example, how much passing counts for a QB), and
          how fast stats take over from Madden, are set in the project’s settings file, config/ratings.json, which
          explains each choice.
        </Text>
      </Screen>
    </>
  );
}

const RANK_SLIDERS: { key: keyof RankWeights; label: string; explain: string }[] = [
  { key: 'results', label: 'Wins & losses (in context)', explain: rankingSettings.weightsWhy.results },
  { key: 'rating', label: 'Team rating', explain: rankingSettings.weightsWhy.rating },
  { key: 'form', label: 'Recent form', explain: rankingSettings.weightsWhy.form },
  {
    key: 'injuries',
    label: 'Current injuries',
    explain: 'How much key players out right now lower a team (1× = a missing average starting QB costs about 8 rating points; 0 = ignore injuries).',
  },
];

const s = StyleSheet.create({
  factor: { paddingVertical: 12, gap: 4 },
  divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  label: { color: colors.text, fontSize: 16, fontWeight: '600' },
  share: { color: colors.text, fontSize: 15, fontWeight: '700', fontVariant: ['tabular-nums'] },
  explain: { color: colors.muted, fontSize: 13, lineHeight: 18 },
  reset: { alignSelf: 'flex-start', paddingVertical: 10 },
  resetText: { color: '#7FB2FF', fontWeight: '700', fontSize: 15 },
});
