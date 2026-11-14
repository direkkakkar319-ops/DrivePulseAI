// Controlled or uncontrolled native fields with labels, error feedback, and password visibility.
import { forwardRef, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View, type StyleProp, type TextInputProps, type ViewStyle } from 'react-native';
import { colors, layout, radii, spacing, typography } from '@/theme/tokens';
import { AppText } from './app-text';
import { AppIcon } from './app-icon';

export interface AppTextFieldProps extends TextInputProps {
  label: string;
  hint?: string;
  error?: string;
  disabled?: boolean;
  password?: boolean;
  containerStyle?: StyleProp<ViewStyle>;
}

export const AppTextField = forwardRef<TextInput, AppTextFieldProps>(function AppTextField({
  label, hint, error, disabled = false, password = false, editable = true, secureTextEntry,
  containerStyle, style, onFocus, onBlur, accessibilityLabel, accessibilityHint, accessibilityState, ...props
}, ref) {
  const [focused, setFocused] = useState(false);
  const [visible, setVisible] = useState(false);
  const unavailable = disabled || !editable;
  const isPassword = password || secureTextEntry === true;
  const description = [accessibilityHint, error || hint].filter(Boolean).join('. ') || undefined;
  return <View style={[styles.container, containerStyle]}>
    <AppText variant="label">{label}</AppText>
    <View style={[styles.field, {
      backgroundColor: unavailable ? colors.disabledBackground : colors.background,
      borderColor: error ? colors.danger : focused && !unavailable ? colors.focus : colors.borderStrong,
    }]}>
      <TextInput {...props} ref={ref} accessibilityLabel={accessibilityLabel ?? label}
        accessibilityHint={description} accessibilityState={{ ...accessibilityState, disabled: unavailable }}
        editable={!unavailable} secureTextEntry={isPassword ? !visible : false}
        autoCapitalize={isPassword ? 'none' : props.autoCapitalize}
        autoCorrect={isPassword ? false : props.autoCorrect}
        spellCheck={isPassword ? false : props.spellCheck}
        placeholderTextColor={colors.textSecondary} selectionColor={colors.accent}
        onFocus={event => { setFocused(true); onFocus?.(event); }}
        onBlur={event => { setFocused(false); onBlur?.(event); }}
        style={[styles.input, style, unavailable && { color: colors.disabledText }]} />
      {isPassword && <PasswordToggle visible={visible} disabled={unavailable} label={label} onPress={() => setVisible(current => !current)} />}
    </View>
    {!!error && <AppText variant="caption" tone="error" accessibilityRole="alert" accessibilityLiveRegion="polite">{error}</AppText>}
    {!error && !!hint && <AppText variant="caption" tone="secondary">{hint}</AppText>}
  </View>;
});

function PasswordToggle({ visible, disabled, label, onPress }: { visible: boolean; disabled: boolean; label: string; onPress: () => void }) {
  const [focused, setFocused] = useState(false);
  return <Pressable accessibilityRole="button" accessibilityLabel={`${visible ? 'Hide' : 'Show'} ${label.toLowerCase()}`}
    accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
    onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
    style={({ pressed }) => [styles.toggle, { backgroundColor: pressed ? colors.accentSoft : 'transparent' },
      focused && !disabled && { outlineColor: colors.focus, outlineWidth: 2, outlineOffset: -3 }]}>
    <AppIcon name={visible ? 'eyeOff' : 'eye'} color={disabled ? colors.disabledText : colors.accent} />
  </Pressable>;
}

const styles = StyleSheet.create({
  container: { gap: spacing.xs },
  field: { minHeight: 52, borderWidth: 2, borderRadius: radii.md, flexDirection: 'row', alignItems: 'center' },
  input: { ...typography.body, color: colors.text, flex: 1, minWidth: 0, minHeight: layout.minimumTouchTarget,
    paddingHorizontal: spacing.sm, paddingVertical: spacing.sm },
  toggle: { minWidth: layout.minimumTouchTarget, minHeight: layout.minimumTouchTarget,
    alignItems: 'center', justifyContent: 'center', borderRadius: radii.sm },
});
