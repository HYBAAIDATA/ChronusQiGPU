'use client'
import { useState } from 'react'
import Nav from '@/components/Nav'
import Link from 'next/link'
import { Users, Package, CreditCard, TrendingUp, Shield, Globe, FileText, Zap, Building2, ChevronRight } from 'lucide-react'

const CONSOLE_MODULES = [
  { href: '/admin/sales', title: 'Sales Dashboard', desc: 'Pipeline, leads, conversions, renewals, expansions', icon: TrendingUp, color: 'var(--hyba-gold)' },
  { href: '/admin/clients', title: 'Client Overview', desc: 'Sector, region, compliance, active products, health score', icon: Building2, color: 'var(--hyba-bright)' },
  { href: '/admin/products', title: 'Product Management', desc: 'One-touch upgrade / downgrade across all client tenants', icon: Package, color: 'var(--hyba-orange)' },
  { href: '/admin/billing', title: 'Billing Integration', desc: 'Per-product, per-seat, per-usage, multi-currency, tax rules', icon: CreditCard, color: 'var(--hyba-primary)' },
  { href: '/admin/users', title: 'User Management', desc: 'Add/remove users, assign roles, enforce compliance', icon: Users, color: 'var(--hyba-light)' },
]

const CLIENT_SECTORS = [
  { name: 'JP Morgan', sector: 'Regulated Finance', tier: 'Enterprise', products: 5, health: 98, seats: 240 },
  { name: 'DIFC', sector: 'Sovereign Fintech', tier: 'Sovereign', products: 6, health: 96, seats: 120 },
  { name: 'Bank of England', sector: 'Central Bank', tier: 'Sovereign', products: 4, health: 99, seats: 80 },
  { name: 'Aramco', sector: 'Industrial Telemetry', tier: 'Enterprise', products: 4, health: 94, seats: 350 },
  { name: 'Government of Dubai', sector: 'National AI', tier: 'Sovereign', products: 8, health: 97, seats: 500 },
]

export default function AdminConsolePage() {
  return (
    <div style={{ background: 'var(--hyba-midnight)', minHeight: '100vh', color: 'var(--hyba-cream)' }}>
      <Nav />
      <main className="container mx-auto px-4 lg:px-8 py-8">
        <div className="mb-8">
          <p className="text-xs tracking-[0.3em] uppercase" style={{ color: 'var(--hyba-gold)' }}>HYBA Team Cockpit</p>
          <h1 className="text-3xl font-bold mt-2" style={{ fontFamily: "'Playfair Display', serif" }}>Sales & Admin Console</h1>
          <p className="text-sm mt-2" style={{ color: 'var(--hyba-grey)' }}>Internal-facing system for sales, support, and engineering — one client at a time.</p>
        </div>

        {/* KPI strip */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          {[
            { label: 'Active Clients', value: '47' },
            { label: 'ARR', value: '$142M' },
            { label: 'Pipeline', value: '$318M' },
            { label: 'NPS', value: '72' },
            { label: 'Uptime', value: '99.99%' },
          ].map(k => (
            <div key={k.label} className="p-4 rounded border" style={{ background: 'rgba(0,66,106,0.2)', borderColor: 'rgba(127,184,221,0.15)' }}>
              <p className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--hyba-grey)' }}>{k.label}</p>
              <p className="text-2xl font-semibold mt-1" style={{ color: 'var(--hyba-gold)', fontFamily: "'Playfair Display', serif" }}>{k.value}</p>
            </div>
          ))}
        </div>

        {/* Module grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-10">
          {CONSOLE_MODULES.map(m => (
            <Link key={m.href} href={m.href} className="group p-5 rounded border transition-all" style={{ background: 'rgba(0,30,60,0.4)', borderColor: 'rgba(127,184,221,0.15)' }}>
              <div className="flex items-start justify-between">
                <m.icon className="w-6 h-6" style={{ color: m.color }} />
                <ChevronRight className="w-4 h-4 opacity-40 group-hover:opacity-100 transition-opacity" />
              </div>
              <h3 className="mt-3 text-base font-semibold">{m.title}</h3>
              <p className="text-xs mt-1" style={{ color: 'var(--hyba-grey)' }}>{m.desc}</p>
            </Link>
          ))}
        </div>

        {/* Sector-adaptive client roster */}
        <div>
          <h2 className="text-lg font-semibold mb-3" style={{ fontFamily: "'Playfair Display', serif" }}>Sector-Adaptive Client Roster</h2>
          <div className="rounded border overflow-hidden" style={{ borderColor: 'rgba(127,184,221,0.15)' }}>
            <table className="w-full text-sm">
              <thead style={{ background: 'rgba(0,66,106,0.3)' }}>
                <tr>
                  {['Client', 'Sector', 'Tier', 'Products', 'Seats', 'Health'].map(h => (
                    <th key={h} className="px-4 py-2 text-left text-[10px] uppercase tracking-widest" style={{ color: 'var(--hyba-grey)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {CLIENT_SECTORS.map(c => (
                  <tr key={c.name} className="border-t" style={{ borderColor: 'rgba(127,184,221,0.08)' }}>
                    <td className="px-4 py-3 font-medium">{c.name}</td>
                    <td className="px-4 py-3" style={{ color: 'var(--hyba-light)' }}>{c.sector}</td>
                    <td className="px-4 py-3"><span className="text-xs px-2 py-0.5 rounded" style={{ background: 'rgba(242,169,0,0.15)', color: 'var(--hyba-gold)' }}>{c.tier}</span></td>
                    <td className="px-4 py-3">{c.products}</td>
                    <td className="px-4 py-3">{c.seats}</td>
                    <td className="px-4 py-3"><span style={{ color: c.health >= 96 ? '#4ade80' : '#facc15' }}>{c.health}%</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  )
}
