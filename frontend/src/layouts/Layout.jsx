import { Outlet, NavLink } from 'react-router-dom'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: '📊' },
  { to: '/conversations', label: 'Conversations', icon: '💬' },
  { to: '/disputes', label: 'Disputes', icon: '🔍' },
  { to: '/approvals', label: 'Approvals', icon: '✅' },
  { to: '/escalations', label: 'Escalations', icon: '⚠️' },
]

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <span className="text-xl">🚀</span>
            <div>
              <div className="text-sm font-bold text-gray-900">QuickDrop</div>
              <div className="text-xs text-gray-500">Dispute Desk</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-brand-50 text-brand-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              <span>{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-3 border-t border-gray-200">
          <span className="text-xs text-gray-400">Ops Dashboard v1.0</span>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-gray-50">
        <Outlet />
      </main>
    </div>
  )
}
