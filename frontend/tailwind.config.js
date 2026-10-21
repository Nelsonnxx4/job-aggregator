/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1c2434",
        muted: "#788194",
        brand: {
          DEFAULT: "#4268e8",
          dark: "#3154cc",
        },
      },
      fontFamily: {
        sans: ["Segoe UI", "Arial", "sans-serif"],
      },
      boxShadow: {
        card: "0 2px 7px rgb(28 36 52 / 2%)",
        elevated: "0 5px 15px rgb(43 64 119 / 6%)",
      },
    },
  },
  plugins: [],
};
