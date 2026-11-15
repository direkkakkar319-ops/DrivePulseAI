// Exercise the opt-in UI foundation without Firebase, providers, or application routes.
import { createRef } from 'react';
import { fireEvent, render, screen } from '@testing-library/react-native';
import { TextInput } from 'react-native';
import { AppButton } from '../src/components/ui/app-button';
import { AppCard } from '../src/components/ui/app-card';
import { AppDataState } from '../src/components/ui/app-data-state';
import { AppHeader } from '../src/components/ui/app-header';
import { AppIcon } from '../src/components/ui/app-icon';
import { AppScreen } from '../src/components/ui/app-screen';
import { AppStatus } from '../src/components/ui/app-status';
import { AppText } from '../src/components/ui/app-text';
import { AppTextField } from '../src/components/ui/app-text-field';
import { colors, statusColors } from '../src/theme/tokens';

it('runs actions, preserves their accessible names, and blocks disabled and loading presses', async () => {
  const onPress = jest.fn();
  const view = await render(<AppButton title="Save" onPress={onPress} />);
  await fireEvent.press(screen.getByRole('button', { name: 'Save' }));
  expect(onPress).toHaveBeenCalledTimes(1);
  await view.rerender(<AppButton title="Save" onPress={onPress} disabled />);
  expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
  await fireEvent.press(screen.getByRole('button', { name: 'Save' }));
  await view.rerender(<AppButton title="Save" onPress={onPress} loading />);
  expect(screen.getByRole('button', { name: 'Save' })).toHaveProp('accessibilityState', expect.objectContaining({ busy: true, disabled: true }));
  await fireEvent.press(screen.getByRole('button', { name: 'Save' }));
  expect(onPress).toHaveBeenCalledTimes(1);
  await view.rerender(<AppButton title="Save" onPress={onPress} />);
  await fireEvent.press(screen.getByRole('button', { name: 'Save' }));
  expect(onPress).toHaveBeenCalledTimes(2);
});

it('shows keyboard focus on buttons and forwards focus/blur handlers', async () => {
  const onFocus = jest.fn(), onBlur = jest.fn();
  await render(<AppButton title="Continue" variant="secondary" onFocus={onFocus} onBlur={onBlur} />);
  await fireEvent(screen.getByRole('button'), 'focus', { nativeEvent: {} });
  expect(screen.getByRole('button')).toHaveStyle({ outlineWidth: 2, outlineColor: colors.text });
  expect(onFocus).toHaveBeenCalledTimes(1);
  await fireEvent(screen.getByRole('button'), 'blur', { nativeEvent: {} });
  expect(screen.getByRole('button')).not.toHaveStyle({ outlineWidth: 2 });
  expect(onBlur).toHaveBeenCalledTimes(1);
});

it('forwards field changes, focus callbacks, refs, and native keyboard props', async () => {
  const onChangeText = jest.fn(), onFocus = jest.fn(), onBlur = jest.fn();
  const ref = createRef<TextInput>();
  await render(<AppTextField ref={ref} label="Email" value="" hint="Use your account email" keyboardType="email-address"
    onChangeText={onChangeText} onFocus={onFocus} onBlur={onBlur} />);
  const input = screen.getByLabelText('Email');
  expect(input).toHaveProp('keyboardType', 'email-address');
  expect(input).toHaveProp('accessibilityHint', 'Use your account email');
  expect(ref.current?.focus).toEqual(expect.any(Function));
  await fireEvent.changeText(input, 'driver@example.com');
  expect(onChangeText).toHaveBeenCalledWith('driver@example.com');
  await fireEvent(input, 'focus', { nativeEvent: {} });
  expect(input.parent).toHaveStyle({ borderColor: colors.focus });
  expect(onFocus).toHaveBeenCalledTimes(1);
  await fireEvent(input, 'blur', { nativeEvent: {} });
  expect(input.parent).toHaveStyle({ borderColor: colors.borderStrong });
  expect(onBlur).toHaveBeenCalledTimes(1);
});

it('announces field errors and keeps the error boundary visible while focused', async () => {
  await render(<AppTextField label="Email" hint="Account email" error="Enter a valid email" accessibilityHint="Required" />);
  expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid email');
  expect(screen.queryByText('Account email')).toBeNull();
  const input = screen.getByLabelText('Email');
  expect(input).toHaveProp('accessibilityHint', 'Required. Enter a valid email');
  await fireEvent(input, 'focus', { nativeEvent: {} });
  expect(input.parent).toHaveStyle({ borderColor: colors.danger });
});

it('toggles password visibility without replacing the field value', async () => {
  await render(<AppTextField label="Password" value="a private value" password />);
  expect(screen.getByLabelText('Password')).toHaveProp('secureTextEntry', true);
  await fireEvent.press(screen.getByRole('button', { name: 'Show password' }));
  expect(screen.getByLabelText('Password')).toHaveProp('secureTextEntry', false);
  expect(screen.getByLabelText('Password')).toHaveProp('value', 'a private value');
  await fireEvent.press(screen.getByRole('button', { name: 'Hide password' }));
  expect(screen.getByLabelText('Password')).toHaveProp('secureTextEntry', true);
});

it.each([{ disabled: true }, { editable: false }])('disables editing and password visibility controls: %o', async props => {
  const onChangeText = jest.fn();
  await render(<AppTextField label="Password" value="retained" password onChangeText={onChangeText} {...props} />);
  expect(screen.getByLabelText('Password')).toHaveProp('editable', false);
  expect(screen.getByLabelText('Password')).toHaveProp('accessibilityState', expect.objectContaining({ disabled: true }));
  await fireEvent.changeText(screen.getByLabelText('Password'), 'replacement');
  await fireEvent.press(screen.getByRole('button', { name: 'Show password' }));
  expect(onChangeText).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Password')).toHaveProp('secureTextEntry', true);
});

it('keeps nested card actions individually accessible', async () => {
  const onPress = jest.fn();
  await render(<AppCard variant="raised"><AppText>Recording</AppText><AppButton title="Open" onPress={onPress} /></AppCard>);
  await fireEvent.press(screen.getByRole('button', { name: 'Open' }));
  expect(onPress).toHaveBeenCalledTimes(1);
});

it('keeps decorative icons out of the accessible tree and names standalone icons', async () => {
  await render(<><AppIcon name="car" /><AppIcon name="info" accessibilityLabel="Recording information" /></>);
  expect(screen.getAllByRole('image')).toHaveLength(1);
  expect(screen.getByRole('image', { name: 'Recording information' })).toBeTruthy();
});

it('uses caller-supplied header actions without requiring a router', async () => {
  const onBack = jest.fn(), onProfile = jest.fn();
  await render(<AppHeader title="Garage" subtitle="Your vehicles" onBack={onBack}
    trailing={<AppButton title="Profile" variant="text" onPress={onProfile} />} />);
  expect(screen.getByRole('header')).toHaveTextContent('Garage');
  await fireEvent.press(screen.getByRole('button', { name: 'Back' }));
  await fireEvent.press(screen.getByRole('button', { name: 'Profile' }));
  expect(onBack).toHaveBeenCalledTimes(1);
  expect(onProfile).toHaveBeenCalledTimes(1);
});

it('renders readable status text and announces error notices', async () => {
  await render(<AppStatus label="Request failed" tone="error" variant="notice" description="Please retry" icon="warning" />);
  expect(screen.getByRole('alert')).toHaveTextContent('Request failed');
  expect(screen.getByText('Please retry')).toBeTruthy();
});

it('shows loading, empty, and error feedback and supports recoverable retry', async () => {
  const onRetry = jest.fn();
  const view = await render(<AppDataState status="loading" title="Loading recordings" onRetry={onRetry} />);
  expect(screen.getByLabelText('Loading recordings')).toBeTruthy();
  expect(screen.queryByRole('button')).toBeNull();
  await view.rerender(<AppDataState status="empty" message="Choose a recording" />);
  expect(screen.getByText('Nothing here yet')).toBeTruthy();
  expect(screen.getByText('Choose a recording')).toBeTruthy();
  await view.rerender(<AppDataState status="error" onRetry={onRetry} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Unable to load');
  await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
  expect(onRetry).toHaveBeenCalledTimes(1);
  await view.rerender(<AppDataState status="error" onRetry={onRetry} retrying />);
  await fireEvent.press(screen.getByRole('button', { name: 'Try again' }));
  expect(onRetry).toHaveBeenCalledTimes(1);
});

it('supports scrolling and fixed page shells without mounting app navigation', async () => {
  const view = await render(<AppScreen testID="page" background="secondary" scrollViewProps={{ testID: 'scroll-content' }}><AppText>Content</AppText></AppScreen>);
  expect(screen.getByTestId('page')).toHaveStyle({ backgroundColor: colors.backgroundSecondary });
  expect(screen.getByTestId('scroll-content')).toHaveProp('keyboardShouldPersistTaps', 'handled');
  await view.rerender(<AppScreen scroll={false} keyboardAvoiding><AppText>Fixed content</AppText></AppScreen>);
  expect(screen.queryByTestId('scroll-content')).toBeNull();
  expect(screen.getByText('Fixed content')).toBeTruthy();
});

it('preserves native text scaling and caller accessibility props', async () => {
  await render(<AppText variant="title" tone="secondary" accessibilityRole="header">Battery overview</AppText>);
  expect(screen.getByRole('header')).toHaveStyle({ color: colors.textSecondary, fontSize: 24 });
  expect(screen.getByRole('header').props.allowFontScaling).not.toBe(false);
});

// Contrast guards cover actual default foreground/surface pairs, not snapshots.
function luminance(hex: string) {
  const linear = [1, 3, 5].map(offset => {
    const value = parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}

const contrastPairs: [string, string][] = [
  [colors.text, colors.background], [colors.textSecondary, colors.backgroundSecondary],
  [colors.onAccent, colors.accent], [colors.onAccent, colors.accentPressed],
  [colors.accent, colors.accentSoft],
  ...Object.values(statusColors).map((pair): [string, string] => [pair.foreground, pair.background]),
];
it.each(contrastPairs)('maintains normal-text contrast between %s and %s', (foreground, background) => {
  const a = luminance(foreground), b = luminance(background);
  expect((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)).toBeGreaterThanOrEqual(4.5);
});
