import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  // safelist: clases de color que se arman dinámicamente (en colorEstado) o que
  // vienen de componentes (switch). Tailwind no las detecta solo, las forzamos.
  safelist: [
    "bg-amber-100", "text-amber-900", "border-amber-300",
    "bg-blue-100", "text-blue-900", "border-blue-300",
    "bg-purple-100", "text-purple-900", "border-purple-300",
    "bg-green-100", "text-green-900", "border-green-300",
    "bg-gray-100", "text-gray-500", "border-gray-300", "line-through",
    "bg-red-50", "text-red-700", "border-red-200",
    "text-blue-600", "text-amber-600", "text-green-600",
    "bg-green-500", "bg-zinc-400", "bg-zinc-600",
    "bg-green-500", "bg-zinc-300", "bg-zinc-600", "bg-red-500",
    "bg-amber-400/20", "text-amber-600", "text-amber-400",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
        display: ["Syne", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;