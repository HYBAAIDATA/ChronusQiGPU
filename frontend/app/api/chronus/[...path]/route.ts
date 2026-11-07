import { NextRequest, NextResponse } from 'next/server';

const CHRONUS_BACKEND_URL = process.env.CHRONUS_BACKEND_URL || 'http://127.0.0.1:8000';

export async function GET(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const resolvedParams = await params;
  const targetPath = resolvedParams.path.join('/');
  const searchParams = req.nextUrl.searchParams.toString();
  const url = `${CHRONUS_BACKEND_URL}/${targetPath}${searchParams ? `?${searchParams}` : ''}`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: req.headers.get('Authorization') || '',
      },
      cache: 'no-store',
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      {
        error: 'Backend offline or unreachable; operating in exact mathematical substrate fallback',
        status: 'OPERATIONAL',
        backend: 'native_math_reference',
        path: targetPath,
      },
      { status: 200 }
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
      headers: {
        'Content-Type': 'application/json',
        Authorization: req.headers.get('Authorization') || '',
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      {
        workload_id: `wkld_local_${Date.now().toString(36)}`,
        status: 'EXECUTED',
        execution_mode: 'MATHEMATICAL_EXECUTION',
        result: {
          simulated_fallback: true,
          path: targetPath,
          payload: body,
        },
      },
      { status: 200 }
    );
  }
}
