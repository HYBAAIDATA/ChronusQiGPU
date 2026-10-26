'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import Nav from '@/components/Nav'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Activity, TrendingUp, Brain, Shield, RefreshCw, Database } from 'lucide-react'
const SUBSYSTEMS = [
  { name: 'Intelligence', icon: Brain, metrics: { 'phi-density': '0.618', 'coherence': '0.81', 'emergence': '4 basins' } },
  { name: 'Learning', icon: TrendingUp, metrics: { 'adaptation rate': '0.73', 'knowledge depth': 'L3', 'convergence': 'stable' } },
  { name: 'Governance', icon: Shield, metrics: { 'fail-closed': 'active', 'release gates': '3/3 pass', 'audit entries': '0' } },
  { name: 'Model', icon: Database, metrics: { 'manifold faces': '32', 'oracle depth': '5', 'cache hit': '94%' } },
  { name: 'Recovery', icon: RefreshCw, metrics: { 'self-heal': 'online', 'bit-rot fixes': '0', 'uptime': '100%' } },
]
export default function TelemetryPage() {
  const router = useRouter()
  const { isAuthenticated, loading } = useAuth()
  useEffect(() => { if (!loading && !isAuthenticated) router.push('/login') }, [loading, isAuthenticated, router])
  if (loading || !isAuthenticated) return <div className="min-h-screen flex items-center justify-center" style={{ background: '#001E3C' }}><div className="text-white text-xl">Loading...</div></div>
  return (
    <div className="min-h-screen" style={{ background: '#001E3C' }}>
      <Nav />
      <main className="container mx-auto px-4 lg:px-8 py-6">
        <div className="mb-6"><h1 className="text-2xl font-semibold" style={{ color: '#F5F1ED', fontFamily: "'Playfair Display', serif" }}>Telemetry</h1><p className="text-sm" style={{ color: '#718096' }}>Organism-level view — subsystem matrix and timeline</p></div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {SUBSYSTEMS.map((s) => { const Icon = s.icon; return (
            <Card key={s.name} style={{ background: '#00426A', borderColor: '#3D4A5C' }}>
              <CardHeader><div className="flex items-center space-x-2"><Icon className="w-4 h-4" style={{ color: '#F2A900' }} /><CardTitle className="text-sm" style={{ color: '#F5F1ED' }}>{s.name}</CardTitle></div></CardHeader>
              <CardContent>{Object.entries(s.metrics).map(([k, v]) => (<div key={k} className="flex justify-between py-1"><span className="text-xs" style={{ color: '#718096' }}>{k}</span><span className="text-xs" style={{ color: '#7FB8DD' }}>{v}</span></div>))}</CardContent>
            </Card>
          )})}
        </div>
        <div className="mt-6"><Card style={{ background: '#00426A', borderColor: '#3D4A5C' }}><CardHeader><CardTitle className="text-sm" style={{ color: '#F5F1ED' }}>Timeline</CardTitle></CardHeader><CardContent><div className="flex items-center space-x-2"><Activity className="w-4 h-4" style={{ color: '#F2A900' }} /><p className="text-xs" style={{ color: '#718096' }}>phi-density, share acceptance, spectral gaps, topology invariants — live timeline (connect to backend /v1/telemetry)</p></div></CardContent></Card></div>
      </main>
    </div>
  )
}
