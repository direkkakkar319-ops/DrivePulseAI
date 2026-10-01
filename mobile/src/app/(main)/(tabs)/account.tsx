// Real Firebase account and profile-sync status alongside explicitly labelled demo controls.
import { useState } from 'react';
import { View } from 'react-native';
import { useAuthStore } from '@/store/authStore';
import { useProfileSync } from '@/hooks/use-profile-sync';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';
import { UsernameSaveNotice } from '@/components/username-save-notice';
import { AuthMessage, AuthButton } from '@/components/auth-form';
import { Avatar, Badge, Card, Copy, Page, styles } from '@/components/vehicle-health/ui';
import { DemoControls } from '@/components/vehicle-health/data-state';
export function AccountDetails() {
  const { user } = useAuthStore();
  const sync = useProfileSync();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function logout() {
    setBusy(true);
    setError('');
    try {
      await authService.signOut();
    } catch (e) {
      setError(authErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Card>
        <View style={styles.row}>
          <Avatar name={user?.displayName || 'Driver'} />
          <View style={{ flex: 1 }}>
            <Copy style={{ fontSize: 19, fontWeight: '600' }}>
              {user?.displayName || 'Your account'}
            </Copy>
            <Copy muted>{user?.email ?? 'Email unavailable'}</Copy>
          </View>
        </View>
        <Badge label={user?.emailVerified ? 'EMAIL VERIFIED' : 'VERIFICATION PENDING'} />
        <Copy muted>Account information from Firebase</Copy>
      </Card>
      <UsernameSaveNotice />
      <Card>
        <Copy style={{ fontWeight: '600' }}>Account synchronization</Copy>
        <AuthMessage message={sync.message} error={sync.failed} />
        {sync.failed && <AuthButton title="Retry account sync" secondary onPress={sync.retry} />}
      </Card>
      <AuthMessage message={error} error />
      <AuthButton title="Log out" onPress={logout} loading={busy} />
    </>
  );
}
export default function Account() {
  return (
    <Page title="Account">
      <AccountDetails />
      <DemoControls />
      <Copy muted>DrivePulse AI · Vehicle-health prototype</Copy>
    </Page>
  );
}
