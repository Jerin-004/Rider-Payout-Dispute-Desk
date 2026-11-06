import { statsApi } from '../services/api.js'
import { useApi } from '../hooks/useApi.js'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'

const STAT_CARDS = [
  { key: 'total_disputes', label: 'Total Disputes', icon: '📋', color: 'text-gray-900' },
  { key: 'resolved_disputes', label: 'Resolved', icon: '✅', color: 'text-green-600' },
  { key: 'pending_approvals', label: 'Pending Approvals', icon: '⏳', color: 'text-yellow-600' },
  { key: 'escalated_disputes', label: 'Escalated', icon: '⚠️', color: 'text-red-600' },
]

const PIE_COLORS = ['#22c55e', '#f59e0b', '#ef4444', '#3b82f6']

export default function Dashboard() {
  const { data: stats, loading, error } = useApi(statsApi)

  if (loading) return <LoadingSpinner message="Loading dashboard..." />
  if (error) return (
    <div className="p-6">
      <ErrorBanner message={`Could not load stats: ${error}`} />
    </div>
  )

  const pieData = [
    { name: 'Resolved', value: stats.resolved_disputes },
    { name: 'Pending Approval', value: stats.pending_approvals },
    { name: 'Escalated', value: stats.escalated_disputes },
    { name: 'Other', value: Math.max(0, stats.total_disputes - stats.resolved_disputes - stats.pending_approvals - stats.escalated_disputes) },
  ].filter(d => d.value > 0)

  const barData = [
    { name: 'Amount Owed', value: stats.total_amount_owed },
    { name: 'Amount Paid', value: stats.total_amount_paid },
  ]

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">QuickDrop Rider Payout Dispute Overview</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STAT_CARDS.map(({ key, label, icon, color }) => (
          <div key={key} className="card p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xl">{icon}</span>
            </div>
            <div className={`text-3xl font-bold ${color}`}>{stats[key] ?? 0}</div>
            <div className="text-sm text-gray-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Financial summary */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Total Amount Owed</h2>
          <div className="text-3xl font-bold text-red-600">₹{stats.total_amount_owed?.toFixed(0) ?? 0}</div>
          <div className="text-xs text-gray-400 mt-1">Across all open disputes</div>
        </div>
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Total Amount Paid</h2>
          <div className="text-3xl font-bold text-green-600">₹{stats.total_amount_paid?.toFixed(0) ?? 0}</div>
          <div className="text-xs text-gray-400 mt-1">Successfully processed via PaySwift</div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Dispute Status Distribution</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={4} dataKey="value">
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => [v, 'Disputes']} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[220px] text-gray-400 text-sm">No disputes yet</div>
          )}
        </div>

        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Financial Summary (₹)</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barData} barSize={60}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v) => [`₹${v.toFixed(0)}`, '']} />
              <Bar dataKey="value" fill="#3b82f6" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
