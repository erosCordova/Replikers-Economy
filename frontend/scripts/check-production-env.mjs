const apiUrl =
  (
    process.env.VITE_API_URL
    ?? ''
  ).trim()


if (!apiUrl) {
  console.error(
    'VITE_API_URL ........................ MISSING',
  )

  process.exitCode = 1
} else {
  let parsed

  try {
    parsed = new URL(
      apiUrl,
    )
  } catch {
    console.error(
      'VITE_API_URL ........................ INVALID',
    )

    process.exitCode = 1
  }

  if (parsed) {
    if (
      parsed.protocol
      !== 'https:'
    ) {
      console.error(
        'VITE_API_URL_HTTPS .................. REQUIRED',
      )

      process.exitCode = 1
    }

    if (
      !parsed.pathname
        .replace(
          /\/+$/,
          '',
        )
        .endsWith(
          '/api/v1'
        )
    ) {
      console.error(
        'VITE_API_URL_PREFIX ................. INVALID',
      )

      process.exitCode = 1
    }
  }
}


if (
  process.exitCode
  === undefined
) {
  console.log(
    'VITE_API_URL ........................ OK',
  )

  console.log(
    'FRONTEND_PRODUCTION_ENV ............ OK',
  )
}
