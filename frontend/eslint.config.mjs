// Configuração ESLint 9 (flat config) — Parte 8.3.
// Tolerância para código legado: regras que gerariam erros novos em
// componentes antigos são ajustadas/desligadas pontualmente (regra 5).
import js from "@eslint/js";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import prettier from "eslint-config-prettier";

export default [
  {
    ignores: ["dist", "node_modules", "coverage", "release", "*.config.js"],
  },
  js.configs.recommended,
  {
    files: ["**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: {
        ...globals.browser,
        ...globals.node,
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      react,
      "react-hooks": reactHooks,
    },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      // Vite/React 17+: JSX não exige `import React` no escopo.
      "react/react-in-jsx-scope": "off",
      // Código legado: componentes sem PropTypes permanecem válidos.
      "react/prop-types": "off",
      // Legado: aspas `"` e `'` em texto JSX (ex.: rótulos com tipo "X").
      "react/no-unescaped-entities": "off",
      // Legado: efeitos com deps incompletas são comuns no código atual;
      // reescrevê-los mudaria comportamento (regra 5).
      "react-hooks/exhaustive-deps": "off",
      // Legado: `catch {}` silencioso é intencional em chamadas de API.
      "no-empty": ["error", { allowEmptyCatch: true }],
      // Legado: `_` como placeholder de argumento/erro não utilizado.
      "no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
        },
      ],
    },
    settings: {
      react: { version: "18.3" },
    },
  },
  prettier,
];