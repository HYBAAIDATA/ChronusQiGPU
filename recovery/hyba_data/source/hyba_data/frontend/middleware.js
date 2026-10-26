import { NextResponse } from 'next/server'

const AUTH_COOKIE = 'auth_token'

const PUBLIC_PATHS = ['/', '/login', '/api/auth', '/api/health']

const PROTECTED_PREFIXES = ['/home', '/workbench', '/telemetry', '/security', '/research', '/dashboard', '/admin', '/al-haras', '/millennium']

export function middleware(request) {
  const { pathname } = request.nextUrl

  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '/'))) {
    return NextResponse.next()
  }

  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/favicon') ||
    pathname.includes('.')
  ) {
    return NextResponse.next()
  }

  const isProtected = PROTECTED_PREFIXES.some((p) => pathname.startsWith(p))

  if (isProtected) {
    const token = request.cookies.get(AUTH_COOKIE)?.value

    if (!token) {
      const loginUrl = new URL('/login', request.url)
      loginUrl.searchParams.set('redirect', pathname)
      return NextResponse.redirect(loginUrl)
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
