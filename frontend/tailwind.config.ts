// Design tokens for the dark premium automotive theme (colors, fonts, spacing)
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#090b0e",
        panel: "#11151a",
        line: "#2a3038",
        silver: "#edf0f3",
        muted: "#a2acb9",
        accent: "#96dfd3",
      },
      fontFamily: {
        sans: ["Arial", "Helvetica", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
