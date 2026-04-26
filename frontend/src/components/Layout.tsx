import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import {
  MessageSquare, LayoutDashboard, ClipboardList, BookOpen,
  BarChart2, Settings, Shield, Activity, FileText, Gavel,
  LogOut, Menu, X, ChevronRight,
} from 'lucide-react'
import { useState } from 'react'

interface NavItem {
  label: string
  path: string
  icon: React.ReactNode
  roles: string[]
  section?: string
}

const navItems: NavItem[] = [
  { label: 'Chat', path: '/chat', icon: <MessageSquare size={16} />, roles: ['user', 'reviewer', 'manager', 'director', 'admin'], section: 'Main' },
  { label: 'Dashboard', path: '/dashboard', icon: <LayoutDashboard size={16} />, roles: ['user', 'reviewer', 'manager', 'director', 'admin'], section: 'Main' },
  { label: 'Review', path: '/manage', icon: <ClipboardList size={16} />, roles: ['reviewer', 'manager', 'director', 'admin'], section: 'Operations' },
  { label: 'Analytics', path: '/analytics', icon: <BarChart2 size={16} />, roles: ['reviewer', 'manager', 'director', 'admin'], section: 'Operations' },
  { label: 'Audit', path: '/audit/all', icon: <BookOpen size={16} />, roles: ['reviewer', 'manager', 'director', 'admin'], section: 'Operations' },
  { label: 'Manage Users', path: '/manage', icon: <Settings size={16} />, roles: ['manager', 'director', 'admin'], section: 'Operations' },
  { label: 'Policies', path: '/policies', icon: <Shield size={16} />, roles: ['admin'], section: 'Admin' },
  { label: 'Health', path: '/health', icon: <Activity size={16} />, roles: ['admin'], section: 'Admin' },
  { label: 'Logs', path: '/logs', icon: <FileText size={16} />, roles: ['admin'], section: 'Admin' },
  { label: 'LLM as Judge', path: '/llmasjudge', icon: <Gavel size={16} />, roles: ['admin'], section: 'Admin' },
]

const roleBadge: Record<string, { bg: string; text: string }> = {
  admin:    { bg: '#7c3aed20', text: '#7c3aed' },
  director: { bg: '#0ea5e920', text: '#0284c7' },
  manager:  { bg: '#16a34a20', text: '#15803d' },
  reviewer: { bg: '#d9770620', text: '#b45309' },
  user:     { bg: '#2563eb20', text: '#2563eb' },
}

export default function Layout() {
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const visibleItems = navItems.filter((item) => user ? item.roles.includes(user.role) : false)
  const uniqueItems = visibleItems.filter((item, idx, arr) => arr.findIndex((i) => i.path === item.path && i.label === item.label) === idx)

  const sections = [...new Set(uniqueItems.map((i) => i.section))]

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const badge = roleBadge[user?.role ?? 'user'] ?? roleBadge.user

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg)' }}>
      {/* Sidebar */}
      <aside
        className={`flex flex-col shrink-0 transition-all duration-200 ${sidebarOpen ? 'w-60' : 'w-[52px]'}`}
        style={{ background: 'var(--sidebar-bg)' }}
      >
        {/* Logo */}
        <div className="flex items-center h-14 px-3 gap-2.5 shrink-0" style={{ borderBottom: '1px solid var(--sidebar-border)' }}>
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center text-white font-bold text-xs shrink-0"
            style={{ background: 'var(--accent)' }}
          >
            EC
          </div>
          {sidebarOpen && (
            <span className="text-sm font-semibold text-white truncate flex-1">ExpenseClaims</span>
          )}
          <button
            onClick={() => setSidebarOpen((v) => !v)}
            className="p-1 rounded transition-colors ml-auto shrink-0"
            style={{ color: 'var(--sidebar-muted)' }}
            aria-label="Toggle sidebar"
          >
            {sidebarOpen ? <X size={14} /> : <Menu size={14} />}
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-5">
          {sections.map((section) => {
            const items = uniqueItems.filter((i) => i.section === section)
            return (
              <div key={section}>
                {sidebarOpen && (
                  <div className="px-2 mb-1.5 text-[10px] font-bold uppercase tracking-widest" style={{ color: '#475569' }}>
                    {section}
                  </div>
                )}
                <div className="space-y-0.5">
                  {items.map((item) => (
                    <NavLink
                      key={item.path + item.label}
                      to={item.path}
                      title={!sidebarOpen ? item.label : undefined}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] font-medium transition-all ${
                          isActive
                            ? 'text-white'
                            : 'hover:text-white'
                        }`
                      }
                      style={({ isActive }) => ({
                        background: isActive ? 'var(--accent)' : 'transparent',
                        color: isActive ? '#fff' : 'var(--sidebar-muted)',
                      })}
                    >
                      <span className="shrink-0">{item.icon}</span>
                      {sidebarOpen && <span className="truncate flex-1">{item.label}</span>}
                      {sidebarOpen && <ChevronRight size={12} className="shrink-0 opacity-40" />}
                    </NavLink>
                  ))}
                </div>
              </div>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-3 shrink-0" style={{ borderTop: '1px solid var(--sidebar-border)' }}>
          {sidebarOpen ? (
            <div className="flex items-center gap-2.5">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
                style={{ background: badge.text }}
              >
                {(user?.displayName || user?.username || '?')[0].toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-semibold text-white truncate">
                  {user?.displayName || user?.username}
                </div>
                <span
                  className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                  style={{ background: badge.bg, color: badge.text }}
                >
                  {user?.role}
                </span>
              </div>
              <button onClick={handleLogout} className="p-1.5 rounded-lg transition-colors shrink-0" style={{ color: 'var(--sidebar-muted)' }} title="Sign out">
                <LogOut size={14} />
              </button>
            </div>
          ) : (
            <button onClick={handleLogout} className="flex justify-center w-full p-1.5 rounded-lg" style={{ color: 'var(--sidebar-muted)' }} title="Sign out">
              <LogOut size={14} />
            </button>
          )}
        </div>
      </aside>

      {/* Main area */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Topbar */}
        <header
          className="h-14 shrink-0 flex items-center px-6 gap-4"
          style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}
        >
          <div className="flex-1" />
          <div className="flex items-center gap-3">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white"
              style={{ background: badge.text }}
            >
              {(user?.displayName || user?.username || '?')[0].toUpperCase()}
            </div>
            <div className="text-right hidden sm:block">
              <div className="text-xs font-semibold" style={{ color: 'var(--fg)' }}>
                {user?.displayName || user?.username}
              </div>
              <div className="text-[10px]" style={{ color: 'var(--muted)' }}>{user?.role}</div>
            </div>
          </div>
        </header>

        {/* Page */}
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
