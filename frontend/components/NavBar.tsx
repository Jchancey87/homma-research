'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  BarChart2, LayoutDashboard, LayoutGrid, Search, Bookmark,
  BookOpen, AreaChart, Rss, ChevronDown, Sun, Moon, Settings, Menu, X
} from 'lucide-react'

const primaryLinks = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/history', label: 'Command', icon: LayoutGrid },
  { href: '/research', label: 'Research', icon: Search },
  { href: '/watchlist', label: 'Watchlist', icon: Bookmark },
]

const journalsLinks = [
  { href: '/alerts', label: 'Alerts' },
  { href: '/continuation', label: 'Continuation' },
  { href: '/observations', label: 'Observations' },
  { href: '/alert-config', label: 'Config' },
]

const chartsLinks = [
  { href: '/daily-charts', label: 'Daily' },
  { href: '/charts', label: 'Interactive' },
]

const feedsLinks = [
  { href: '/rss', label: 'Curation' },
]

export default function NavBar() {
  const path = usePathname()
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [menuOpen, setMenuOpen] = useState(false)
  const [journalsOpen, setJournalsOpen] = useState(false)
  const [chartsOpen, setChartsOpen] = useState(false)
  const [feedsOpen, setFeedsOpen] = useState(false)

  // Initialize theme on client mount
  useEffect(() => {
    const isLight = !document.documentElement.classList.contains('dark')
    setTheme(isLight ? 'light' : 'dark')
  }, [])

  useEffect(() => {
    if (!journalsOpen && !chartsOpen && !feedsOpen) return
    const handleOutsideClick = () => {
      setJournalsOpen(false)
      setChartsOpen(false)
      setFeedsOpen(false)
    }
    window.addEventListener('click', handleOutsideClick)
    return () => window.removeEventListener('click', handleOutsideClick)
  }, [journalsOpen, chartsOpen, feedsOpen])

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

  const getLinkClass = (isActive: boolean) => {
    return `flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border rounded-none transition-all duration-150 ${
      isActive
        ? 'border-border-strong text-text-primary bg-hover border-b-2 border-b-info-custom font-bold shadow-sm'
        : 'border-transparent text-text-secondary hover:text-text-primary hover:bg-raised hover:border-border-subtle'
    }`
  }

  const getDropdownItemClass = (isActive: boolean) => {
    return `block w-full text-left font-mono text-[11px] uppercase tracking-wider px-3 py-2 border rounded-none transition-all duration-150 ${
      isActive
        ? 'border-border-strong text-text-primary bg-hover border-l-2 border-l-info-custom font-bold'
        : 'border-transparent text-text-secondary hover:text-text-primary hover:bg-hover hover:border-border-subtle'
    }`
  }

  const getMobileLinkClass = (isActive: boolean) => {
    return `flex items-center gap-2.5 w-full font-mono text-[11px] uppercase tracking-wider px-3 py-2 border rounded-none transition-all duration-150 ${
      isActive
        ? 'border-border-strong text-text-primary bg-hover border-l-2 border-l-info-custom font-bold'
        : 'border-transparent text-text-secondary hover:text-text-primary hover:border-border-subtle'
    }`
  }

  return (
    <nav className="bg-panel border-b border-border-subtle sticky top-0 z-50 shadow-sm">
      <div className="max-w-screen-2xl mx-auto px-4">
        <div className="flex items-center justify-between h-14">
          
          <div className="flex items-center gap-6">
            {/* Brand/Logo */}
            <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
              <BarChart2 className="text-green-custom" size={22} />
              <span className="font-mono font-bold text-white text-sm uppercase tracking-widest">TradeJournal</span>
            </Link>

            {/* Desktop Nav Links */}
            <div className="hidden lg:flex items-center gap-1.5">
              {/* Primary Links */}
              {primaryLinks.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className={getLinkClass(path === href)}
                >
                  <Icon size={14} />
                  {label}
                </Link>
              ))}

              {/* Journals Dropdown */}
              <div className="relative">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setJournalsOpen(!journalsOpen)
                    setChartsOpen(false)
                    setFeedsOpen(false)
                  }}
                  className={getLinkClass(journalsLinks.some(link => path === link.href))}
                >
                  <BookOpen size={14} />
                  Journals
                  <ChevronDown size={10} className="opacity-60" />
                </button>
                {journalsOpen && (
                  <div className="absolute left-0 mt-1 w-48 bg-panel border border-border-subtle z-50 flex flex-col p-1 gap-1 shadow-lg">
                    {journalsLinks.map(({ href, label }) => (
                      <Link
                        key={href}
                        href={href}
                        onClick={() => setJournalsOpen(false)}
                        className={getDropdownItemClass(path === href)}
                      >
                        {label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>

              {/* Charts Dropdown */}
              <div className="relative">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setChartsOpen(!chartsOpen)
                    setJournalsOpen(false)
                    setFeedsOpen(false)
                  }}
                  className={getLinkClass(chartsLinks.some(link => path === link.href))}
                >
                  <AreaChart size={14} />
                  Charts
                  <ChevronDown size={10} className="opacity-60" />
                </button>
                {chartsOpen && (
                  <div className="absolute left-0 mt-1 w-48 bg-panel border border-border-subtle z-50 flex flex-col p-1 gap-1 shadow-lg">
                    {chartsLinks.map(({ href, label }) => (
                      <Link
                        key={href}
                        href={href}
                        onClick={() => setChartsOpen(false)}
                        className={getDropdownItemClass(path === href)}
                      >
                        {label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>

              {/* Feeds Dropdown */}
              <div className="relative">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setFeedsOpen(!feedsOpen)
                    setJournalsOpen(false)
                    setChartsOpen(false)
                  }}
                  className={getLinkClass(feedsLinks.some(link => path === link.href))}
                >
                  <Rss size={14} />
                  Feeds
                  <ChevronDown size={10} className="opacity-60" />
                </button>
                {feedsOpen && (
                  <div className="absolute left-0 mt-1 w-48 bg-panel border border-border-subtle z-50 flex flex-col p-1 gap-1 shadow-lg">
                    {feedsLinks.map(({ href, label }) => (
                      <Link
                        key={href}
                        href={href}
                        onClick={() => setFeedsOpen(false)}
                        className={getDropdownItemClass(path === href)}
                      >
                        {label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Utility Cluster & Mobile Burger */}
          <div className="flex items-center gap-1.5">
            {/* Desktop Utilities */}
            <div className="hidden lg:flex items-center">
              {/* Theme Toggle Button */}
              <button
                onClick={toggleTheme}
                className="p-1.5 border border-transparent text-text-secondary hover:text-text-primary hover:border-border-subtle bg-panel hover:bg-hover rounded-none transition-all duration-150"
                aria-label="Toggle theme"
              >
                {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              </button>

              {/* Vertical Divider */}
              <div className="h-6 w-[1px] bg-border-subtle mx-2" />

              {/* Settings Cog */}
              <Link
                href="/alert-config"
                className={`p-1.5 border bg-panel rounded-none transition-all duration-150 ${
                  path === '/alert-config'
                    ? 'border-border-strong text-text-primary bg-hover border-b-2 border-b-info-custom font-bold'
                    : 'border-transparent text-text-secondary hover:text-text-primary hover:bg-hover hover:border-border-subtle'
                }`}
                aria-label="Alert Settings"
              >
                <Settings size={16} />
              </Link>
            </div>

            {/* Mobile utilities & Hamburger */}
            <div className="lg:hidden flex items-center gap-1.5">
              {/* Theme Toggle Button */}
              <button
                onClick={toggleTheme}
                className="p-1.5 border border-border-subtle text-text-secondary hover:text-text-primary hover:border-border-strong bg-panel hover:bg-hover rounded-none transition-all duration-150 shadow-sm"
                aria-label="Toggle theme"
              >
                {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              </button>

              {/* Mobile Hamburger Burger Button */}
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="p-1.5 border border-border-subtle text-text-secondary hover:text-text-primary hover:border-border-strong bg-panel hover:bg-hover rounded-none transition-all duration-150 shadow-sm"
                aria-label="Toggle navigation menu"
              >
                {menuOpen ? <X size={16} /> : <Menu size={16} />}
              </button>
            </div>
          </div>

        </div>

        {/* Mobile Navigation Drawer */}
        {menuOpen && (
          <div className="lg:hidden bg-panel border-t border-border-subtle py-2 space-y-3">
            
            {/* PRIMARY */}
            <div>
              <div className="px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-text-muted font-semibold border-b border-border-subtle/40 mb-1">
                PRIMARY
              </div>
              <div className="space-y-0.5">
                {primaryLinks.map(({ href, label, icon: Icon }) => (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setMenuOpen(false)}
                    className={getMobileLinkClass(path === href)}
                  >
                    <Icon size={14} />
                    {label}
                  </Link>
                ))}
              </div>
            </div>

            {/* JOURNALS */}
            <div>
              <div className="px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-text-muted font-semibold border-b border-border-subtle/40 mb-1">
                JOURNALS
              </div>
              <div className="space-y-0.5">
                {journalsLinks.map(({ href, label }) => (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setMenuOpen(false)}
                    className={getMobileLinkClass(path === href)}
                  >
                    {label}
                  </Link>
                ))}
              </div>
            </div>

            {/* CHARTS */}
            <div>
              <div className="px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-text-muted font-semibold border-b border-border-subtle/40 mb-1">
                CHARTS
              </div>
              <div className="space-y-0.5">
                {chartsLinks.map(({ href, label }) => (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setMenuOpen(false)}
                    className={getMobileLinkClass(path === href)}
                  >
                    {label}
                  </Link>
                ))}
              </div>
            </div>

            {/* FEEDS */}
            <div>
              <div className="px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-text-muted font-semibold border-b border-border-subtle/40 mb-1">
                FEEDS
              </div>
              <div className="space-y-0.5">
                {feedsLinks.map(({ href, label }) => (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setMenuOpen(false)}
                    className={getMobileLinkClass(path === href)}
                  >
                    {label}
                  </Link>
                ))}
              </div>
            </div>

          </div>
        )}
      </div>
    </nav>
  )
}
