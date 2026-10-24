'use client'
import Nav from '@/components/Nav'
import { useState } from 'react'

const CLIENTS = [
  { name: 'JP Morgan', sector: 'Regulated Finance', region: 'US/UK', compliance: 'FCA + PRA + SEC', products: ['PULVINI', 'HERMES', 'AL HARAS', 'THEMIS', 'Manifold'], seats: 240, tier: 'Enterprise', health: 98, renewal: '2027-03-14', posture: 'Fail-closed · evidence-bound' },
  { name: 'DIFC', sector: 'Sovereign Fintech', region: 'UAE', compliance: 'DFSA + CBUAE + VARA', products: ['PULVINI', 'HERMES', 'VQC', 'AL HARAS', 'THEMIS', 'Manifold'], seats: 120, tier: 'Sovereign', health: 96, renewal: '2028-11-02', posture: 'Sovereign residency · evidence-bound' },
  { name: 'Bank of England', sector: 'Central Bank', region: 'UK', compliance: 'PRA + FPC', products: ['PULVINI', 'HERMES', 'THEMIS', 'Manifold'], seats: 80, tier: 'Sovereign', health: 99, renewal: '2029-04-30', posture: 'Fail-closed · audited quarterly' },
  { name: 'Aramco', sector: 'Industrial Telemetry', region: 'KSA', compliance: 'NCA + SAMA', products: ['PULVINI', 'HERMES', 'AL HARAS', 'Manifold'], seats: 350, tier: 'Enterprise', health: 94, renewal: '2027-09-18', posture: 'SCADA-gated · evidence-bound' },
  { name: 'Government of Dubai', sector: 'National AI', region: 'UAE', compliance: 'DDA + VARA + CBUAE', products: ['PULVINI', 'HERMES', 'VQC', 'AL HARAS', 'THEMIS', 'Manifold', 'PRISMA', 'Allegro'], seats: 500, tier: 'Sovereign', health: 97, renewal: '2029-01-01', posture: 'National-scale · evidence-bound' },
]

export default function ClientsPage() {
  const [active, setActive] = useState(CLIENTS[0])
  return (
    <div style={{ background: 'var(--hyba-midnight)', minHeight: '100vh', color: 'var(--hyba-cream)' }}>
      <Nav />
      <main className="container mx-auto px-4 lg:px-8 py-8">
        <div className="mb-8">
          <p className="text-xs tracking-[0.3em] uppercase" style={{ color: 'var(--hyba-gold)' }}>Sector-Adaptive Cockpit</p>
          <h1 className="text-3xl font-bold mt-2" style={{ fontFamily: "'Playfair Display', serif" }}>Client Overview</h1>
          <p className="text-sm mt-2" style={{ color: 'var(--hyba-grey)' }}>Every client sees a different HYBA — but HYBA sees one client.</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="space-y-2">
            {CLIENTS.map(c => (
              <button key={c.name} onClick={() => setActive(c)} className="w-full text-left p-3 rounded border transition-colors" style={{ background: active.name === c.name ? 'rgba(242,169,0,0.1)' : 'rgba(0,30,60,0.4)', borderColor: active.name === c.name ? 'var(--hyba-gold)' : 'rgba(127,184,221,0.15)' }}>
                <p className="font-semibold">{c.name}</p>
                <p className="text-xs" style={{ color: 'var(--hyba-grey)' }}>{c.sector} · {c.region}</p>
              </button>
            ))}
          </div>

          <div className="lg:col-span-2 p-5 rounded border" style={{ background: 'rgba(0,30,60,0.5)', borderColor: 'rgba(127,184,221,0.15)' }}>
            <h2 className="text-xl font-semibold" style={{ fontFamily: "'Playfair Display', serif" }}>{active.name}</h2>
            <p className="text-sm" style={{ color: 'var(--hyba-light)' }}>{active.sector}</p>
            <div className="grid grid-cols-2 gap-4 mt-6 text-sm">
              {[['Region', active.region], ['Compliance', active.compliance], ['Tier', active.tier], ['Seats', active.seats], ['Health', active.health + '%'], ['Renewal', active.renewal], ['Posture', active.posture]].map(([k, v]) => (
                <div key={k}>
                  <p className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--hyba-grey)' }}>{k}</p>
                  <p className="mt-1">{v}</p>
                </div>
              ))}
            </div>
            <div className="mt-5">
              <p className="text-[10px] uppercase tracking-widest mb-2" style={{ color: 'var(--hyba-grey)' }}>Active Products</p>
              <div className="flex flex-wrap gap-2">
                {active.products.map(p => <span key={p} className="text-xs px-2 py-1 rounded border" style={{ borderColor: 'rgba(242,169,0,0.3)', color: 'var(--hyba-gold)' }}>{p}</span>)}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
