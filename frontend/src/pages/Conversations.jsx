import { Link } from 'react-router-dom'
import { conversationsApi } from '../services/api.js'
import { useApi } from '../hooks/useApi.js'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import StatusBadge from '../components/StatusBadge.jsx'

function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return mins + 'm ago'
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return hrs + 'h ago'
  return Math.floor(hrs / 24) + 'd ago'
}

export default function Conversations() {
  const { data, loading, error, refetch } = useApi(conversationsApi)

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Conversations</h1>
          <p className="text-sm text-gray-500 mt-1">{data ? data.length : 0} total conversations</p>
        </div>
        <button onClick={refetch} className="btn-secondary">Refresh</button>
      </div>

      {loading && <LoadingSpinner />}
      {error && <ErrorBanner message={error} />}

      {!loading && !error && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Rider ID', 'State', 'Messages', 'Disputes', 'Latest Message', 'Last Activity'].map(function(h) {
                  return <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {(!data || data.length === 0) && (
                <tr><td colSpan={6} className="px-4 py-10 text-center text-gray-400">No conversations yet</td></tr>
              )}
              {data && data.map(function(conv) {
                return (
                  <tr key={conv.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <Link to={'/conversations/' + conv.id} className="font-medium text-brand-600 hover:underline">
                        {conv.rider_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={conv.state} /></td>
                    <td className="px-4 py-3 text-gray-600">{conv.message_count}</td>
                    <td className="px-4 py-3 text-gray-600">{conv.dispute_count}</td>
                    <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{conv.latest_message || '-'}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs">{timeAgo(conv.last_activity)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
