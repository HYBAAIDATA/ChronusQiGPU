'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import Nav from '@/components/Nav'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Database, Cpu, Atom, Shield, Search, Activity, CheckCircle } from 'lucide-react'
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const PANELS = [
  { key: 'pulvini', label: 'PULVINI', icon: Database, desc: 'Memory Compression', status: 'online' },
  { key: 'backend', label: 'HYBA Backend', icon: Activity, desc: 'API & Compute', status: 'online' },
  { key: 'gpu', label: 'GPU Fabric', icon: Cpu, desc: 'HERMES Acceleration', status: 'online' },
  { key: 'quantum', label: 'Quantum Sandbox', icon: Atom, desc: 'VQC & Simulators', status: 'online' },
  { key: 'security', label: 'Security Posture', icon: Shield, desc: 'AL HARAS Active', status: 'online' },
  { key: 'search', label: 'Manifold Search', icon: Search, desc: 'Geodesic Navigation', status: 'online' },
]
const TILES = [
  { key: 'compression', label: 'Compression', icon: Database, metric: '85.4%', sub: 'W-reduction (M2, d=4)', color: 'gold' },
  { key: 'gpu', label: 'GPU Scaling', icon: Cpu, metric: '12 active', sub: 'jobs across 4 nodes', color: 'blue' },
  { key: 'vqc', label: 'Virtual QC', icon: Atom, metric: '1,247', sub: 'circuits executed', color: 'blue' },
  { key: 'security', label: 'Security', icon: Shield, metric: '0 incidents', sub: 'audit chain verified', color: 'green' },
  { key: 'search', label: 'Search', icon: Search, metric: '0.3ms', sub: 'avg geodesic query', color: 'blue' },
]
export default function HomePage() {
  const router = useRouter()
  const { isAuthenticated, loading } = useAuth()
  const [health, setHealth] = useState(null)
  useEffect(() => { if (!loading && !isAuthenticated) router.push('/login') }, [loading, isAuthenticated, router])
  useEffect(() => { if (isAuthenticated) fetch(`${API_URL}/health`).then(r => r.json()).then(setHealth).catch(() => {}) }, [isAuthenticated])
  if (loading || !isAuthenticated) return <div className="min-h-screen flex items-center justify-center" style={{ background: '#001E3C' }}><div className="text-white text-xl">Loading...</div></div>
  return (
    <div className="min-h-screen" style={{ background: '#001E3C' }}>
      <Nav />
      <main className="container mx-auto px-4 lg:px-8 py-6">
        <div className="mb-6"><h1 className="text-2xl font-semibold mb-1" style={{ color: '#F5F1ED', fontFamily: "'Playfair Display', serif" }}>System Overview</h1><p className="text-sm" style={{ color: '#718096' }}>HYBA Data — Computational Intelligence as a Service</p></div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
          {PANELS.map((p) => { const Icon = p.icon; return (
            <Card key={p.key} style={{ background: '#00426A', borderColor: '#3D4A5C' }}><CardContent className="p-3">
              <div className="flex items-center justify-between mb-2"><Icon className="w-4 h-4" style={{ color: '#F2A900' }} /><span className="hyba-status-dot online" /></div>
              <p className="text-xs font-semibold" style={{ color: '#F5F1ED' }}>{p.label}</p><p className="text-[10px]" style={{ color: '#718096' }}>{p.desc}</p>
            </CardContent></Card>
          )})}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {TILES.map((t) => { const Icon = t.icon; const mc = t.color === 'gold' ? '#F2A900' : t.color === 'green' ? '#2AC890' : '#009FDA'; return (
            <Card key={t.key} style={{ background: '#00426A', borderColor: '#3D4A5C' }}>
              <CardHeader className="pb-2"><div className="flex items-center space-x-2"><Icon className="w-4 h-4" style={{ color: '#F2A900' }} /><CardTitle className="text-sm" style={{ color: '#F5F1ED' }}>{t.label}</CardTitle></div></CardHeader>
              <CardContent><p className="text-2xl font-semibold" style={{ color: mc, fontFamily: "'Playfair Display', serif" }}>{t.metric}</p><p className="text-xs mt-1" style={{ color: '#718096' }}>{t.sub}</p></CardContent>
            </Card>
          )})}
        </div>
        {health && (<div className="mt-6"><Card style={{ background: '#00426A', borderColor: '#3D4A5C' }}><CardContent className="p-4"><div className="flex items-center space-x-2 mb-2"><CheckCircle className="w-4 h-4" style={{ color: '#2AC890' }} /><p className="text-sm font-semibold" style={{ color: '#F5F1ED' }}>Backend Health</p></div><pre className="text-xs" style={{ color: '#7FB8DD' }}>{JSON.stringify(health, null, 2)}</pre></CardContent></Card></div>)}
      </main>
    </div>
  )
}
