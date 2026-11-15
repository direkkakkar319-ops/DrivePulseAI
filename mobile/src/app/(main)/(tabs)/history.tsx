// No history endpoint exists yet; render the honest empty state without synthetic requests.
import { useRouter } from 'expo-router';
import { HistoryScreen } from '@/components/history/history-screen';

export default function HistoryRoute() {
  const router = useRouter();
  return <HistoryScreen onExploreInsights={() => router.navigate('/(main)/(tabs)/insights')} />;
}
