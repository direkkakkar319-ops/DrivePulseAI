// API profile contract; mirrored by backend/app/schemas/user.py and mobile/src/api/profile.types.ts.
export interface UserProfile {
  firebase_uid: string;
  email: string;
  username: string | null;
  created_at: string;
  updated_at: string;
}
