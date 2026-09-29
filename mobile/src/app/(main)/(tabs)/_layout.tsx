// Four primary tabs; vehicle, history, insight and report details stay in the parent stack.
import { Tabs, TabList, TabTrigger, TabSlot } from 'expo-router/ui';
import { Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon } from '@/components/vehicle-health/ui';
import { colors as c } from '@/theme/colors';
import type { TabTriggerSlotProps } from 'expo-router/ui';
function TabButton({
  children,
  isFocused,
  icon,
  ...props
}: TabTriggerSlotProps & { icon: string }) {
  return (
    <Pressable
      {...props}
      accessibilityRole="tab"
      accessibilityState={{ selected: isFocused }}
      style={{ flex: 1, minHeight: 58, alignItems: 'center', justifyContent: 'center', gap: 5 }}
    >
      <Icon name={icon} color={isFocused ? c.primary : c.textMuted} />
      <Text style={{ fontSize: 11, color: isFocused ? c.primary : c.textMuted }}>{children}</Text>
    </Pressable>
  );
}
export default function ProductTabs() {
  const insets = useSafeAreaInsets();
  return (
    <Tabs style={{ flex: 1, backgroundColor: c.background }}>
      <View style={{ flex: 1 }}>
        <TabSlot />
      </View>
      <TabList
        style={{
          borderTopWidth: 1,
          borderColor: c.border,
          backgroundColor: c.card,
          paddingBottom: insets.bottom,
        }}
      >
        <TabTrigger name="home" href="/(main)/(tabs)/home" asChild>
          <TabButton icon="home">Home</TabButton>
        </TabTrigger>
        <TabTrigger name="vehicles" href="/(main)/(tabs)/vehicles" asChild>
          <TabButton icon="car">Vehicles</TabButton>
        </TabTrigger>
        <TabTrigger name="insights" href="/(main)/(tabs)/insights" asChild>
          <TabButton icon="pulse">Insights</TabButton>
        </TabTrigger>
        <TabTrigger name="account" href="/(main)/(tabs)/account" asChild>
          <TabButton icon="account">Account</TabButton>
        </TabTrigger>
      </TabList>
    </Tabs>
  );
}
