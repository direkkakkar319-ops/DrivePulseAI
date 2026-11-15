// Name editing and screen-local optional photos; only the name is sent to the existing account API.
import { useState } from 'react';
import { AppButton } from '@/components/ui/app-button';
import { AppCard } from '@/components/ui/app-card';
import { AppText } from '@/components/ui/app-text';
import { AppTextField } from '@/components/ui/app-text-field';
import { useProfileOnboarding } from '@/hooks/use-profile-onboarding';
import { useAccountAction } from '@/hooks/use-account-action';
import type { ProfileIdentity, PickProfilePhoto } from '@/types/profile-onboarding';
import { ActionFeedback } from './action-feedback';
import { ProfileAvatar } from './profile-avatar';

export function EditProfileForm({ identity, onSave, onCancel, pickPhoto }: {
  identity: ProfileIdentity;
  onSave: (name: string) => Promise<void>;
  onCancel: () => void;
  pickPhoto?: PickProfilePhoto;
}) {
  const form = useProfileOnboarding(identity, pickPhoto);
  const action = useAccountAction(error => error instanceof Error ? error.message : 'Could not save your name. Please try again.');
  const [nameError, setNameError] = useState('');
  const busy = action.busy || form.selectingPhoto;
  function save() {
    if (busy) return;
    const name = form.draft.fullName.trim();
    if (!name || name.length > 120) { setNameError('Enter a name between 1 and 120 characters.'); action.clear(); return; }
    setNameError('');
    void action.run(async () => { await onSave(name); return 'Profile name saved.'; });
  }
  return <>
    <AppTextField label="Full name" value={form.draft.fullName} autoCapitalize="words" maxLength={120}
      disabled={busy} error={nameError} hint="Your name in DrivePulse AI." returnKeyType="done" onSubmitEditing={save}
      onChangeText={name => { form.setFullName(name); setNameError(''); action.clear(); }} />
    <AppCard>
      <ProfileAvatar name={form.displayName} photo={form.draft.photo} />
      <AppText variant="subtitle">Profile photo preview</AppText>
      <AppText tone="secondary">Photo previews are local to this screen and disappear when you leave. They are not uploaded, synced, or permanently stored.</AppText>
      <AppButton title={form.draft.photo ? 'Replace photo' : 'Choose photo'} variant="secondary" disabled={action.busy || !form.canSelectPhoto}
        loading={form.selectingPhoto} onPress={() => { void form.selectPhoto(); }} />
      {form.draft.photo && <AppButton title="Remove photo" variant="text" disabled={busy} onPress={form.removePhoto} />}
      <ActionFeedback error={form.photoError} message="" />
    </AppCard>
    <ActionFeedback error={action.error} message={action.message} />
    <AppButton title="Save changes" loading={action.busy} disabled={form.selectingPhoto} onPress={save} />
    <AppButton title="Cancel" variant="text" disabled={busy} onPress={onCancel} />
  </>;
}
