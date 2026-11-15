import { NextRequest, NextResponse } from 'next/server';

const CHRONUS_BACKEND_URL = process.env.CHRONUS_BACKEND_URL?.trim();

function forwardHeaders(req: NextRequest): Headers {
  const headers = new Headers({ Accept: 'application/json' });
  const contentType = req.headers.get('content-type');
  if (contentType) headers.set('content-type', contentType);

  // Forward only the authentication and request-correlation headers the API uses.
  for (const name of [
    'authorization',
    'x-chronus-webhook-signature',
    'x-docusign-signature-1',
    'x-ironclad-signature',
    'x-tenant-id',
    'x-request-id',
  ]) {
    const value = req.headers.get(name);
    if (value) headers.set(name, value);
  }
  return headers;
}

function jsonError(status: number, code: string, message: string) {
  return NextResponse.json({ status: code, error: message }, { status });
}

async function forward(req: NextRequest, params: Promise<{ path: string[] }>, method: string) {
  if (!CHRONUS_BACKEND_URL) {
    return jsonError(
      503,
      'unconfigured',
      'Chronus backend is not configured. Set CHRONUS_BACKEND_URL for the web service.'
    );
  }

  let backend: URL;
  try {
    backend = new URL(CHRONUS_BACKEND_URL);
    if (!['http:', 'https:'].includes(backend.protocol)) throw new Error('Unsupported protocol');
  } catch {
    return jsonError(503, 'unconfigured', 'CHRONUS_BACKEND_URL must be a valid HTTP(S) URL.');
  }

  const resolved = await params;
  if (!resolved.path.length || resolved.path.some((part) => part === '.' || part === '..')) {
    return jsonError(400, 'invalid_path', 'Invalid Chronus API path.');
  }
  const target = new URL(resolved.path.map(encodeURIComponent).join('/'), `${backend.toString().replace(/\/$/, '')}/`);
  target.search = req.nextUrl.search;

  try {
    const body = method === 'GET' ? undefined : await req.text();
    const response = await fetch(target, {
      method,
      headers: forwardHeaders(req),
      body: body || undefined,
      cache: 'no-store',
      redirect: 'manual',
    });
    if (response.status === 204) return new NextResponse(null, { status: 204 });
    const text = await response.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { detail: text };
      }
    }
    return NextResponse.json(data ?? {}, { status: response.status });
  } catch {
    return jsonError(503, 'unavailable', 'Chronus backend could not be reached.');
  }
}

export async function GET(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return forward(req, context.params, 'GET');
}

export async function POST(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return forward(req, context.params, 'POST');
}

export async function PATCH(req: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return forward(req, context.params, 'PATCH');
}
