/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './election_core/templates/**/*.html',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui'],
      },
      colors: {
        indigo: {
          50: '#f5f7ff',
          100: '#ebf0fe',
          600: '#4f46e5',
          700: '#4338ca',
        }
      }
    }
  },
  plugins: [],
}
