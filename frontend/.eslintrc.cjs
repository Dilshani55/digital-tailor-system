// ESLint for the React app (run: npm run lint). Rules: the recommended sets for JavaScript, React and hooks.
module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', 'node_modules', 'test-results', 'playwright-report', 'public'],
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: { jsx: true } },
  settings: { react: { version: '18.2' } },
  rules: {
    // components are plain JavaScript without PropTypes; props are checked by the tests instead
    'react/prop-types': 'off',
    // names starting with "_" are deliberately unused (for example a value removed by destructuring)
    'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrors: 'none' }],
  },
  overrides: [
    // react-three-fiber elements take three.js properties (position, args, intensity ...), not DOM attributes
    { files: ['src/components/MannequinViewer3D.jsx'], rules: { 'react/no-unknown-property': 'off' } },
    { files: ['*.cjs', '*.config.js', 'playwright.config.js'], env: { node: true } },
    { files: ['e2e/**/*.js'], env: { node: true } },
    {
      files: ['src/__tests__/**/*.{js,jsx}'],
      env: { node: true },
      globals: { global: 'writable' },
      rules: { 'react/display-name': 'off' },
    },
  ],
};
