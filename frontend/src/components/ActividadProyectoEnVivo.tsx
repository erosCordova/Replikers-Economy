import {
  textoSistemaVisible,
} from '../utils/textoVisible'

import {
  Activity,
  Bot,
  CheckCircle2,
  CircleDollarSign,
  Radio,
  RefreshCw,
  ShieldCheck,
  WifiOff,
  XCircle,
} from 'lucide-react'
import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import {
  connectRealtime,
} from '../services/tiempoReal'

import type {
  RealtimeConnectionStatus,
  RealtimeEvent,
} from '../services/tiempoReal'

import '../styles/TiempoReal.css'


interface ProjectSummary {
  id: number
  title: string
}


interface Props {
  currentUserId: number

  selectedProjectId:
    number | 'all'

  projects: ProjectSummary[]

  onRealtimeActivity:
    () => void
}


function stageLabel(
  event: RealtimeEvent,
) {
  const stage =
    typeof event.payload.stage ===
    'string'
      ? event.payload.stage
      : ''

  const labels:
    Record<string, string> = {
      inspect: 'Inspección',
      planning: 'Planificación R00',
      market: 'Mercado',
      funding: 'Financiación',
      contracting: 'Contratación',
      delegation: 'Delegación',
      execution: 'Ejecución',
      qa: 'Pruebas',
      retry: 'Reintento',
      integration: 'Integración',
      economy: 'Economía',
    }

  return textoSistemaVisible(
    labels[stage]
    ?? event.title
    ?? event.event_type,
    'Actividad',
  )
}


function statusLabel(
  event: RealtimeEvent,
) {
  const status =
    typeof event.payload.status ===
    'string'
      ? event.payload.status
      : ''

  switch (status) {
    case 'started':
      return 'Ejecutando'

    case 'completed':
      return 'Completado'

    case 'failed':
      return 'Fallido'

    case 'settled':
      return 'Liquidado'

    default:
      return textoSistemaVisible(
        event.kind,
        'Actividad',
      )
  }
}


function statusClass(
  event: RealtimeEvent,
) {
  const status =
    typeof event.payload.status ===
    'string'
      ? event.payload.status
      : ''

  if (
    status === 'failed'
  ) {
    return 'failed'
  }

  if (
    status === 'completed' ||
    status === 'settled'
  ) {
    return 'completed'
  }

  if (
    status === 'started'
  ) {
    return 'running'
  }

  return 'neutral'
}


function EventIcon({
  event,
}: {
  event: RealtimeEvent
}) {
  if (
    event.kind === 'economy'
  ) {
    return (
      <CircleDollarSign
        size={17}
      />
    )
  }

  if (
    event.kind === 'message'
  ) {
    return (
      <Bot size={17} />
    )
  }

  if (
    event.payload.status ===
    'failed'
  ) {
    return (
      <XCircle size={17} />
    )
  }

  if (
    event.payload.status ===
    'completed'
  ) {
    return (
      <CheckCircle2
        size={17}
      />
    )
  }

  if (
    event.payload.stage ===
    'qa'
  ) {
    return (
      <ShieldCheck
        size={17}
      />
    )
  }

  return (
    <Activity size={17} />
  )
}


function connectionLabel(
  status:
    RealtimeConnectionStatus,
) {
  switch (status) {
    case 'connected':
      return 'En vivo'

    case 'connecting':
      return 'Conectando'

    case 'reconnecting':
      return 'Reconectando'

    case 'unauthorized':
      return 'Sesión requerida'

    default:
      return 'Desconectado'
  }
}


export default function ActividadProyectoEnVivo({
  currentUserId,
  selectedProjectId,
  projects,
  onRealtimeActivity,
}: Props) {
  const [
    events,
    setEvents,
  ] = useState<RealtimeEvent[]>(
    [],
  )

  const [
    connection,
    setConnection,
  ] =
    useState<RealtimeConnectionStatus>(
      'connecting',
    )

  const callbackRef =
    useRef(
      onRealtimeActivity,
    )

  const refreshTimerRef =
    useRef<number | null>(
      null,
    )


  useEffect(() => {
    callbackRef.current =
      onRealtimeActivity
  }, [onRealtimeActivity])


  useEffect(() => {
    const controller =
      new AbortController()

    void connectRealtime({
      userId:
        currentUserId,

      signal:
        controller.signal,

      onStatus:
        setConnection,

      onEvent:
        (event) => {
          setEvents(
            (current) => {
              if (
                current.some(
                  (item) =>
                    item.id ===
                    event.id,
                )
              ) {
                return current
              }

              return [
                event,
                ...current,
              ].slice(
                0,
                80,
              )
            },
          )

          if (
            refreshTimerRef.current
            === null
          ) {
            refreshTimerRef.current =
              window.setTimeout(
                () => {
                  refreshTimerRef.current =
                    null

                  callbackRef.current()
                },
                350,
              )
          }
        },
    })

    return () => {
      controller.abort()

      if (
        refreshTimerRef.current
        !== null
      ) {
        window.clearTimeout(
          refreshTimerRef.current,
        )

        refreshTimerRef.current =
          null
      }
    }
  }, [currentUserId])


  const visibleEvents =
    useMemo(
      () => {
        if (
          selectedProjectId ===
          'all'
        ) {
          return events
        }

        return events.filter(
          (event) =>
            event.project_id ===
            selectedProjectId,
        )
      },
      [
        events,
        selectedProjectId,
      ],
    )


  function projectLabel(
    projectId: number | null,
  ) {
    if (
      projectId === null
    ) {
      return 'Sistema'
    }

    return (
      projects.find(
        (project) =>
          project.id ===
          projectId,
      )?.title ??
      `Proyecto #${projectId}`
    )
  }


  return (
    <section className="realtime-console">
      <div className="realtime-console-head">
        <div>
          <span className="realtime-kicker">
            <Radio size={14} />
            MONITOR EN TIEMPO REAL
          </span>

          <h2>
            Actividad de agentes en vivo
          </h2>

          <p>
            R00, mercado, Repliker, ejecución, pruebas, reintentos y economía simulada.
          </p>
        </div>

        <div
          className={
            `realtime-connection ` +
            connection
          }
        >
          {connection ===
          'connected' ? (
            <Radio size={15} />
          ) : connection ===
            'offline' ? (
            <WifiOff size={15} />
          ) : (
            <RefreshCw
              size={15}
              className="spin-icon"
            />
          )}

          {connectionLabel(
            connection,
          )}
        </div>
      </div>


      <div className="realtime-stage-strip">
        {[
          'R00',
          'Mercado',
          'Contrato',
          'Delegación',
          'Ejecución',
          'Pruebas',
          'Economía',
        ].map(
          (label) => (
            <span key={label}>
              {label}
            </span>
          ),
        )}
      </div>


      <div className="realtime-feed">
        {visibleEvents.length ===
        0 ? (
          <div className="realtime-empty">
            <Radio size={26} />

            <strong>
              Esperando eventos
            </strong>

            <span>
              La conexion permanecera
              abierta mientras los
              Repliker trabajan.
            </span>
          </div>
        ) : (
          visibleEvents
            .slice(
              0,
              30,
            )
            .map(
              (event) => (
                <article
                  key={event.id}
                  className={
                    `realtime-event ` +
                    statusClass(
                      event,
                    )
                  }
                >
                  <div className="realtime-event-icon">
                    <EventIcon
                      event={event}
                    />
                  </div>

                  <div className="realtime-event-body">
                    <div className="realtime-event-top">
                      <strong>
                        {stageLabel(
                          event,
                        )}
                      </strong>

                      <span>
                        {statusLabel(
                          event,
                        )}
                      </span>
                    </div>

                    <p>
                      {textoSistemaVisible(event.title, 'Actividad registrada')}
                    </p>

                    <small>
                      {projectLabel(
                        event.project_id,
                      )}

                      {event.repliker_id
                        ? ` · Repliker #${event.repliker_id}`
                        : ''}

                      {event.task_id
                        ? ` · Tarea #${event.task_id}`
                        : ''}
                    </small>
                  </div>
                </article>
              ),
            )
        )}
      </div>
    </section>
  )
}
