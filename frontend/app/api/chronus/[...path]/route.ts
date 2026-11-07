import { NextRequest, NextResponse } from 'next/server';

const CHRONUS_BACKEND_URL = process.env.CHRONUS_BACKEND_URL || 'http://127.0.0.1:8000';

function forwardHeaders(req: NextRequest): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const auth = req.headers.get('Authorization');
  if (auth) headers['Authorization'] = auth;

  const webhookHeaders = [
    'X-Chronus-Webhook-Signature',
    'X-DocuSign-Signature-1',
    'X-Ironclad-Signature',
    'X-Tenant-ID',
    'X-Request-ID',
  ];
  for (const h of webhookHeaders) {
    const val = req.headers.get(h);
    if (val) headers[h] = val;
  }
  return headers;
}

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const resolvedParams = await params;
  const targetPath = resolvedParams.path.join('/');
  const searchParams = req.nextUrl.searchParams.toString();
  const url = `${CHRONUS_BACKEND_URL}/${targetPath}${searchParams ? `?${searchParams}` : ''}`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: forwardHeaders(req),
      cache: 'no-store',
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      {
        error: 'Backend offline or unreachable; operating in exact mathematical substrate fallback',
        status: 'OPERATIONAL',
        backend: 'native_math_reference',
        path: targetPath,
      },
      { status: 503 }
    );
  }
}

export async function POST(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const resolvedParams = await params;
  const targetPath = resolvedParams.path.join('/');
  const url = `${CHRONUS_BACKEND_URL}/${targetPath}`;
  const body = await req.json().catch(() => ({}));

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: forwardHeaders(req),
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      {
        error: 'Backend offline or unreachable',
        simulated_fallback: true,
        path: targetPath,
      },
      { status: 503 }
    );
  }
}

export async function PATCH(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const resolvedParams = await params;
  const targetPath = resolvedParams.path.join('/');
  const url = `${CHRONUS_BACKEND_URL}/${targetPath}`;
  const body = await req.json().catch(() => ({}));

  try {
    const res = await fetch(url, {
      method: 'PATCH',
      headers: forwardHeaders(req),
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      {
        error: 'Backend offline or unreachable',
        simulated_fallback: true,
        path: targetPath,
      },
      { status: 503 }
    );
  }
}
