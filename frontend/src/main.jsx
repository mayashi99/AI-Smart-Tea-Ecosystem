// Load the shared shell first. Tailwind utilities must be emitted afterwards
// so Component 02's utility-first layouts retain their original appearance.
import './styles.css'
import './index.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { AuthProvider } from './lib/auth.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProvider><App /></AuthProvider>
  </StrictMode>,
)
