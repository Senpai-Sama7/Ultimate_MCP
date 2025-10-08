module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: {
    project: null,
    tsconfigRootDir: __dirname,
  },
  plugins: ["@typescript-eslint"],
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
  ],
  settings: {
    react: {
      version: "detect",
    },
  },
  env: {
    browser: true,
    es2021: true,
  },
  rules: {
    "react/react-in-jsx-scope": "off",
    "@typescript-eslint/no-misused-promises": "error"
  },
};
