// Transient profile form state and normalization, with no account writes or completion flags.
import { useEffect, useRef, useState } from 'react';
import { ProfilePhotoSelectionError, type DrivingLicenceAnswer, type PickProfilePhoto, type ProfileIdentity, type ProfileOnboardingDraft, type ProfileOnboardingResult } from '@/types/profile-onboarding';

export function profileDisplayName(identity: ProfileIdentity, fullName: string) {
  return fullName.trim() || identity.email?.split('@')[0]?.trim() || identity.displayName?.trim() || 'Your profile';
}

export function profileInitials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return '?';
  return (words.length > 1
    ? `${Array.from(words[0])[0]}${Array.from(words[words.length - 1])[0]}`
    : Array.from(words[0]).slice(0, 2).join('')).toLocaleUpperCase();
}

export function profileResult(identity: ProfileIdentity, draft: ProfileOnboardingDraft): ProfileOnboardingResult {
  return { ...draft, fullName: draft.fullName.trim() || null, userId: identity.uid,
    displayName: profileDisplayName(identity, draft.fullName) };
}

export function useProfileOnboarding(identity: ProfileIdentity, pickPhoto?: PickProfilePhoto) {
  const [draft, setDraft] = useState<ProfileOnboardingDraft>(() => ({
    fullName: identity.displayName?.trim() ?? '', photo: null, drivingLicence: null,
  }));
  const [selectingPhoto, setSelectingPhoto] = useState(false);
  const [photoError, setPhotoError] = useState('');
  const request = useRef(0);
  const selecting = useRef(false);
  useEffect(() => () => { request.current++; }, []);

  async function selectPhoto() {
    if (!pickPhoto || selecting.current) return;
    const ticket = ++request.current;
    selecting.current = true;
    setSelectingPhoto(true);
    setPhotoError('');
    try {
      const photo = await pickPhoto();
      if (ticket === request.current && photo) setDraft(current => ({ ...current, photo }));
    } catch (error) {
      if (ticket === request.current) {
        setPhotoError(error instanceof ProfilePhotoSelectionError && error.reason === 'permission'
          ? 'Photo access was not allowed. You can change photo permissions in device settings or continue without a photo.'
          : error instanceof ProfilePhotoSelectionError && error.reason === 'unavailable'
            ? 'Photo selection is unavailable in this build. Update the app or continue without a photo.'
            : 'Could not select a photo. Try again or continue with your initials.');
      }
    } finally {
      if (ticket === request.current) { selecting.current = false; setSelectingPhoto(false); }
    }
  }

  const displayName = profileDisplayName(identity, draft.fullName);
  return {
    draft, displayName, initials: profileInitials(displayName), selectingPhoto, photoError,
    canSelectPhoto: Boolean(pickPhoto), selectPhoto,
    setFullName: (fullName: string) => setDraft(current => ({ ...current, fullName })),
    setDrivingLicence: (drivingLicence: DrivingLicenceAnswer) => setDraft(current => ({ ...current, drivingLicence })),
    removePhoto: () => { setPhotoError(''); setDraft(current => ({ ...current, photo: null })); },
    result: () => profileResult(identity, draft),
  };
}
