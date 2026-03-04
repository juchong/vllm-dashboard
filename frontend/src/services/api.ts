import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300_000,
  withCredentials: true,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url ?? ''
    const status = error.response?.status
    const detail = error.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : null
    if (status === 403 && msg && (msg.includes('disabled') || msg.includes('deactivated'))) {
      sessionStorage.setItem('auth_error', msg)
      window.location.href = '/login'
    } else if (status === 401 && !url.includes('auth/login') && !url.includes('auth/me')) {
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
