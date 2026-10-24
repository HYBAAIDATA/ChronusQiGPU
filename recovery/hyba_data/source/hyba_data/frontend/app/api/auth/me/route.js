import { NextResponse } from 'next/server'

const TURING_URL = (process.env.TURING_BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '')
const COOKIE_NAME = 'auth_token'

/**
 * GET /api/auth/me
 *
 * Reads the httpOnly auth_token cookie, validates it against the backend,
 * and returns the current user's public profile.
 * Returns 401 if the cookie is absent or the token is expired/invalid.
 */
export async function GET(request) {
  const token = request.cookies.get(COOKIE_NAME)?.value

  if (!token) {
    return NextResponse.json({ detail: 'Not authenticated.' }, { status: 401 })
  }

  let backendRes
  try {
    backendRes = await fetch(`${TURING_URL}/api/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(5000),
    })
  } catch {
    return NextResponse.json({ detail: 'Authentication service unavailable.' }, { status: 503 })
  }

  if (!backendRes.ok) {
    // Token invalid or expired — clear the stale cookie
    const response = NextResponse.json({ detail: 'Session expired.' }, { status: 401 })
    response.cookies.set(COOKIE_NAME, '', { httpOnly: true, maxAge: 0, path: '/' })
    return response
  }

  const user = await backendRes.json()
  return NextResponse.json({ user, authenticated: true })
}
