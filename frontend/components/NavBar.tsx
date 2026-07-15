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
    return `flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border rounded-none transition-colors ${
      isActive
        ? 'border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10'
        : 'border-transparent text-gray-400 hover:text-white hover:border-[#262626]'
    }`
  }

  const getDropdownItemClass = (isActive: boolean) => {
    return `block w-full text-left font-mono text-[11px] uppercase tracking-wider px-3 py-2 border rounded-none transition-colors ${
      isActive
        ? 'border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10'
        : 'border-transparent text-gray-400 hover:text-white hover:bg-[#121212] hover:border-[#262626]'
    }`
  }

  const getMobileLinkClass = (isActive: boolean) => {
    return `flex items-center gap-2.5 w-full font-mono text-[11px] uppercase tracking-wider px-3 py-2 border rounded-none transition-colors ${
      isActive
        ? 'border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10'
        : 'border-transparent text-gray-400 hover:text-white hover:border-[#262626]'
    }`
  }

  return (
    <nav className="bg-black border-b border-[#262626] sticky top-0 z-50">
      <div className="max-w-screen-2xl mx-auto px-4">
        <div className="flex items-center justify-between h-14">
          
          <div className="flex items-center gap-6">
            {/* Brand/Logo */}
            <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
              <BarChart2 className="text-[#00ff00]" size={22} />
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
                  <div className="absolute left-0 mt-1 w-48 bg-black border border-[#262626] z-50 flex flex-col p-1 gap-1">
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
                  <div className="absolute left-0 mt-1 w-48 bg-black border border-[#262626] z-50 flex flex-col p-1 gap-1">
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
                  <div className="absolute left-0 mt-1 w-48 bg-black border border-[#262626] z-50 flex flex-col p-1 gap-1">
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
                className="p-1.5 border border-transparent text-gray-400 hover:text-white hover:border-[#262626] bg-black rounded-none transition-colors"
                aria-label="Toggle theme"
              >
                {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              </button>

              {/* Vertical Divider */}
              <div className="h-6 w-[1px] bg-[#262626] mx-2" />

              {/* Settings Cog */}
              <Link
                href="/alert-config"
                className={`p-1.5 border bg-black rounded-none transition-colors ${
                  path === '/alert-config'
                    ? 'border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10'
                    : 'border-transparent text-gray-400 hover:text-white hover:border-[#262626]'
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
                className="p-1.5 border border-[#262626] text-gray-400 hover:text-white bg-black rounded-none transition-colors"
                aria-label="Toggle theme"
              >
                {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              </button>

              {/* Mobile Hamburger Burger Button */}
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="p-1.5 border border-[#262626] text-gray-400 hover:text-white bg-black rounded-none transition-colors"
                aria-label="Toggle navigation menu"
              >
                {menuOpen ? <X size={16} /> : <Menu size={16} />}
              </button>
            </div>
          </div>

        </div>

        {/* Mobile Navigation Drawer */}
        {menuOpen && (
          <div className="lg:hidden bg-black border-t border-[#262626] py-2 space-y-3">
            
            {/* PRIMARY */}
            <div>
              <div className="px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-gray-500 font-semibold border-b border-[#262626]/40 mb-1">
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
              <div className="px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-gray-500 font-semibold border-b border-[#262626]/40 mb-1">
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
              <div className="px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-gray-500 font-semibold border-b border-[#262626]/40 mb-1">
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
              <div className="px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-gray-500 font-semibold border-b border-[#262626]/40 mb-1">
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
