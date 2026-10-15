import { Link, Stack } from 'expo-router';
import { Pressable, Text } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { RatingWeightsProvider } from '@/lib/ratings';
import { colors } from '@/lib/theme';

// If someone opens a deep link (e.g. a bookmarked category), keep the team list
// underneath it so there's always a way back.
export const unstable_settings = { initialRouteName: 'index' };

export default function RootLayout() {
  return (
    <RatingWeightsProvider>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.bg },
          headerTintColor: colors.text,
          headerTitleStyle: { fontWeight: '700' },
          headerShadowVisible: false,
          headerBackButtonDisplayMode: 'minimal',
          contentStyle: { backgroundColor: colors.bg },
          headerRight: () => <SettingsButton />,
        }}
      >
        <Stack.Screen name="index" options={{ title: 'NFL Stats' }} />
      </Stack>
    </RatingWeightsProvider>
  );
}

/** Gear in the top-right corner of every screen. */
function SettingsButton() {
  return (
    <Link href="/settings" asChild>
      <Pressable hitSlop={10} accessibilityRole="button" accessibilityLabel="Settings" style={{ paddingHorizontal: 8 }}>
        <Text style={{ color: colors.text, fontSize: 22 }}>⚙︎</Text>
      </Pressable>
    </Link>
  );
}
