// Shared confirmed-success and error notices for account actions.
import { AppStatus } from '@/components/ui/app-status';

export function ActionFeedback({ error, message }: { error: string; message: string }) {
  return <>
    {!!error && <AppStatus label={error} tone="error" variant="notice" />}
    {!!message && <AppStatus label={message} tone="success" variant="notice" />}
  </>;
}
