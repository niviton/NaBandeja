/**
 * Gera static/css/app.css a partir das classes usadas nos templates.
 * Rode: scripts\build_css.bat   (ou tools\tailwindcss.exe, veja docs/desenvolvimento.md)
 */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
    './restaurante/**/*.py',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
