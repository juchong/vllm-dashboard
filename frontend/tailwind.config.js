/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'primary-color': 'var(--primary-color)',
        'primary-dark': 'var(--primary-dark)',
        'secondary-color': 'var(--secondary-color)',
        'background-color': 'var(--background-color)',
        'card-bg': 'var(--card-bg)',
        'text-primary': 'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'text-muted': 'var(--text-muted)',
        'border-color': 'var(--border-color)',
        'surface-hover': 'var(--surface-hover)',
        'code-bg': 'var(--code-bg)',
      },
    },
  },
  plugins: [],
}
