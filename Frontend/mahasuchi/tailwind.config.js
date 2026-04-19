module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: "#0d1c32",
        "primary-light": "#1e2e4a",
        azure: "#3b82f6",
        "institutional-navy": "#002147",
        "institutional-azure": "#007FFF",
        navy: {
          900: '#0D1C32',
          800: '#1A2B44',
          700: '#263B5B',
          950: '#0f172a',
          DEFAULT: '#0D1C32'
        },
        vidhan: {
          primary: "#0D1C32",
          azure: "#F0F7FF"
        }
      },
      borderRadius: {
        "DEFAULT": "0.5rem",
        "lg": "0.75rem",
        "xl": "1rem",
        "2xl": "1.5rem",
        "3xl": "2rem",
        "full": "9999px"
      },
      fontFamily: {
        sans: ["Inter", "Public Sans", "sans-serif"],
        headline: ["Public Sans", "sans-serif"],
        body: ["Public Sans", "sans-serif"]
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/container-queries')
  ],
}
