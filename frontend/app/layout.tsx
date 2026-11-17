import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import { Sidebar } from '@/components/navigation/sidebar';
import { Header } from '@/components/navigation/header';

const geistSans = Geist({ variable: '--font-geist-sans', subsets: ['latin'] });
const geistMono = Geist_Mono({ variable: '--font-geist-mono', subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Chronus | Compute operations preview',
  description: 'Evidence-first preview console for Chronus compute services.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} min-h-screen bg-neutral-950 font-sans text-neutral-100 antialiased`}>
        <a href="#main-content" className="sr-only z-50 rounded-lg bg-white p-3 font-medium text-neutral-950 focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Skip to main content</a>
        <div className="flex min-h-screen flex-col md:flex-row">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <Header />
            <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
              <div role="note" className="mx-auto mb-6 max-w-7xl rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-4 py-3 text-xs leading-5 text-amber-100/80">
                Product preview: the UI is not release-qualified. Some features are exploratory or intentionally withheld; verify source code, tests, and observed service responses before operational use.
              </div>
              <div className="mx-auto max-w-7xl">{children}</div>
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
