import axios, { AxiosInstance } from 'axios'

const isServer = typeof window === 'undefined'
export const BASE = isServer
  ? (process.env.INTERNAL_API_URL || 'http://127.0.0.1:5000')
  : (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:5000')

export const api: AxiosInstance = axios.create({ baseURL: BASE })

export default api
