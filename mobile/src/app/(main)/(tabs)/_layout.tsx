// Three recorded-data tabs; legacy vehicle/account URLs remain reachable but hidden.
import { Tabs } from 'expo-router';
import { Icon } from '@/components/vehicle-health/ui';
import { palette } from '@/components/recorded/ui';
import { minimumTouchTarget, spacing, type } from '@/components/recorded/theme';
export default function ProductTabs() {
  return <Tabs initialRouteName="home" screenOptions={{
    headerShown: false,
    tabBarHideOnKeyboard: true,
    tabBarActiveTintColor: palette.accent,
    tabBarInactiveTintColor: palette.muted,
    tabBarLabelStyle: { ...type.caption, fontWeight: '600', marginTop: spacing.xxs },
    tabBarItemStyle: { minHeight: minimumTouchTarget, paddingTop: spacing.xs },
    tabBarStyle: { backgroundColor: palette.surface, borderTopColor: palette.line, borderTopWidth: 1 },
    sceneStyle: { backgroundColor: palette.background },
  }}>
    <Tabs.Screen name="home" options={{ title: 'Overview', tabBarIcon: ({ color }) => <Icon name="home" color={String(color)} /> }} />
    <Tabs.Screen name="telemetry" options={{ title: 'Telemetry', tabBarIcon: ({ color }) => <Icon name="gauge" color={String(color)} /> }} />
    <Tabs.Screen name="insights" options={{ title: 'Insights', tabBarIcon: ({ color }) => <Icon name="pulse" color={String(color)} /> }} />
    <Tabs.Screen name="vehicles" options={{ href: null }} />
    <Tabs.Screen name="account" options={{ href: null }} />
  </Tabs>;
}
