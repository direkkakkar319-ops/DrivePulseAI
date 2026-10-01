// Run mobile authentication tests with Expo's native-module mocks.
module.exports = {
  preset: 'jest-expo/android',
  testMatch: ['<rootDir>/tests/**/*.test.ts?(x)'],
  moduleNameMapper: {
    '^@/assets/(.*)$': '<rootDir>/assets/$1',
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  clearMocks: true,
};
