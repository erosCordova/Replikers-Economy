import axios from 'axios'

import {
  clearAccessToken,
  getAccessToken,
} from './auth/session'


export const API_URL =
  import.meta.env.VITE_API_URL ??
  'http://127.0.0.1:8000/api/v1'


export const api = axios.create({
  baseURL: API_URL,
  timeout: 120000,
  withCredentials: false,
})


api.interceptors.request.use(
  (config) => {
    const token =
      getAccessToken()

    if (token) {
      config.headers.Authorization =
        `Bearer ${token}`
    }

    return config
  },
)


api.interceptors.response.use(
  (response) => response,

  (error) => {
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 401
    ) {
      clearAccessToken()
    }

    return Promise.reject(error)
  },
)
