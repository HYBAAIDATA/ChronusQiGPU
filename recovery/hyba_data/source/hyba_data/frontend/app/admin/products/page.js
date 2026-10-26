'use client'
import { useState } from 'react'
import Nav from '@/components/Nav'
import { ChevronUp, ChevronDown, Zap, Shield, Cpu, Database, Search, Scale, Users, Package } from 'lucide-react'

const PRODUCTS = [
  { id: 'pulvini', name: 'PULVINI', desc: 'Memory Compression (φ-folding)', icon: Database, tier: 'Enterprise', seats: 240, connectors: 12 },
  { id: 'hermes', name: 'HERMES', desc: 'GPU Scaling & Acceleration', icon: Cpu, tier: 'Enterprise', seats: 240, connectors: 8 },
  { id: 'vqc', name: 'VQC', desc: 'Virtual Quantum Computer', icon: Zap, tier: 'Sovereign', seats: 40, connectors: 3 },
  { id: 'al-haras', name: 'AL HARAS', desc: 'Unhackable Security Substrate', icon: Shield, tier: 'Sovereign', seats: 40, connectors: 6 },
  { id: 'themis', name: 'THEMIS', desc: 'Regulatory Report Generation', icon: Scale, tier: 'Enterprise', seats: 120, connectors: 14 },
  { id: 'manifold', name: 'Manifold Search', desc: 'Geodesic Intelligence Search', icon: Search, tier: 'Growth', seats: 60, connectors: 4 },
]

const TIERS = ['Trial', 'Growth', 'Enterprise', 'Sovereign']

export default function ProductsAdminPage() {
  const [items, setItems] = useState(PRODUCTS)
  const [activity, setActivity] = useState([])

  const change = (id, field, delta) => {
    setItems(prev => prev.map(p => {
      if (p.id !== id) return p
      if (field === 'tier') {
        const idx = Math.max(0, Math.min(TIERS.length - 1, TIERS.indexOf(p.tier) + delta))
        const next = { ...p, tier: TIERS[idx] }
        setActivity(a => [{ ts: new Date().toLocaleTimeString(), msg: `${p.name}: ${delta > 0 ? 'Upgraded' : 'Downgraded'} to ${TIERS[idx]}` }, ...a].slice(0, 8))
        return next
      }
      const next = { ...p, [field]: Math.max(0, p[field] + delta) }
      setActivity(a => [{ ts: new Date().toLocaleTimeString(), msg: `${p.name}: ${field} ${delta > 0 ? '+' : ''}${delta}` }, ...a].slice(0, 8))
      return next
    }))
  }

  return (
    <div style={{ background: 'var(--hyba-midnight)', minHeight: '100vh', color: 'var(--hyba-cream)' }}>
      <Nav />
      <main className="container mx-auto px-4 lg:px-8 py-8">
        <div className="mb-8">
          <p className="text-xs tracking-[0.3em] uppercase" style={{ color: 'var(--hyba-gold)' }}>One-Touch Upgrade / Downgrade</p>
          <h1 className="text-3xl font-bold mt-2" style={{ fontFamily: "'Playfair Display', serif" }}>Product Management</h1>
          <p className="text-sm mt-2" style={{ color: 'var(--hyba-grey)' }}>Instant activation — no downtime, no support tickets. Every change is billed, evidenced, and audit-logged.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-3">
            {items.map(p => (
              <div key={p.id} className="p-4 rounded border" style={{ background: 'rgba(0,30,60,0.5)', borderColor: 'rgba(127,184,221,0.15)' }}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <p.icon className="w-6 h-6" style={{ color: 'var(--hyba-gold)' }} />
                    <div>
                      <p className="font-semibold">{p.name}</p>
                      <p className="text-xs" style={{ color: 'var(--hyba-grey)' }}>{p.desc}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    {['tier', 'seats', 'connectors'].map(f => (
                      <div key={f} className="flex flex-col items-center">
                        <p className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--hyba-grey)' }}>{f}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <button onClick={() => change(p.id, f, -1)} className="p-1 rounded border" style={{ borderColor: 'rgba(232,108,30,0.4)', color: 'var(--hyba-orange)' }}><ChevronDown className="w-3 h-3" /></button>
                          <span className="min-w-[70px] text-center text-sm font-semibold">{p[f]}</span>
                          <button onClick={() => change(p.id, f, 1)} className="p-1 rounded border" style={{ borderColor: 'rgba(242,169,0,0.4)', color: 'var(--hyba-gold)' }}><ChevronUp className="w-3 h-3" /></button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div>
            <h2 className="text-sm uppercase tracking-widest mb-3" style={{ color: 'var(--hyba-gold)' }}>Live Activity</h2>
            <div className="rounded border p-3 space-y-2 text-xs" style={{ background: 'rgba(0,30,60,0.4)', borderColor: 'rgba(127,184,221,0.15)' }}>
              {activity.length === 0 && <p style={{ color: 'var(--hyba-grey)' }}>No changes yet — try upgrading or downgrading.</p>}
              {activity.map((a, i) => (
                <div key={i} className="flex justify-between">
                  <span>{a.msg}</span>
                  <span style={{ color: 'var(--hyba-grey)' }}>{a.ts}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
