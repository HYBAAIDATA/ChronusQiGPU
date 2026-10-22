'use client'

import { Component } from 'react'

const MONO = "'JetBrains Mono','Fira Code','Courier New',monospace"
const SANS = "'Inter',-apple-system,BlinkMacSystemFont,sans-serif"

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    // In production, errors are already surface-suppressed; log to console only.
    if (process.env.NODE_ENV !== 'production') {
      console.error('[ErrorBoundary] Uncaught error:', error, info.componentStack)
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh', background: '#060D1A',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: SANS, color: '#EEF4FB',
        }}>
          <div style={{
            maxWidth: 520, padding: '48px 40px',
            background: '#0B1826', border: '1px solid #1A3050', borderRadius: 8,
            textAlign: 'center',
          }}>
            <div style={{ fontFamily: MONO, fontSize: 11, letterSpacing: 3, color: '#E04545', marginBottom: 20 }}>
              SYSTEM FAULT
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 12 }}>
              Instrument Error
            </div>
            <div style={{ color: '#7A9CB8', fontSize: 14, lineHeight: 1.6, marginBottom: 32 }}>
              An unexpected error occurred in the mining instrument.
              The system has been isolated to prevent data corruption.
            </div>
            {process.env.NODE_ENV !== 'production' && this.state.error && (
              <pre style={{
                background: '#112440', border: '1px solid #1A3050', borderRadius: 4,
                padding: 16, textAlign: 'left', fontFamily: MONO, fontSize: 11,
                color: '#E04545', overflowX: 'auto', marginBottom: 28,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              }}>
                {this.state.error.message}
              </pre>
            )}
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: '10px 28px',
                background: 'transparent', border: '1px solid #3D8EDB',
                borderRadius: 4, color: '#3D8EDB',
                fontFamily: MONO, fontSize: 11, letterSpacing: 2, cursor: 'pointer',
              }}
            >
              REINITIALISE
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
