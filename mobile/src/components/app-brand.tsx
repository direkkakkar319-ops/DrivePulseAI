// Existing DrivePulse pulse mark and wordmark in the shared light-theme palette.
import { StyleSheet, View } from 'react-native';
import { colors, spacing } from '@/theme/tokens';
import { AppIcon } from './ui/app-icon';
import { AppText } from './ui/app-text';

export function AppBrand() {
  return <View style={styles.brand}>
    <AppIcon name="insights" color={colors.accent} size={32} />
    <AppText variant="title">DrivePulse <AppText variant="title" tone="accent">AI</AppText></AppText>
  </View>;
}

const styles = StyleSheet.create({
  brand: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
});
