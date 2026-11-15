// A distinct Home request opens demo mode without effects or repeated navigation updates.
import { useLocalSearchParams } from 'expo-router';
import { AIInsightsScreen } from '@/components/insights/ai-insights-screen';

export default function InsightsRoute() {
  const { demo } = useLocalSearchParams<{ demo?: string }>();
  const request = typeof demo === 'string' && demo ? demo : undefined;
  return <AIInsightsScreen key={request ?? 'manual'} initialDemo={Boolean(request)} />;
}
