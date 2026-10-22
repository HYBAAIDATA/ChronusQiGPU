'use client'
import Nav from '@/components/Nav'
import { TrendingUp, Users, Target, DollarSign } from 'lucide-react'

const STAGES = [
  { name: 'Leads', count: 84, value: '$212M', color: 'var(--hyba-light)' },
  { name: 'Qualified', count: 42, value: '$164M', color: 'var(--hyba-bright)' },
  { name: 'Trials', count: 18, value: '$88M', color: 'var(--hyba-primary)' },
  { name: 'Negotiation', count: 9, value: '$62M', color: 'var(--hyba-orange)' },
  { name: 'Won', count: 6, value: '$34M', color: 'var(--hyba-gold)' },
]

const RECENT = [
  { client: 'JP Morgan', event: 'Upgraded to Enterprise (PULVINI +80 seats)', ts: '2h ago', value: '+$1.2M ARR' },
  { client: 'DIFC', event: 'Signed Sovereign THEMIS + AL HARAS bundle', ts: '5h ago', value: '+$4.8M ARR' },
  { client: 'Bank of England', event: 'Renewed 3-year Sovereign contract', ts: '1d ago', value: '+$12M TCV' },
  { client: 'Aramco', event: 'Added HERMES to industrial telemetry stack', ts: '2d ago', value: '+$2.6M ARR' },
  { client: 'Government of Dubai', event: 'Expansion: +8 connectors, +200 seats', ts: '3d ago', value: '+$3.4M ARR' },
]

export default function SalesDashboardPage() {
  return (
    <div style={{ background: 'var(--hyba-midnight)', minHeight: '100vh', color: 'var(--hyba-cream)' }}>
      <Nav />
      <main className="container mx-auto px-4 lg:px-8 py-8">
        <div className="mb-8">
          <p className="text-xs tracking-[0.3em] uppercase" style={{ color: 'var(--hyba-gold)' }}>Pipeline · Conversions · Renewals</p>
          <h1 className="text-3xl font-bold mt-2" style={{ fontFamily: "'Playfair Display', serif" }}>Sales Dashboard</h1>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[{ label: 'Pipeline Value', value: '$318M', icon: DollarSign }, { label: 'Active Deals', value: '69', icon: Target }, { label: 'Win Rate', value: '34%', icon: TrendingUp }, { label: 'New Logos QTD', value: '11', icon: Users }].map(k => (
            <div key={k.label} className="p-4 rounded border" style={{ background: 'rgba(0,66,106,0.2)', borderColor: 'rgba(127,184,221,0.15)' }}>
              <k.icon className="w-5 h-5 mb-2" style={{ color: 'var(--hyba-gold)' }} />
              <p className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--hyba-grey)' }}>{k.label}</p>
              <p className="text-2xl font-semibold mt-1" style={{ fontFamily: "'Playfair Display', serif" }}>{k.value}</p>
            </div>
          ))}
        </div>

        <h2 className="text-sm uppercase tracking-widest mb-3" style={{ color: 'var(--hyba-gold)' }}>Pipeline Stages</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
          {STAGES.map(s => (
            <div key={s.name} className="p-4 rounded border" style={{ background: 'rgba(0,30,60,0.5)', borderColor: 'rgba(127,184,221,0.15)' }}>
              <div className="w-full h-1 rounded" style={{ background: s.color }} />
              <p className="text-xs mt-2 uppercase tracking-widest" style={{ color: 'var(--hyba-grey)' }}>{s.name}</p>
              <p className="text-2xl font-semibold mt-1">{s.count}</p>
              <p className="text-xs" style={{ color: 'var(--hyba-light)' }}>{s.value}</p>
            </div>
          ))}
        </div>

        <h2 className="text-sm uppercase tracking-widest mb-3" style={{ color: 'var(--hyba-gold)' }}>Recent Events</h2>
        <div className="space-y-2">
          {RECENT.map((r, i) => (
            <div key={i} className="p-3 rounded border flex items-center justify-between text-sm" style={{ background: 'rgba(0,30,60,0.4)', borderColor: 'rgba(127,184,221,0.15)' }}>
              <div>
                <p className="font-semibold">{r.client}</p>
                <p className="text-xs" style={{ color: 'var(--hyba-grey)' }}>{r.event}</p>
              </div>
              <div className="text-right">
                <p style={{ color: 'var(--hyba-gold)' }}>{r.value}</p>
                <p className="text-xs" style={{ color: 'var(--hyba-grey)' }}>{r.ts}</p>
              </div>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
