// Accessible shared layout, fields, and buttons for account screens.
import { useState, type PropsWithChildren } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View, type TextInputProps } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { SymbolView } from 'expo-symbols';

export function AuthForm({ title, subtitle, children }: PropsWithChildren<{ title: string; subtitle: string }>) {
  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView style={styles.safeArea} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView contentContainerStyle={styles.form} keyboardShouldPersistTaps="handled">
          <Text style={styles.brand}>DrivePulseAI</Text>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.subtitle}>{subtitle}</Text>
          {children}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

export function AuthInput({ label, ...props }: TextInputProps & { label: string }) {
  return <><Text style={styles.label}>{label}</Text><TextInput {...props} accessibilityLabel={label} placeholderTextColor="#9aa5a0" style={styles.input} /></>;
}

export function AuthPasswordInput(props: Omit<TextInputProps, 'secureTextEntry'>) {
  const [visible, setVisible] = useState(false);
  return <>
    <Text style={styles.label}>Password</Text>
    <View style={styles.passwordBox}>
      <TextInput {...props} accessibilityLabel="Password" secureTextEntry={!visible}
        autoCapitalize="none" autoCorrect={false} spellCheck={false}
        style={[styles.input, styles.passwordInput]} />
      <Pressable accessibilityRole="button" accessibilityLabel={visible ? 'Hide password' : 'Show password'}
        disabled={props.editable === false} onPress={() => setVisible((value) => !value)} style={styles.eyeButton}>
        <SymbolView name={{ ios: visible ? 'eye.slash' : 'eye', android: visible ? 'visibility_off' : 'visibility', web: visible ? 'visibility_off' : 'visibility' }}
          size={24} tintColor="#a6f4c5" />
      </Pressable>
    </View>
  </>;
}

export function AuthButton({ title, onPress, disabled = false, loading = false, secondary = false }: {
  title: string; onPress: () => void; disabled?: boolean; loading?: boolean; secondary?: boolean;
}) {
  return (
    <Pressable accessibilityRole="button" accessibilityState={{ disabled: disabled || loading, busy: loading }} disabled={disabled || loading} onPress={onPress}
      style={({ pressed }) => [styles.button, secondary && styles.secondary, (disabled || loading || pressed) && styles.dimmed]}>
      {loading ? <ActivityIndicator accessibilityLabel="Working" color={secondary ? '#a6f4c5' : '#10251a'} /> : <Text style={[styles.buttonText, secondary && styles.secondaryText]}>{title}</Text>}
    </Pressable>
  );
}

export function AuthMessage({ message, error = false }: { message: string; error?: boolean }) {
  if (!message) return null;
  return <Text accessibilityRole={error ? 'alert' : undefined} accessibilityLiveRegion="polite" style={[styles.message, error && styles.error]}>{message}</Text>;
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#090d10' },
  form: { flexGrow: 1, justifyContent: 'center', padding: 24, width: '100%', maxWidth: 480, alignSelf: 'center' },
  brand: { color: '#a6f4c5', fontSize: 20, fontWeight: '700', marginBottom: 32 },
  title: { color: '#edf2f3', fontSize: 30, fontWeight: '600', marginBottom: 12 },
  subtitle: { color: '#abb9b2', lineHeight: 23, marginBottom: 24 },
  label: { color: '#edf2f3', marginBottom: 8 },
  input: { backgroundColor: '#17201c', borderColor: '#34473f', borderWidth: 1, color: '#fff', padding: 14, borderRadius: 8, marginBottom: 18, minHeight: 50 },
  passwordBox: { position: 'relative', marginBottom: 18 },
  passwordInput: { marginBottom: 0, paddingRight: 58 },
  eyeButton: { position: 'absolute', right: 1, top: 1, bottom: 1, width: 50, justifyContent: 'center', alignItems: 'center' },
  button: { backgroundColor: '#a6f4c5', padding: 15, borderRadius: 8, alignItems: 'center', justifyContent: 'center', minHeight: 50, marginTop: 12 },
  secondary: { backgroundColor: 'transparent', borderWidth: 1, borderColor: '#34473f' },
  buttonText: { color: '#10251a', fontWeight: '600', fontSize: 16 },
  secondaryText: { color: '#a6f4c5' },
  dimmed: { opacity: 0.6 },
  message: { color: '#a6f4c5', lineHeight: 22, marginVertical: 12 },
  error: { color: '#ffb4ab' },
});
