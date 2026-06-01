# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

## Information-system screens

Alongside the original matrix solver (`/`) and experiment pages, the app
includes an authenticated information system. Server state is managed with
`@tanstack/react-query`; forms use `react-hook-form` + `zod`; toasts use `sonner`.

| Route | Screen | Description |
|---|---|---|
| `/login`, `/register` | Login / Register | JWT auth; token stored in `localStorage` |
| `/services` | Services | service catalogue CRUD; shows group memberships |
| `/service-groups` | ServiceGroups | interdependency groups; checkbox multi-select of members |
| `/providers` | Providers | provider directory CRUD |
| `/planning` | Planning | four tabbed matrices (prices, resources, provider revenue, discounts); cell edits autosave (debounced) with a per-cell indicator |
| `/formations` | Formations | list of scenarios; "Нове формування" dialog (name, algorithm, params, T); polls while running |
| `/formations/:id` | FormationDetail | totals + assignments grouped by provider; JSON/CSV export; "compare" launcher |
| `/formations/compare?ids=…` | FormationsCompare | side-by-side totals table + recharts bar chart |

Auth lives in `src/auth/` (`AuthContext`, `RequireAuth`); the typed API client
and per-resource modules live in `src/api/`. Routes under the information system
are wrapped in `<RequireAuth>`; `/` and the experiment routes stay public.

---


Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default tseslint.config({
  extends: [
    // Remove ...tseslint.configs.recommended and replace with this
    ...tseslint.configs.recommendedTypeChecked,
    // Alternatively, use this for stricter rules
    ...tseslint.configs.strictTypeChecked,
    // Optionally, add this for stylistic rules
    ...tseslint.configs.stylisticTypeChecked,
  ],
  languageOptions: {
    // other options...
    parserOptions: {
      project: ['./tsconfig.node.json', './tsconfig.app.json'],
      tsconfigRootDir: import.meta.dirname,
    },
  },
})
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default tseslint.config({
  plugins: {
    // Add the react-x and react-dom plugins
    'react-x': reactX,
    'react-dom': reactDom,
  },
  rules: {
    // other rules...
    // Enable its recommended typescript rules
    ...reactX.configs['recommended-typescript'].rules,
    ...reactDom.configs.recommended.rules,
  },
})
```
