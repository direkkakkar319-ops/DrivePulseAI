import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

export default function HomeScreen() {
  const router = useRouter();
  
  // Dummy data
  const vehicles = [
    { id: 'SIM-001', score: 73 },
    { id: 'SIM-002', score: 92 }
  ];

  return (
    <View style={styles.container}>
      <FlatList
        data={vehicles}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <TouchableOpacity 
            style={styles.card}
            onPress={() => router.push(`/(main)/vehicle/${item.id}`)}
          >
            <Text style={styles.cardTitle}>{item.id}</Text>
            <Text style={styles.cardScore}>Health: {item.score}/100</Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20 },
  card: { backgroundColor: '#222', padding: 20, borderRadius: 10, marginBottom: 15 },
  cardTitle: { color: '#fff', fontSize: 18, fontWeight: 'bold' },
  cardScore: { color: '#aaa', marginTop: 5 }
});
