import { useParams, Link } from 'react-router-dom'
import { conversationDetailApi } from '../services/api.js'
import { useApi } from '../hooks/useApi.js'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import StatusBadge from '../components/StatusBadge.jsx'

export default function ConversationDetail() {
  const { id } = useParams()
  const { data, loading, error } = useApi(function() { return conversationDetailApi(id) }, [id])

  if (loading) return <LoadingSpinner />
  if (error) return <div className="p-6"><ErrorBanner message={error} /></div>
  if (!data) return null

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/conversations" className="text-brand-600 text-sm hover:underline">Conversations</Link>
        <span className="text-gray-400">/</span>
        <span className="text-sm text-gray-700 font-medium">{data.rider_id}</span>
      </div>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Rider {data.rider_id}</h1>
          <p className="text-sm text-gray-500">Conversation {data.id.slice(0,8)}</p>
        </div>
        <StatusBadge status={data.state} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Messages */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Messages</h2>
          <div className="space-y-3">
            {data.messages.map(function(m) {
              return (
                <div key={m.id} className="space-y-1">
                  <div className="bg-gray-100 rounded-lg p-3 text-sm">
                    <div className="font-medium text-gray-700 text-xs mb-1">Rider · {new Date(m.received_at).toLocaleString()}</div>
                    {m.text}
                    {m.intent && <div className="mt-1 text-xs text-brand-600">Intent: {m.intent}</div>}
                  </div>
                  {m.reply && (
                    <div className="bg-brand-50 rounded-lg p-3 text-sm ml-4">
                      <div className="font-medium text-brand-700 text-xs mb-1">Agent</div>
                      {m.reply}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Disputes */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Disputes ({data.disputes.length})</h2>
          {data.disputes.length === 0 && <p className="text-sm text-gray-400">No disputes</p>}
          <div className="space-y-3">
            {data.disputes.map(function(d) {
              return (
                <div key={d.id} className="border border-gray-200 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-gray-600">{d.type.replace(/_/g, ' ')}</span>
                    <StatusBadge status={d.status} />
                  </div>
                  {d.trip_id && <div className="text-xs text-gray-500">Trip: {d.trip_id}</div>}
                  {d.delivery_date && <div className="text-xs text-gray-500">Date: {d.delivery_date}</div>}
                  <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <div className="text-gray-400">Expected</div>
                      <div className="font-medium">{d.expected_amount != null ? 'Rs.' + d.expected_amount.toFixed(0) : '-'}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Paid</div>
                      <div className="font-medium">{d.actual_paid != null ? 'Rs.' + d.actual_paid.toFixed(0) : '-'}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Owed</div>
                      <div className="font-medium text-red-600">{d.amount_owed != null ? 'Rs.' + d.amount_owed.toFixed(0) : '-'}</div>
                    </div>
                  </div>
                  {d.notes && <div className="mt-2 text-xs text-gray-500 italic">{d.notes.slice(0,120)}</div>}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
