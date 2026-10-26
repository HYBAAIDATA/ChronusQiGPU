'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import { LogOut, Shield } from 'lucide-react'

const NAV_ITEMS = [
  { href: '/home', label: 'Home' },
  { href: '/workbench', label: 'Workbench' },
  { href: '/telemetry', label: 'Telemetry' },
  { href: '/security', label: 'Security' },
  { href: '/themis', label: 'THEMIS' },
  { href: '/al-haras', label: 'AL HARAS' },
  { href: '/millennium', label: 'Millennium' },
  { href: '/research', label: 'Research' },
]

export default function Nav() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout, isAdmin } = useAuth()

  const handleLogout = () => {
    logout()
    router.push('/')
  }

  return (
    <header
      className="sticky top-0 z-50 border-b"
      style={{
        background: 'rgba(0, 33, 71, 0.95)',
        borderColor: 'rgba(127, 184, 221, 0.1)',
        backdropFilter: 'blur(12px)',
      }}
    >
      <div className="container mx-auto px-4 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <div className="flex items-center space-x-6">
            <Link href="/home" className="flex items-center space-x-2">
              <div
                className="w-7 h-7 border rotate-45 flex items-center justify-center"
                style={{ borderColor: 'var(--hyba-gold)' }}
              >
                <div
                  className="w-2.5 h-2.5 -rotate-45"
                  style={{ background: 'var(--hyba-gold)' }}
                />
              </div>
              <span
                className="text-sm font-semibold tracking-[0.2em] uppercase"
                style={{ color: 'var(--hyba-cream)', fontFamily: "'Playfair Display', serif" }}
              >
                HYBA
              </span>
            </Link>

            {/* Nav Links */}
            <nav className="hidden md:flex items-center space-x-6">
              {NAV_ITEMS.map((item) => {
                const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`hyba-nav-link ${isActive ? 'active' : ''}`}
                  >
                    {item.label}
                  </Link>
                )
              })}
              {isAdmin() && (
                <Link
                  href="/admin/users"
                  className={`hyba-nav-link ${pathname.startsWith('/admin') ? 'active' : ''}`}
                >
                  Admin
                </Link>
              )}
            </nav>
          </div>

          {/* User */}
          <div className="flex items-center space-x-3">
            <div className="text-right hidden sm:block">
              <p className="text-xs" style={{ color: 'var(--hyba-light)' }}>{user?.email}</p>
              <p className="text-[10px]" style={{ color: 'var(--hyba-grey)' }}>
                {isAdmin() ? 'Administrator' : 'Authorized User'}
              </p>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded transition-colors"
              style={{ color: 'var(--hyba-grey)' }}
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
