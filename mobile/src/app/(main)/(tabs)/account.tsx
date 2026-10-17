// Preserve Firebase account operations in the recorded-data account presentation.
import { useState } from 'react';
import { Text, View } from 'react-native';
import { useAuthStore } from '@/store/authStore';
import { useProfileSync } from '@/hooks/use-profile-sync';
import { authService } from '@/api/auth';
import { authErrorMessage } from '@/api/auth-errors';
import { UsernameSaveNotice } from '@/components/username-save-notice';
import { Button, Copy, Page, Panel, SectionHeader, StatusPill } from '@/components/recorded/ui';
import { colors, spacing, type } from '@/components/recorded/theme';
export function AccountDetails() {
  const { user, usernameSavePending } = useAuthStore();
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
      <Panel>
        <View style={{ gap: spacing.xxs }}>
          <Copy muted style={type.caption}>SIGNED IN AS</Copy>
          <Copy style={{ fontSize: 22, lineHeight: 29, fontWeight: '600' }}>{user?.displayName || 'Your account'}</Copy>
          <Copy muted>{user?.email ?? 'Email unavailable'}</Copy>
        </View>
        <StatusPill label={user?.emailVerified ? 'Email verified' : 'Verification pending'} unusual={!user?.emailVerified} />
        <Copy muted>Account information from Firebase</Copy>
      </Panel>
      {usernameSavePending && <View style={{ backgroundColor: colors.surface, padding: spacing.md, borderRadius: 10 }}><UsernameSaveNotice /></View>}
      <Panel>
        <SectionHeader title="Account synchronization" />
        <Copy muted>{sync.message}</Copy>
        {sync.failed && <Button title="Retry account sync" secondary onPress={sync.retry} />}
      </Panel>
      {!!error && <Text accessibilityRole="alert" accessibilityLiveRegion="polite" style={{ color: colors.danger, ...type.body }}>{error}</Text>}
      <Button title={busy ? 'Logging out…' : 'Log out'} onPress={logout} disabled={busy} />
    </>
  );
}
export default function Account() {
  return (
    <Page title="Account" back accountAction={false}>
      <Copy muted>Manage the Firebase account used to access this recorded telemetry prototype.</Copy>
      <AccountDetails />
      <Copy muted style={type.caption}>DrivePulse AI · Recorded battery telemetry prototype</Copy>
    </Page>
  );
}
