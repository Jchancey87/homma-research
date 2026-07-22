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
      fontFamily: {
        sans: ['Inter', 'Roboto Condensed', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['IBM Plex Mono', 'Source Code Pro', 'Consolas', 'Liberation Mono', 'Courier New', 'ui-monospace', 'monospace'],
        condensed: ['Roboto Condensed', 'Inter', 'sans-serif'],
        tabular: ['IBM Plex Mono', 'Source Code Pro', 'ui-monospace', 'monospace'],
      },
      letterSpacing: {
        ticker: '0.03em',
        'ticker-wide': '0.04em',
        tightest: '-0.02em',
      },
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
        'text-bright': "var(--text-bright)",
        'text-secondary': "var(--text-secondary)",
        'text-muted': "var(--text-muted)",
        'green-custom': "var(--green)",
        'green-bright': "var(--green-bright)",
        'red-custom': "var(--red)",
        'red-bright': "var(--red-bright)",
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


