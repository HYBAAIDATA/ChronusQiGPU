'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import Nav from '@/components/Nav'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Shield, FileJson, Lock, CheckCircle, AlertTriangle, ScrollText } from 'lucide-react'
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const CONFIG_ROWS = [
  { feature: 'CORS', enabled: 'localhost:3000 only', safe: true },
  { feature: 'Auth middleware', enabled: 'cookie-based JWT', safe: true },
  { feature: 'AL HARAS mount', enabled: 'startup (v1/al-haras/*)', safe: true },
  { feature: 'Zero-trust RBAC', enabled: 'module exists, not wired', safe: false },
  { feature: 'Data sovereignty', enabled: 'module exists, not wired', safe: false },
  { feature: 'Salamander self-heal', enabled: 'module exists', safe: true },
  { feature: 'Fail-closed gates', enabled: 'production_guard.py', safe: true },
]
export default function SecurityPage() {
  const router = useRouter()
  const { isAuthenticated, loading } = useAuth()
  const [status, setStatus] = useState(null)
  useEffect(() => { if (!loading && !isAuthenticated) router.push('/login') }, [loading, isAuthenticated, router])
  useEffect(() => { if (isAuthenticated) fetch(`${API_URL}/v1/al-haras/status`).then(r => r.json()).then(setStatus).catch(() => {}) }, [isAuthenticated])
  if (loading || !isAuthenticated) return <div className="min-h-screen flex items-center justify-center" style={{ background: '#001E3C' }}><div className="text-white text-xl">Loading...</div></div>
  return (
    <div className="min-h-screen" style={{ background: '#001E3C' }}>
      <Nav />
      <main className="container mx-auto px-4 lg:px-8 py-6">
        <div className="mb-6"><h1 className="text-2xl font-semibold" style={{ color: '#F5F1ED', fontFamily: "'Playfair Display', serif" }}>Security & Governance</h1><p className="text-sm" style={{ color: '#718096' }}>Config truth table, doctrine view, evidence browser</p></div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <Card style={{ background: '#00426A', borderColor: '#3D4A5C' }}><CardHeader><CardTitle className="text-sm" style={{ color: '#F5F1ED' }}>Config Truth Table</CardTitle></CardHeader><CardContent><div className="space-y-2">{CONFIG_ROWS.map((r) => (<div key={r.feature} className="flex items-center justify-between"><div><span className="text-sm" style={{ color: '#F5F1ED' }}>{r.feature}</span><p className="text-xs" style={{ color: '#718096' }}>{r.enabled}</p></div>{r.safe ? <Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}><CheckCircle className="w-3 h-3 mr-1" />SAFE</Badge> : <Badge variant="outline" style={{ color: '#E86C1E', borderColor: '#E86C1E' }}><AlertTriangle className="w-3 h-3 mr-1" />GAP</Badge>}</div>))}</div></CardContent></Card>
          <Card style={{ background: '#00426A', borderColor: '#3D4A5C' }}><CardHeader><CardTitle className="text-sm" style={{ color: '#F5F1ED' }}>Doctrine View</CardTitle></CardHeader><CardContent><div className="space-y-2"><div className="flex items-center space-x-2"><Shield className="w-4 h-4" style={{ color: '#F2A900' }} /><span className="text-sm" style={{ color: '#7FB8DD' }}>Salamander: self-heal online</span></div><div className="flex items-center space-x-2"><Lock className="w-4 h-4" style={{ color: '#F2A900' }} /><span className="text-sm" style={{ color: '#7FB8DD' }}>Fail-closed: production_guard active</span></div><div className="flex items-center space-x-2"><ScrollText className="w-4 h-4" style={{ color: '#F2A900' }} /><span className="text-sm" style={{ color: '#7FB8DD' }}>Release gates: 3/3 pass</span></div></div></CardContent></Card>
        </div>
        <Card style={{ background: '#00426A', borderColor: '#3D4A5C' }}><CardHeader><CardTitle className="text-sm" style={{ color: '#F5F1ED' }}>Evidence Browser</CardTitle></CardHeader><CardContent><Button variant="outline" size="sm" className="border-white/20 text-white/70"><FileJson className="w-3.5 h-3.5 mr-1.5" />Browse JSON Artifacts</Button></CardContent></Card>
      </main>
    </div>
  )
}
