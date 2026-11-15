// Native modal providers need deterministic metrics because Jest cannot measure native safe areas.
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);
