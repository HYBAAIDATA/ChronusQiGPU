'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import Nav from '@/components/Nav'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Scale, FileText, Shield, Globe, BarChart3, FileCheck, AlertCircle, CheckCircle } from 'lucide-react'
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const REGULATIONS = [
  { id: 'basel_iii', name: 'Basel III', jurisdiction: 'Global', icon: Globe },
  { id: 'basel_iv', name: 'Basel IV', jurisdiction: 'Global', icon: Globe },
  { id: 'fca', name: 'FCA Handbook', jurisdiction: 'UK', icon: Scale },
  { id: 'pra', name: 'PRA Rulebook', jurisdiction: 'UK', icon: Scale },
  { id: 'cbuae', name: 'Central Bank UAE', jurisdiction: 'UAE', icon: Scale },
  { id: 'dfsa', name: 'DFSA Rulebook', jurisdiction: 'UAE (DIFC)', icon: Scale },
  { id: 'vara', name: 'VARA Virtual Assets', jurisdiction: 'UAE (Dubai)', icon: Scale },
  { id: 'finra_3110', name: 'FINRA 3110', jurisdiction: 'US', icon: Scale },
  { id: 'sec_15c3_1', name: 'SEC Rule 15c3-1', jurisdiction: 'US', icon: Scale },
  { id: 'sec_15c3_3', name: 'SEC Rule 15c3-3', jurisdiction: 'US', icon: Scale },
  { id: 'sec_606', name: 'SEC Rule 606', jurisdiction: 'US', icon: Scale },
]
const CAPABILITIES = [
  { name: 'Constraint Solving', icon: BarChart3, desc: 'Exact & approximate solvers with phi-optimization' },
  { name: 'Stress Testing', icon: AlertCircle, desc: 'Scenario generation and stress engine' },
  { name: 'Compliance Reports', icon: FileText, desc: 'Audit-ready structured reports for regulators' },
  { name: 'PDF Export', icon: FileCheck, desc: 'McKinsey-style PDF reports for board review' },
  { name: 'Capital Relief', icon: Scale, desc: 'Capital relief calculation and optimization' },
  { name: 'Portfolio Optimization', icon: BarChart3, desc: 'Portfolio optimization under regulatory constraints' },
  { name: 'White Label', icon: Globe, desc: 'Tenant-specific configuration and branding' },
  { name: 'Evidence Generation', icon: Shield, desc: 'Cryptographically-sealed evidence packets' },
]
export default function ThemisPage() {
  const router = useRouter()
  const { isAuthenticated, loading } = useAuth()
  const [status, setStatus] = useState(null)
  useEffect(() => { if (!loading && !isAuthenticated) router.push('/login') }, [loading, isAuthenticated, router])
  useEffect(() => { if (isAuthenticated) fetch(`${API_URL}/v1/themis/status`).then(r => r.json()).then(setStatus).catch(() => {}) }, [isAuthenticated])
  if (loading || !isAuthenticated) return <div className="min-h-screen flex items-center justify-center" style={{ background: '#001E3C' }}><div className="text-white text-xl">Loading...</div></div>
  return (
    <div className="min-h-screen" style={{ background: '#001E3C' }}>
      <Nav />
      <main className="container mx-auto px-4 lg:px-8 py-6">
        <div className="mb-6"><h1 className="text-2xl font-semibold" style={{ color: '#F5F1ED', fontFamily: "'Playfair Display', serif" }}>THEMIS</h1><p className="text-sm" style={{ color: '#718096' }}>Regulatory Constraint Solver & Report Generation — sovereign defence regulatory</p></div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          {CAPABILITIES.map((c) => { const Icon = c.icon; return (
            <Card key={c.name} style={{ background: '#00426A', borderColor: '#3D4A5C' }}><CardContent className="p-3">
              <Icon className="w-4 h-4 mb-2" style={{ color: '#F2A900' }} />
              <p className="text-xs font-semibold" style={{ color: '#F5F1ED' }}>{c.name}</p><p className="text-[10px] mt-1" style={{ color: '#718096' }}>{c.desc}</p>
            </CardContent></Card>
          )})}
        </div>
        <div className="mb-6"><h2 className="text-lg font-semibold mb-3" style={{ color: '#F5F1ED', fontFamily: "'Playfair Display', serif" }}>Supported Regulations</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {REGULATIONS.map((r) => { const Icon = r.icon; return (
              <Card key={r.id} style={{ background: '#00426A', borderColor: '#3D4A5C' }}><CardContent className="p-3">
                <div className="flex items-center justify-between mb-2"><Icon className="w-4 h-4" style={{ color: '#F2A900' }} /><Badge variant="outline" style={{ color: '#7FB8DD', borderColor: '#3D4A5C' }}>{r.jurisdiction}</Badge></div>
                <p className="text-sm font-semibold" style={{ color: '#F5F1ED' }}>{r.name}</p><p className="text-xs" style={{ color: '#718096' }}>{r.id}</p>
              </CardContent></Card>
            )})}
          </div>
        </div>
        {status && (<Card style={{ background: '#00426A', borderColor: '#3D4A5C' }}><CardContent className="p-4"><div className="flex items-center space-x-2 mb-2"><CheckCircle className="w-4 h-4" style={{ color: '#2AC890' }} /><p className="text-sm font-semibold" style={{ color: '#F5F1ED' }}>THEMIS Service Status</p></div><pre className="text-xs" style={{ color: '#7FB8DD' }}>{JSON.stringify(status, null, 2)}</pre></CardContent></Card>)}
      </main>
    </div>
  )
}
