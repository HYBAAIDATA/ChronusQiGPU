import './globals.css'
import ErrorBoundary from '../components/ErrorBoundary'
import { AIProvider } from '../contexts/AIContext'
import { AuthProvider } from '../contexts/AuthContext'
import AIAssistant from '../components/AIAssistant'

export const metadata = {
  title: 'HYBA Data — Computational Intelligence as a Service',
  description: 'One interface. Many intelligences. Zero friction.',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{__html:'window.addEventListener("error",function(e){if(e.error instanceof DOMException&&e.error.name==="DataCloneError"&&e.message&&e.message.includes("PerformanceServerTiming")){e.stopImmediatePropagation();e.preventDefault()}},true);'}} />
      </head>
      <body style={{ background: '#001E3C', margin: 0, padding: 0 }}>
        <ErrorBoundary>
          <AuthProvider>
            <AIProvider>
              {children}
              <AIAssistant />
            </AIProvider>
          </AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  )
}
