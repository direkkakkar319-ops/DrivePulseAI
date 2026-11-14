// Five main destinations; recorded Telemetry keeps its existing URL without a tab button.
import { Tabs } from 'expo-router';
import { StyleSheet, View, type ColorValue } from 'react-native';
import { AppIcon, type AppIconName } from '@/components/ui/app-icon';
import { colors, layout, typography } from '@/theme/tokens';

function TabIcon({ name, color, focused }: { name: AppIconName; color: ColorValue; focused: boolean }) {
  return <View style={[styles.icon, { borderTopColor: focused ? colors.accent : 'transparent' }]}>
    <AppIcon name={name} color={color} />
  </View>;
}

export default function ProductTabs() {
  return <Tabs initialRouteName="home" backBehavior="initialRoute" screenOptions={{
    headerShown: false,
    tabBarHideOnKeyboard: true,
    tabBarActiveTintColor: colors.accent,
    tabBarInactiveTintColor: colors.textSecondary,
    tabBarLabelPosition: 'below-icon',
    tabBarAllowFontScaling: true,
    tabBarLabelStyle: { ...typography.caption, fontWeight: '600' },
    tabBarItemStyle: { minHeight: layout.minimumTouchTarget },
    // The navigator supplies the bottom safe-area inset; do not fix the bar height.
    tabBarStyle: { backgroundColor: colors.background, borderTopColor: colors.border, borderTopWidth: 1,
      elevation: 0, shadowOpacity: 0 },
    sceneStyle: { backgroundColor: colors.background },
  }}>
    <Tabs.Screen name="home" options={{ title: 'Home', tabBarIcon: props => <TabIcon name="home" {...props} /> }} />
    <Tabs.Screen name="vehicles" options={{ title: 'Garage', tabBarIcon: props => <TabIcon name="car" {...props} /> }} />
    <Tabs.Screen name="insights" options={{ title: 'AI Insights', tabBarIcon: props => <TabIcon name="insights" {...props} /> }} />
    <Tabs.Screen name="history" options={{ title: 'History', tabBarIcon: props => <TabIcon name="history" {...props} /> }} />
    <Tabs.Screen name="account" options={{ title: 'Profile', tabBarIcon: props => <TabIcon name="profile" {...props} /> }} />
    <Tabs.Screen name="telemetry" options={{ href: null }} />
  </Tabs>;
}

const styles = StyleSheet.create({
  icon: { width: 40, height: 26, alignItems: 'center', justifyContent: 'center', borderTopWidth: 2 },
});
