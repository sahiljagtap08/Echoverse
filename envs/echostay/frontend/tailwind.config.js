/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        echostay: {
          primary: '#10B981',
          'primary-dark': '#059669',
          teal: '#00A699',
          orange: '#FC642D',
          dark: '#484848',
          gray: '#767676',
          'light-gray': '#EBEBEB',
          'bg-gray': '#F7F7F7',
        }
      },
      fontFamily: {
        echostay: ['Circular', '-apple-system', 'BlinkMacSystemFont', 'Roboto', 'Helvetica Neue', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
