'use client'
import Nav from '@/components/Nav'
import { CreditCard, Globe, FileText, Zap } from 'lucide-react'

const MODELS = [
  { name: 'Per-Product', desc: 'Flat license per product per year', example: 'PULVINI Enterprise: $180K/yr', color: 'var(--hyba-gold)' },
  { name: 'Per-Seat', desc: 'Priced by active seats per month', example: 'AL HARAS: $2,400/seat/mo', color: 'var(--hyba-bright)' },
  { name: 'Per-Usage', desc: 'GPU-hours, folds, quantum shots', example: 'HERMES: $0.014 / GPU-hour', color: 'var(--hyba-orange)' },
  { name: 'Gain-Share', desc: 'HYBA earns a share of measured savings', example: 'Pulvini: 25% of VRAM Δcost', color: 'var(--hyba-primary)' },
  { name: 'Enterprise Invoice', desc: 'Multi-currency, quarterly billing', example: 'Sovereign contracts ≥ $10M TCV', color: 'var(--hyba-light)' },
]

const INVOICES = [
  { client: 'JP Morgan', period: '2026-Q3', amount: '$2,840,000', currency: 'USD', status: 'Paid' },
  { client: 'DIFC', period: '2026-Q3', amount: 'د.إ 12,450,000', currency: 'AED', status: 'Paid' },
  { client: 'Bank of England', period: '2026-Q3', amount: '£1,940,000', currency: 'GBP', status: 'Pending' },
  { client: 'Aramco', period: '2026-Q3', amount: 'SAR 9,620,000', currency: 'SAR', status: 'Paid' },
  { client: 'Government of Dubai', period: '2026-Q3', amount: 'د.إ 21,300,000', currency: 'AED', status: 'Invoiced' },
]

export default function BillingPage() {
  return (
    <div style={{ background: 'var(--hyba-midnight)', minHeight: '100vh', color: 'var(--hyba-cream)' }}>
      <Nav />
      <main className="container mx-auto px-4 lg:px-8 py-8">
        <div className="mb-8">
          <p className="text-xs tracking-[0.3em] uppercase" style={{ color: 'var(--hyba-gold)' }}>Multi-Currency · Multi-Region · Multi-Model</p>
          <h1 className="text-3xl font-bold mt-2" style={{ fontFamily: "'Playfair Display', serif" }}>Billing Integration</h1>
        </div>

        <h2 className="text-sm uppercase tracking-widest mb-3" style={{ color: 'var(--hyba-gold)' }}>Pricing Models</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-8">
          {MODELS.map(m => (
            <div key={m.name} className="p-4 rounded border" style={{ background: 'rgba(0,30,60,0.5)', borderColor: 'rgba(127,184,221,0.15)' }}>
              <div className="w-8 h-0.5 mb-3" style={{ background: m.color }} />
              <p className="font-semibold">{m.name}</p>
              <p className="text-xs mt-1" style={{ color: 'var(--hyba-grey)' }}>{m.desc}</p>
              <p className="text-xs mt-3" style={{ color: 'var(--hyba-light)' }}>{m.example}</p>
            </div>
          ))}
        </div>

        <h2 className="text-sm uppercase tracking-widest mb-3" style={{ color: 'var(--hyba-gold)' }}>Recent Invoices</h2>
        <div className="rounded border overflow-hidden" style={{ borderColor: 'rgba(127,184,221,0.15)' }}>
          <table className="w-full text-sm">
            <thead style={{ background: 'rgba(0,66,106,0.3)' }}>
              <tr>
                {['Client', 'Period', 'Amount', 'Currency', 'Status'].map(h => (
                  <th key={h} className="px-4 py-2 text-left text-[10px] uppercase tracking-widest" style={{ color: 'var(--hyba-grey)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {INVOICES.map((r, i) => (
                <tr key={i} className="border-t" style={{ borderColor: 'rgba(127,184,221,0.08)' }}>
                  <td className="px-4 py-3 font-medium">{r.client}</td>
                  <td className="px-4 py-3" style={{ color: 'var(--hyba-light)' }}>{r.period}</td>
                  <td className="px-4 py-3">{r.amount}</td>
                  <td className="px-4 py-3" style={{ color: 'var(--hyba-grey)' }}>{r.currency}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-2 py-0.5 rounded" style={{ background: r.status === 'Paid' ? 'rgba(74,222,128,0.15)' : r.status === 'Pending' ? 'rgba(250,204,21,0.15)' : 'rgba(127,184,221,0.15)', color: r.status === 'Paid' ? '#4ade80' : r.status === 'Pending' ? '#facc15' : 'var(--hyba-light)' }}>{r.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  )
}
