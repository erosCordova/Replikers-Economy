import {
  Activity,
  ArrowRight,
  BriefcaseBusiness,
  Clock3,
  MessageCircle,
  Network,
  Radio,
  Route,
  Sparkles,
  Users,
} from 'lucide-react'

import ReplikerAvatar from './ReplikerAvatar'

import type {
  ReplikerAppearance,
} from './ReplikerAvatar'

import '../styles/LivingEcosystem.css'


interface LivingAgent {
  id: number
  owner_id: number

  name: string
  specialty: string
  description: string

  status: string
  reputation_score: number
  jobs_completed: number
  is_active: boolean

  skills: {
    name: string
    level: number
  }[]

  appearance: ReplikerAppearance

  current_project_id:
    number | null

  current_task_id:
    number | null

  current_activity:
    string | null
}


interface LivingProject {
  id: number
  title: string
  status: string

  task_count: number
  agents_involved: number
}


interface LivingEvent {
  id: number

  project_id:
    number | null

  task_id:
    number | null

  repliker_id:
    number | null

  actor_type: string
  event_type: string

  title: string
  description: string

  created_at: string
}


interface LivingMessage {
  id: number

  project_id: number
  task_id: number | null

  sender_type: string
  sender_repliker_id:
    number | null

  receiver_type: string
  receiver_repliker_id:
    number | null

  message_type: string
  content: string

  created_at: string
}


interface Props {
  agents: LivingAgent[]
  projects: LivingProject[]
  events: LivingEvent[]
  messages: LivingMessage[]

  selectedProjectId:
    number | 'all'

  onSelectProject:
    (
      value:
        number | 'all',
    ) => void

  onSelectAgent:
    (
      agent: LivingAgent,
    ) => void

  specialtyLabel:
    (
      value: string,
    ) => string
}


type PresenceState =
  | 'collaborating'
  | 'working'
  | 'available'
  | 'waiting'
  | 'inactive'


function normalizedStatus(
  value: string,
) {
  return (
    value
      .trim()
      .toLowerCase()
  )
}


function isWorking(
  agent: LivingAgent,
) {
  return (
    agent.current_project_id
      !== null
    ||
    [
      'working',
      'busy',
      'assigned',
      'executing',
    ].includes(
      normalizedStatus(
        agent.status,
      ),
    )
  )
}


function isAvailable(
  agent: LivingAgent,
) {
  return (
    agent.is_active
    &&
    !isWorking(agent)
    &&
    [
      '',
      'available',
      'ready',
    ].includes(
      normalizedStatus(
        agent.status,
      ),
    )
  )
}


function presenceState(
  agent: LivingAgent,
  projectAgents: number,
): PresenceState {
  if (!agent.is_active) {
    return 'inactive'
  }

  if (isWorking(agent)) {
    return (
      projectAgents > 1
        ? 'collaborating'
        : 'working'
    )
  }

  if (isAvailable(agent)) {
    return 'available'
  }

  return 'waiting'
}


function presenceLabel(
  state: PresenceState,
) {
  switch (state) {
    case 'collaborating':
      return 'Colaborando'

    case 'working':
      return 'En misión'

    case 'available':
      return 'Disponible'

    case 'waiting':
      return 'En espera'

    default:
      return 'En reposo'
  }
}


function projectStatusLabel(
  value: string,
) {
  const labels:
    Record<string, string> = {
      draft:
        'Borrador',

      planned:
        'Planificado',

      planning:
        'Planificación',

      open:
        'Abierto',

      market:
        'En mercado',

      contracted:
        'Contratado',

      executing:
        'En ejecución',

      qa:
        'En pruebas',

      awaiting_final_review:
        'Esperando revisión final',

      correcting:
        'En corrección',

      completed:
        'Completado',

      failed:
        'Fallido',
    }

  return (
    labels[
      normalizedStatus(value)
    ]
    ??
    'En proceso'
  )
}


function isRecentEvent(
  value: string,
) {
  const time =
    new Date(value).getTime()

  if (
    Number.isNaN(time)
  ) {
    return false
  }

  return (
    Date.now() - time
    < 45_000
  )
}


function eventLabel(
  event: LivingEvent,
) {
  const labels:
    Record<string, string> = {
      task_started:
        'Comenzó una tarea',

      work_started:
        'Comenzó a trabajar',

      task_executing:
        'Ejecutando tarea',

      execution_started:
        'Ejecución iniciada',

      revision_started:
        'Revisión iniciada',

      qa_started:
        'Pruebas iniciadas',

      delegated_task_started:
        'Tarea delegada iniciada',

      task_completed:
        'Tarea completada',

      execution_completed:
        'Ejecución completada',

      qa_completed:
        'Pruebas completadas',

      project_completed:
        'Proyecto completado',
  }

  return (
    labels[event.event_type]
    ?? event.title
    ?? 'Actividad registrada'
  )
}


type MissionPhase =
  | 'joining'
  | 'executing'
  | 'collaborating'
  | 'returning'
  | 'available'
  | 'waiting'
  | 'resting'


function missionPhase(
  agent: LivingAgent,
  event: LivingEvent | undefined,
  projectAgents: number,
): MissionPhase {
  if (!agent.is_active) {
    return 'resting'
  }

  const eventType =
    (
      event?.event_type
      ?? ''
    ).toLowerCase()

  const recent =
    event
      ? isRecentEvent(
          event.created_at,
        )
      : false

  if (
    agent.current_project_id
    === null
  ) {
    if (
      recent
      &&
      (
        eventType.includes(
          'completed',
        )
        ||
        eventType.includes(
          'finished',
        )
        ||
        eventType.includes(
          'settled',
        )
        ||
        eventType.includes(
          'released',
        )
        ||
        eventType.includes(
          'closed',
        )
      )
    ) {
      return 'returning'
    }

    return (
      isAvailable(agent)
        ? 'available'
        : 'waiting'
    )
  }

  if (
    recent
    &&
    (
      eventType.includes(
        'accepted',
      )
      ||
      eventType.includes(
        'assigned',
      )
      ||
      eventType.includes(
        'contract',
      )
      ||
      eventType.includes(
        'delegat',
      )
    )
  ) {
    return 'joining'
  }

  if (projectAgents > 1) {
    return 'collaborating'
  }

  return 'executing'
}


function missionPhaseLabel(
  phase: MissionPhase,
) {
  switch (phase) {
    case 'joining':
      return 'Entrando a misión'

    case 'executing':
      return 'Ejecutando'

    case 'collaborating':
      return 'Colaborando'

    case 'returning':
      return 'Regresando al claro'

    case 'available':
      return 'Listo para misión'

    case 'waiting':
      return 'En espera'

    default:
      return 'En reposo'
  }
}


function relativeTime(
  value: string,
) {
  const time =
    new Date(value).getTime()

  if (
    Number.isNaN(time)
  ) {
    return ''
  }

  const seconds =
    Math.max(
      0,
      Math.floor(
        (
          Date.now()
          - time
        )
        / 1000,
      ),
    )

  if (seconds < 60) {
    return 'Ahora'
  }

  const minutes =
    Math.floor(
      seconds / 60,
    )

  if (minutes < 60) {
    return (
      `Hace ${minutes} min`
    )
  }

  const hours =
    Math.floor(
      minutes / 60,
    )

  if (hours < 24) {
    return (
      `Hace ${hours} h`
    )
  }

  const days =
    Math.floor(
      hours / 24,
    )

  return (
    `Hace ${days} d`
  )
}


export default function LivingEcosystem({
  agents,
  projects,
  events,
  messages,
  selectedProjectId,
  onSelectProject,
  onSelectAgent,
  specialtyLabel,
}: Props) {
  const projectAgentCounts =
    new Map<number, number>()

  agents.forEach(
    (agent) => {
      if (
        agent.current_project_id
        === null
      ) {
        return
      }

      projectAgentCounts.set(
        agent.current_project_id,
        (
          projectAgentCounts.get(
            agent.current_project_id,
          )
          ?? 0
        ) + 1,
      )
    },
  )


  const latestEventByAgent =
    new Map<
      number,
      LivingEvent
    >()

  events.forEach(
    (event) => {
      if (
        event.repliker_id
        === null
        ||
        latestEventByAgent.has(
          event.repliker_id,
        )
      ) {
        return
      }

      latestEventByAgent.set(
        event.repliker_id,
        event,
      )
    },
  )


  const latestEventByProject =
    new Map<
      number,
      LivingEvent
    >()

  events.forEach(
    (event) => {
      if (
        event.project_id
        === null
        ||
        latestEventByProject.has(
          event.project_id,
        )
      ) {
        return
      }

      latestEventByProject.set(
        event.project_id,
        event,
      )
    },
  )


  const latestSignals =
    events
      .filter(
        (event) =>
          event.repliker_id
          !== null,
      )
      .slice(
        0,
        5,
      )


  const messageLinksByProject =
    new Map<
      number,
      LivingMessage[]
    >()

  const seenMessageLinks =
    new Set<string>()

  messages.forEach(
    (message) => {
      if (
        message.sender_repliker_id
        === null
        ||
        message.receiver_repliker_id
        === null
      ) {
        return
      }

      const first =
        Math.min(
          message.sender_repliker_id,
          message.receiver_repliker_id,
        )

      const second =
        Math.max(
          message.sender_repliker_id,
          message.receiver_repliker_id,
        )

      const key =
        (
          `${message.project_id}:` +
          `${first}:${second}`
        )

      if (
        seenMessageLinks.has(key)
      ) {
        return
      }

      seenMessageLinks.add(key)

      const current =
        messageLinksByProject.get(
          message.project_id,
        )
        ?? []

      if (current.length >= 4) {
        return
      }

      messageLinksByProject.set(
        message.project_id,
        [
          ...current,
          message,
        ],
      )
    },
  )


  function agentName(
    replikerId: number | null,
  ) {
    if (replikerId === null) {
      return 'Sistema'
    }

    return (
      agents.find(
        (agent) =>
          agent.id ===
          replikerId,
      )?.name
      ??
      `Repliker #${replikerId}`
    )
  }


  const recentEvents =
    events.filter(
      (event) =>
        isRecentEvent(
          event.created_at,
        ),
    )

  const latestGlobalEvent =
    events[0]

  const ecosystemPulse =
    recentEvents.length >= 5
      ? 'intense'
      : recentEvents.length >= 2
        ? 'active'
        : recentEvents.length === 1
          ? 'soft'
          : 'quiet'


  function pulseLabel() {
    switch (ecosystemPulse) {
      case 'intense':
        return 'Actividad intensa'

      case 'active':
        return 'Actividad sostenida'

      case 'soft':
        return 'Actividad reciente'

      default:
        return 'Red tranquila'
    }
  }


  const workingAgents =
    agents.filter(
      isWorking,
    )

  const collaboratingAgents =
    workingAgents.filter(
      (agent) =>
        agent.current_project_id
          !== null
        &&
        (
          projectAgentCounts.get(
            agent.current_project_id,
          )
          ?? 0
        ) > 1,
    )

  const availableAgents =
    agents.filter(
      isAvailable,
    )

  const waitingAgents =
    agents.filter(
      (agent) =>
        agent.is_active
        &&
        !isWorking(agent)
        &&
        !isAvailable(agent),
    )

  const inactiveAgents =
    agents.filter(
      (agent) =>
        !agent.is_active,
    )


  const visibleProjects =
    projects.filter(
      (project) =>
        selectedProjectId
          === 'all'
        ||
        project.id
          === selectedProjectId,
    )


  function renderAgentNode(
    agent: LivingAgent,
  ) {
    const projectAgents =
      agent.current_project_id
        === null
        ? 0
        : (
            projectAgentCounts.get(
              agent.current_project_id,
            )
            ?? 0
          )

    const state =
      presenceState(
        agent,
        projectAgents,
      )

    const event =
      latestEventByAgent.get(
        agent.id,
      )

    const recent =
      event
        ? isRecentEvent(
            event.created_at,
          )
        : false

    const phase =
      missionPhase(
        agent,
        event,
        projectAgents,
      )

    return (
      <button
        type="button"
        key={agent.id}
        className={[
          'living-agent-node',
          state,
          recent
            ? 'recent-activity'
            : '',
          `phase-${phase}`,
        ].join(' ')}
        onClick={() =>
          onSelectAgent(agent)
        }
        aria-label={
          `${agent.name}. ` +
          `${specialtyLabel(agent.specialty)}. ` +
          `${missionPhaseLabel(phase)}.`
        }
      >
        <span className="living-agent-orbit" />

        <span className="living-agent-avatar">
          <ReplikerAvatar
            appearance={
              agent.appearance
            }
            name={agent.name}
            size="medium"
            active={
              state === 'working'
              ||
              state ===
                'collaborating'
            }
          />

          <span
            className={
              `living-presence-dot ${state}`
            }
          />
        </span>

        <span className="living-agent-copy">
          <strong>
            {agent.name}
          </strong>

          <small>
            {specialtyLabel(
              agent.specialty,
            )}
          </small>

          <span
            className={
              `living-state ${state}`
            }
          >
            {presenceLabel(
              state,
            )}
          </span>

          <span
            className={
              `living-mission-phase ${phase}`
            }
          >
            <Route size={9} />

            {missionPhaseLabel(
              phase,
            )}
          </span>

          {agent.current_activity && (
            <span className="living-current-activity">
              {agent.current_activity}
            </span>
          )}

          {event && (
            <em>
              {recent && (
                <i>
                  Señal reciente
                </i>
              )}

              {relativeTime(
                event.created_at,
              )}
            </em>
          )}
        </span>
      </button>
    )
  }


  return (
    <section className="living-ecosystem">
      <div className="living-ecosystem-head">
        <div>
          <span className="living-kicker">
            <Radio size={14} />
            ECOSISTEMA VIVO
          </span>

          <h2>
            Bosque Repliker
          </h2>

          <p>
            Presencia, colaboración y
            actividad de los Replikers
            dentro de la red.
          </p>
        </div>

        <div className="living-network-state">
          <span />

          Red activa

          <strong>
            {agents.length}
          </strong>
        </div>
      </div>


      <div
        className={
          `living-pulse-panel ${ecosystemPulse}`
        }
      >
        <div className="living-pulse-core">
          <span className="living-pulse-wave" />

          <Activity size={16} />
        </div>

        <div className="living-pulse-copy">
          <span>
            Pulso del ecosistema
          </span>

          <strong>
            {pulseLabel()}
          </strong>
        </div>

        <div className="living-pulse-meta">
          <span>
            {
              recentEvents.length
            } señales recientes
          </span>

          <span>
            {
              latestGlobalEvent
                ? relativeTime(
                    latestGlobalEvent
                      .created_at,
                  )
                : 'Sin actividad reciente'
            }
          </span>
        </div>
      </div>


      <div className="living-summary">
        <article>
          <Activity size={17} />

          <div>
            <strong>
              {workingAgents.length}
            </strong>

            <span>
              En misión
            </span>
          </div>
        </article>

        <article>
          <Network size={17} />

          <div>
            <strong>
              {
                collaboratingAgents
                  .length
              }
            </strong>

            <span>
              Colaborando
            </span>
          </div>
        </article>

        <article>
          <Sparkles size={17} />

          <div>
            <strong>
              {availableAgents.length}
            </strong>

            <span>
              Disponibles
            </span>
          </div>
        </article>

        <article>
          <Clock3 size={17} />

          <div>
            <strong>
              {waitingAgents.length}
            </strong>

            <span>
              En espera
            </span>
          </div>
        </article>
      </div>


      <div className="living-signal-stream">
        <div className="living-signal-title">
          <Radio size={14} />

          <span>
            Señales recientes
          </span>
        </div>

        {latestSignals.length === 0 ? (
          <div className="living-signal-empty">
            Esperando nueva actividad
          </div>
        ) : (
          <div className="living-signal-list">
            {latestSignals.map(
              (event) => {
                const agent =
                  agents.find(
                    (item) =>
                      item.id ===
                      event.repliker_id,
                  )

                return (
                  <article
                    key={event.id}
                    className={
                      isRecentEvent(
                        event.created_at,
                      )
                        ? 'recent'
                        : ''
                    }
                  >
                    <span className="living-signal-pulse" />

                    <div>
                      <strong>
                        {agent?.name ??
                          `Repliker #${event.repliker_id}`}
                      </strong>

                      <small>
                        {eventLabel(
                          event,
                        )}
                      </small>
                    </div>

                    <time>
                      {relativeTime(
                        event.created_at,
                      )}
                    </time>
                  </article>
                )
              },
            )}
          </div>
        )}
      </div>


      <div className="living-world">
        <div className="living-world-grid" />

        <div className="living-world-glow glow-one" />
        <div className="living-world-glow glow-two" />


        <div className="living-project-zone">
          <div className="living-zone-title">
            <div>
              <BriefcaseBusiness
                size={17}
              />

              <div>
                <strong>
                  Misiones activas
                </strong>

                <span>
                  Replikers agrupados
                  por proyecto
                </span>
              </div>
            </div>

            <b>
              {
                visibleProjects
                  .length
              }
            </b>
          </div>


          {visibleProjects.length ===
          0 ? (
            <div className="living-zone-empty">
              <BriefcaseBusiness
                size={24}
              />

              <strong>
                Sin misiones activas
              </strong>

              <span>
                Los equipos aparecerán
                aquí cuando un proyecto
                entre en ejecución.
              </span>
            </div>
          ) : (
            <div className="living-project-list">
              {visibleProjects.map(
                (project) => {
                  const members =
                    agents.filter(
                      (agent) =>
                        agent
                          .current_project_id
                        === project.id,
                    )

                  const selected =
                    selectedProjectId
                    === project.id

                  const projectEvent =
                    latestEventByProject.get(
                      project.id,
                    )

                  const projectRecent =
                    projectEvent
                      ? isRecentEvent(
                          projectEvent
                            .created_at,
                        )
                      : false

                  const messageLinks =
                    messageLinksByProject.get(
                      project.id,
                    )
                    ?? []

                  return (
                    <article
                      key={
                        project.id
                      }
                      className={[
                        'living-project',
                        selected
                          ? 'selected'
                          : '',
                        projectRecent
                          ? 'recent-activity'
                          : '',
                      ].join(' ')}
                    >
                      <button
                        type="button"
                        className="living-project-head"
                        onClick={() =>
                          onSelectProject(
                            selected
                              ? 'all'
                              : project.id,
                          )
                        }
                        aria-pressed={
                          selected
                        }
                        aria-label={
                          selected
                            ? (
                                `Quitar filtro del proyecto ` +
                                `${project.title}`
                              )
                            : (
                                `Mostrar proyecto ` +
                                `${project.title}`
                              )
                        }
                      >
                        <span>
                          Proyecto #{project.id}
                        </span>

                        <strong>
                          {project.title}
                        </strong>

                        <small>
                          {projectStatusLabel(
                            project.status,
                          )}
                        </small>

                        {projectRecent && (
                          <span className="living-project-live">
                            <Radio
                              size={10}
                            />
                            Actividad ahora
                          </span>
                        )}
                      </button>

                      <div className="living-project-line">
                        <span />
                      </div>

                      <div className="living-project-members">
                        {members.length ===
                        0 ? (
                          <div className="living-awaiting-team">
                            <Users
                              size={17}
                            />

                            Esperando
                            asignaciones
                          </div>
                        ) : (
                          members.map(
                            renderAgentNode,
                          )
                        )}
                      </div>

                      {messageLinks.length > 0 && (
                        <div className="living-project-links">
                          <div className="living-project-links-title">
                            <MessageCircle
                              size={11}
                            />

                            <span>
                              Comunicación activa
                            </span>
                          </div>

                          <div className="living-link-list">
                            {messageLinks.map(
                              (message) => (
                                <div
                                  key={
                                    message.id
                                  }
                                  className={
                                    isRecentEvent(
                                      message.created_at,
                                    )
                                      ? 'living-link recent'
                                      : 'living-link'
                                  }
                                  title={
                                    message.content
                                  }
                                >
                                  <strong>
                                    {agentName(
                                      message.sender_repliker_id,
                                    )}
                                  </strong>

                                  <span className="living-link-path">
                                    <i />

                                    <ArrowRight
                                      size={8}
                                    />
                                  </span>

                                  <strong>
                                    {agentName(
                                      message.receiver_repliker_id,
                                    )}
                                  </strong>
                                </div>
                              ),
                            )}
                          </div>
                        </div>
                      )}

                      <footer>
                        <span>
                          {
                            project
                              .task_count
                          } tareas
                        </span>

                        <span>
                          {
                            project
                              .agents_involved
                          } participantes
                        </span>
                      </footer>
                    </article>
                  )
                },
              )}
            </div>
          )}
        </div>


        <aside className="living-availability-zone">
          <div className="living-zone-title">
            <div>
              <Sparkles
                size={17}
              />

              <div>
                <strong>
                  Claro disponible
                </strong>

                <span>
                  Preparados para una
                  nueva oportunidad
                </span>
              </div>
            </div>

            <b>
              {availableAgents.length}
            </b>
          </div>

          <div className="living-available-cloud">
            {availableAgents.length ===
            0 ? (
              <div className="living-zone-empty compact">
                <Activity
                  size={22}
                />

                <strong>
                  Todos están ocupados
                </strong>
              </div>
            ) : (
              availableAgents.map(
                renderAgentNode,
              )
            )}
          </div>


          {waitingAgents.length > 0 && (
            <div className="living-waiting">
              <span>
                En espera
              </span>

              <div>
                {waitingAgents.map(
                  renderAgentNode,
                )}
              </div>
            </div>
          )}


          {inactiveAgents.length > 0 && (
            <div className="living-resting">
              <span>
                En reposo
              </span>

              <strong>
                {
                  inactiveAgents
                    .length
                }
              </strong>
            </div>
          )}
        </aside>
      </div>


      <div className="living-legend">
        <span>
          <i className="collaborating" />
          Colaborando
        </span>

        <span>
          <i className="working" />
          En misión
        </span>

        <span>
          <i className="available" />
          Disponible
        </span>

        <span>
          <i className="waiting" />
          En espera
        </span>
      </div>
    </section>
  )
}
