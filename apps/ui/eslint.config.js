import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import boundaries from 'eslint-plugin-boundaries'
import importPlugin from 'eslint-plugin-import'

// FSD layer order: lower index = lower layer = may be imported by higher layers only.
const FSD_LAYERS = ['shared', 'entities', 'features', 'widgets', 'pages', 'app']

export default tseslint.config(
  { ignores: ['dist'] },

  // ── TypeScript + React ──────────────────────────────────────────────────────
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  },

  // ── FSD boundary rules ──────────────────────────────────────────────────────
  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: {
      boundaries,
      import: importPlugin,
    },
    settings: {
      'boundaries/elements': [
        { type: 'shared',   pattern: 'src/shared/**/*' },
        { type: 'entities', pattern: 'src/entities/**/*' },
        { type: 'features', pattern: 'src/features/**/*' },
        { type: 'widgets',  pattern: 'src/widgets/**/*' },
        { type: 'pages',    pattern: 'src/pages/**/*' },
        { type: 'app',      pattern: 'src/app/**/*' },
      ],
      'boundaries/ignore': ['**/*.test.*', '**/*.spec.*'],
    },
    rules: {
      // Each layer may only import from strictly-lower layers.
      'boundaries/element-types': [
        'error',
        {
          default: 'disallow',
          rules: FSD_LAYERS.map((layer, i) => ({
            from: layer,
            allow: FSD_LAYERS.slice(0, i), // everything below
          })),
        },
      ],
    },
  },
)
