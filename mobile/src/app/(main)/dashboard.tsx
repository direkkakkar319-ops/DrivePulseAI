// Preserve the existing dashboard entry URL while routing into the Home tab.
import { Redirect } from 'expo-router';
export default function Dashboard() {
  return <Redirect href="/(main)/(tabs)/home" />;
}
