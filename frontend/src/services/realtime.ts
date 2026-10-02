export type RealtimeConnectionStatus =
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'unauthorized'
  | 'offline'


export interface RealtimeEvent {
  id: number

  project_id: number | null
  task_id: number | null
  repliker_id: number | null

  kind:
    | 'activity'
    | 'message'
    | 'workflow'
    | 'economy'
    | 'system'

  event_type: string
  actor_type: string

  title: string

  payload: Record<
    string,
    unknown
  >

  created_at: string | null
}


interface ConnectOptions {
  userId: number

  signal: AbortSignal

  onEvent: (
    event: RealtimeEvent,
  ) => void

  onStatus: (
    status:
      RealtimeConnectionStatus,
  ) => void
}


const API_URL =
  (
    import.meta.env.VITE_API_URL ||
    'http://127.0.0.1:8000/api/v1'
  ).replace(
    /\/+$/,
    '',
  )


function cursorKey(
  userId: number,
) {
  return (
    `repliker_realtime_cursor:${userId}`
  )
}


function readCursor(
  userId: number,
) {
  const raw =
    localStorage.getItem(
      cursorKey(userId),
    )

  const parsed =
    Number(raw ?? '0')

  if (
    !Number.isFinite(parsed) ||
    parsed < 0
  ) {
    return 0
  }

  return Math.floor(parsed)
}


function saveCursor(
  userId: number,
  cursor: number,
) {
  localStorage.setItem(
    cursorKey(userId),
    String(cursor),
  )
}


function sleep(
  milliseconds: number,
  signal: AbortSignal,
) {
  return new Promise<void>(
    (resolve) => {
      const timer =
        window.setTimeout(
          () => {
            cleanup()
            resolve()
          },
          milliseconds,
        )

      function aborted() {
        window.clearTimeout(
          timer,
        )

        cleanup()
        resolve()
      }

      function cleanup() {
        signal.removeEventListener(
          'abort',
          aborted,
        )
      }

      signal.addEventListener(
        'abort',
        aborted,
        {
          once: true,
        },
      )
    },
  )
}


interface ParsedFrame {
  id: number | null
  retry: number | null
  data: string | null
}


function parseFrame(
  frame: string,
): ParsedFrame {
  let id: number | null = null
  let retry: number | null = null

  const dataLines: string[] = []

  for (
    const rawLine
    of frame.split('\n')
  ) {
    const line =
      rawLine.replace(
        /\r$/,
        '',
      )

    if (
      !line ||
      line.startsWith(':')
    ) {
      continue
    }

    const separator =
      line.indexOf(':')

    const field =
      separator === -1
        ? line
        : line.slice(
            0,
            separator,
          )

    let value =
      separator === -1
        ? ''
        : line.slice(
            separator + 1,
          )

    if (
      value.startsWith(' ')
    ) {
      value =
        value.slice(1)
    }

    if (field === 'id') {
      const parsed =
        Number(value)

      if (
        Number.isInteger(parsed) &&
        parsed >= 0
      ) {
        id = parsed
      }
    }

    if (field === 'retry') {
      const parsed =
        Number(value)

      if (
        Number.isFinite(parsed) &&
        parsed >= 250
      ) {
        retry = parsed
      }
    }

    if (field === 'data') {
      dataLines.push(
        value,
      )
    }
  }

  return {
    id,
    retry,
    data:
      dataLines.length > 0
        ? dataLines.join('\n')
        : null,
  }
}


export async function connectRealtime(
  options: ConnectOptions,
) {
  const {
    userId,
    signal,
    onEvent,
    onStatus,
  } = options

  let cursor =
    readCursor(
      userId,
    )

  let retryMilliseconds =
    2000

  let firstAttempt =
    true

  while (!signal.aborted) {
    onStatus(
      firstAttempt
        ? 'connecting'
        : 'reconnecting',
    )

    firstAttempt = false

    const token =
      localStorage.getItem(
        'repliker_token',
      )

    if (!token) {
      onStatus(
        'unauthorized',
      )

      return
    }

    try {
      const response =
        await fetch(
          (
            `${API_URL}` +
            `/realtime/mine/stream` +
            `?after_id=${cursor}`
          ),
          {
            method: 'GET',

            headers: {
              Accept:
                'text/event-stream',

              Authorization:
                `Bearer ${token}`,

              ...(cursor > 0
                ? {
                    'Last-Event-ID':
                      String(cursor),
                  }
                : {}),
            },

            cache: 'no-store',

            signal,
          },
        )

      if (
        response.status === 401 ||
        response.status === 403
      ) {
        onStatus(
          'unauthorized',
        )

        return
      }

      if (!response.ok) {
        throw new Error(
          `SSE HTTP ${response.status}`,
        )
      }

      if (!response.body) {
        throw new Error(
          'El navegador no expuso ' +
          'el stream SSE.',
        )
      }

      onStatus(
        'connected',
      )

      const reader =
        response.body.getReader()

      const decoder =
        new TextDecoder()

      let buffer = ''

      while (!signal.aborted) {
        const {
          value,
          done,
        } =
          await reader.read()

        if (done) {
          break
        }

        buffer += decoder.decode(
          value,
          {
            stream: true,
          },
        )

        buffer =
          buffer.replace(
            /\r\n/g,
            '\n',
          )

        let boundary =
          buffer.indexOf('\n\n')

        while (boundary !== -1) {
          const frame =
            buffer.slice(
              0,
              boundary,
            )

          buffer =
            buffer.slice(
              boundary + 2,
            )

          const parsed =
            parseFrame(
              frame,
            )

          if (
            parsed.retry !== null
          ) {
            retryMilliseconds =
              Math.min(
                Math.max(
                  parsed.retry,
                  250,
                ),
                30_000,
              )
          }

          if (
            parsed.data !== null
          ) {
            const event =
              JSON.parse(
                parsed.data,
              ) as RealtimeEvent

            const nextCursor =
              parsed.id ??
              event.id

            if (
              Number.isInteger(
                nextCursor,
              ) &&
              nextCursor > cursor
            ) {
              cursor =
                nextCursor

              saveCursor(
                userId,
                cursor,
              )
            }

            onEvent(
              event,
            )
          }

          boundary =
            buffer.indexOf(
              '\n\n',
            )
        }
      }
    } catch (error) {
      if (signal.aborted) {
        return
      }

      console.warn(
        'Realtime SSE desconectado:',
        error,
      )
    }

    if (signal.aborted) {
      return
    }

    onStatus(
      'reconnecting',
    )

    await sleep(
      retryMilliseconds,
      signal,
    )
  }

  onStatus(
    'offline',
  )
}
