import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// SPAs manage their own scroll — prevent the browser from restoring a
// previous scroll position on every page load/navigation.
if ('scrollRestoration' in history) {
  history.scrollRestoration = 'manual'
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
