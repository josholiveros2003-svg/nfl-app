import { router } from 'expo-router';
import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { breakdown, effectiveWeights, useRating, useRatingWeights } from '@/lib/ratings';
import { colors, ratingColor } from '@/lib/theme';
import type { RatingContext, Rt } from '@/lib/types';

/** What a rating is made of, for the "why" sheet (e.g. a category's stats). */
export type RatingPart = { label: string; w?: number; rt?: Rt | null };

export type WhyInfo = {
  title: string;
  rt: Rt | null | undefined;
  context?: RatingContext | null;
  parts?: RatingPart[];
  partsLabel?: string;
  /** Teams: the baseline is built from the starters' Madden ratings. */
  team?: boolean;
};

/** A small colored 0-100 box. Shows "—" when there's nothing to rate. */
export function RatingBadge({ rt, size = 'md' }: { rt: Rt | null | undefined; size?: 'sm' | 'md' | 'lg' }) {
  const b = useRating(rt);
  const dims = SIZES[size];
  const c = ratingColor(b?.rating);
  return (
    <View
      style={[s.badge, { width: dims.box, height: dims.box, borderColor: c, backgroundColor: b ? `${c}22` : 'transparent' }]}
      accessibilityLabel={b ? `Rating ${b.rating}${b.limited ? ', limited sample' : ''}` : 'No rating'}
    >
      <Text style={[s.badgeText, { color: c, fontSize: dims.font }]}>{b ? b.rating : '—'}</Text>
      {b?.limited ? <Text style={[s.ltd, { color: c }]}>LTD</Text> : null}
    </View>
  );
}

const SIZES = { sm: { box: 34, font: 14 }, md: { box: 40, font: 16 }, lg: { box: 58, font: 24 } };

/** A rating badge you can tap to see why it is what it is. */
export function RatingButton({ info, size = 'md' }: { info: WhyInfo; size?: 'sm' | 'md' | 'lg' }) {
  const [open, setOpen] = useState(false);
  if (!info.rt) return <RatingBadge rt={null} size={size} />;
  return (
    <>
      <Pressable onPress={() => setOpen(true)} accessibilityRole="button" accessibilityHint="Shows why this rating is what it is" hitSlop={6}>
        <RatingBadge rt={info.rt} size={size} />
      </Pressable>
      {open ? <WhySheet info={info} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

/** A card with the big rating and a "Why this rating?" button, for the top of a screen. */
export function RatingSummary({ info, caption }: { info: WhyInfo; caption: string }) {
  const [open, setOpen] = useState(false);
  const b = useRating(info.rt);
  return (
    <>
      <Pressable
        onPress={() => b && setOpen(true)}
        style={({ pressed }) => [s.summary, pressed && b ? { backgroundColor: colors.cardPressed } : null]}
        accessibilityRole="button"
      >
        <RatingBadge rt={info.rt} size="lg" />
        <View style={{ flex: 1 }}>
          <Text style={s.summaryTitle}>{caption}</Text>
          <Text style={s.summarySub}>
            {b
              ? `${b.limited ? 'Limited sample · ' : ''}Tap to see why this rating`
              : 'Not enough data to rate yet'}
          </Text>
        </View>
        {b ? <Text style={s.why}>Why?</Text> : null}
      </Pressable>
      {open ? <WhySheet info={info} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

const fmtMove = (x: number) => `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(1)}`;
const pct = (x: number) => `${Math.round(x * 100)}%`;

/** The "why this rating" sheet: where it starts, what moved it, and what it's made of. */
export function WhySheet({ info, onClose }: { info: WhyInfo; onClose: () => void }) {
  const { weights, influence } = useRatingWeights();
  const b = breakdown(info.rt, weights, influence);
  if (!b) return null;
  const ctxFor: Record<string, string | undefined> = {
    opponents: info.context?.opp,
    injuries: info.context?.inj,
    recent: info.context?.recent,
  };
  const parts = (info.parts ?? []).filter((p) => p.rt && (p.w ?? 0) > 0);
  const totalW = parts.reduce((a, p) => a + (p.w ?? 0), 0);

  return (
    <Modal transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={s.backdrop} onPress={onClose} accessibilityLabel="Close">
        <Pressable style={s.sheet} onPress={() => {}}>
          <ScrollView contentContainerStyle={{ padding: 18, gap: 12 }}>
            <View style={s.sheetHead}>
              <RatingBadge rt={info.rt} size="lg" />
              <View style={{ flex: 1 }}>
                <Text style={s.sheetTitle}>{info.title}</Text>
                <Text style={s.sheetSub}>Why this rating</Text>
              </View>
              <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button" accessibilityLabel="Close">
                <Text style={s.close}>✕</Text>
              </Pressable>
            </View>

            <View style={s.box}>
              <Row
                label={
                  info.team ? 'Madden roster baseline' : b.estimatedBaseline ? 'Starting point (estimated)' : 'Madden NFL 27 rating'
                }
                detail={
                  info.team
                    ? 'Average Madden rating of the expected starters (QB counts 4×), scaled to Madden\'s team range.'
                    : b.estimatedBaseline
                      ? 'Not in the Madden file, so he starts at a typical backup rating for his position.'
                      : 'The starting point, from EA\'s launch ratings.'
                }
                value={b.baseline.toFixed(1)}
                strong
              />
              <Row
                label="This season's stats"
                detail={`Compared with what a ${Math.round(b.baseline)} normally produces · stats count ${pct(b.statShare)} here${b.limited ? ' (limited sample)' : ''} · ${pct(effectiveWeights(weights)[0])} weight`}
                value={fmtMove(b.stats)}
                color={b.stats >= 0.05 ? colors.good : b.stats <= -0.05 ? colors.bad : colors.muted}
              />
              {b.moves.map((m) => (
                <Row
                  key={m.factor.id}
                  label={m.factor.label}
                  detail={
                    m.move == null
                      ? 'Not available yet. Its share is spread across the other factors.'
                      : `${pct(m.share)} weight${ctxFor[m.factor.id] ? ` · ${ctxFor[m.factor.id]}` : ''}`
                  }
                  value={m.move == null ? 'n/a' : fmtMove(m.move)}
                  color={m.move == null ? colors.muted : m.move >= 0.05 ? colors.good : m.move <= -0.05 ? colors.bad : colors.muted}
                />
              ))}
              <View style={s.totalRow}>
                <Text style={s.totalLabel}>Rating</Text>
                <Text style={[s.totalValue, { color: ratingColor(b.rating) }]}>{b.rating}</Text>
              </View>
            </View>

            {parts.length ? (
              <>
                <Text style={s.section}>{info.partsLabel ?? 'Made up of'}</Text>
                <View style={s.box}>
                  {parts.map((p) => (
                    <PartRow key={p.label} part={p} share={(p.w ?? 0) / totalW} />
                  ))}
                </View>
              </>
            ) : null}

            {b.limited ? (
              <Text style={s.note}>
                Limited sample: he hasn’t played enough yet for his stats to say much, so this rating stays close to his
                Madden rating. The more he plays, the more his stats count.
              </Text>
            ) : null}
            {b.respread && b.respread > 1.01 ? (
              <Text style={s.note}>
                Averaging many stats lets good and bad ones cancel out, so the adjustment here is scaled back up (×
                {b.respread.toFixed(2)}) to move as much as a single stat would. That’s why it can differ from the
                weighted average of its parts.
              </Text>
            ) : null}
            <Text style={s.note}>
              Every rating starts at Madden and moves with real results. Stats count more as the season goes on, and
              more at positions where stats explain Madden ratings well.
            </Text>

            <Pressable
              onPress={() => {
                onClose();
                router.push('/settings');
              }}
              style={s.settingsBtn}
              accessibilityRole="button"
            >
              <Text style={s.settingsText}>Change how much each factor counts in Settings</Text>
            </Pressable>
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function Row({ label, detail, value, color, strong }: { label: string; detail?: string; value: string; color?: string; strong?: boolean }) {
  return (
    <View style={s.row}>
      <View style={{ flex: 1 }}>
        <Text style={[s.rowLabel, strong && { fontWeight: '700' }]}>{label}</Text>
        {detail ? <Text style={s.rowDetail}>{detail}</Text> : null}
      </View>
      <Text style={[s.rowValue, { color: color ?? colors.text }]}>{value}</Text>
    </View>
  );
}

function PartRow({ part, share }: { part: RatingPart; share: number }) {
  const b = useRating(part.rt);
  return (
    <View style={s.row}>
      <Text style={[s.rowLabel, { flex: 1 }]}>{part.label}</Text>
      <Text style={s.rowDetail}>{pct(share)}</Text>
      <Text style={[s.rowValue, { color: ratingColor(b?.rating), minWidth: 36, textAlign: 'right' }]}>{b?.rating ?? '—'}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  badge: { borderWidth: 1.5, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  badgeText: { fontWeight: '800', fontVariant: ['tabular-nums'] },
  ltd: { position: 'absolute', bottom: -7, fontSize: 8, fontWeight: '800', backgroundColor: colors.bg, paddingHorizontal: 2 },
  summary: {
    flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: colors.card, borderRadius: 14, padding: 14,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  summaryTitle: { color: colors.text, fontSize: 17, fontWeight: '700' },
  summarySub: { color: colors.muted, fontSize: 13, marginTop: 2 },
  why: { color: '#7FB2FF', fontWeight: '700', fontSize: 14 },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end', alignItems: 'center' },
  sheet: {
    width: '100%', maxWidth: 640, maxHeight: '88%', backgroundColor: colors.bg, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border,
  },
  sheetHead: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  sheetTitle: { color: colors.text, fontSize: 18, fontWeight: '800' },
  sheetSub: { color: colors.muted, fontSize: 13, marginTop: 2 },
  close: { color: colors.muted, fontSize: 20, padding: 4 },
  box: { backgroundColor: colors.card, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 4, borderWidth: StyleSheet.hairlineWidth, borderColor: colors.border },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  rowLabel: { color: colors.text, fontSize: 15 },
  rowDetail: { color: colors.muted, fontSize: 12, marginTop: 2 },
  rowValue: { fontSize: 16, fontWeight: '700', fontVariant: ['tabular-nums'] },
  totalRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 12 },
  totalLabel: { color: colors.text, fontSize: 16, fontWeight: '800' },
  totalValue: { fontSize: 22, fontWeight: '800' },
  section: { color: colors.muted, fontSize: 13, fontWeight: '700', letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 4 },
  note: { color: colors.muted, fontSize: 12, lineHeight: 17 },
  settingsBtn: { alignSelf: 'flex-start', paddingVertical: 8 },
  settingsText: { color: '#7FB2FF', fontWeight: '700', fontSize: 14 },
});
