// Controlled profile-setup presentation; account services and navigation stay in the route.
import { useState } from 'react';
import { Image, Pressable, StyleSheet, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import type { DrivingLicenceAnswer, ProfileOnboardingDraft } from '@/types/profile-onboarding';
import { colors, layout, radii, spacing } from '@/theme/tokens';
import { AppBrand } from './app-brand';
import { AppButton } from './ui/app-button';
import { AppCard } from './ui/app-card';
import { AppScreen } from './ui/app-screen';
import { AppStatus } from './ui/app-status';
import { AppText } from './ui/app-text';
import { AppTextField } from './ui/app-text-field';

export interface ProfileOnboardingProps {
  draft: ProfileOnboardingDraft;
  displayName: string;
  initials: string;
  selectingPhoto: boolean;
  photoError: string;
  canSelectPhoto: boolean;
  setFullName: (name: string) => void;
  setDrivingLicence: (answer: DrivingLicenceAnswer) => void;
  selectPhoto: () => void | Promise<void>;
  removePhoto: () => void;
  onContinue: () => void;
  onSkip: () => void;
}

const licenceChoices: { value: DrivingLicenceAnswer; label: string }[] = [
  { value: 'yes', label: 'Yes' },
  { value: 'no', label: 'No' },
  { value: 'prefer-not-to-say', label: 'Prefer not to say' },
];

export function ProfileOnboardingForm({ draft, displayName, initials, selectingPhoto, photoError, canSelectPhoto,
  setFullName, setDrivingLicence, selectPhoto, removePhoto, onContinue, onSkip }: ProfileOnboardingProps) {
  return <AppScreen keyboardAvoiding contentContainerStyle={styles.page}>
    <StatusBar style="dark" />
    <AppBrand />
    <View style={styles.section}>
      <AppText variant="display" accessibilityRole="header">A little about you</AppText>
      <AppText tone="secondary">Make DrivePulse AI feel more personal. Every detail here is optional.</AppText>
    </View>
    <AppCard style={styles.avatarCard}>
      {draft.photo
        ? <Image source={{ uri: draft.photo.uri }} style={styles.avatar} accessibilityLabel="Selected profile photo" onError={removePhoto} />
        : <View style={[styles.avatar, styles.initials]} accessible accessibilityLabel={`Profile initials: ${initials}`}>
            <AppText variant="metric" tone="accent">{initials}</AppText>
          </View>}
      <AppText variant="subtitle" accessibilityLabel={`Display name: ${displayName}`}>{displayName}</AppText>
      <AppButton title={draft.photo ? 'Change photo' : 'Choose photo'} variant="secondary" loading={selectingPhoto}
        disabled={!canSelectPhoto} onPress={selectPhoto} />
      {draft.photo && <AppButton title="Remove photo" variant="text" disabled={selectingPhoto} onPress={removePhoto} />}
      {!canSelectPhoto && <AppText variant="caption" tone="secondary">Photo selection is unavailable in this build. You can use your initials.</AppText>}
      <AppText variant="caption" tone="secondary">Profile photo · Optional</AppText>
    </AppCard>
    {!!photoError && <AppStatus label={photoError} tone="error" variant="notice" />}
    <AppTextField label="Full name" value={draft.fullName} onChangeText={setFullName}
      autoComplete="name" autoCapitalize="words" maxLength={120}
      hint="Optional. Leave blank to use the name before @ in your email." />
    <View style={styles.section}>
      <AppText variant="subtitle">Do you have a driving licence?</AppText>
      <AppText tone="secondary">Optional. Your answer does not affect access to the app.</AppText>
      <View accessibilityRole="radiogroup" accessibilityLabel="Do you have a driving licence?" style={styles.choices}>
        {licenceChoices.map(choice => <LicenceChoice key={choice.value} label={choice.label}
          selected={draft.drivingLicence === choice.value} onPress={() => setDrivingLicence(choice.value)} />)}
      </View>
    </View>
    <AppText variant="caption" tone="secondary">These details are only kept while this screen is open. They are not saved to your account yet.</AppText>
    <View style={styles.section}>
      <AppButton title="Continue" disabled={selectingPhoto} onPress={onContinue} />
      <AppButton title="Skip for now" variant="text" disabled={selectingPhoto} onPress={onSkip} />
    </View>
  </AppScreen>;
}

function LicenceChoice({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  const [focused, setFocused] = useState(false);
  return <Pressable accessibilityRole="radio" accessibilityLabel={label} accessibilityState={{ checked: selected }}
    onPress={onPress} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
    style={({ pressed }) => [styles.choice, {
      backgroundColor: selected || pressed ? colors.accentSoft : colors.background,
      borderColor: selected ? colors.accent : colors.borderStrong,
    }, focused && { outlineWidth: 2, outlineOffset: 2, outlineColor: colors.focus }]}>
    <View style={[styles.radio, selected && { borderColor: colors.accent }]}>
      {selected && <View style={styles.radioDot} />}
    </View>
    <AppText style={styles.choiceLabel}>{label}</AppText>
  </Pressable>;
}

const styles = StyleSheet.create({
  page: { maxWidth: 480, padding: spacing.xl, paddingTop: spacing.xxl, gap: spacing.xl },
  section: { gap: spacing.sm },
  avatarCard: { alignItems: 'center' },
  avatar: { width: 88, height: 88, borderRadius: radii.pill },
  initials: { alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accentSoft },
  choices: { gap: spacing.sm },
  choice: { minHeight: layout.minimumTouchTarget, borderWidth: 1, borderRadius: radii.md,
    flexDirection: 'row', alignItems: 'center', gap: spacing.sm, padding: spacing.sm },
  choiceLabel: { flex: 1 },
  radio: { width: 22, height: 22, borderRadius: radii.pill, borderWidth: 2, borderColor: colors.borderStrong,
    alignItems: 'center', justifyContent: 'center' },
  radioDot: { width: 10, height: 10, borderRadius: radii.pill, backgroundColor: colors.accent },
});
