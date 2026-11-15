// Check the actual tab declarations, Expo's tab back handling, and the honest History placeholder.
import { Children, type ReactElement, type ReactNode } from 'react';
import { StyleSheet, type ColorValue } from 'react-native';
import { render, screen } from '@testing-library/react-native';
import { TabRouter, TabActions, type BackBehavior } from 'expo-router/build/react-navigation/routers/TabRouter';
import type { BottomTabNavigationOptions } from 'expo-router/build/react-navigation/bottom-tabs/types';
import ProductTabs from '../src/app/(main)/(tabs)/_layout';
import HistoryScreen from '../src/app/(main)/(tabs)/history';
import { colors } from '../src/theme/tokens';

// Only replace the native navigator boundary; options and icon rendering come from the real layout.
jest.mock('expo-router', () => {
  const Tabs = ({ children }: { children: ReactNode }) => children;
  Tabs.Screen = () => null;
  return { Tabs, useRouter: () => ({ navigate: jest.fn() }) };
});

const destinations = [
  ['home', 'Home'], ['vehicles', 'Garage'], ['insights', 'AI Insights'],
  ['history', 'History'], ['account', 'Profile'],
] as const;

function configuration() {
  const element = ProductTabs() as ReactElement<{
    children: ReactNode; initialRouteName: string; backBehavior: BackBehavior;
    screenOptions: BottomTabNavigationOptions; safeAreaInsets?: object;
  }>;
  const screens = Children.toArray(element.props.children) as ReactElement<{
    name: string;
    options: { title?: string; href?: null; tabBarIcon?: (props: { color: ColorValue; focused: boolean; size: number }) => ReactNode };
  }>[];
  return { ...element.props, screens };
}

it('exposes exactly the five named destinations in order and keeps Telemetry routable but hidden', () => {
  const { screens } = configuration();
  expect(screens.filter(item => item.props.options.href !== null).map(item => [item.props.name, item.props.options.title]))
    .toEqual(destinations);
  expect(screens.find(item => item.props.name === 'telemetry')?.props.options.href).toBeNull();
});

it.each(destinations)('can navigate to %s and returns to Home on Android Back', (name) => {
  const { initialRouteName, backBehavior, screens } = configuration();
  const router = TabRouter({ initialRouteName, backBehavior });
  const options = { routeNames: screens.map(item => item.props.name), routeParamList: {}, routeGetIdList: {} };
  const initial = router.getInitialState(options);
  const next = router.getRehydratedState(router.getStateForAction(initial, TabActions.jumpTo(name), options)!, options);
  expect(next.routes[next.index].name).toBe(name);
  const back = router.getStateForAction(next, { type: 'GO_BACK' }, options);
  if (name === 'home') expect(back).toBeNull(); // Allow the parent stack/OS to handle Back.
  else {
    expect(back).not.toBeNull();
    const restored = router.getRehydratedState(back!, options);
    expect(restored.routes[restored.index].name).toBe('home');
  }
});

it('keeps the hidden Telemetry route navigable with the same Home back destination', () => {
  const { initialRouteName, backBehavior, screens } = configuration();
  const router = TabRouter({ initialRouteName, backBehavior });
  const options = { routeNames: screens.map(item => item.props.name), routeParamList: {}, routeGetIdList: {} };
  const next = router.getRehydratedState(router.getStateForAction(router.getInitialState(options), TabActions.jumpTo('telemetry'), options)!, options);
  expect(next.routes[next.index].name).toBe('telemetry');
  const back = router.getRehydratedState(router.getStateForAction(next, { type: 'GO_BACK' }, options)!, options);
  expect(back.routes[back.index].name).toBe('home');
});

it.each(destinations)('renders a consistent decorative icon for %s with a blue focus indicator', async name => {
  const { screens, screenOptions } = configuration();
  const icon = screens.find(item => item.props.name === name)!.props.options.tabBarIcon!;
  const focused = await render(<>{icon({ focused: true, color: screenOptions.tabBarActiveTintColor!, size: 24 })}</>);
  expect(screen.root).toHaveStyle({ borderTopColor: colors.accent });
  expect(screen.queryAllByRole('image')).toHaveLength(0); // Tab labels provide the accessible names.
  await focused.rerender(<>{icon({ focused: false, color: screenOptions.tabBarInactiveTintColor!, size: 24 })}</>);
  expect(screen.root).toHaveStyle({ borderTopColor: 'transparent' });
});

it('lets the navigator manage safe-area height and keeps touch targets and scalable labels', () => {
  const { screenOptions, safeAreaInsets } = configuration();
  expect(safeAreaInsets).toBeUndefined();
  expect(StyleSheet.flatten(screenOptions.tabBarStyle)).toMatchObject({ backgroundColor: colors.background, borderTopColor: colors.border });
  expect(StyleSheet.flatten(screenOptions.tabBarStyle)).not.toHaveProperty('height');
  expect(StyleSheet.flatten(screenOptions.tabBarItemStyle)?.minHeight).toBeGreaterThanOrEqual(48);
  expect(screenOptions.tabBarAllowFontScaling).toBe(true);
  expect(screenOptions.headerShown).toBe(false);
});

it('explains empty history with an explicit Insights action and no fabricated records', async () => {
  await render(<HistoryScreen />);
  expect(screen.getByRole('header')).toHaveTextContent('History');
  expect(screen.getByText('Your completed vehicle analyses will appear here once real analysis is available.')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Explore AI Insights' })).toBeTruthy();
  expect(screen.queryAllByTestId(/^history-record-/)).toHaveLength(0);
  expect(screen.queryByText(/Trip|Nissan|score/i)).toBeNull();
});
