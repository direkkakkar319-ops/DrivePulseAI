// Honest placeholder until saved analysis history has a persistent implementation.
import { AppDataState } from '@/components/ui/app-data-state';
import { AppHeader } from '@/components/ui/app-header';
import { AppScreen } from '@/components/ui/app-screen';

export default function HistoryScreen() {
  return <AppScreen edges={['top', 'left', 'right']}>
    <AppHeader title="History" />
    <AppDataState status="empty" title="Saved analysis history"
      message="Saved analysis history will be implemented in a future update." />
  </AppScreen>;
}
