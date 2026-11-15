// Existing recorded-tool account destination shares Profile and retains explicit Back navigation.
import { ProfileScreen } from '@/components/profile/profile-screen';
import { useProfileBack } from '@/hooks/use-profile-back';

export default function AccountRoute() {
  const back = useProfileBack();
  return <ProfileScreen onBack={back} />;
}
