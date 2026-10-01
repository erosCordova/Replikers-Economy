import axios from 'axios'


export const API_URL =
  import.meta.env.VITE_API_URL ??
  'http://127.0.0.1:8000/api/v1'


export const api = axios.create({
  baseURL: API_URL,
  timeout: 120000,
})


api.interceptors.request.use(
  (config) => {
    const token =
      localStorage.getItem(
        'repliker_token',
      )

    if (token) {
      config.headers.Authorization =
        `Bearer ${token}`
    }

    return config
  },
)
