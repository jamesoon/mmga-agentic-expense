import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import {
  MessageSquare, LayoutDashboard, ClipboardList, BookOpen,
  BarChart2, Settings, Shield, Activity, FileText, Gavel,
  LogOut, Menu, X,
} from 'lucide-react'
import { useState } from 'react'

interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
  roles: string[]
}

const navItems: NavItem[] = [
  { label: 'Chat', path: '/chat', icon: <MessageSquare size={18} />, roles: ['user', 'reviewer', 'manager', 'director', 'admin'] },
  { label: 'Dashboard', path: '/dashboard', icon: <LayoutDashboard size={18} />, roles: ['user', 'reviewer', 'manager', 'director', 'admin'] },
  { label: 'Review', path: '/manage', icon: <ClipboardList size={18} />, roles: ['reviewer', 'manager', 'director', 'admin'] },
  { label: 'Audit', path: '/audit/all', icon: <BookOpen size={18} />, roles: ['reviewer', 'manager', 'director', 'admin'] },
  { label: 'Analytics', path: '/analytics', icon: <BarChart2 size={18} />, roles: ['reviewer', 'manager', 'director', 'admin'] },
  { label: 'Manage', path: '/manage', icon: <Settings size={18} />, roles: ['reviewer', 'manager', 'director', 'admin'] },
  { label: 'Policies', path: '/policies', icon: <Shield size={18} />, roles: ['admin'] },
  { label: 'Health', path: '/health', icon: <Activity size={18} />, roles: ['admin'] },
  { label: 'Logs', path: '/logs', icon: <FileText size={18} />, roles: ['admin'] },
  { label: 'LLM as Judge', path: '/llmasjudge', icon: <Gavel size={18} />, roles: ['admin'] },
]

const roleBadgeColor: Record<string, string> = {
  admin: 'bg-purple-600',
  director: 'bg-blue-600',
  manager: 'bg-green-600',
  reviewer: 'bg-yellow-600',
  user: 'bg-indigo-600',
}

export default function Layout() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const visibleItems = navItems.filter((item) =>
    user ? item.roles.includes(user.role) : false
  )

  // Deduplicate by path (Review and Manage both point to /manage)
  const uniqueItems = visibleItems.filter(
    (item, idx, arr) => arr.findIndex((i) => i.path === item.path) === idx
  )

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const roleColor = roleBadgeColor[user?.role ?? 'user'] ?? 'bg-indigo-600'

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
      {/* Sidebar */}
      <aside
        className={`flex flex-col transition-all duration-200 border-r shrink-0 ${sidebarOpen ? 'w-56' : 'w-14'}`}
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
      >
        {/* Logo / toggle */}
        <div className="flex items-center justify-between px-3 h-14 border-b" style={{ borderColor: 'var(--border)' }}>
          {sidebarOpen && (
            <span className="text-sm font-semibold truncate" style={{ color: 'var(--fg)' }}>
              ExpenseClaims
            </span>
          )}
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className="p-1 rounded hover:opacity-80 ml-auto"
            style={{ color: 'var(--muted)' }}
            aria-label="Toggle sidebar"
          >
            {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-3 space-y-1 px-2 overflow-y-auto">
          {uniqueItems.map((item) => (
            <NavLink
              key={item.path + item.label}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-2 py-2 rounded text-sm transition-colors ${
                  isActive
                    ? 'bg-indigo-600 text-white'
                    : 'hover:bg-[#1e2540] text-[var(--muted)] hover:text-[var(--fg)]'
                }`
              }
              title={!sidebarOpen ? item.label : undefined}
            >
              {item.icon}
              {sidebarOpen && <span className="truncate">{item.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* User footer */}
        <div
          className="border-t p-3"
          style={{ borderColor: 'var(--border)' }}
        >
          {sidebarOpen ? (
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="text-xs font-medium truncate" style={{ color: 'var(--fg)' }}>
                  {user?.displayName || user?.username}
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded text-white font-medium ${roleColor}`}>
                  {user?.role}
                </span>
              </div>
              <button
                onClick={handleLogout}
                className="p-1.5 rounded hover:opacity-80 shrink-0"
                style={{ color: 'var(--muted)' }}
                aria-label="Logout"
                title="Logout"
              >
                <LogOut size={15} />
              </button>
            </div>
          ) : (
            <button
              onClick={handleLogout}
              className="flex justify-center w-full p-1.5 rounded hover:opacity-80"
              style={{ color: 'var(--muted)' }}
              aria-label="Logout"
              title="Logout"
            >
              <LogOut size={15} />
            </button>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Topbar */}
        <header
          className="h-14 border-b flex items-center px-5 shrink-0"
          style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
        >
          <span className="text-sm font-semibold" style={{ color: 'var(--fg)' }}>
            Multimodal Expense Claims
          </span>
          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs" style={{ color: 'var(--muted)' }}>
              {user?.username}
            </span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
