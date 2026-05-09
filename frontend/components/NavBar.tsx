'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  BarChart2, Camera, TrendingUp, LayoutDashboard, LayoutGrid,
  Search, Bookmark, FileText, AreaChart, History,
} from 'lucide-react'

const links = [
  { href: '/',             label: 'Dashboard',      icon: LayoutDashboard },
  { href: '/history',      label: 'Command Center', icon: LayoutGrid },
  { href: '/daily-charts', label: 'Daily Charts',   icon: AreaChart },
  { href: '/charts',       label: 'Charts',       icon: Camera },
  { href: '/research',     label: 'Research',     icon: Search },
  { href: '/watchlist',    label: 'Watchlist',    icon: Bookmark },
  { href: '/observations', label: 'Observations', icon: FileText },
]

export default function NavBar() {
  const path = usePathname()
  return (
    <nav className="border-b border-gray-800 bg-gray-900/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-screen-2xl mx-auto px-4 flex items-center gap-1 h-14">
        <Link href="/" className="flex items-center gap-2 mr-6 hover:opacity-80 transition-opacity">
          <BarChart2 className="text-emerald-400" size={22} />
          <span className="font-semibold tracking-tight text-white">TradeJournal</span>
        </Link>
        {links.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors
              ${path === href
                ? 'bg-emerald-500/20 text-emerald-400'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'}`}
          >
            <Icon size={15} />
            {label}
          </Link>
        ))}
      </div>
    </nav>
  )
}
