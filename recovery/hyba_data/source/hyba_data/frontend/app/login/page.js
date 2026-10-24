'use client'

import { useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Loader2 } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

function LoginFormContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const validateEmailDomain = (email) => {
    const domain = email.split('@')[1]
    return domain === 'hybamine.com'
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    // Validate email domain
    if (!validateEmailDomain(email)) {
      setError('Access restricted to hybamine.com email addresses only')
      setLoading(false)
      return
    }

    // Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email)) {
      setError('Please enter a valid email address')
      setLoading(false)
      return
    }

    // Minimum password length (server enforces the real policy)
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      setLoading(false)
      return
    }

    try {
      const result = await login(email, password)
      if (result.success) {
        const redirectTo = searchParams.get('redirect') || '/dashboard'
        router.push(redirectTo)
      } else {
        setError(result.error || 'Login failed. Please try again.')
        setLoading(false)
      }
    } catch {
      setError('Login failed. Please try again.')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0A0A0A] p-4 relative overflow-hidden">
      {/* Subtle geometric background (matches landing page) */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          className="landing-geo-animate absolute -top-1/2 -right-1/4 w-[800px] h-[800px] border border-white/[0.03] rounded-full"
        />
        <div
          className="landing-geo-animate absolute -bottom-1/3 -left-1/4 w-[600px] h-[600px] border border-white/[0.02] rounded-full"
          style={{ animationDirection: 'reverse', animationDuration: '90s' }}
        />
      </div>

      <div className="relative z-10 w-full max-w-sm landing-animate">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-12">
          <div className="w-8 h-8 border border-white/20 rotate-45 flex items-center justify-center">
            <div className="w-3 h-3 bg-white/80 -rotate-45" />
          </div>
          <span
            className="text-sm font-medium tracking-[0.3em] uppercase text-white/70"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            Euclid
          </span>
        </div>

        {/* Title */}
        <h1
          className="text-2xl font-500 text-white/90 text-center mb-2"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          Client Access
        </h1>
        <p
          className="text-xs tracking-[0.15em] uppercase text-white/25 text-center mb-10"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          Authorised personnel only
        </p>

        {/* Form */}
        <form onSubmit={handleLogin} className="space-y-5">
          <div className="space-y-2">
            <Label
              htmlFor="email"
              className="text-[10px] font-medium tracking-[0.2em] uppercase text-white/40"
              style={{ fontFamily: "'Inter', sans-serif" }}
            >
              Email
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="you@hybamine.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-white/[0.04] border-white/10 text-white/90 placeholder:text-white/20 focus:border-white/25 focus:ring-white/10 rounded-none h-11"
              required
            />
          </div>
          <div className="space-y-2">
            <Label
              htmlFor="password"
              className="text-[10px] font-medium tracking-[0.2em] uppercase text-white/40"
              style={{ fontFamily: "'Inter', sans-serif" }}
            >
              Password
            </Label>
            <Input
              id="password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="bg-white/[0.04] border-white/10 text-white/90 placeholder:text-white/20 focus:border-white/25 focus:ring-white/10 rounded-none h-11"
              required
            />
          </div>
          {error && (
            <p className="text-xs text-red-400/80 tracking-wide">{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full border border-white/15 hover:border-white/40 bg-transparent hover:bg-white/[0.03] text-white/60 hover:text-white/90 py-3.5 transition-all duration-500 flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            {loading ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span className="text-xs font-medium tracking-[0.2em] uppercase">Verifying</span>
              </>
            ) : (
              <span className="text-xs font-medium tracking-[0.2em] uppercase">Continue</span>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-12 text-center">
          <button
            onClick={() => router.push('/')}
            className="text-[10px] tracking-[0.15em] uppercase text-white/15 hover:text-white/30 transition-colors duration-500"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            Return to homepage
          </button>
        </div>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-[#0A0A0A] text-white/30">Loading...</div>}>
      <LoginFormContent />
    </Suspense>
  )
}
