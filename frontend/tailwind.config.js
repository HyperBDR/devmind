/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a'
        },
        gray: {
          50: '#f9fafb',
          100: '#f3f4f6',
          200: '#e5e7eb',
          300: '#d1d5db',
          400: '#9ca3af',
          500: '#6b7280',
          600: '#4b5563',
          700: '#374151',
          800: '#1f2937',
          900: '#111827'
        },
        agione: {
          50: '#ece9f9',
          100: '#d8d2f0',
          200: '#b3a8e2',
          300: '#8b7dd1',
          400: '#7a6ac4',
          500: '#6a5ac7',
          600: '#5f4ecf',
          700: '#4a3eb0',
          800: '#3d3399',
          900: '#312870'
        },
        dm: {
          page: '#f0f2f5',
          container: '#ffffff',
          primary: '#1677ff',
          'primary-hover': '#4096ff',
          'primary-bg': '#e6f4ff',
          border: '#e4e7ed',
          'border-light': '#f0f0f0',
          text: '#262626',
          'text-secondary': '#595959',
          'text-tertiary': '#8c8c8c',
          'table-head': '#fafafa',
          success: '#52c41a',
          'success-bg': '#f6ffed',
          warning: '#faad14',
          'warning-bg': '#fffbe6',
          error: '#ff4d4f',
          'error-bg': '#fff2f0'
        }
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans SC', 'system-ui', 'sans-serif']
      },
      borderRadius: {
        DEFAULT: '16px',
        sm: '8px',
        md: '12px',
        lg: '16px',
        xl: '20px',
        '2xl': '24px',
        dm: '8px',
        'dm-lg': '12px'
      },
      boxShadow: {
        soft: '0 2px 8px rgba(0, 0, 0, 0.08)',
        'soft-md': '0 4px 12px rgba(0, 0, 0, 0.10)',
        'soft-lg': '0 8px 16px rgba(0, 0, 0, 0.12)',
        dm: '0 1px 2px 0 rgba(0, 0, 0, 0.03), 0 1px 6px -1px rgba(0, 0, 0, 0.02)',
        'dm-card': '0 1px 2px 0 rgba(0, 0, 0, 0.03)'
      },
      container: {
        center: true,
        padding: '1rem',
        screens: {
          sm: '640px',
          md: '768px',
          lg: '1024px',
          xl: '1280px',
          '2xl': '1400px'
        }
      }
    }
  },
  plugins: []
}
