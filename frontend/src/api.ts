import axios from 'axios'
import type {
  InternalAxiosRequestConfig,
} from 'axios'

import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from './auth/sesion'


export const API_URL =
  import.meta.env.VITE_API_URL ??
  'http://127.0.0.1:8000/api/v1'


interface RefreshPayload {
  access_token: string
  token_type?: string
  user: unknown
}


interface RetryRequestConfig
  extends InternalAxiosRequestConfig {
  _replikerRetry?: boolean
}


export const api = axios.create({
  baseURL: API_URL,
  timeout: 120000,
  withCredentials: true,
})


const refreshClient =
  axios.create({
    baseURL: API_URL,
    timeout: 30000,
    withCredentials: true,
  })


let refreshPromise:
  Promise<RefreshPayload> | null = null


function isRefreshableRequest(
  url?: string,
) {
  if (!url) {
    return true
  }

  const blocked = [
    '/auth/login',
    '/auth/register',
    '/auth/refresh',
    '/auth/logout',
  ]

  return !blocked.some(
    (path) =>
      url.includes(path),
  )
}


async function performRefresh() {
  const response =
    await refreshClient.post<RefreshPayload>(
      '/auth/refresh',
    )

  const token =
    response.data.access_token

  if (
    typeof token !== 'string' ||
    token.trim().length === 0
  ) {
    throw new Error(
      'El servidor no devolvió ' +
      'un access token valido.',
    )
  }

  setAccessToken(
    token,
  )

  return response.data
}


function getRefreshPromise() {
  if (!refreshPromise) {
    refreshPromise =
      performRefresh()
        .finally(
          () => {
            refreshPromise = null
          },
        )
  }

  return refreshPromise
}


export async function refreshAccessToken() {
  try {
    const payload =
      await getRefreshPromise()

    return payload.access_token
  } catch {
    clearAccessToken()
    return null
  }
}


export async function restoreSession<T>() {
  try {
    const payload =
      await getRefreshPromise()

    return payload.user as T
  } catch {
    clearAccessToken()
    return null
  }
}


export async function logoutSession() {
  try {
    await refreshClient.post(
      '/auth/logout',
    )
  } catch {
    // El cierre local debe ocurrir aunque
    // el servidor no pueda responder.
  } finally {
    clearAccessToken()
  }
}


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

  async (error) => {
    if (
      !axios.isAxiosError(error) ||
      error.response?.status !== 401
    ) {
      return Promise.reject(
        error
      )
    }

    const original =
      error.config as
        RetryRequestConfig | undefined

    if (
      !original ||
      original._replikerRetry ||
      !isRefreshableRequest(
        original.url
      )
    ) {
      return Promise.reject(
        error
      )
    }

    original._replikerRetry = true

    const token =
      await refreshAccessToken()

    if (!token) {
      return Promise.reject(
        error
      )
    }

    original.headers.Authorization =
      `Bearer ${token}`

    return api(
      original
    )
  },
)
