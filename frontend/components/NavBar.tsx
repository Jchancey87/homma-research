'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  BarChart2, Camera, LayoutDashboard, LayoutGrid,
  Search, Bookmark, FileText, AreaChart, Sun, Moon, Menu, X, Bell, Zap, Rss,
  BookOpen, ChevronDown, Settings
} from 'lucide-react'

const journalLinks = [
  { href: '/alerts',       label: 'Alert Journal',  icon: Bell },
  { href: '/alert-config', label: 'Alert Config',   icon: Settings },
  { href: '/continuation', label: 'Continuation Journal', icon: Zap },
  { href: '/observations', label: 'Observations',   icon: FileText },
]

const researchLinks = [
  { href: '/research',     label: 'Research',       icon: Search },
  { href: '/watchlist',    label: 'Watchlist',      icon: Bookmark },
]

const mainLinks = [
  { href: '/',             label: 'Dashboard',      icon: LayoutDashboard },
  { href: '/history',      label: 'Command Center', icon: LayoutGrid },
  { href: '/daily-charts', label: 'Daily Charts',   icon: AreaChart },
  { href: '/charts',       label: 'Charts',         icon: Camera },
  { href: '/rss',          label: 'RSS Curation',   icon: Rss },
]

export default function NavBar() {
  const path = usePathname()
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [menuOpen, setMenuOpen] = useState(false)
  const [journalOpen, setJournalOpen] = useState(false)
  const [researchOpen, setResearchOpen] = useState(false)

  // Initialize theme on client mount
  useEffect(() => {
    const isLight = !document.documentElement.classList.contains('dark')
    setTheme(isLight ? 'light' : 'dark')
  }, [])

  useEffect(() => {
    if (!journalOpen && !researchOpen) return
    const handleOutsideClick = () => {
      setJournalOpen(false)
      setResearchOpen(false)
    }
    window.addEventListener('click', handleOutsideClick)
    return () => window.removeEventListener('click', handleOutsideClick)
  }, [journalOpen, researchOpen])

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
    <nav className="bg-black border-b border-[#262626] sticky top-0 z-50">
      <div className="max-w-screen-2xl mx-auto px-4">
        <div className="flex items-center justify-between h-14">
          
          {/* Brand/Logo */}
          <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <BarChart2 className="text-[#00ff00]" size={22} />
            <span className="font-mono font-bold text-white text-sm uppercase tracking-widest">TradeJournal</span>
          </Link>

          {/* Desktop Nav Links */}
          <div className="hidden lg:flex items-center gap-1.5">
            {/* Dashboard & Command Center */}
            {mainLinks.slice(0, 2).map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-none transition-colors
                  ${path === href
                    ? 'font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 rounded-none'
                    : 'font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-transparent text-gray-400 hover:text-white hover:border-[#262626] rounded-none'}`}
              >
                <Icon size={14} />
                {label}
              </Link>
            ))}

            {/* Journal Dropdown */}
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setJournalOpen(!journalOpen)
                  setResearchOpen(false)
                }}
                className={`flex items-center gap-1.5 rounded-none transition-colors
                  ${journalLinks.some(link => path === link.href)
                    ? 'font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 rounded-none'
                    : 'font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-transparent text-gray-400 hover:text-white hover:border-[#262626] rounded-none'}`}
              >
                <BookOpen size={14} />
                Journal
                <ChevronDown size={10} className="opacity-60" />
              </button>
              {journalOpen && (
                <div className="absolute left-0 mt-1 w-48 bg-black border border-[#262626] z-50 flex flex-col py-1">
                  {journalLinks.map(({ href, label, icon: Icon }) => (
                    <Link
                      key={href}
                      href={href}
                      onClick={() => setJournalOpen(false)}
                      className={`flex items-center gap-2 px-3 py-2 font-mono text-[11px] uppercase tracking-wider transition-colors
                        ${path === href 
                          ? 'text-[#00ff00] bg-[#121212] border-l-2 border-[#00ff00]' 
                          : 'text-gray-400 hover:text-white hover:bg-[#121212]'}`}
                    >
                      <Icon size={14} />
                      {label}
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Daily Charts & Charts */}
            {mainLinks.slice(2, 4).map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-none transition-colors
                  ${path === href
                    ? 'font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 rounded-none'
                    : 'font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-transparent text-gray-400 hover:text-white hover:border-[#262626] rounded-none'}`}
              >
                <Icon size={14} />
                {label}
              </Link>
            ))}

            {/* Research Dropdown */}
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setResearchOpen(!researchOpen)
                  setJournalOpen(false)
                }}
                className={`flex items-center gap-1.5 rounded-none transition-colors
                  ${researchLinks.some(link => path === link.href)
                    ? 'font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 rounded-none'
                    : 'font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-transparent text-gray-400 hover:text-white hover:border-[#262626] rounded-none'}`}
              >
                <Search size={14} />
                Research
                <ChevronDown size={10} className="opacity-60" />
              </button>
              {researchOpen && (
                <div className="absolute left-0 mt-1 w-48 bg-black border border-[#262626] z-50 flex flex-col py-1">
                  {researchLinks.map(({ href, label, icon: Icon }) => (
                    <Link
                      key={href}
                      href={href}
                      onClick={() => setResearchOpen(false)}
                      className={`flex items-center gap-2 px-3 py-2 font-mono text-[11px] uppercase tracking-wider transition-colors
                        ${path === href 
                          ? 'text-[#00ff00] bg-[#121212] border-l-2 border-[#00ff00]' 
                          : 'text-gray-400 hover:text-white hover:bg-[#121212]'}`}
                    >
                      <Icon size={14} />
                      {label}
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {/* Remaining mainLinks (RSS Curation) */}
            {mainLinks.slice(4).map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-none transition-colors
                  ${path === href
                    ? 'font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 rounded-none'
                    : 'font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 border border-transparent text-gray-400 hover:text-white hover:border-[#262626] rounded-none'}`}
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
              className="p-1.5 border border-[#262626] text-gray-400 hover:text-white bg-black rounded-none transition-colors"
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            {/* Mobile Hamburger Burger Button */}
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="lg:hidden p-1.5 border border-[#262626] text-gray-400 hover:text-white bg-black rounded-none transition-colors"
              aria-label="Toggle navigation menu"
            >
              {menuOpen ? <X size={16} /> : <Menu size={16} />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {menuOpen && (
          <div className="lg:hidden bg-black border-t border-[#262626] py-2 space-y-0.5">
            {/* Dashboard & Command Center */}
            {mainLinks.slice(0, 2).map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMenuOpen(false)}
                className={`flex items-center gap-2.5 w-full transition-colors rounded-none
                  ${path === href
                    ? 'font-mono text-[11px] uppercase tracking-wider px-3 py-2 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 rounded-none'
                    : 'font-mono text-[11px] uppercase tracking-wider px-3 py-2 border border-transparent text-gray-400 hover:text-white hover:border-[#262626] rounded-none'}`}
              >
                <Icon size={16} />
                {label}
              </Link>
            ))}

            {/* Journal Sub-group */}
            <div className="px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-gray-600 border-b border-[#262626]/40">Journal</div>
            {journalLinks.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMenuOpen(false)}
                className={`flex items-center gap-2.5 w-full transition-colors rounded-none pl-6
                  ${path === href
                    ? 'font-mono text-[11px] uppercase tracking-wider px-3 py-2 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 rounded-none'
                    : 'font-mono text-[11px] uppercase tracking-wider px-3 py-2 border border-transparent text-gray-400 hover:text-white hover:border-[#262626] rounded-none'}`}
              >
                <Icon size={14} />
                {label}
              </Link>
            ))}

            {/* Daily Charts & Charts */}
            {mainLinks.slice(2, 4).map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMenuOpen(false)}
                className={`flex items-center gap-2.5 w-full transition-colors rounded-none
                  ${path === href
                    ? 'font-mono text-[11px] uppercase tracking-wider px-3 py-2 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 rounded-none'
                    : 'font-mono text-[11px] uppercase tracking-wider px-3 py-2 border border-transparent text-gray-400 hover:text-white hover:border-[#262626] rounded-none'}`}
              >
                <Icon size={16} />
                {label}
              </Link>
            ))}

            {/* Research Sub-group */}
            <div className="px-3 py-1 font-mono text-[9px] uppercase tracking-widest text-gray-600 border-b border-[#262626]/40">Research</div>
            {researchLinks.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMenuOpen(false)}
                className={`flex items-center gap-2.5 w-full transition-colors rounded-none pl-6
                  ${path === href
                    ? 'font-mono text-[11px] uppercase tracking-wider px-3 py-2 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 rounded-none'
                    : 'font-mono text-[11px] uppercase tracking-wider px-3 py-2 border border-transparent text-gray-400 hover:text-white hover:border-[#262626] rounded-none'}`}
              >
                <Icon size={14} />
                {label}
              </Link>
            ))}

            {/* Remaining mainLinks (RSS Curation) */}
            {mainLinks.slice(4).map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMenuOpen(false)}
                className={`flex items-center gap-2.5 w-full transition-colors rounded-none
                  ${path === href
                    ? 'font-mono text-[11px] uppercase tracking-wider px-3 py-2 border border-[#00ff00]/30 text-[#00ff00] bg-emerald-950/10 rounded-none'
                    : 'font-mono text-[11px] uppercase tracking-wider px-3 py-2 border border-transparent text-gray-400 hover:text-white hover:border-[#262626] rounded-none'}`}
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
