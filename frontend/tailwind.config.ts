import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: 'class',
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        app: "var(--bg-app)",
        panel: "var(--bg-panel)",
        raised: "var(--bg-raised)",
        hover: "var(--bg-hover)",
        'border-subtle': "var(--border-subtle)",
        'border-strong': "var(--border-strong)",
        'text-primary': "var(--text-primary)",
        'text-secondary': "var(--text-secondary)",
        'text-muted': "var(--text-muted)",
        'green-custom': "var(--green)",
        'red-custom': "var(--red)",
        'amber-custom': "var(--amber)",
        'info-custom': "var(--info)",
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
};
export default config;

