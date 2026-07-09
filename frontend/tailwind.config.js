/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Eigener Auftritt: Royal-Blau ersetzt ueberall das Mint des Fin.Co-Systems.
        // Blau ist ein DUNKLER Akzent -> Vordergrund auf Flaeche = Weiss (paper),
        // und Blau DARF als Textfarbe (Kontrast auf Weiss ~7.4:1, AA/AAA).
        royal: {
          DEFAULT: '#2947c9',
          soft: '#aeb9ee',
        },
        ink: '#161a24',
        paper: '#ffffff',
      },
      fontFamily: {
        sans: ['Roboto', 'system-ui', 'sans-serif'],
      },
      letterSpacing: {
        wordmark: '-0.02em',
        tagline: '0.18em',
      },
    },
  },
  plugins: [],
}
