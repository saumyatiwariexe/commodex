/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0D1117',
        surface: '#161B22',
        surfaceHover: '#21262D',
        border: '#30363D',
        gold: '#D4AF37',
        goldBright: '#FFD700',
        textPrimary: '#C9D1D9',
        textSecondary: '#8B949E',
        accentError: '#F85149',
        accentSuccess: '#2EA043',
      },
      fontFamily: {
        sans: ['"Inter"', 'sans-serif'],
        mono: ['"Roboto Mono"', 'monospace'],
      }
    },
  },
  plugins: [],
}
