import axios from 'axios'
import AuthAPI from './auth_api'

const api = axios.create({
  baseURL: '/api',
  timeout: 300_000,
  withCredentials: true,
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const url = error.config?.url ?? ''
    const status = error.response?.status
    const detail = error.response?.data?.detail
    const msg = typeof detail === 'string' ? detail : null
    const req = error.config as (typeof error.config & { _retry?: boolean }) | undefined
    if (status === 401 && req && !req._retry && !url.includes('auth/login') && !url.includes('auth/refresh') && !url.includes('auth/me')) {
      req._retry = true
      try {
        await AuthAPI.refreshToken()
        return api(req)
      } catch {
        window.location.href = '/login'
      }
    }
    if (status === 403 && msg && (msg.includes('disabled') || msg.includes('deactivated'))) {
      sessionStorage.setItem('auth_error', msg)
      window.location.href = '/login'
    } else if (status === 401 && !url.includes('auth/login') && !url.includes('auth/me')) {
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

api.interceptors.request.use((config) => {
  const method = (config.method || 'get').toUpperCase()
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrf = document.cookie
      .split('; ')
      .find((c) => c.startsWith('csrf_token='))
      ?.split('=')[1]
    if (csrf) {
      config.headers = config.headers || {}
      config.headers['X-CSRF-Token'] = decodeURIComponent(csrf)
    }
  }
  return config
})

export default api
