export default [
    {
        files: ['frontend/**/*.js'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'script',
            globals: {
                document: 'readonly',
                window: 'readonly',
                console: 'readonly',
                fetch: 'readonly',
                marked: 'readonly',
                Date: 'readonly',
            },
        },
        rules: {
            'no-unused-vars': 'warn',
            'no-console': 'off',
            eqeqeq: ['error', 'always'],
            'no-var': 'error',
            'prefer-const': 'warn',
        },
    },
];
