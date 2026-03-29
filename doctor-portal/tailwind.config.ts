import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        who: {
          blue: "#0077B6",
          "blue-dark": "#005F8A",
          "blue-light": "#90E0EF",
        },
        triage: {
          red: "#E63946",
          yellow: "#F4A261",
          green: "#2A9D8F",
          critical: "#7C2D12",
        },
        sidebar: "#1A1A2E",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        heading: ["var(--font-heading)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
