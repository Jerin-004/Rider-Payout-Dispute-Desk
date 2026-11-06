export default function ErrorBanner({ message }) {
  return (
    <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-800">
      ⚠️ {message}
    </div>
  )
}
