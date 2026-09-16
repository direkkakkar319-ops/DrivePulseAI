import { View, Text, StyleSheet, Button } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

export default function VehicleDetailScreen() {
  const { id } = useLocalSearchParams();
  const router = useRouter();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Digital Twin: {id}</Text>

      {/* Placeholder for Health Gauge and Chart */}
      <View style={styles.placeholderBox}>
        <Text style={styles.boxText}>Live Telemetry Stream</Text>
      </View>

      <Button
        title="View Maintenance Report"
        onPress={() => router.push(`/(main)/report/${id}`)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  title: { color: '#fff', fontSize: 24, fontWeight: 'bold', marginBottom: 20 },
  placeholderBox: { height: 200, backgroundColor: '#222', justifyContent: 'center', alignItems: 'center', borderRadius: 10, marginBottom: 20 },
  boxText: { color: '#666' }
});
