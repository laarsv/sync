/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Royal blue accent. A DARK accent -> foreground on a fill = white
        // (paper), and blue may be used as a text color (~7.4:1 on white).
        royal: {
          DEFAULT: '#2947c9',
          soft: '#aeb9ee',
        },
        ink: '#161a24',
        paper: '#ffffff',
        // VRWB-CI v3 (Suite, theme-v3.css): Arbeitsfläche und Flächen-Stufen.
        canvas: '#f3f5fa',
        surface: { 2: '#f7f8fc', 3: '#eef1f8' },
        // Signalfarben, nur als Soll-Ist-Signal. `tint` = Tönung für Chips und Bänder.
        pos: { DEFAULT: '#177245', tint: 'rgba(23, 114, 69, .1)' },
        neg: { DEFAULT: '#c0392b', tint: 'rgba(192, 57, 43, .1)', line: 'rgba(192, 57, 43, .35)' },
        warn: { DEFAULT: '#9a5900', tint: 'rgba(178, 106, 0, .12)' },
      },
      boxShadow: {
        // VRWB-CI v3: Karten/Kacheln (1) und Dialoge/Popups (2).
        1: '0 1px 2px rgba(22, 26, 36, .04), 0 6px 18px -10px rgba(22, 26, 36, .12)',
        2: '0 2px 6px rgba(22, 26, 36, .05), 0 18px 40px -18px rgba(22, 26, 36, .22)',
      },
      fontFamily: {
        sans: ['Roboto', 'system-ui', 'sans-serif'],
        mono: ['Roboto Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      letterSpacing: {
        // VRWB CI: Wortmarke −4,5 %, Produkt-Lockup-Toolname −1 %.
        wordmark: '-0.045em',
        toolname: '-0.01em',
        tagline: '0.18em',
      },
    },
  },
  plugins: [],
}
