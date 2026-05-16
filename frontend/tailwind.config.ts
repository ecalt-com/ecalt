import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        theme: {
          bg:      'var(--bg)',
          surface: 'var(--surface)',
          card:    'var(--card-bg)',
          border:  'var(--card-border)',
          t1:      'var(--t1)',
          t2:      'var(--t2)',
          t3:      'var(--t3)',
        },
      },
      keyframes: {
        'glow-pulse': { '0%, 100%': { opacity: '0.35' }, '50%': { opacity: '0.75' } },
        float:        { '0%, 100%': { transform: 'translateY(0px)' }, '50%': { transform: 'translateY(-10px)' } },
        'slide-up':   { from: { opacity: '0', transform: 'translateY(24px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        'fade-in':    { from: { opacity: '0' }, to: { opacity: '1' } },
        'gradient-x': { '0%, 100%': { backgroundPosition: '0% 50%' }, '50%': { backgroundPosition: '100% 50%' } },
        shimmer:      { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
        'toast-in':   { from: { opacity: '0', transform: 'translateY(10px) scale(0.96)' }, to: { opacity: '1', transform: 'translateY(0) scale(1)' } },
        'celebration':{ '0%': { opacity: '0', transform: 'scale(0.92) translateY(16px)' }, '100%': { opacity: '1', transform: 'scale(1) translateY(0)' } },
      },
      animation: {
        'glow-pulse':  'glow-pulse 3s ease-in-out infinite',
        float:         'float 6s ease-in-out infinite',
        'slide-up':    'slide-up 0.55s ease-out forwards',
        'fade-in':     'fade-in 0.7s ease-out forwards',
        'gradient-x':  'gradient-x 4s ease infinite',
        shimmer:       'shimmer 2.5s linear infinite',
        'toast-in':    'toast-in 0.25s ease-out forwards',
        'celebration': 'celebration 0.4s cubic-bezier(0.16,1,0.3,1) forwards',
      },
    },
  },
  plugins: [],
}

export default config
