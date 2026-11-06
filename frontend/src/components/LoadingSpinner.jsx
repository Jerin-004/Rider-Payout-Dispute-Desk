export default function LoadingSpinner({ message = 'Loading...' }) {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center">
        <div className="inline-block w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full animate-spin mb-3" />
        <div className="text-sm text-gray-500">{message}</div>
      </div>
    </div>
  )
}
