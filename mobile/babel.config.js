// Share Expo's TypeScript and native syntax transforms between Metro and Jest.
module.exports = function (api) {
  api.cache(true);
  return { presets: ['babel-preset-expo'] };
};
