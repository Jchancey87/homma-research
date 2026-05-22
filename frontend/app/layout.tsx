import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import NavBar from '@/components/NavBar'
import OnboardingWizard from '@/components/OnboardingWizard'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Trading Journal',
  description: 'Local small-cap breakout & gap trade journal',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <script dangerouslySetInnerHTML={{ __html: `
          (function() {
            try {
              const stored = localStorage.getItem('theme');
              if (stored === 'light') {
                document.documentElement.classList.remove('dark');
              } else {
                document.documentElement.classList.add('dark');
              }
            } catch (_) {}
          })()
        ` }} />
      </head>
      <body className={`${inter.className} bg-[var(--background)] text-[var(--foreground)] min-h-screen transition-colors duration-300`}>
        <NavBar />
        <main className="max-w-screen-2xl mx-auto px-4 py-6">{children}</main>
        <OnboardingWizard />
      </body>
    </html>
  )
}
