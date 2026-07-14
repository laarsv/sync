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
