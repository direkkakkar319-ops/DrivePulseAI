// Accessible actions with explicit loading, disabled, pressed, and keyboard focus states.
import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, type PressableProps, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';
import { colors, layout, radii, spacing } from '@/theme/tokens';
import { AppText } from './app-text';
import { AppIcon, type AppIconName } from './app-icon';

export interface AppButtonProps extends Omit<PressableProps, 'children' | 'style'> {
  title: string;
  variant?: 'primary' | 'secondary' | 'text';
  loading?: boolean;
  icon?: AppIconName;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
}

export function AppButton({ title, variant = 'primary', loading = false, disabled = false, icon, style, textStyle,
  onFocus, onBlur, accessibilityLabel, accessibilityState, ...props }: AppButtonProps) {
  const [focused, setFocused] = useState(false);
  const unavailable = disabled || loading;
  const foreground = unavailable ? colors.disabledText : variant === 'primary' ? colors.onAccent : colors.accent;
  return <Pressable {...props} accessibilityRole="button" accessibilityLabel={accessibilityLabel ?? title}
    accessibilityState={{ ...accessibilityState, disabled: unavailable, busy: loading }} disabled={unavailable}
    onFocus={event => { setFocused(true); onFocus?.(event); }}
    onBlur={event => { setFocused(false); onBlur?.(event); }}
    style={({ pressed }) => [styles.button, style, {
      backgroundColor: unavailable ? colors.disabledBackground : variant === 'primary'
        ? pressed ? colors.accentPressed : colors.accent
        : pressed ? colors.accentSoft : variant === 'secondary' ? colors.background : 'transparent',
      borderColor: focused && !unavailable ? colors.focus : variant === 'secondary' ? colors.borderStrong : 'transparent',
      // A separate outline also distinguishes focus on the blue primary action.
    }, focused && !unavailable && styles.focused]}>
    {loading ? <ActivityIndicator color={foreground} accessible={false} />
      : icon ? <AppIcon name={icon} color={foreground} size={20} /> : null}
    <AppText variant="label" style={[{ color: foreground, textAlign: 'center', flexShrink: 1 }, textStyle]}>{title}</AppText>
  </Pressable>;
}

const styles = StyleSheet.create({
  button: { minHeight: layout.minimumTouchTarget, minWidth: layout.minimumTouchTarget,
    paddingHorizontal: spacing.md, paddingVertical: spacing.sm, borderRadius: radii.md,
    borderWidth: 2, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: spacing.xs },
  focused: { outlineColor: colors.text, outlineWidth: 2, outlineOffset: 2 },
});
