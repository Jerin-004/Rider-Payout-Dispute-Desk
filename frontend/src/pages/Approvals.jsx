import { useState } from 'react'
import { pendingApi, approveApi, rejectApi } from '../services/api.js'
import { useApi } from '../hooks/useApi.js'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'

function ApprovalCard({ item, onAction }) {
  const [comments, setComments] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [confirm, setConfirm] = useState(null) // 'approve' | 'reject'

  async function handleDecision(action) {
    if (!comments.trim()) { setError('Comments are required'); return }
    setLoading(true); setError(null)
    try {
      const fn = action === 'approve' ? approveApi : rejectApi
      await fn(item.id, { operator_id: 'ops_user', comments: comments.trim() })
      onAction()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false); setConfirm(null)
    }
  }

  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-gray-900">{item.rider_id}</span>
            <span className="badge bg-blue-100 text-blue-800">{item.type}</span>
          </div>
          {item.trip_id && <div className="text-xs text-gray-500 mt-1">Trip: {item.trip_id}</div>}
        </div>
        {item.amount && (
          <div className="text-right">
            <div className="text-xs text-gray-400">Amount</div>
            <div className="text-xl font-bold text-gray-900">Rs.{item.amount.toFixed(0)}</div>
          </div>
        )}
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
        <div className="text-xs font-medium text-amber-700 mb-1">Reason for Approval</div>
        <div className="text-sm text-amber-900">{item.reason}</div>
      </div>

      {item.agent_reasoning && (
        <details className="text-xs text-gray-500">
          <summary className="cursor-pointer font-medium text-gray-600">Agent reasoning</summary>
          <pre className="mt-2 whitespace-pre-wrap break-words">{item.agent_reasoning.slice(0, 500)}</pre>
        </details>
      )}

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">
          Operator Comments <span className="text-red-500">*</span>
        </label>
        <textarea
          value={comments}
          onChange={function(e) { setComments(e.target.value) }}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
          rows={2}
          placeholder="Required before approving or rejecting..."
        />
        {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
      </div>

      {confirm ? (
        <div className="flex gap-2">
          <div className="text-sm text-gray-600 flex-1">
            Confirm {confirm} for Rs.{item.amount?.toFixed(0)}?
          </div>
          <button onClick={function() { handleDecision(confirm) }} disabled={loading}
            className={confirm === 'approve' ? 'btn-primary' : 'btn-danger'}>
            {loading ? 'Processing...' : 'Confirm'}
          </button>
          <button onClick={function() { setConfirm(null) }} className="btn-secondary">Cancel</button>
        </div>
      ) : (
        <div className="flex gap-2">
          <button onClick={function() { setConfirm('approve') }} className="btn-primary">Approve Payment</button>
          <button onClick={function() { setConfirm('reject') }} className="btn-danger">Reject</button>
        </div>
      )}
    </div>
  )
}

export default function Approvals() {
  const { data, loading, error, refetch } = useApi(function() {
    return pendingApi().then(function(r) {
      return { data: r.data.filter(function(i) { return i.type === 'approval' }) }
    })
  })

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pending Approvals</h1>
          <p className="text-sm text-gray-500 mt-1">{data ? data.length : 0} items waiting</p>
        </div>
        <button onClick={refetch} className="btn-secondary">Refresh</button>
      </div>

      {loading && <LoadingSpinner />}
      {error && <ErrorBanner message={error} />}

      {!loading && !error && data && data.length === 0 && (
        <div className="card p-10 text-center text-gray-400">
          No pending approvals. All caught up!
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {data && data.map(function(item) {
          return <ApprovalCard key={item.id} item={item} onAction={refetch} />
        })}
      </div>
    </div>
  )
}
