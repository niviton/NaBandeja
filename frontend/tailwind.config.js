/**
 * Tokens do design system NaBandeja (veja DESIGN.md).
 * Gera static/css/app.css: scripts\build_css.bat
 */
const tone = (base, soft) => ({ DEFAULT: base, 50: soft });

module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
    './restaurante/**/*.py',
  ],
  theme: {
    extend: {
      colors: {
        creme: '#FAF6EF',
        papel: '#FFFFFF',
        linha: '#E9E1D4',
        carvao: { DEFAULT: '#1F1A17', 800: '#2A2420', 700: '#3A322C' },
        fumaca: '#6E655C',
        tomate: tone('#D9442B', '#FBEAE6'),
        brasa: '#B23620',
        mostarda: tone('#E9A23B', '#FDF3E1'),
        manjericao: tone('#2E7D57', '#E4F2EA'),
        uva: tone('#6D3B8C', '#F2EAF7'),
        cebola: tone('#2563A8', '#E7EFF8'),
        pimenta: tone('#C0262D', '#FBE8E8'),
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        display: ['Fraunces', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'Consolas', 'monospace'],
      },
      boxShadow: {
        float: '0 12px 32px -16px rgb(31 26 23 / 0.25)',
      },
      borderRadius: {
        card: '20px',
      },
    },
  },
  plugins: [],
};
