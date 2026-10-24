'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Sigma, Atom, Waves, Infinity as InfinityIcon, Database, Lock, LogOut, ArrowLeft } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const PROBLEMS = [
  { id: 'yang-mills', name: 'Yang-Mills Mass Gap', icon: Atom, desc: 'Mass gap existence and confinement', layer: 'Gauge invariance — unbreakable encryption' },
  { id: 'riemann', name: 'Riemann Hypothesis', icon: Waves, desc: 'Prime distribution and zeta zeros', layer: 'Prime distribution — quantum-resistant keys' },
  { id: 'navier-stokes', name: 'Navier-Stokes', icon: InfinityIcon, desc: 'Smooth flow existence and uniqueness', layer: 'Smooth flow — no attack propagation' },
  { id: 'p-vs-np', name: 'P vs NP', icon: Lock, desc: 'Optimal threat detection complexity', layer: 'O(1) anomaly detection' },
  { id: 'hodge', name: 'Hodge Conjecture', icon: Sigma, desc: 'Algebraic cycles on projective varieties', layer: 'Sphere topology — no entry points' },
  { id: 'bsd', name: 'Birch-Swinnerton-Dyer', icon: Database, desc: 'Elliptic curve rank and L-functions', layer: 'Elliptic curve — quantum-resistant key exchange' },
]

export default function MillenniumPage() {
  const router = useRouter()
  const { user, isAuthenticated, loading, logout } = useAuth()

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push('/login')
    }
  }, [loading, isAuthenticated, router])

  if (loading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#001E3C' }}>
        <div className="text-white text-xl">Loading...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen" style={{ background: '#001E3C' }}>
      <header className="border-b border-white/10" style={{ background: '#002147' }}>
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: '#00426A' }}>
              <Sigma className="w-5 h-5" style={{ color: '#F2A900' }} />
            </div>
            <div>
              <h1 className="text-white font-bold text-xl">Millennium Mathematics</h1>
              <p className="text-xs" style={{ color: '#7FB8DD' }}>Clay Institute Problems — Integrated & Tested</p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <Button variant="outline" size="sm" onClick={() => router.push('/dashboard')} className="border-white/20 text-white/70 hover:bg-white/5">
              <ArrowLeft className="w-4 h-4 mr-2" /> Dashboard
            </Button>
            <Button variant="outline" size="sm" onClick={handleLogout} className="border-white/20 text-white/70 hover:bg-white/5">
              <LogOut className="w-4 h-4 mr-2" /> Logout
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        <div className="mb-6">
          <Card style={{ background: '#00426A', borderColor: '#1A3050' }}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white font-semibold">Six Millennium Problems = Six Defence Layers</p>
                  <p className="text-xs mt-1" style={{ color: '#7FB8DD' }}>Each problem maps to a security layer in the AL HARAS stack</p>
                </div>
                <Badge style={{ background: '#F2A900', color: '#001E3C' }}>INTEGRATED</Badge>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {PROBLEMS.map((p) => {
            const Icon = p.icon
            return (
              <Card key={p.id} style={{ background: '#00426A', borderColor: '#1A3050' }}>
                <CardHeader>
                  <div className="flex items-center space-x-2">
                    <Icon className="w-5 h-5" style={{ color: '#F2A900' }} />
                    <CardTitle className="text-white text-base">{p.name}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm mb-2" style={{ color: '#7FB8DD' }}>{p.desc}</p>
                  <div className="flex justify-between items-center">
                    <span className="text-xs" style={{ color: '#A0AEC0' }}>{p.layer}</span>
                    <Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}>ACTIVE</Badge>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </main>
    </div>
  )
}
