'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  BarChart2, Camera, TrendingUp, LayoutDashboard,
  Search, Bookmark, FileText, AreaChart, History,
} from 'lucide-react'

const links = [
  { href: '/',             label: 'Dashboard',    icon: LayoutDashboard },
  { href: '/gainers',      label: 'Gainers',      icon: TrendingUp },
  { href: '/history',      label: 'History',      icon: History },
  { href: '/daily-charts', label: 'Daily Charts', icon: AreaChart },
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
        <div className="flex items-center gap-2 mr-6">
          <BarChart2 className="text-emerald-400" size={22} />
          <span className="font-semibold tracking-tight text-white">TradeJournal</span>
        </div>
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
