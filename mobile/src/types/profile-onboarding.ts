// Local profile draft contracts; these do not extend the backend or Firebase schema.
export type DrivingLicenceAnswer = 'yes' | 'no' | 'prefer-not-to-say';

export interface ProfileIdentity {
  uid: string;
  email: string | null;
  displayName: string | null;
}

export interface ProfilePhoto {
  uri: string;
  width: number;
  height: number;
  mimeType?: string;
}

export interface ProfileOnboardingDraft {
  fullName: string;
  photo: ProfilePhoto | null;
  drivingLicence: DrivingLicenceAnswer | null;
}

/** Phase 3.4 may persist this result after an explicit Continue action. */
export interface ProfileOnboardingResult extends Omit<ProfileOnboardingDraft, 'fullName'> {
  userId: string;
  fullName: string | null;
  displayName: string;
}

/** Null means the user cancelled, leaving any existing selection unchanged. */
export type PickProfilePhoto = () => Promise<ProfilePhoto | null>;

/** Safe failure categories; native SDK messages and local paths are never displayed. */
export class ProfilePhotoSelectionError extends Error {
  constructor(readonly reason: 'permission' | 'unavailable' | 'invalid-image') {
    super('Profile photo selection failed');
    this.name = 'ProfilePhotoSelectionError';
  }
}
