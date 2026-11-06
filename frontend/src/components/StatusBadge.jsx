const COLOR = {
  PAID: 'bg-green-100 text-green-800',
  RESOLVED: 'bg-green-100 text-green-800',
  NO_DISCREPANCY: 'bg-gray-100 text-gray-700',
  OPEN: 'bg-blue-100 text-blue-800',
  VERIFYING: 'bg-blue-100 text-blue-800',
  WAITING_FOR_APPROVAL: 'bg-yellow-100 text-yellow-800',
  PAYMENT_PROCESSING: 'bg-yellow-100 text-yellow-800',
  PENDING: 'bg-yellow-100 text-yellow-800',
  APPROVED: 'bg-green-100 text-green-800',
  REJECTED: 'bg-red-100 text-red-800',
  ESCALATED: 'bg-red-100 text-red-800',
  FAILED: 'bg-red-100 text-red-800',
  NEW: 'bg-gray-100 text-gray-700',
  COLLECTING_INFORMATION: 'bg-purple-100 text-purple-800',
}

export default function StatusBadge({ status }) {
  const cls = COLOR[status] || 'bg-gray-100 text-gray-700'
  return (
    <span className={`badge ${cls}`}>
      {status?.replace(/_/g, ' ')}
    </span>
  )
}
