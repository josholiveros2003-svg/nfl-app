// Extends app.json. When the site is hosted at a sub-path (GitHub Pages serves
// it at https://<user>.github.io/<repo>/), the build sets EXPO_PUBLIC_BASE_URL
// to "/<repo>" so every link and data file is found at the right address.
module.exports = ({ config }) => ({
  ...config,
  experiments: {
    ...config.experiments,
    baseUrl: process.env.EXPO_PUBLIC_BASE_URL || undefined,
  },
});
