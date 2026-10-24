'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import Dashboard from '../../components/mining/Dashboard'
import { Button } from '@/components/ui/button'
import { LogOut, Shield } from 'lucide-react'

export default function DashboardPage() {
  const router = useRouter()
  const { user, isAuthenticated, loading, logout, isAdmin } = useAuth()

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push('/login')
    }
  }, [loading, isAuthenticated, router])

  const handleLogout = () => {
    logout()
    router.push('/')
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
        <div className="text-white text-xl">Loading...</div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return null
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <header className="border-b border-slate-700/50 bg-slate-900/50 backdrop-blur-xl">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-blue-500 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xl">E</span>
            </div>
            <div>
              <h1 className="text-white font-bold text-xl">EUCLID Platform</h1>
              <p className="text-slate-400 text-sm">Quantum-Enhanced Mining & Intelligence</p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            {isAdmin() && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push('/admin/users')}
                className="border-purple-500/50 text-purple-400 hover:bg-purple-500/10"
              >
                <Shield className="w-4 h-4 mr-2" />
                User Management
              </Button>
            )}
            <div className="text-right">
              <p className="text-white text-sm font-medium">{user?.email}</p>
              <p className={`text-xs ${isAdmin() ? 'text-purple-400' : 'text-slate-400'}`}>
                {isAdmin() ? 'Administrator' : 'Authorized User'}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleLogout}
              className="border-slate-600 text-slate-300 hover:bg-slate-800"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>
      </header>
      <main className="container mx-auto px-4 py-6">
        <Dashboard initialData={{}} isAdmin={isAdmin()} user={user} />
      </main>
    </div>
  )
}
