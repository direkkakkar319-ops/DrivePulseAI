// PostgreSQL profile response from the authenticated FastAPI /api/v1/users/me endpoint.
export interface UserProfile {
  firebase_uid: string;
  email: string;
  username: string | null;
  created_at: string;
  updated_at: string;
}
