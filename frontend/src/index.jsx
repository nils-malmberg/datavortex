import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { DarkModeProvider } from './hooks/useDarkMode.jsx'
import { ToastProvider } from './components/ui/ToastProvider.jsx'

// Point de montage React : crée la racine et rend l'application.
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <DarkModeProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </DarkModeProvider>
  </React.StrictMode>,
)
