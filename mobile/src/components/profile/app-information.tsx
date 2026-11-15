// Accurate app/about/privacy content; no nonfunctional preference toggles.
import { AppCard } from '@/components/ui/app-card';
import { AppText } from '@/components/ui/app-text';
import { appVersion } from '@/lib/app-version';

export function AppInformation() {
  const version = appVersion();
  return <>
    <AppCard>
      <AppText variant="subtitle" accessibilityRole="header">About DrivePulse AI</AppText>
      <AppText variant="label">DrivePulse AI</AppText>
      <AppText tone="secondary">Manufacturer-independent vehicle intelligence, with saved vehicle management and clearly separated demonstration and recorded research tools.</AppText>
      <AppText>Installed app version: {version.installed ?? 'Unavailable in this build'}</AppText>
      {!version.installed && <AppText tone="secondary">App configuration version: {version.configured ?? 'Unavailable'}</AppText>}
      <AppText tone="secondary">Live OBD connectivity and new ML inference are not integrated.</AppText>
    </AppCard>
    <AppCard>
      <AppText variant="subtitle" accessibilityRole="header">Privacy information</AppText>
      <AppText tone="secondary">Firebase Authentication manages sign-in credentials, email verification, and session restoration.</AppText>
      <AppText tone="secondary">Your DrivePulse profile name, driving licence response, onboarding completion, and saved vehicles are stored through the authenticated backend in PostgreSQL.</AppText>
      <AppText tone="secondary">Avatar selections are local previews only. They are not uploaded or synced, and the app does not permanently store them.</AppText>
      <AppText tone="secondary">Demo AI Insights values are illustrative UI samples, not real ML predictions. They are not saved to analysis history or attached to your vehicles.</AppText>
      <AppText tone="secondary">Recorded research telemetry and its saved experimental results remain separate from your account vehicles and demo values.</AppText>
    </AppCard>
  </>;
}
