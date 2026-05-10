import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ['var(--font-mono)', 'ui-monospace', 'SFMono-Regular', 'monospace'],
        serif: ['var(--font-serif)', 'Newsreader', 'Times New Roman', 'serif'],
      },
      colors: {
        bg: 'var(--bg)',
        'bg-elev': 'var(--bg-elev)',
        'bg-tint': 'var(--bg-tint)',
        fg: 'var(--fg)',
        'fg-soft': 'var(--fg-soft)',
        'fg-faint': 'var(--fg-faint)',
        line: 'var(--line)',
        'line-bright': 'var(--line-bright)',
        mark: 'var(--mark)',
        'mark-soft': 'var(--mark-soft)',
        warn: 'var(--warn)',
        hot: 'var(--hot)',
      },
      letterSpacing: {
        caps: '0.08em',
      },
    },
  },
  plugins: [],
};

export default config;
