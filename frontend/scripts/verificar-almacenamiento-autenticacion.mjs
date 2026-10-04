import {
  readFileSync,
  readdirSync,
  statSync,
} from 'node:fs'

import {
  join,
  relative,
} from 'node:path'

import {
  fileURLToPath,
} from 'node:url'


const rutaSrc =
  fileURLToPath(
    new URL(
      '../src/',
      import.meta.url,
    ),
  )


function recopilarArchivos(
  directorio,
) {
  const resultado = []

  for (
    const entrada
    of readdirSync(directorio)
  ) {
    const ruta =
      join(
        directorio,
        entrada,
      )

    const estado =
      statSync(ruta)

    if (estado.isDirectory()) {
      resultado.push(
        ...recopilarArchivos(
          ruta,
        ),
      )

      continue
    }

    if (
      ruta.endsWith('.ts') ||
      ruta.endsWith('.tsx')
    ) {
      resultado.push(
        ruta,
      )
    }
  }

  return resultado
}


const infracciones = []


for (
  const archivo
  of recopilarArchivos(
    rutaSrc,
  )
) {
  const contenido =
    readFileSync(
      archivo,
      'utf8',
    )

  const rutaVisible =
    relative(
      rutaSrc,
      archivo,
    ).replaceAll(
      '\\',
      '/',
    )

  if (
    rutaVisible !==
      'auth/sesion.ts' &&
    contenido.includes(
      'repliker_token',
    )
  ) {
    infracciones.push(
      `${rutaVisible}: referencia directa ` +
      'a repliker_token',
    )
  }

  if (
    rutaVisible ===
      'auth/sesion.ts' &&
    (
      contenido.includes(
        'localStorage.setItem',
      ) ||
      contenido.includes(
        'sessionStorage.setItem',
      )
    )
  ) {
    infracciones.push(
      'auth/sesion.ts: el token ' +
      'no puede persistirse',
    )
  }
}


if (
  infracciones.length > 0
) {
  console.error(
    'AUTH_STORAGE_CHECK ................. ERROR',
  )

  for (
    const infraccion
    of infracciones
  ) {
    console.error(
      infraccion,
    )
  }

  process.exitCode = 1
} else {
  console.log(
    'AUTH_STORAGE_CHECK ................. OK',
  )

  console.log(
    'ACCESS_TOKEN_STORAGE ............... MEMORY_ONLY',
  )
}


const fuenteApi =
  readFileSync(
    new URL(
      '../src/api.ts',
      import.meta.url,
    ),
    'utf8',
  )


if (
  !fuenteApi.includes(
    'withCredentials: true',
  )
) {
  console.error(
    'CREDENTIALLED_COOKIE_CHECK ........ ERROR',
  )

  process.exitCode = 1
} else {
  console.log(
    'CREDENTIALLED_COOKIE_CHECK ........ OK',
  )
}
