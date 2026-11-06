import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg = err.response?.data?.detail || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

export const statsApi = () => api.get('/ops/stats')
export const pendingApi = () => api.get('/ops/pending')
export const conversationsApi = () => api.get('/ops/conversations')
export const conversationDetailApi = (id) => api.get(`/ops/conversations/${id}`)
export const disputesApi = () => api.get('/ops/disputes')
export const traceApi = (riderId) => api.get(`/trace/${riderId}`)
export const approveApi = (id, data) => api.post(`/ops/approvals/${id}/approve`, data)
export const rejectApi = (id, data) => api.post(`/ops/approvals/${id}/reject`, data)
export const sendMessageApi = (data) => api.post('/messages', data)
export const healthApi = () => api.get('/health')

export default api
