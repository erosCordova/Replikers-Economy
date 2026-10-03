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


const srcPath =
  fileURLToPath(
    new URL(
      '../src/',
      import.meta.url,
    ),
  )


function collectFiles(
  directory,
) {
  const result = []

  for (
    const entry
    of readdirSync(directory)
  ) {
    const path =
      join(
        directory,
        entry,
      )

    const stat =
      statSync(path)

    if (stat.isDirectory()) {
      result.push(
        ...collectFiles(path),
      )

      continue
    }

    if (
      path.endsWith('.ts') ||
      path.endsWith('.tsx')
    ) {
      result.push(path)
    }
  }

  return result
}


const violations = []


for (
  const file
  of collectFiles(srcPath)
) {
  const content =
    readFileSync(
      file,
      'utf8',
    )

  const display =
    relative(
      srcPath,
      file,
    ).replaceAll(
      '\\',
      '/',
    )

  if (
    display !== 'auth/session.ts' &&
    content.includes(
      'repliker_token',
    )
  ) {
    violations.push(
      `${display}: referencia directa ` +
      'a repliker_token',
    )
  }

  if (
    display === 'auth/session.ts' &&
    (
      content.includes(
        'localStorage.setItem'
      ) ||
      content.includes(
        'sessionStorage.setItem'
      )
    )
  ) {
    violations.push(
      'auth/session.ts: el token ' +
      'no puede persistirse',
    )
  }
}


if (violations.length > 0) {
  console.error(
    'AUTH_STORAGE_CHECK ................. ERROR',
  )

  for (
    const violation
    of violations
  ) {
    console.error(
      violation,
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
