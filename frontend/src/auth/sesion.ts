const LEGACY_TOKEN_KEY =
  'repliker_token'


let accessToken:
  string | null = null


export function purgeLegacyAuthStorage() {
  if (
    typeof window === 'undefined'
  ) {
    return
  }

  try {
    window.localStorage.removeItem(
      LEGACY_TOKEN_KEY,
    )
  } catch (error) {
    void error
  }

  try {
    window.sessionStorage.removeItem(
      LEGACY_TOKEN_KEY,
    )
  } catch (error) {
    void error
  }
}


export function getAccessToken() {
  return accessToken
}


export function setAccessToken(
  token: string,
) {
  const normalized =
    token.trim()

  accessToken =
    normalized.length > 0
      ? normalized
      : null
}


export function clearAccessToken() {
  accessToken = null

  purgeLegacyAuthStorage()
}
