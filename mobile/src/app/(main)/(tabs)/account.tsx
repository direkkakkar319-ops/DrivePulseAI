// Profile tab shares existing auth/account state; session actions live in Settings.
export { ProfileScreen as default } from '@/components/profile/profile-screen';
// Preserve the existing exported action surface for embedded consumers and regression tests.
export { AccountSessionActions as AccountDetails } from '@/components/profile/account-session-actions';
