// Public welcome screen uses decorative art without implying live monitoring.
import { Image, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Brand, Button, Copy, Page } from '@/components/vehicle-health/ui';
import { carArtwork } from '@/components/vehicle-health/cards';
export default function Welcome() {
  const router = useRouter();
  return (
    <Page>
      <View style={{ flex: 1, justifyContent: 'center', gap: 26, paddingTop: 48 }}>
        <Brand large />
        <Copy muted style={{ textAlign: 'center', fontSize: 17, lineHeight: 25 }}>
          Understand your vehicle. Explore clearer maintenance insights.
        </Copy>
        <Image
          source={carArtwork}
          style={{ width: '100%', aspectRatio: 1.35, borderRadius: 20 }}
          resizeMode="cover"
          accessible={false}
        />
        <Copy muted style={{ textAlign: 'center', fontSize: 12 }}>
          Vehicle-health prototype · demo readings
        </Copy>
        <Button
          title="Get started"
          onPress={() => router.push({ pathname: '/(auth)/login', params: { mode: 'signup' } })}
        />
        <Button title="Sign in" secondary onPress={() => router.push('/(auth)/login')} />
      </View>
    </Page>
  );
}
