import { pendingApi, traceApi } from '../services/api.js'
import { useApi } from '../hooks/useApi.js'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'

export default function Escalations() {
  const { data, loading, error, refetch } = useApi(function() {
    return pendingApi().then(function(r) {
      return { data: r.data.filter(function(i) { return i.type === 'escalation' }) }
    })
  })

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Escalations</h1>
          <p className="text-sm text-gray-500 mt-1">{data ? data.length : 0} open escalations</p>
        </div>
        <button onClick={refetch} className="btn-secondary">Refresh</button>
      </div>

      {loading && <LoadingSpinner />}
      {error && <ErrorBanner message={error} />}

      {!loading && !error && data && data.length === 0 && (
        <div className="card p-10 text-center text-gray-400">
          No escalations. All cases handled automatically.
        </div>
      )}

      <div className="space-y-3">
        {data && data.map(function(item) {
          return (
            <div key={item.id} className="card p-5 border-l-4 border-l-red-500">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <span className="font-semibold text-gray-900">{item.rider_id}</span>
                  <span className="ml-2 badge bg-red-100 text-red-800">ESCALATION</span>
                </div>
                <span className="text-xs text-gray-400">{new Date(item.created_at).toLocaleString()}</span>
              </div>
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-900 mb-3">
                {item.reason}
              </div>
              {item.dispute_id && (
                <div className="text-xs text-gray-500">Dispute: {item.dispute_id.slice(0,8)}</div>
              )}
              {item.agent_reasoning && (
                <details className="text-xs text-gray-500 mt-2">
                  <summary className="cursor-pointer font-medium text-gray-600">Agent context</summary>
                  <pre className="mt-2 whitespace-pre-wrap break-words">{item.agent_reasoning.slice(0,400)}</pre>
                </details>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
