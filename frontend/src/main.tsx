import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Bundle the same Thai and Latin Kanit weights as pplus-inv-v1.
import '@fontsource/kanit/thai-300.css'
import '@fontsource/kanit/thai-400.css'
import '@fontsource/kanit/thai-500.css'
import '@fontsource/kanit/thai-600.css'
import '@fontsource/kanit/thai-700.css'
import '@fontsource/kanit/latin-300.css'
import '@fontsource/kanit/latin-400.css'
import '@fontsource/kanit/latin-500.css'
import '@fontsource/kanit/latin-600.css'
import '@fontsource/kanit/latin-700.css'
import './index.css'
import App from './App.tsx'
import { LanguageProvider } from '@/i18n/context'
import { ThemeProvider } from '@/theme/context'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </ThemeProvider>
  </StrictMode>,
)
