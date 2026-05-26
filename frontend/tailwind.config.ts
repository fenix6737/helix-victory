import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        helix: {
          bg: "#0a0a0a",
          surface: "#141414",
          border: "#2a2a2a",
          muted: "#888888",
          text: "#f5f5f5",
          accent: "#3b82f6",
          slot: "#f59e0b",
          pachinko: "#ec4899",
        },
      },
      fontSize: {
        rank: ["2.5rem", { lineHeight: "1", fontWeight: "700" }],
        title: ["1.25rem", { lineHeight: "1.3", fontWeight: "600" }],
        body: ["1rem", { lineHeight: "1.5" }],
        meta: ["0.875rem", { lineHeight: "1.4" }],
      },
      minHeight: {
        tap: "48px",
      },
    },
  },
  plugins: [],
};

export default config;
