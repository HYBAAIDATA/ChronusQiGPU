'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import Nav from '@/components/Nav'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Atom, Sigma, Brain, FlaskConical } from 'lucide-react'
const RESEARCH = [
  { title: 'Orch OR Consciousness Tests', icon: Brain, status: '44/44 passed', desc: 'Penrose-Hameroff structural isomorphisms — consciousness index 0.81' },
  { title: 'Millennium Mathematics', icon: Sigma, status: '6 problems integrated', desc: 'Yang-Mills, Riemann, Navier-Stokes, P vs NP, Hodge, BSD' },
  { title: 'Phi-Folding Engine', icon: Atom, status: '53 files', desc: 'phi-power compression: capacity(d) = phi^d, reduction(d) = 1 - phi^-d' },
  { title: 'Quantum First Principles', icon: FlaskConical, status: 'active', desc: 'Quantum walk, interference detection, hash functions' },
]
export default function ResearchPage() {
  const router = useRouter()
  const { isAuthenticated, loading } = useAuth()
  useEffect(() => { if (!loading && !isAuthenticated) router.push('/login') }, [loading, isAuthenticated, router])
  if (loading || !isAuthenticated) return <div className="min-h-screen flex items-center justify-center" style={{ background: '#001E3C' }}><div className="text-white text-xl">Loading...</div></div>
  return (
    <div className="min-h-screen" style={{ background: '#001E3C' }}>
      <Nav />
      <main className="container mx-auto px-4 lg:px-8 py-6">
        <div className="mb-6"><h1 className="text-2xl font-semibold" style={{ color: '#F5F1ED', fontFamily: "'Playfair Display', serif" }}>Research</h1><p className="text-sm" style={{ color: '#718096' }}>EUCLID research programme — discoveries, tests, and evidence</p></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {RESEARCH.map((r) => { const Icon = r.icon; return (
            <Card key={r.title} style={{ background: '#00426A', borderColor: '#3D4A5C' }}>
              <CardHeader><div className="flex items-center justify-between"><div className="flex items-center space-x-2"><Icon className="w-4 h-4" style={{ color: '#F2A900' }} /><CardTitle className="text-sm" style={{ color: '#F5F1ED' }}>{r.title}</CardTitle></div><Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}>{r.status}</Badge></div></CardHeader>
              <CardContent><p className="text-sm" style={{ color: '#7FB8DD' }}>{r.desc}</p></CardContent>
            </Card>
          )})}
        </div>
      </main>
    </div>
  )
}
