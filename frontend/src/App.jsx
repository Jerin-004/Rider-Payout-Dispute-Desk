import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './layouts/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Conversations from './pages/Conversations.jsx'
import ConversationDetail from './pages/ConversationDetail.jsx'
import Disputes from './pages/Disputes.jsx'
import Approvals from './pages/Approvals.jsx'
import Escalations from './pages/Escalations.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="conversations" element={<Conversations />} />
        <Route path="conversations/:id" element={<ConversationDetail />} />
        <Route path="disputes" element={<Disputes />} />
        <Route path="approvals" element={<Approvals />} />
        <Route path="escalations" element={<Escalations />} />
      </Route>
    </Routes>
  )
}
