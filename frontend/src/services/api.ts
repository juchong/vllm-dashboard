import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300_000,
})

export default api
