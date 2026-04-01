/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html",
  ],
  theme: {
    extend: {
      colors: {
        'app-bg': '#ffffff',
        'app-sidebar': '#f9f9f9',
        'app-border': '#e5e5e5',
        'app-text-primary': '#343541',
        'app-text-secondary': '#6e6e80',
        'app-accent': '#10a37f',
        'app-accent-hover': '#1a7f64',
        'app-input-bg': '#ffffff',
        'app-message-user': '#f7f7f8',
        'app-message-ai': '#ffffff',
      },
      fontFamily: {
        'app': ['"Söhne"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', '"Helvetica Neue"', 'Arial', 'sans-serif'],
      },
      keyframes: {
        fadeIn: {
          'from': {
            opacity: '0',
            transform: 'translateY(8px)',
          },
          'to': {
            opacity: '1',
            transform: 'translateY(0)',
          },
        },
        slideIn: {
          'from': {
            opacity: '0',
            transform: 'translateX(-10px)',
          },
          'to': {
            opacity: '1',
            transform: 'translateX(0)',
          },
        },
        typingDot: {
          '0%, 60%, 100%': {
            transform: 'translateY(0)',
          },
          '30%': {
            transform: 'translateY(-4px)',
          },
        },
        blink: {
          '0%, 100%': {
            opacity: '1',
          },
          '50%': {
            opacity: '0',
          },
        },
        pulseRing: {
          '0%': {
            boxShadow: '0 0 0 0 rgba(239, 68, 68, 0.7)',
          },
          '70%': {
            boxShadow: '0 0 0 20px rgba(239, 68, 68, 0)',
          },
          '100%': {
            boxShadow: '0 0 0 0 rgba(239, 68, 68, 0)',
          },
        },
        wave: {
          from: {
            backgroundPosition: '0 0',
          },
          to: {
            backgroundPosition: '8px 0',
          },
        },
      },
      animation: {
        fadeIn: 'fadeIn 0.3s ease-out forwards',
        slideIn: 'slideIn 0.3s ease-out forwards',
        pulse: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        typingDot: 'typingDot 1.4s infinite ease-in-out both',
        blink: 'blink 1s infinite',
        pulseRing: 'pulseRing 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        wave: 'wave 0.8s linear infinite',
      },
      spacing: {
        'sidebar-width': '260px',
      },
      width: {
        '15': '3.75rem',
        '7.5': '1.875rem',
        '10': '2.5rem',
      },
      height: {
        '15': '3.75rem',
        '7.5': '1.875rem',
        '12': '3rem',
      },
      minHeight: {
        '12': '3rem',
      },
    },
  },
  plugins: [],
}
