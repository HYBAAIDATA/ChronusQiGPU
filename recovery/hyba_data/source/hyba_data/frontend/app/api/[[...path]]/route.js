import { MongoClient } from 'mongodb'
import { NextResponse } from 'next/server'

// ============================================================
// TURING BACKEND URL — resolved once at module load time
// ============================================================
const TURING_URL = (process.env.TURING_BACKEND_URL || 'http://localhost:8765').replace(/\/$/, '')
// Request timeout: 10 s in production, 5 s in development
const TURING_TIMEOUT_MS = process.env.NODE_ENV === 'production' ? 10000 : 5000

// Name of the httpOnly cookie that carries the JWT
const AUTH_COOKIE = 'auth_token'

// ============================================================
// MONGODB — connection with reconnect guard
// ============================================================
let _client = null
let _db = null
async function getDB() {
  // Return healthy cached connection
  if (_db && _client) {
    try {
      // Lightweight ping to verify the connection is still alive
      await _client.db('admin').command({ ping: 1 })
      return _db
    } catch {
      // Connection is stale — fall through to reconnect
      _client = null
      _db = null
    }
  }
  if (!process.env.MONGO_URL) throw new Error('MONGO_URL environment variable is not set')
  try {
    _client = new MongoClient(process.env.MONGO_URL, {
      maxPoolSize: 10,
      serverSelectionTimeoutMS: 5000,
      connectTimeoutMS: 5000,
    })
    await _client.connect()
    _db = _client.db(process.env.DB_NAME || 'pythagoras')
    return _db
  } catch (e) {
    _client = null
    _db = null
    throw e
  }
}
// ============================================================
// CORS HELPERS
// In production, reflect the request Origin only when it matches an
// entry in the CORS_ORIGINS allow-list.  In development, allow all.
// ============================================================
const CORS_ALLOW_LIST = process.env.CORS_ORIGINS
  ? process.env.CORS_ORIGINS.split(',').map((o) => o.trim()).filter(Boolean)
  : []

function resolveAllowedOrigin(requestOrigin) {
  if (process.env.NODE_ENV !== 'production') return '*'
  if (!requestOrigin) return 'null'
  if (CORS_ALLOW_LIST.includes(requestOrigin)) return requestOrigin
  // Origin is not on the allowlist — return 'null' to refuse the CORS grant
  return 'null'
}

function handleCORS(res, requestOrigin) {
  const allowed = resolveAllowedOrigin(requestOrigin)
  res.headers.set('Access-Control-Allow-Origin', allowed)
  res.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS')
  res.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization')
  if (allowed !== '*') {
    res.headers.set('Vary', 'Origin')
  }
  return res
}
export async function OPTIONS(request) {
  const origin = request.headers.get('origin')
  return handleCORS(new NextResponse(null, { status: 200 }), origin)
}

// ============================================================
// TURING PROXY HELPER
// Forwards a request to the TURING FastAPI backend, preserving
// the HTTP method, Authorization header, query string, and body.
// ============================================================
async function turingProxy(request, pathArr, method) {
  const origin = request.headers.get('origin')
  const subPath = pathArr.slice(1).join('/')
  const qs = method === 'GET' || method === 'DELETE' ? new URL(request.url).search : ''
  const targetUrl = `${TURING_URL}/${subPath}${qs}`
  const forwardHeaders = { 'Content-Type': 'application/json', 'Accept': 'application/json' }

  // Prefer the httpOnly cookie token; fall back to an explicit Authorization
  // header only for non-browser clients (e.g. server-to-server calls).
  const cookieToken = request.cookies.get(AUTH_COOKIE)?.value
  const authHeader = request.headers.get('authorization')
  if (cookieToken) {
    forwardHeaders['Authorization'] = `Bearer ${cookieToken}`
  } else if (authHeader) {
    forwardHeaders['Authorization'] = authHeader
  }

  let body
  if (method !== 'GET' && method !== 'DELETE') {
    try { body = await request.text() } catch (e) {
      if (process.env.NODE_ENV !== 'production') {
        console.error(`[TURING proxy] ${method} ${subPath} body read failed:`, e.message)
      }
    }
  }
  try {
    const res = await fetch(targetUrl, {
      method,
      headers: forwardHeaders,
      body: body || undefined,
      signal: AbortSignal.timeout(TURING_TIMEOUT_MS),
    })
    let data
    try { data = await res.json() } catch (_) { data = {} }
    return handleCORS(NextResponse.json(data, { status: res.status }), origin)
  } catch (e) {
    if (process.env.NODE_ENV !== 'production') {
      console.error(`[TURING proxy] ${method} ${targetUrl} failed:`, e.message)
    }
    if (subPath.split('/')[0] === 'health') {
      return handleCORS(NextResponse.json({ status: 'offline', message: 'TURING backend not reachable', uptime: 0 }, { status: 503 }), origin)
    }
    return handleCORS(NextResponse.json({ error: 'TURING backend unavailable', detail: e.message }, { status: 503 }), origin)
  }
}

// ============================================================
// ROUTE HANDLERS
// ============================================================
export async function GET(request, { params }) {
  const pathArr = params.path || []
  const route = pathArr[0]
  const origin = request.headers.get('origin')

  // ---- HEALTH CHECK (/api/health) ----
  // Used by Docker HEALTHCHECK, Kubernetes liveness/readiness probes, and the CI smoke test.
  if (route === 'health') {
    return handleCORS(NextResponse.json({
      status: 'ok',
      service: 'Pythagoras Mining Instrument',
      version: '2.1',
      timestamp: new Date().toISOString(),
    }), origin)
  }

  if (route === 'sessions') {
    try {
      const db = await getDB()
      const sessions = await db.collection('mining_sessions').find({}).sort({ start_time: -1 }).limit(20).toArray()
      return handleCORS(NextResponse.json({ sessions: sessions.map(s => ({ ...s, _id: undefined })) }), origin)
    } catch (e) { return handleCORS(NextResponse.json({ sessions: [] }), origin) }
  }

  // ---- TURING BACKEND PROXY (/api/turing/*) ----
  // Proxies REST calls to the TURING FastAPI backend.
  // Backend URL is read from TURING_BACKEND_URL (defaults to localhost:8765 for local dev).
  if (route === 'turing') return turingProxy(request, pathArr, 'GET')

  if (!route || route === '') return handleCORS(NextResponse.json({ service: 'Pythagoras Mining Instrument', version: '2.1' }), origin)
  return handleCORS(NextResponse.json({ error: 'route not found' }, { status: 404 }), origin)
}

export async function POST(request, { params }) {
  const pathArr = params.path || []
  const origin = request.headers.get('origin')
  if (pathArr[0] === 'turing') return turingProxy(request, pathArr, 'POST')
  return handleCORS(NextResponse.json({ error: 'route not found' }, { status: 404 }), origin)
}

export async function PUT(request, { params }) {
  const pathArr = params.path || []
  const origin = request.headers.get('origin')
  if (pathArr[0] === 'turing') return turingProxy(request, pathArr, 'PUT')
  return handleCORS(NextResponse.json({ error: 'route not found' }, { status: 404 }), origin)
}

export async function PATCH(request, { params }) {
  const pathArr = params.path || []
  const origin = request.headers.get('origin')
  if (pathArr[0] === 'turing') return turingProxy(request, pathArr, 'PATCH')
  return handleCORS(NextResponse.json({ error: 'route not found' }, { status: 404 }), origin)
}

export async function DELETE(request, { params }) {
  const pathArr = params.path || []
  const origin = request.headers.get('origin')
  if (pathArr[0] === 'turing') return turingProxy(request, pathArr, 'DELETE')
  return handleCORS(NextResponse.json({ error: 'route not found' }, { status: 404 }), origin)
}
