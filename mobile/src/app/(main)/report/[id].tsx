import { View, Text, StyleSheet } from 'react-native';
import { useLocalSearchParams } from 'expo-router';

export default function ReportScreen() {
  const { id } = useLocalSearchParams();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>AI Report: {id}</Text>

      <View style={styles.card}>
        <Text style={styles.cardText}>
          No recent anomalies detected. Battery voltage and Engine RPM are within normal operational baseline.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  title: { color: '#fff', fontSize: 24, fontWeight: 'bold', marginBottom: 20 },
  card: { backgroundColor: '#222', padding: 20, borderRadius: 10 },
  cardText: { color: '#ddd', lineHeight: 24 }
});
