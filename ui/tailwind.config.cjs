/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        flow: {
          bg: "var(--flow-bg)",
          surface: "var(--flow-surface)",
          text: "var(--flow-text)",
          muted: "var(--flow-muted)",
          amber: "var(--flow-amber)",
          sage: "var(--flow-sage)",
          rose: "var(--flow-rose)",
        },
      },
      fontFamily: {
        sans: [
          "Noto Sans CJK SC",
          "Noto Sans SC",
          "Source Han Sans SC",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
