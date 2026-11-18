// A distinct Home request opens demo mode without effects or repeated navigation updates.
import { useLocalSearchParams } from 'expo-router';
import { AIInsightsScreen } from '@/components/insights/ai-insights-screen';
import { useAuthStore } from '@/store/authStore';
import { useAnalysis } from '@/hooks/use-analysis';
import { pickKitCsv } from '@/lib/csv-picker';

export default function InsightsRoute() {
  const { demo } = useLocalSearchParams<{ demo?: string }>();
  const request = typeof demo === 'string' && demo ? demo : undefined;
  const { user } = useAuthStore();
  return <SessionInsights key={`${user?.uid ?? 'signed-out'}:${request ?? 'manual'}`} uid={user?.emailVerified ? user.uid : null} initialDemo={Boolean(request)} />;
}

function SessionInsights({ uid, initialDemo }: { uid: string | null; initialDemo: boolean }) {
  const analysis = useAnalysis(uid, initialDemo, pickKitCsv);
  return <AIInsightsScreen analysis={analysis} />;
}
