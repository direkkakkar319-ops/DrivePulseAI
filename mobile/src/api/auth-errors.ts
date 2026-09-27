// Translate Firebase errors without displaying tokens or SDK internals.
export function authErrorMessage(error: unknown): string {
  const code = (error as { code?: string } | null)?.code;
  switch (code) {
    case 'auth/invalid-email': return 'Enter a valid email address.';
    case 'auth/invalid-credential':
    case 'auth/invalid-login-credentials':
    case 'auth/wrong-password':
    case 'auth/user-not-found': return 'The email or password is incorrect.';
    case 'auth/email-already-in-use': return 'Unable to create this account. Try logging in or resetting your password.';
    case 'auth/weak-password':
    case 'auth/password-does-not-meet-requirements': return 'Choose a stronger password that meets the account requirements.';
    case 'auth/network-request-failed': return 'Could not connect. Check your internet connection and try again.';
    case 'auth/too-many-requests': return 'Too many attempts. Please wait before trying again.';
    case 'auth/user-disabled': return 'This account has been disabled.';
    case 'auth/user-token-expired':
    case 'auth/invalid-user-token': return 'Your session has expired. Please log out and sign in again.';
    case 'auth/operation-not-allowed': return 'Email/password login is not enabled yet. Please contact support.';
    default:
      // A bounded SDK error code helps diagnose device-only failures without
      // exposing the raw error message, email, password, or tokens.
      return typeof code === 'string' && /^auth\/[a-z-]{1,80}$/.test(code)
        ? `Authentication failed (${code}). Please try again.`
        : 'Something went wrong. Please try again.';
  }
}
