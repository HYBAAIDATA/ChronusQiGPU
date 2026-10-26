'use client'

import { useRouter } from 'next/navigation'
import { ArrowRight } from 'lucide-react'

export default function LandingPage() {
  const router = useRouter()

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white overflow-hidden relative">
      {/* Subtle geometric background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          className="landing-geo-animate absolute -top-1/2 -right-1/4 w-[800px] h-[800px] border border-white/[0.03] rounded-full"
        />
        <div
          className="landing-geo-animate absolute -bottom-1/3 -left-1/4 w-[600px] h-[600px] border border-white/[0.02] rounded-full"
          style={{ animationDirection: 'reverse', animationDuration: '90s' }}
        />
        <div
          className="landing-geo-animate absolute top-1/4 left-1/3 w-[400px] h-[400px] border border-white/[0.015] rounded-full"
          style={{ animationDuration: '120s' }}
        />
      </div>

      {/* Navigation */}
      <nav className="relative z-10 flex items-center justify-between px-8 lg:px-16 py-8 landing-animate">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 border border-white/20 rotate-45 flex items-center justify-center">
            <div className="w-3 h-3 bg-white/80 -rotate-45" />
          </div>
          <span
            className="text-sm font-medium tracking-[0.3em] uppercase text-white/70"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            Euclid
          </span>
        </div>
        <button
          onClick={() => router.push('/login')}
          className="group flex items-center gap-2 text-xs font-medium tracking-[0.2em] uppercase text-white/50 hover:text-white/90 transition-colors duration-500"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          Client Access
          <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform duration-300" />
        </button>
      </nav>

      {/* Hero */}
      <main className="relative z-10 flex flex-col items-center justify-center min-h-[80vh] px-8">
        {/* Overline */}
        <p
          className="landing-animate-delay-1 text-[10px] font-medium tracking-[0.5em] uppercase text-white/30 mb-8"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          Strategic Intelligence
        </p>

        {/* Main headline */}
        <h1
          className="landing-animate-delay-2 text-center max-w-4xl"
          style={{ fontFamily: "'Playfair Display', serif" }}
        >
          <span className="block text-5xl md:text-7xl lg:text-8xl font-500 leading-[0.95] tracking-tight text-white/90">
            Precision.
          </span>
          <span className="block text-5xl md:text-7xl lg:text-8xl font-500 leading-[0.95] tracking-tight text-white/90 mt-2 md:mt-4">
            Clarity.
          </span>
          <span className="block text-5xl md:text-7xl lg:text-8xl font-500 leading-[0.95] tracking-tight text-white/90 mt-2 md:mt-4">
            Advantage.
          </span>
        </h1>

        {/* Divider */}
        <div className="landing-line-animate w-24 h-px bg-white/20 mt-12 mb-10" />

        {/* Subtext */}
        <p
          className="landing-animate-delay-3 text-center max-w-md text-sm md:text-base leading-relaxed text-white/35"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          We partner with organisations to unlock
          <br className="hidden md:block" />
          transformative outcomes through rigorous
          <br className="hidden md:block" />
          analytical frameworks and deep domain expertise.
        </p>

        {/* CTA */}
        <button
          onClick={() => router.push('/login')}
          className="landing-animate-delay-4 group mt-14 flex items-center gap-3 border border-white/15 hover:border-white/40 px-8 py-4 transition-all duration-500 hover:bg-white/[0.03]"
        >
          <span
            className="text-xs font-medium tracking-[0.25em] uppercase text-white/60 group-hover:text-white/90 transition-colors duration-500"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            Enter
          </span>
          <ArrowRight className="w-3.5 h-3.5 text-white/40 group-hover:text-white/80 group-hover:translate-x-1 transition-all duration-300" />
        </button>
      </main>

      {/* Footer */}
      <footer className="relative z-10 absolute bottom-0 left-0 right-0 px-8 lg:px-16 py-8 flex items-center justify-between">
        <p
          className="text-[10px] tracking-[0.15em] uppercase text-white/15"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          &copy; {new Date().getFullYear()} Euclid Partners
        </p>
        <p
          className="text-[10px] tracking-[0.15em] uppercase text-white/15"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          By invitation only
        </p>
      </footer>
    </div>
  )
}
