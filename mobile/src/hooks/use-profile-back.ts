// Back is an explicit user action; direct links return to the existing Profile tab.
import { useRouter } from 'expo-router';

export function useProfileBack() {
  const router = useRouter();
  return () => {
    if (router.canGoBack()) router.back();
    else router.replace('/(main)/(tabs)/account');
  };
}
