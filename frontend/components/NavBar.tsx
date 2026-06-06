'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  BarChart2, Camera, LayoutDashboard, LayoutGrid,
  Search, Bookmark, FileText, AreaChart, Sun, Moon, Menu, X, Bell
} from 'lucide-react'

const links = [
  { href: '/',             label: 'Dashboard',      icon: LayoutDashboard },
  { href: '/history',      label: 'Command Center', icon: LayoutGrid },
  { href: '/alerts',       label: 'Alert Journal',  icon: Bell },
  { href: '/daily-charts', label: 'Daily Charts',   icon: AreaChart },
  { href: '/charts',       label: 'Charts',         icon: Camera },
  { href: '/research',     label: 'Research',       icon: Search },
  { href: '/watchlist',    label: 'Watchlist',      icon: Bookmark },
  { href: '/observations', label: 'Observations',   icon: FileText },
]

export default function NavBar() {
  const path = usePathname()
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [menuOpen, setMenuOpen] = useState(false)

  // Initialize theme on client mount
  useEffect(() => {
    const isLight = !document.documentElement.classList.contains('dark')
    setTheme(isLight ? 'light' : 'dark')
  }, [])

  const toggleTheme = () => {
    if (theme === 'dark') {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
      setTheme('light')
    } else {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
      setTheme('dark')
    }
  }

  return (
    <nav className="border-b border-gray-200 dark:border-gray-800 bg-white/90 dark:bg-gray-900/80 backdrop-blur sticky top-0 z-50 transition-colors duration-300">
      <div className="max-w-screen-2xl mx-auto px-4">
        <div className="flex items-center justify-between h-14">
          
          {/* Brand/Logo */}
          <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <BarChart2 className="text-emerald-500 dark:text-emerald-400 animate-pulse" size={22} />
            <span className="font-bold tracking-tight text-gray-950 dark:text-white">TradeJournal</span>
          </Link>

          {/* Desktop Nav Links */}
          <div className="hidden lg:flex items-center gap-1.5">
            {links.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200
                  ${path === href
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-950 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800/60'}`}
              >
                <Icon size={14} />
                {label}
              </Link>
            ))}
          </div>

          {/* Controls (Theme Toggle & Menu Burger) */}
          <div className="flex items-center gap-2">
            
            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-xl text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-150 dark:hover:bg-gray-800 transition-all duration-300 border border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700"
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            {/* Mobile Hamburger Burger Button */}
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="lg:hidden p-2 rounded-xl text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-150 dark:hover:bg-gray-800 transition-all duration-200 border border-gray-200 dark:border-gray-800"
              aria-label="Toggle navigation menu"
            >
              {menuOpen ? <X size={16} /> : <Menu size={16} />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {menuOpen && (
          <div className="lg:hidden border-t border-gray-100 dark:border-gray-805 py-3 space-y-1 transition-all duration-300">
            {links.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMenuOpen(false)}
                className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors
                  ${path === href
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800/50'}`}
              >
                <Icon size={16} />
                {label}
              </Link>
            ))}
          </div>
        )}
      </div>
    </nav>
  )
}
