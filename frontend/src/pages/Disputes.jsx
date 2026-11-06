import { disputesApi } from '../services/api.js'
import { useApi } from '../hooks/useApi.js'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import StatusBadge from '../components/StatusBadge.jsx'

export default function Disputes() {
  const { data, loading, error, refetch } = useApi(disputesApi)

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Disputes</h1>
          <p className="text-sm text-gray-500 mt-1">{data ? data.length : 0} disputes</p>
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
                {['Rider', 'Type', 'Trip ID', 'Date', 'Expected', 'Paid', 'Owed', 'Status'].map(function(h) {
                  return <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {(!data || data.length === 0) && (
                <tr><td colSpan={8} className="px-4 py-10 text-center text-gray-400">No disputes yet</td></tr>
              )}
              {data && data.map(function(d) {
                return (
                  <tr key={d.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{d.rider_id}</td>
                    <td className="px-4 py-3 text-gray-600 text-xs">{d.dispute_type.replace(/_/g, ' ')}</td>
                    <td className="px-4 py-3 text-gray-600 font-mono text-xs">{d.trip_id || '-'}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{d.delivery_date || '-'}</td>
                    <td className="px-4 py-3">{d.expected_amount != null ? 'Rs.' + d.expected_amount.toFixed(0) : '-'}</td>
                    <td className="px-4 py-3">{d.actual_paid != null ? 'Rs.' + d.actual_paid.toFixed(0) : '-'}</td>
                    <td className="px-4 py-3 font-semibold text-red-600">{d.amount_owed != null && d.amount_owed > 0 ? 'Rs.' + d.amount_owed.toFixed(0) : '-'}</td>
                    <td className="px-4 py-3"><StatusBadge status={d.status} /></td>
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
