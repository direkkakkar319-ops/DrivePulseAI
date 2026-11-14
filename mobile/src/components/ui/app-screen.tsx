// Opt-in safe-area page shell with explicit scrolling and keyboard avoidance.
import type { PropsWithChildren } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, View, type ScrollViewProps, type StyleProp, type ViewStyle } from 'react-native';
import { SafeAreaView, type SafeAreaViewProps } from 'react-native-safe-area-context';
import { colors, layout, spacing } from '@/theme/tokens';

export interface AppScreenProps extends PropsWithChildren {
  scroll?: boolean;
  keyboardAvoiding?: boolean;
  keyboardVerticalOffset?: number;
  edges?: SafeAreaViewProps['edges'];
  background?: 'primary' | 'secondary';
  style?: StyleProp<ViewStyle>;
  contentContainerStyle?: StyleProp<ViewStyle>;
  scrollViewProps?: Omit<ScrollViewProps, 'children' | 'style' | 'contentContainerStyle'>;
  testID?: string;
}

export function AppScreen({ children, scroll = true, keyboardAvoiding = false, keyboardVerticalOffset = 0,
  edges = ['top', 'right', 'bottom', 'left'], background = 'primary', style, contentContainerStyle, scrollViewProps, testID }: AppScreenProps) {
  const content = scroll
    ? <ScrollView keyboardShouldPersistTaps="handled" {...scrollViewProps} style={styles.flex}
        contentContainerStyle={[styles.content, contentContainerStyle]}>{children}</ScrollView>
    : <View style={[styles.content, styles.flex, contentContainerStyle]}>{children}</View>;
  return <SafeAreaView edges={edges} testID={testID} style={[styles.flex, {
    backgroundColor: background === 'primary' ? colors.background : colors.backgroundSecondary,
  }, style]}>
    {keyboardAvoiding ? <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={keyboardVerticalOffset}>{content}</KeyboardAvoidingView> : content}
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  content: { flexGrow: 1, width: '100%', maxWidth: layout.contentMaxWidth, alignSelf: 'center',
    padding: spacing.lg, gap: spacing.lg },
});
