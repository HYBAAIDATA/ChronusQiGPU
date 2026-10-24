import { NextResponse } from 'next/server'

const TURING_URL = (process.env.TURING_BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '')

// ---------------------------------------------------------------------------
// In-process rate limiter — 5 attempts per 15 minutes per IP.
// For multi-instance deployments replace with a Redis-backed store.
// ---------------------------------------------------------------------------
const MAX_ATTEMPTS = 5
const WINDOW_MS = 15 * 60 * 1000 // 15 minutes
const _attempts = new Map() // ip -> { count, resetAt }

function getRateLimitEntry(ip) {
  const now = Date.now()
  let entry = _attempts.get(ip)
  if (!entry || now > entry.resetAt) {
    entry = { count: 0, resetAt: now + WINDOW_MS }
    _attempts.set(ip, entry)
  }
  return entry
}

function isRateLimited(ip) {
  const entry = getRateLimitEntry(ip)
  return entry.count >= MAX_ATTEMPTS
}

function recordAttempt(ip) {
  const entry = getRateLimitEntry(ip)
  entry.count += 1
}

function clearAttempts(ip) {
  _attempts.delete(ip)
}

// ---------------------------------------------------------------------------
// Cookie configuration
// ---------------------------------------------------------------------------
const COOKIE_NAME = 'auth_token'
const COOKIE_OPTIONS = {
  httpOnly: true,                                          // inaccessible to JS — XSS-safe
  secure: process.env.NODE_ENV === 'production',           // HTTPS only in prod
  sameSite: 'lax',                                         // CSRF mitigation
  path: '/',
  maxAge: 60 * 60 * 24,                                    // 24 hours (matches backend JWT TTL)
}

// ---------------------------------------------------------------------------
// POST /api/auth/login
// ---------------------------------------------------------------------------
export async function POST(request) {
  // Resolve client IP (works behind proxies when TRUST_PROXY is set)
  const ip =
    request.headers.get('x-forwarded-for')?.split(',')[0].trim() ||
    request.headers.get('x-real-ip') ||
    '127.0.0.1'

  // Rate limit check
  if (isRateLimited(ip)) {
    return NextResponse.json(
      { detail: 'Too many login attempts. Please try again in 15 minutes.' },
      { status: 429 }
    )
  }

  let body
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ detail: 'Invalid request body.' }, { status: 400 })
  }

  const { email, password } = body ?? {}

  if (!email || !password) {
    return NextResponse.json({ detail: 'Email and password are required.' }, { status: 400 })
  }

  // Forward credentials to the TURING backend
  let backendRes
  try {
    backendRes = await fetch(`${TURING_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
      signal: AbortSignal.timeout(8000),
    })
  } catch (err) {
    return NextResponse.json({ detail: 'Authentication service unavailable.' }, { status: 503 })
  }

  if (!backendRes.ok) {
    recordAttempt(ip)
    // Return a generic message — never echo backend error details to the client
    return NextResponse.json(
      { detail: 'Invalid credentials.' },
      { status: 401 }
    )
  }

  let data
  try {
    data = await backendRes.json()
  } catch {
    return NextResponse.json({ detail: 'Unexpected response from auth service.' }, { status: 502 })
  }

  // Success — clear rate-limit counter for this IP
  clearAttempts(ip)

  // Set the JWT in an httpOnly cookie; never expose it to client-side JS
  const response = NextResponse.json({
    user: data.user,          // safe public fields only (password_hash excluded by backend)
    authenticated: true,
  })

  response.cookies.set(COOKIE_NAME, data.access_token, COOKIE_OPTIONS)
  return response
}

// ---------------------------------------------------------------------------
// POST /api/auth/logout
// ---------------------------------------------------------------------------
export async function DELETE() {
  const response = NextResponse.json({ authenticated: false })
  response.cookies.set(COOKIE_NAME, '', { ...COOKIE_OPTIONS, maxAge: 0 })
  return response
}
