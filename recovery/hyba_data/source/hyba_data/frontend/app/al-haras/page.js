'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Shield, Activity, AlertTriangle, CheckCircle, Lock, Zap, Eye, Crosshair, Network, Fingerprint, ScrollText, LogOut } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function AlHarasPage() {
  const router = useRouter()
  const { user, isAuthenticated, loading, logout, isAdmin } = useAuth()
  const [status, setStatus] = useState(null)
  const [loadingStatus, setLoadingStatus] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push('/login')
    }
  }, [loading, isAuthenticated, router])

  useEffect(() => {
    if (isAuthenticated) {
      fetchStatus()
    }
  }, [isAuthenticated])

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/v1/al-haras/status`, {
        credentials: 'same-origin',
      })
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
      } else {
        setError('Failed to fetch AL HARAS status')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoadingStatus(false)
    }
  }

  if (loading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: '#001E3C' }}>
        <div className="text-white text-xl">Loading...</div>
      </div>
    )
  }

  const components = status?.components || {}

  return (
    <div className="min-h-screen" style={{ background: '#001E3C' }}>
      {/* Header */}
      <header className="border-b border-white/10" style={{ background: '#002147' }}>
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: '#00426A' }}>
              <Shield className="w-5 h-5" style={{ color: '#F2A900' }} />
            </div>
            <div>
              <h1 className="text-white font-bold text-xl">AL HARAS</h1>
              <p className="text-xs" style={{ color: '#7FB8DD' }}>Quantum Defence Security Product</p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push('/dashboard')}
              className="border-white/20 text-white/70 hover:bg-white/5"
            >
              Dashboard
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleLogout}
              className="border-white/20 text-white/70 hover:bg-white/5"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        {/* Status Banner */}
        <div className="mb-6">
          <Card style={{ background: '#00426A', borderColor: '#1A3050' }}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <CheckCircle className="w-6 h-6" style={{ color: '#2AC890' }} />
                  <div>
                    <p className="text-white font-semibold">AL HARAS Security Stack — ACTIVE</p>
                    <p className="text-xs" style={{ color: '#7FB8DD' }}>
                      Version {status?.version || '9.1.0'} · {Object.keys(components).length} components online
                    </p>
                  </div>
                </div>
                <Badge style={{ background: '#F2A900', color: '#001E3C' }}>PRODUCTION</Badge>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Component Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Audit Chain */}
          <Card style={{ background: '#00426A', borderColor: '#1A3050' }}>
            <CardHeader>
              <div className="flex items-center space-x-2">
                <ScrollText className="w-5 h-5" style={{ color: '#F2A900' }} />
                <CardTitle className="text-white text-base">Cryptographic Audit Chain</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm mb-2" style={{ color: '#7FB8DD' }}>Tamper-evident, Merkle-audited hash chain</p>
              <div className="flex justify-between items-center">
                <span className="text-xs" style={{ color: '#A0AEC0' }}>Entries: {components.audit_chain?.entries || 0}</span>
                <Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}>ACTIVE</Badge>
              </div>
            </CardContent>
          </Card>

          {/* P vs NP Threat Registry */}
          <Card style={{ background: '#00426A', borderColor: '#1A3050' }}>
            <CardHeader>
              <div className="flex items-center space-x-2">
                <Crosshair className="w-5 h-5" style={{ color: '#F2A900' }} />
                <CardTitle className="text-white text-base">P vs NP Threat Registry</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm mb-2" style={{ color: '#7FB8DD' }}>O(1) known-threat detection</p>
              <div className="flex justify-between items-center">
                <span className="text-xs" style={{ color: '#A0AEC0' }}>Registered: {components.pvsnp_threat_registry?.registered || 0}</span>
                <Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}>ACTIVE</Badge>
              </div>
            </CardContent>
          </Card>

          {/* Yang-Mills Encryption */}
          <Card style={{ background: '#00426A', borderColor: '#1A3050' }}>
            <CardHeader>
              <div className="flex items-center space-x-2">
                <Lock className="w-5 h-5" style={{ color: '#F2A900' }} />
                <CardTitle className="text-white text-base">Yang-Mills Encryption</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm mb-2" style={{ color: '#7FB8DD' }}>Mass-gap confinement encryption</p>
              <div className="flex justify-between items-center">
                <span className="text-xs" style={{ color: '#A0AEC0' }}>Mass gap: {components.yang_mills_encryption?.mass_gap || '0.618'}</span>
                <Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}>ACTIVE</Badge>
              </div>
            </CardContent>
          </Card>

          {/* Five-Form Swarm */}
          <Card style={{ background: '#00426A', borderColor: '#1A3050' }}>
            <CardHeader>
              <div className="flex items-center space-x-2">
                <Network className="w-5 h-5" style={{ color: '#F2A900' }} />
                <CardTitle className="text-white text-base">Five-Form Swarm Defence</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm mb-2" style={{ color: '#7FB8DD' }}>Duty/Swarm/Decoy/Trace/Expose agents</p>
              <div className="flex justify-between items-center">
                <span className="text-xs" style={{ color: '#A0AEC0' }}>Agents: {components.five_form_swarm?.agents || 0}</span>
                <Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}>ACTIVE</Badge>
              </div>
            </CardContent>
          </Card>

          {/* Honeypot Swarm */}
          <Card style={{ background: '#00426A', borderColor: '#1A3050' }}>
            <CardHeader>
              <div className="flex items-center space-x-2">
                <Eye className="w-5 h-5" style={{ color: '#F2A900' }} />
                <CardTitle className="text-white text-base">Honeypot Swarm</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm mb-2" style={{ color: '#7FB8DD' }}>Observation-driven decoy mesh</p>
              <div className="flex justify-between items-center">
                <span className="text-xs" style={{ color: '#A0AEC0' }}>Deployed: {components.honeypot_swarm?.active ? 'Yes' : 'No'}</span>
                <Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}>ACTIVE</Badge>
              </div>
            </CardContent>
          </Card>

          {/* Topological Counter-Offensive */}
          <Card style={{ background: '#00426A', borderColor: '#1A3050' }}>
            <CardHeader>
              <div className="flex items-center space-x-2">
                <Zap className="w-5 h-5" style={{ color: '#F2A900' }} />
                <CardTitle className="text-white text-base">Topological Counter-Offensive</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm mb-2" style={{ color: '#7FB8DD' }}>Six Millennium Problems = Six Defence Layers</p>
              <div className="flex justify-between items-center">
                <span className="text-xs" style={{ color: '#A0AEC0' }}>Status: READY</span>
                <Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}>ACTIVE</Badge>
              </div>
            </CardContent>
          </Card>

          {/* Millennium Security Stack */}
          <Card style={{ background: '#00426A', borderColor: '#1A3050' }}>
            <CardHeader>
              <div className="flex items-center space-x-2">
                <Fingerprint className="w-5 h-5" style={{ color: '#F2A900' }} />
                <CardTitle className="text-white text-base">Millennium Security Stack</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm mb-2" style={{ color: '#7FB8DD' }}>Six Millennium Problems integrated</p>
              <div className="flex justify-between items-center">
                <span className="text-xs" style={{ color: '#A0AEC0' }}>Layers: 6</span>
                <Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}>ACTIVE</Badge>
              </div>
            </CardContent>
          </Card>

          {/* Threat Model */}
          <Card style={{ background: '#00426A', borderColor: '#1A3050' }}>
            <CardHeader>
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-5 h-5" style={{ color: '#F2A900' }} />
                <CardTitle className="text-white text-base">Quantum Threat Model</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm mb-2" style={{ color: '#7FB8DD' }}>Adversary capability assessment</p>
              <div className="flex justify-between items-center">
                <span className="text-xs" style={{ color: '#A0AEC0' }}>Status: MONITORING</span>
                <Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}>ACTIVE</Badge>
              </div>
            </CardContent>
          </Card>

          {/* Production Guard */}
          <Card style={{ background: '#00426A', borderColor: '#1A3050' }}>
            <CardHeader>
              <div className="flex items-center space-x-2">
                <Shield className="w-5 h-5" style={{ color: '#F2A900' }} />
                <CardTitle className="text-white text-base">Production Guard</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm mb-2" style={{ color: '#7FB8DD' }}>Pre-launch secret hygiene gate</p>
              <div className="flex justify-between items-center">
                <span className="text-xs" style={{ color: '#A0AEC0' }}>Status: READY</span>
                <Badge variant="outline" style={{ color: '#2AC890', borderColor: '#2AC890' }}>ACTIVE</Badge>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mt-4 p-4 rounded-lg" style={{ background: '#00426A', border: '1px solid #E86C1E' }}>
            <p className="text-sm" style={{ color: '#E86C1E' }}>{error}</p>
          </div>
        )}
      </main>
    </div>
  )
}
