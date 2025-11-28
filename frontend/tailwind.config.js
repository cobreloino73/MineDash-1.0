/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'claude': {
          50: '#fef6ee',
          100: '#fdecd7',
          200: '#fad5ad',
          300: '#f7b779',
          400: '#f38d43',
          500: '#f0701f',
          600: '#e15615',
          700: '#bb4013',
          800: '#953417',
          900: '#792e16',
        },
        'warm': {
          50: '#fafaf9',
          100: '#f5f5f4',
          200: '#e7e5e4',
          300: '#d6d3d1',
          400: '#a8a29e',
          500: '#78716c',
          600: '#57534e',
          700: '#44403c',
          800: '#292524',
          900: '#1c1917',
        }
      }
    },
  },
  plugins: [],
}