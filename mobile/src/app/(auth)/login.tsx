import { View, Text, TextInput, TouchableOpacity, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

export default function LoginScreen() {
  const router = useRouter();

  const handleManualLogin = () => {
    // TODO: Implement manual login via API
    router.replace('/(main)');
  };

  const handleGoogleLogin = () => {
    // TODO: Implement Google OAuth login
    router.replace('/(main)');
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>DrivePulseAI</Text>
      
      <TextInput 
        style={styles.input} 
        placeholder="Email or Username" 
        placeholderTextColor="#888" 
      />
      <TextInput 
        style={styles.input} 
        placeholder="Password" 
        placeholderTextColor="#888" 
        secureTextEntry 
      />
      
      <TouchableOpacity style={styles.button} onPress={handleManualLogin}>
        <Text style={styles.buttonText}>Log In</Text>
      </TouchableOpacity>

      <View style={styles.divider} />

      <TouchableOpacity style={[styles.button, styles.googleButton]} onPress={handleGoogleLogin}>
        <Text style={styles.googleButtonText}>Continue with Google</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 20, backgroundColor: '#111' },
  title: { fontSize: 32, fontWeight: 'bold', color: '#fff', textAlign: 'center', marginBottom: 40 },
  input: { backgroundColor: '#222', color: '#fff', padding: 15, borderRadius: 8, marginBottom: 15 },
  button: { backgroundColor: '#007AFF', padding: 15, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: 'bold', fontSize: 16 },
  divider: { height: 1, backgroundColor: '#333', marginVertical: 20 },
  googleButton: { backgroundColor: '#fff' },
  googleButtonText: { color: '#000', fontWeight: 'bold', fontSize: 16 },
});
