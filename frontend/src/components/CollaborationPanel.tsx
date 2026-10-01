import {
  AlertTriangle,
  CheckCheck,
  CircleDot,
  MessageSquare,
  RefreshCw,
  Send,
  ShieldCheck,
  Workflow,
} from 'lucide-react'
import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import { api } from '../api'
import ReplikerAvatar from './ReplikerAvatar'
import type {
  ReplikerAppearance,
} from './ReplikerAvatar'

import '../styles/Collaboration.css'


interface CollaborationAgent {
  id: number
  name: string
  is_active: boolean
  appearance: ReplikerAppearance
}


interface CollaborationProject {
  id: number
  title: string
}


interface CollaborationParticipant {
  participant_key: string
  participant_type: string
  repliker_id: number | null
  role: string
}


interface CollaborationThread {
  id: number

  project_id: number
  task_id: number | null
  contract_id: number | null

  kind: string
  subject: string
  status: string

  created_by_type: string

  participants: CollaborationParticipant[]

  message_count: number

  created_at: string
  updated_at: string
}


interface CollaborationMessage {
  id: number

  project_id: number
  task_id: number | null

  thread_id: number | null
  thread_subject: string | null

  contract_id: number | null
  reply_to_message_id: number | null

  sender_type: string
  sender_repliker_id: number | null

  receiver_type: string
  receiver_repliker_id: number | null

  message_type: string
  content: string

  priority: string
  delivery_status: string

  requires_ack: boolean

  acknowledged_at: string | null
  resolved_at: string | null

  legacy: boolean

  created_at: string
}


interface CollaborationSnapshot {
  project_id: number

  threads: CollaborationThread[]
  messages: CollaborationMessage[]
}


interface Props {
  selectedProjectId:
    | number
    | 'all'

  agents: CollaborationAgent[]
  projects: CollaborationProject[]
}


function dateTimeLabel(
  value: string,
) {
  const date =
    new Date(value)

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return value
  }

  return new Intl.DateTimeFormat(
    'es-PE',
    {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    },
  ).format(date)
}


function priorityLabel(
  priority: string,
) {
  switch (priority) {
    case 'urgent':
      return 'Urgente'

    case 'high':
      return 'Alta'

    case 'low':
      return 'Baja'

    default:
      return 'Normal'
  }
}


function statusLabel(
  status: string,
) {
  switch (status) {
    case 'blocked':
      return 'Bloqueado'

    case 'waiting':
      return 'Esperando'

    case 'resolved':
      return 'Resuelto'

    case 'closed':
      return 'Cerrado'

    default:
      return 'Abierto'
  }
}


function messageStatusLabel(
  status: string,
) {
  switch (status) {
    case 'acknowledged':
      return 'Confirmado'

    case 'resolved':
      return 'Resuelto'

    case 'legacy':
      return 'Historial'

    default:
      return 'Enviado'
  }
}


export default function CollaborationPanel({
  selectedProjectId,
  agents,
  projects,
}: Props) {
  const [snapshot, setSnapshot] =
    useState<CollaborationSnapshot>({
      project_id: 0,
      threads: [],
      messages: [],
    })

  const [
    selectedThreadId,
    setSelectedThreadId,
  ] = useState<number | 'all'>(
    'all',
  )

  const [
    composer,
    setComposer,
  ] = useState('')

  const [
    priority,
    setPriority,
  ] = useState(
    'normal',
  )

  const [
    loading,
    setLoading,
  ] = useState(false)

  const [
    refreshing,
    setRefreshing,
  ] = useState(false)

  const [
    sending,
    setSending,
  ] = useState(false)

  const [
    notice,
    setNotice,
  ] = useState('')

  const [
    error,
    setError,
  ] = useState('')


  const currentProject =
    useMemo(
      () => {
        if (
          selectedProjectId
          === 'all'
        ) {
          return null
        }

        return (
          projects.find(
            (project) =>
              project.id
              === selectedProjectId,
          )
          ?? null
        )
      },
      [
        projects,
        selectedProjectId,
      ],
    )


  async function load(
    silent = false,
  ) {
    if (
      selectedProjectId
      === 'all'
    ) {
      setSnapshot({
        project_id: 0,
        threads: [],
        messages: [],
      })

      return
    }

    if (silent) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    try {
      const response =
        await api.get<CollaborationSnapshot>(
          `/collaboration/projects/${selectedProjectId}`,
        )

      setSnapshot(
        response.data,
      )

      setError('')

      setSelectedThreadId(
        (current) => {
          if (
            current !== 'all'
            && response.data
              .threads
              .some(
                (thread) =>
                  thread.id
                  === current,
              )
          ) {
            return current
          }

          return 'all'
        },
      )
    } catch {
      setError(
        'No fue posible cargar '
        + 'la colaboracion.',
      )
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }


  useEffect(() => {
    setSelectedThreadId(
      'all',
    )

    setComposer('')
    setNotice('')

    void load()

    if (
      selectedProjectId
      === 'all'
    ) {
      return
    }

    const timer =
      window.setInterval(
        () => {
          void load(true)
        },
        8000,
      )

    return () => {
      window.clearInterval(
        timer,
      )
    }
  }, [selectedProjectId])


  const openThreads =
    useMemo(
      () =>
        snapshot.threads.filter(
          (thread) =>
            ![
              'resolved',
              'closed',
            ].includes(
              thread.status,
            ),
        ),
      [snapshot.threads],
    )


  const blockedThreads =
    useMemo(
      () =>
        snapshot.threads.filter(
          (thread) =>
            thread.status
            === 'blocked',
        ),
      [snapshot.threads],
    )


  const visibleMessages =
    useMemo(
      () => {
        if (
          selectedThreadId
          === 'all'
        ) {
          return snapshot.messages
        }

        return (
          snapshot.messages.filter(
            (message) =>
              message.thread_id
              === selectedThreadId,
          )
        )
      },
      [
        snapshot.messages,
        selectedThreadId,
      ],
    )


  const selectedThread =
    useMemo(
      () => {
        if (
          selectedThreadId
          === 'all'
        ) {
          return null
        }

        return (
          snapshot.threads.find(
            (thread) =>
              thread.id
              === selectedThreadId,
          )
          ?? null
        )
      },
      [
        snapshot.threads,
        selectedThreadId,
      ],
    )


  function agentById(
    replikerId: number | null,
  ) {
    if (
      replikerId === null
    ) {
      return null
    }

    return (
      agents.find(
        (agent) =>
          agent.id
          === replikerId,
      )
      ?? null
    )
  }


  function participantName(
    actorType: string,
    replikerId: number | null,
  ) {
    if (
      actorType === 'r00'
    ) {
      return 'R00'
    }

    if (
      actorType === 'project'
      || actorType === 'client'
    ) {
      return 'Cliente'
    }

    if (
      actorType === 'system'
    ) {
      return 'Sistema'
    }

    const agent =
      agentById(
        replikerId,
      )

    return (
      agent?.name
      ?? (
        replikerId !== null
          ? `Repliker #${replikerId}`
          : actorType
      )
    )
  }


  async function sendMessage() {
    if (
      selectedProjectId
      === 'all'
    ) {
      return
    }

    const content =
      composer.trim()

    if (!content) {
      setNotice(
        'Escribe un mensaje.',
      )

      return
    }

    setSending(true)
    setNotice('')

    try {
      const response =
        await api.post<CollaborationMessage>(
          `/collaboration/projects/${selectedProjectId}/messages`,
          {
            content,
            priority,
          },
        )

      setComposer('')

      if (
        response.data.thread_id
        !== null
      ) {
        setSelectedThreadId(
          response.data
            .thread_id,
        )
      }

      setNotice(
        'Mensaje enviado a R00.',
      )

      await load(true)
    } catch {
      setNotice(
        'No se pudo enviar '
        + 'el mensaje.',
      )
    } finally {
      setSending(false)
    }
  }


  async function acknowledge(
    messageId: number,
  ) {
    try {
      await api.post(
        `/collaboration/messages/${messageId}/acknowledge`,
      )

      await load(true)
    } catch {
      setNotice(
        'No se pudo confirmar '
        + 'el mensaje.',
      )
    }
  }


  async function resolveThread() {
    if (!selectedThread) {
      return
    }

    try {
      await api.post(
        `/collaboration/threads/${selectedThread.id}/resolve`,
      )

      setNotice(
        'Conversacion resuelta.',
      )

      await load(true)
    } catch {
      setNotice(
        'Este canal operativo '
        + 'debe ser cerrado por R00.',
      )
    }
  }


  if (
    selectedProjectId
    === 'all'
  ) {
    return (
      <article className="ecosystem-panel collaboration-panel">
        <div className="ecosystem-panel-header">
          <div>
            <span>
              COLABORACION
            </span>

            <h3>
              Centro de comunicaciones
            </h3>
          </div>

          <MessageSquare
            size={19}
          />
        </div>

        <div className="collaboration-select-project">
          <Workflow
            size={34}
          />

          <strong>
            Selecciona un proyecto
          </strong>

          <p>
            Elige un proyecto para
            abrir sus conversaciones,
            solicitudes, bloqueos y
            handoffs.
          </p>
        </div>
      </article>
    )
  }


  return (
    <article className="ecosystem-panel collaboration-panel">
      <div className="ecosystem-panel-header">
        <div>
          <span>
            COLABORACION
          </span>

          <h3>
            Centro de comunicaciones
          </h3>

          <small>
            {currentProject?.title
              ?? `Proyecto #${selectedProjectId}`}
          </small>
        </div>

        <button
          type="button"
          className="collaboration-refresh"
          onClick={() =>
            void load(true)
          }
          title="Actualizar comunicaciones"
        >
          <RefreshCw
            size={17}
            className={
              refreshing
                ? 'spin-icon'
                : ''
            }
          />
        </button>
      </div>


      <div className="collaboration-metrics">
        <div>
          <Workflow size={16} />

          <span>
            {openThreads.length}
          </span>

          <small>
            abiertos
          </small>
        </div>

        <div>
          <AlertTriangle size={16} />

          <span>
            {blockedThreads.length}
          </span>

          <small>
            bloqueos
          </small>
        </div>

        <div>
          <MessageSquare size={16} />

          <span>
            {snapshot.messages.length}
          </span>

          <small>
            mensajes
          </small>
        </div>
      </div>


      {error && (
        <div className="collaboration-alert error">
          {error}
        </div>
      )}


      {notice && (
        <div className="collaboration-alert">
          {notice}
        </div>
      )}


      <div className="collaboration-thread-strip">
        <button
          type="button"
          className={
            selectedThreadId
            === 'all'
              ? 'active'
              : ''
          }
          onClick={() =>
            setSelectedThreadId(
              'all',
            )
          }
        >
          Todo
        </button>

        {snapshot.threads.map(
          (thread) => (
            <button
              type="button"
              key={thread.id}
              className={
                selectedThreadId
                === thread.id
                  ? `active ${thread.status}`
                  : thread.status
              }
              onClick={() =>
                setSelectedThreadId(
                  thread.id,
                )
              }
            >
              <CircleDot
                size={12}
              />

              <span>
                {thread.subject}
              </span>

              <b>
                {thread.message_count}
              </b>
            </button>
          ),
        )}
      </div>


      {selectedThread && (
        <div className="collaboration-thread-info">
          <div>
            <span
              className={`collaboration-thread-status ${selectedThread.status}`}
            >
              {statusLabel(
                selectedThread.status,
              )}
            </span>

            {selectedThread.contract_id && (
              <span>
                Contrato #
                {selectedThread.contract_id}
              </span>
            )}

            {selectedThread.task_id && (
              <span>
                Tarea #
                {selectedThread.task_id}
              </span>
            )}
          </div>

          {selectedThread.kind
            === 'client_coordination'
            && ![
              'resolved',
              'closed',
            ].includes(
              selectedThread.status,
            ) && (
              <button
                type="button"
                onClick={() =>
                  void resolveThread()
                }
              >
                <CheckCheck
                  size={15}
                />

                Resolver
              </button>
            )}
        </div>
      )}


      <div className="collaboration-message-list">
        {loading ? (
          <div className="collaboration-empty">
            <div className="spinner" />

            <span>
              Cargando conversaciones...
            </span>
          </div>
        ) : visibleMessages.length
          === 0 ? (
            <div className="collaboration-empty">
              <MessageSquare
                size={30}
              />

              <strong>
                Sin mensajes
              </strong>

              <span>
                La conversacion comenzara
                cuando R00, el cliente o
                un Repliker envie un mensaje.
              </span>
            </div>
          ) : (
            visibleMessages.map(
              (message) => {
                const senderAgent =
                  agentById(
                    message
                      .sender_repliker_id,
                  )

                const canAcknowledge =
                  message.requires_ack
                  && message.delivery_status
                    === 'sent'
                  && [
                    'project',
                    'client',
                  ].includes(
                    message.receiver_type,
                  )

                return (
                  <div
                    key={message.id}
                    className={`collaboration-message priority-${message.priority}`}
                  >
                    <div className="collaboration-avatar">
                      {senderAgent ? (
                        <ReplikerAvatar
                          appearance={
                            senderAgent
                              .appearance
                          }
                          name={
                            senderAgent
                              .name
                          }
                          size="small"
                          active={
                            senderAgent
                              .is_active
                          }
                        />
                      ) : (
                        <div className="collaboration-system-avatar">
                          {message.sender_type
                            === 'r00'
                            ? 'R00'
                            : message.sender_type
                              === 'project'
                              ? 'CL'
                              : 'SYS'}
                        </div>
                      )}
                    </div>

                    <div className="collaboration-message-content">
                      <div className="collaboration-message-meta">
                        <strong>
                          {participantName(
                            message.sender_type,
                            message.sender_repliker_id,
                          )}
                        </strong>

                        <span>
                          →
                        </span>

                        <b>
                          {participantName(
                            message.receiver_type,
                            message.receiver_repliker_id,
                          )}
                        </b>

                        <time>
                          {dateTimeLabel(
                            message.created_at,
                          )}
                        </time>
                      </div>

                      <p>
                        {message.content}
                      </p>

                      <div className="collaboration-message-tags">
                        <span
                          className={`priority ${message.priority}`}
                        >
                          {priorityLabel(
                            message.priority,
                          )}
                        </span>

                        <span>
                          {message.message_type}
                        </span>

                        <span
                          className={`delivery ${message.delivery_status}`}
                        >
                          {message.delivery_status
                            === 'acknowledged'
                            && (
                              <ShieldCheck
                                size={12}
                              />
                            )}

                          {messageStatusLabel(
                            message.delivery_status,
                          )}
                        </span>

                        {message.contract_id && (
                          <span>
                            Contrato #
                            {message.contract_id}
                          </span>
                        )}

                        {message.task_id && (
                          <span>
                            Tarea #
                            {message.task_id}
                          </span>
                        )}
                      </div>

                      {canAcknowledge && (
                        <button
                          type="button"
                          className="collaboration-ack"
                          onClick={() =>
                            void acknowledge(
                              message.id,
                            )
                          }
                        >
                          <CheckCheck
                            size={14}
                          />

                          Confirmar lectura
                        </button>
                      )}
                    </div>
                  </div>
                )
              },
            )
          )}
      </div>


      <div className="collaboration-composer">
        <div className="collaboration-composer-top">
          <strong>
            Mensaje para R00
          </strong>

          <select
            value={priority}
            onChange={(event) =>
              setPriority(
                event.target.value,
              )
            }
          >
            <option value="low">
              Prioridad baja
            </option>

            <option value="normal">
              Prioridad normal
            </option>

            <option value="high">
              Prioridad alta
            </option>

            <option value="urgent">
              Urgente
            </option>
          </select>
        </div>

        <textarea
          value={composer}
          maxLength={4000}
          placeholder="Escribe una solicitud, aclaracion o informacion para R00..."
          onChange={(event) =>
            setComposer(
              event.target.value,
            )
          }
        />

        <div className="collaboration-composer-footer">
          <span>
            {composer.length}
            /4000
          </span>

          <button
            type="button"
            disabled={
              sending
              || !composer.trim()
            }
            onClick={() =>
              void sendMessage()
            }
          >
            <Send size={15} />

            {sending
              ? 'Enviando...'
              : 'Enviar a R00'}
          </button>
        </div>
      </div>
    </article>
  )
}
