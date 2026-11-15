// Initials fallback and optional local photo preview; never uploads or stores an image.
import { useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';
import { AppText } from '@/components/ui/app-text';
import { profileInitials } from '@/hooks/use-profile-onboarding';
import type { ProfilePhoto } from '@/types/profile-onboarding';
import { colors, radii } from '@/theme/tokens';

function Initials({ name }: { name: string }) {
  const initials = profileInitials(name);
  return <View style={[styles.avatar, styles.initials]} accessible accessibilityRole="image" accessibilityLabel={`Profile initials ${initials}`}>
    <AppText variant="title" tone="accent">{initials}</AppText>
  </View>;
}
function Preview({ name, photo }: { name: string; photo: ProfilePhoto }) {
  const [failed, setFailed] = useState(false);
  return failed ? <Initials name={name} /> : <Image source={{ uri: photo.uri }} style={styles.avatar}
    accessibilityLabel="Local profile photo preview" onError={() => setFailed(true)} />;
}
export function ProfileAvatar({ name, photo }: { name: string; photo?: ProfilePhoto | null }) {
  return photo ? <Preview key={photo.uri} name={name} photo={photo} /> : <Initials name={name} />;
}
const styles = StyleSheet.create({
  avatar: { width: 88, height: 88, borderRadius: radii.pill },
  initials: { backgroundColor: colors.accentSoft, alignItems: 'center', justifyContent: 'center' },
});
