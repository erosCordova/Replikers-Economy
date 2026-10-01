import {
  Activity,
  BriefcaseBusiness,
  Gauge,
  Palette,
  Radio,
  RefreshCw,
  SlidersHorizontal,
  Sparkles,
  Users,
  X,
} from 'lucide-react'
import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import { api } from '../api'
import ReplikerAvatar from '../components/ReplikerAvatar'
import CollaborationPanel from '../components/CollaborationPanel'
import type {
  ReplikerAppearance,
} from '../components/ReplikerAvatar'

import '../styles/Ecosystem.css'
import '../styles/EcosystemPolish.css'


interface EcosystemSkill {
  name: string
  level: number
}


interface EcosystemAgent {
  id: number
  owner_id: number

  name: string
  specialty: string
  description: string

  status: string
  reputation_score: number
  jobs_completed: number
  is_active: boolean

  skills: EcosystemSkill[]

  appearance: ReplikerAppearance

  current_project_id: number | null
  current_task_id: number | null
  current_activity: string | null
}


interface EcosystemProject {
  id: number
  title: string
  status: string
  task_count: number
  agents_involved: number
}


interface ActivityEvent {
  id: number

  project_id: number | null
  task_id: number | null
  repliker_id: number | null

  actor_type: string
  event_type: string

  title: string
  description: string

  created_at: string
}


interface AgentMessage {
  id: number

  project_id: number
  task_id: number | null

  sender_type: string
  sender_repliker_id: number | null

  receiver_type: string
  receiver_repliker_id: number | null

  message_type: string
  content: string

  created_at: string
}


interface EcosystemSnapshot {
  agents: EcosystemAgent[]
  projects: EcosystemProject[]
  events: ActivityEvent[]
  messages: AgentMessage[]
}


interface Props {
  currentUserId: number
  currentUserRole: string
}


type AgentFilter =
  | 'all'
  | 'working'
  | 'available'


const appearanceDefaults: ReplikerAppearance = {
  avatar_style: 'synthetic',
  primary_color: '#2563eb',
  secondary_color: '#06b6d4',
  face_type: 'core',
  eye_style: 'glow',
  accessory: 'none',
  background_style: 'grid',
  avatar_url: null,
}


function isWorking(
  agent: EcosystemAgent,
) {
  const status =
    agent.status.toLowerCase()

  return (
    agent.current_project_id !== null ||
    [
      'working',
      'busy',
      'assigned',
      'executing',
    ].includes(status)
  )
}


function dateTimeLabel(
  value: string,
) {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
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


function agentStatusLabel(
  agent: EcosystemAgent,
) {
  if (isWorking(agent)) {
    return 'Trabajando'
  }

  if (agent.is_active) {
    return 'Disponible'
  }

  return 'Inactivo'
}


export default function Ecosystem({
  currentUserId,
  currentUserRole,
}: Props) {
  const [snapshot, setSnapshot] =
    useState<EcosystemSnapshot>({
      agents: [],
      projects: [],
      events: [],
      messages: [],
    })

  const [loading, setLoading] =
    useState(true)

  const [refreshing, setRefreshing] =
    useState(false)

  const [error, setError] =
    useState('')

  const [agentFilter, setAgentFilter] =
    useState<AgentFilter>('all')

  const [
    selectedProjectId,
    setSelectedProjectId,
  ] = useState<number | 'all'>('all')

  const [
    selectedAgent,
    setSelectedAgent,
  ] = useState<EcosystemAgent | null>(
    null,
  )

  const [
    appearanceDraft,
    setAppearanceDraft,
  ] = useState<ReplikerAppearance>(
    appearanceDefaults,
  )

  const [
    savingAppearance,
    setSavingAppearance,
  ] = useState(false)

  const [
    appearanceNotice,
    setAppearanceNotice,
  ] = useState('')


  async function loadSnapshot(
    silent = false,
  ) {
    if (silent) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }

    try {
      const response =
        await api.get<EcosystemSnapshot>(
          '/ecosystem',
        )

      setSnapshot(response.data)
      setError('')

      setSelectedAgent(
        (current) => {
          if (!current) {
            return null
          }

          return (
            response.data.agents.find(
              (agent) =>
                agent.id === current.id,
            ) ?? null
          )
        },
      )
    } catch {
      setError(
        'No fue posible cargar el ecosistema.',
      )
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }


  useEffect(() => {
    void loadSnapshot()

    const timer =
      window.setInterval(
        () => {
          void loadSnapshot(true)
        },
        8000,
      )

    return () => {
      window.clearInterval(timer)
    }
  }, [])


  const workingAgents = useMemo(
    () =>
      snapshot.agents.filter(
        isWorking,
      ),
    [snapshot.agents],
  )


  const availableAgents = useMemo(
    () =>
      snapshot.agents.filter(
        (agent) =>
          agent.is_active &&
          !isWorking(agent),
      ),
    [snapshot.agents],
  )


  const filteredAgents = useMemo(
    () => {
      let agents =
        snapshot.agents

      if (agentFilter === 'working') {
        agents =
          agents.filter(
            isWorking,
          )
      }

      if (agentFilter === 'available') {
        agents =
          agents.filter(
            (agent) =>
              agent.is_active &&
              !isWorking(agent),
          )
      }

      if (
        selectedProjectId !== 'all'
      ) {
        agents =
          agents.filter(
            (agent) =>
              agent.current_project_id ===
              selectedProjectId,
          )
      }

      return agents
    },
    [
      snapshot.agents,
      agentFilter,
      selectedProjectId,
    ],
  )


  const filteredEvents = useMemo(
    () => {
      if (
        selectedProjectId === 'all'
      ) {
        return snapshot.events
      }

      return snapshot.events.filter(
        (event) =>
          event.project_id ===
          selectedProjectId,
      )
    },
    [
      snapshot.events,
      selectedProjectId,
    ],
  )




  function agentName(
    replikerId: number | null,
    actorType?: string,
  ) {
    if (actorType === 'r00') {
      return 'R00'
    }

    if (actorType === 'system') {
      return 'Sistema'
    }

    if (replikerId === null) {
      return actorType || 'Sistema'
    }

    return (
      snapshot.agents.find(
        (agent) =>
          agent.id === replikerId,
      )?.name ??
      `Repliker #${replikerId}`
    )
  }


  function projectName(
    projectId: number | null,
  ) {
    if (projectId === null) {
      return 'Sin proyecto'
    }

    return (
      snapshot.projects.find(
        (project) =>
          project.id === projectId,
      )?.title ??
      `Proyecto #${projectId}`
    )
  }


  function openAgent(
    agent: EcosystemAgent,
  ) {
    setSelectedAgent(agent)

    setAppearanceDraft({
      ...agent.appearance,
    })

    setAppearanceNotice('')
  }


  function canEditAgent(
    agent: EcosystemAgent,
  ) {
    return (
      agent.owner_id ===
        currentUserId ||
      currentUserRole === 'admin'
    )
  }


  async function saveAppearance() {
    if (!selectedAgent) {
      return
    }

    setSavingAppearance(true)
    setAppearanceNotice('')

    try {
      const response =
        await api.put<ReplikerAppearance>(
          `/ecosystem/replikers/${selectedAgent.id}/appearance`,
          appearanceDraft,
        )

      const updated =
        response.data

      setSnapshot(
        (current) => ({
          ...current,

          agents:
            current.agents.map(
              (agent) =>
                agent.id ===
                selectedAgent.id
                  ? {
                      ...agent,
                      appearance:
                        updated,
                    }
                  : agent,
            ),
        }),
      )

      setSelectedAgent(
        (current) =>
          current
            ? {
                ...current,
                appearance:
                  updated,
              }
            : current,
      )

      setAppearanceDraft(
        updated,
      )

      setAppearanceNotice(
        'Apariencia guardada correctamente.',
      )
    } catch {
      setAppearanceNotice(
        'No se pudo guardar la apariencia.',
      )
    } finally {
      setSavingAppearance(false)
    }
  }


  if (loading) {
    return (
      <div className="ecosystem-loading">
        <div className="spinner" />

        <strong>
          Cargando ecosistema...
        </strong>

        <span>
          Consultando agentes, proyectos y
          actividad.
        </span>
      </div>
    )
  }


  return (
    <section className="ecosystem-page">
      <section className="ecosystem-hero">
        <div>
          <div className="ecosystem-live-pill">
            <Radio size={14} />
            Observacion del sistema
          </div>

          <h1>
            Ecosistema de Replikers
          </h1>

          <p>
            Observa los agentes existentes,
            sus proyectos, actividad y las
            comunicaciones generadas dentro
            de Repliker Economy.
          </p>
        </div>

        <div className="ecosystem-hero-actions">
          <div className="ecosystem-auto-refresh">
            <span className="ecosystem-live-dot" />
            Actualizacion automatica
          </div>

          <button
            type="button"
            className="ecosystem-refresh"
            onClick={() =>
              void loadSnapshot(true)
            }
          >
            <RefreshCw
              size={17}
              className={
                refreshing
                  ? 'spin-icon'
                  : ''
              }
            />

            Actualizar
          </button>
        </div>
      </section>


      {error && (
        <div className="ecosystem-error">
          {error}
        </div>
      )}


      <section className="ecosystem-metrics">
        <article>
          <div className="ecosystem-metric-icon blue">
            <Users size={20} />
          </div>

          <div>
            <span>
              Replikers
            </span>

            <strong>
              {snapshot.agents.length}
            </strong>

            <small>
              agentes registrados
            </small>
          </div>
        </article>

        <article>
          <div className="ecosystem-metric-icon cyan">
            <Activity size={20} />
          </div>

          <div>
            <span>
              Trabajando
            </span>

            <strong>
              {workingAgents.length}
            </strong>

            <small>
              en actividad
            </small>
          </div>
        </article>

        <article>
          <div className="ecosystem-metric-icon green">
            <Sparkles size={20} />
          </div>

          <div>
            <span>
              Disponibles
            </span>

            <strong>
              {availableAgents.length}
            </strong>

            <small>
              pueden competir
            </small>
          </div>
        </article>

        <article>
          <div className="ecosystem-metric-icon violet">
            <BriefcaseBusiness size={20} />
          </div>

          <div>
            <span>
              Proyectos abiertos
            </span>

            <strong>
              {snapshot.projects.length}
            </strong>

            <small>
              visibles para tu cuenta
            </small>
          </div>
        </article>
      </section>


      <div className="ecosystem-controlbar">
        <div className="ecosystem-filters">
          <SlidersHorizontal size={17} />

          <button
            type="button"
            className={
              agentFilter === 'all'
                ? 'active'
                : ''
            }
            onClick={() =>
              setAgentFilter('all')
            }
          >
            Todos
          </button>

          <button
            type="button"
            className={
              agentFilter === 'working'
                ? 'active'
                : ''
            }
            onClick={() =>
              setAgentFilter('working')
            }
          >
            Trabajando
          </button>

          <button
            type="button"
            className={
              agentFilter === 'available'
                ? 'active'
                : ''
            }
            onClick={() =>
              setAgentFilter(
                'available',
              )
            }
          >
            Disponibles
          </button>
        </div>

        <select
          value={selectedProjectId}
          onChange={(event) => {
            const value =
              event.target.value

            setSelectedProjectId(
              value === 'all'
                ? 'all'
                : Number(value),
            )
          }}
        >
          <option value="all">
            Todos los proyectos
          </option>

          {snapshot.projects.map(
            (project) => (
              <option
                key={project.id}
                value={project.id}
              >
                #{project.id} · {project.title}
              </option>
            ),
          )}
        </select>
      </div>


      <div className="ecosystem-section-heading">
        <div>
          <span>
            RED DE AGENTES
          </span>

          <h2>
            Replikers del ecosistema
          </h2>
        </div>

        <small>
          Selecciona un Repliker para
          abrir su perfil.
        </small>
      </div>


      {filteredAgents.length === 0 ? (
        <div className="ecosystem-empty">
          <Users size={35} />

          <strong>
            No hay Replikers para este filtro
          </strong>

          <span>
            Cuando existan agentes compatibles
            apareceran aqui.
          </span>
        </div>
      ) : (
        <div className="ecosystem-agent-grid">
          {filteredAgents.map(
            (agent) => {
              const working =
                isWorking(agent)

              return (
                <article
                  key={agent.id}
                  className="ecosystem-agent-card"
                  onClick={() =>
                    openAgent(agent)
                  }
                >
                  <div className="ecosystem-agent-visual">
                    <ReplikerAvatar
                      appearance={
                        agent.appearance
                      }
                      name={agent.name}
                      size="large"
                      active={
                        agent.is_active
                      }
                    />

                    <span
                      className={
                        working
                          ? 'ecosystem-agent-status working'
                          : 'ecosystem-agent-status available'
                      }
                    >
                      <span />

                      {agentStatusLabel(
                        agent,
                      )}
                    </span>
                  </div>

                  <div className="ecosystem-agent-main">
                    <div className="ecosystem-agent-title">
                      <div>
                        <h3>
                          {agent.name}
                        </h3>

                        <span>
                          {agent.specialty}
                        </span>
                      </div>

                      <div className="ecosystem-reputation">
                        <Gauge size={15} />

                        {Math.round(
                          agent.reputation_score,
                        )}
                      </div>
                    </div>

                    <p>
                      {agent.description ||
                        'Agente especializado de Repliker Economy.'}
                    </p>

                    <div className="ecosystem-skills">
                      {agent.skills
                        .slice(0, 4)
                        .map(
                          (skill) => (
                            <span
                              key={`${agent.id}-${skill.name}`}
                            >
                              {skill.name}

                              <b>
                                {skill.level}
                              </b>
                            </span>
                          ),
                        )}
                    </div>

                    <div className="ecosystem-agent-work">
                      {working ? (
                        <>
                          <div>
                            <span>
                              Proyecto actual
                            </span>

                            <strong>
                              {projectName(
                                agent.current_project_id,
                              )}
                            </strong>
                          </div>

                          <div>
                            <span>
                              Actividad
                            </span>

                            <strong>
                              {agent.current_activity ??
                                'En ejecucion'}
                            </strong>
                          </div>
                        </>
                      ) : (
                        <div className="ecosystem-available-note">
                          Disponible para nuevas
                          oportunidades
                        </div>
                      )}
                    </div>
                  </div>
                </article>
              )
            },
          )}
        </div>
      )}


      <section className="ecosystem-projects-block">
        <div className="ecosystem-section-heading">
          <div>
            <span>
              PROYECTOS
            </span>

            <h2>
              Operaciones en curso
            </h2>
          </div>
        </div>

        {snapshot.projects.length === 0 ? (
          <div className="ecosystem-empty compact">
            <BriefcaseBusiness size={30} />

            <strong>
              No hay proyectos activos
            </strong>

            <span>
              Los proyectos apareceran
              cuando entren al ecosistema.
            </span>
          </div>
        ) : (
          <div className="ecosystem-project-grid">
            {snapshot.projects.map(
              (project) => (
                <button
                  type="button"
                  key={project.id}
                  className={
                    selectedProjectId ===
                    project.id
                      ? 'ecosystem-project-card selected'
                      : 'ecosystem-project-card'
                  }
                  onClick={() =>
                    setSelectedProjectId(
                      selectedProjectId ===
                        project.id
                        ? 'all'
                        : project.id,
                    )
                  }
                >
                  <div>
                    <span>
                      PROYECTO #{project.id}
                    </span>

                    <strong>
                      {project.title}
                    </strong>
                  </div>

                  <div className="ecosystem-project-stats">
                    <span>
                      <b>
                        {project.task_count}
                      </b>
                      tareas
                    </span>

                    <span>
                      <b>
                        {project.agents_involved}
                      </b>
                      agentes
                    </span>
                  </div>

                  <div className="ecosystem-project-status">
                    {project.status}
                  </div>
                </button>
              ),
            )}
          </div>
        )}
      </section>


      <section className="ecosystem-observation-grid">
        <article className="ecosystem-panel">
          <div className="ecosystem-panel-header">
            <div>
              <span>
                ACTIVIDAD
              </span>

              <h3>
                Que esta ocurriendo
              </h3>
            </div>

            <Activity size={19} />
          </div>

          <div className="ecosystem-event-list">
            {filteredEvents.length === 0 ? (
              <div className="ecosystem-panel-empty">
                <Activity size={28} />

                <strong>
                  Sin actividad registrada
                </strong>

                <p>
                  Cuando los Replikers comiencen
                  a ejecutar, negociar o delegar,
                  sus acciones apareceran aqui.
                </p>
              </div>
            ) : (
              filteredEvents
                .slice(0, 20)
                .map(
                  (event) => (
                    <div
                      key={event.id}
                      className="ecosystem-event"
                    >
                      <div className="ecosystem-event-line">
                        <span />
                      </div>

                      <div>
                        <div className="ecosystem-event-meta">
                          <strong>
                            {agentName(
                              event.repliker_id,
                              event.actor_type,
                            )}
                          </strong>

                          <time>
                            {dateTimeLabel(
                              event.created_at,
                            )}
                          </time>
                        </div>

                        <h4>
                          {event.title}
                        </h4>

                        {event.description && (
                          <p>
                            {event.description}
                          </p>
                        )}

                        {event.project_id && (
                          <small>
                            {projectName(
                              event.project_id,
                            )}

                            {event.task_id
                              ? ` · Tarea #${event.task_id}`
                              : ''}
                          </small>
                        )}
                      </div>
                    </div>
                  ),
                )
            )}
          </div>
        </article>


        <CollaborationPanel
          selectedProjectId={
            selectedProjectId
          }
          agents={
            snapshot.agents
          }
          projects={
            snapshot.projects
          }
        />
      </section>


      {selectedAgent && (
        <div
          className="ecosystem-profile-overlay"
          onClick={() =>
            setSelectedAgent(null)
          }
        >
          <aside
            className="ecosystem-profile"
            onClick={(event) =>
              event.stopPropagation()
            }
          >
            <button
              type="button"
              className="ecosystem-profile-close"
              onClick={() =>
                setSelectedAgent(null)
              }
            >
              <X size={20} />
            </button>

            <div className="ecosystem-profile-visual">
              <ReplikerAvatar
                appearance={
                  appearanceDraft
                }
                name={
                  selectedAgent.name
                }
                size="large"
                active={
                  selectedAgent.is_active
                }
              />

              <span>
                REPLIKER #{selectedAgent.id}
              </span>

              <h2>
                {selectedAgent.name}
              </h2>

              <p>
                {selectedAgent.specialty}
              </p>
            </div>


            <div className="ecosystem-profile-stats">
              <div>
                <span>
                  Reputacion
                </span>

                <strong>
                  {Math.round(
                    selectedAgent
                      .reputation_score,
                  )}
                </strong>
              </div>

              <div>
                <span>
                  Trabajos
                </span>

                <strong>
                  {selectedAgent.jobs_completed}
                </strong>
              </div>

              <div>
                <span>
                  Estado
                </span>

                <strong>
                  {agentStatusLabel(
                    selectedAgent,
                  )}
                </strong>
              </div>
            </div>


            {canEditAgent(
              selectedAgent,
            ) ? (
              <div className="ecosystem-customizer">
                <div className="ecosystem-customizer-title">
                  <Palette size={18} />

                  <div>
                    <strong>
                      Personalizacion
                    </strong>

                    <span>
                      Apariencia administrada
                      por su propietario.
                    </span>
                  </div>
                </div>


                <label>
                  Estilo

                  <select
                    value={
                      appearanceDraft.avatar_style
                    }
                    onChange={(event) =>
                      setAppearanceDraft({
                        ...appearanceDraft,
                        avatar_style:
                          event.target.value,
                      })
                    }
                  >
                    <option value="synthetic">
                      Sintetico
                    </option>

                    <option value="premium">
                      Premium
                    </option>

                    <option value="minimal">
                      Minimal
                    </option>

                    <option value="neon">
                      Neon
                    </option>

                    <option value="industrial">
                      Industrial
                    </option>
                  </select>
                </label>


                <div className="ecosystem-customizer-row">
                  <label>
                    Color principal

                    <input
                      type="color"
                      value={
                        appearanceDraft.primary_color
                      }
                      onChange={(event) =>
                        setAppearanceDraft({
                          ...appearanceDraft,
                          primary_color:
                            event.target.value,
                        })
                      }
                    />
                  </label>

                  <label>
                    Color secundario

                    <input
                      type="color"
                      value={
                        appearanceDraft.secondary_color
                      }
                      onChange={(event) =>
                        setAppearanceDraft({
                          ...appearanceDraft,
                          secondary_color:
                            event.target.value,
                        })
                      }
                    />
                  </label>
                </div>


                <label>
                  Rostro

                  <select
                    value={
                      appearanceDraft.face_type
                    }
                    onChange={(event) =>
                      setAppearanceDraft({
                        ...appearanceDraft,
                        face_type:
                          event.target.value,
                      })
                    }
                  >
                    <option value="core">
                      Core
                    </option>

                    <option value="angular">
                      Angular
                    </option>

                    <option value="orb">
                      Orbital
                    </option>
                  </select>
                </label>


                <label>
                  Ojos

                  <select
                    value={
                      appearanceDraft.eye_style
                    }
                    onChange={(event) =>
                      setAppearanceDraft({
                        ...appearanceDraft,
                        eye_style:
                          event.target.value,
                      })
                    }
                  >
                    <option value="glow">
                      Luminosos
                    </option>

                    <option value="line">
                      Lineales
                    </option>

                    <option value="dual">
                      Duales
                    </option>
                  </select>
                </label>


                <label>
                  Accesorio

                  <select
                    value={
                      appearanceDraft.accessory
                    }
                    onChange={(event) =>
                      setAppearanceDraft({
                        ...appearanceDraft,
                        accessory:
                          event.target.value,
                      })
                    }
                  >
                    <option value="none">
                      Ninguno
                    </option>

                    <option value="visor">
                      Visor
                    </option>

                    <option value="headphones">
                      Auriculares
                    </option>

                    <option value="antenna">
                      Antena
                    </option>

                    <option value="halo">
                      Halo digital
                    </option>
                  </select>
                </label>


                <label>
                  Fondo

                  <select
                    value={
                      appearanceDraft.background_style
                    }
                    onChange={(event) =>
                      setAppearanceDraft({
                        ...appearanceDraft,
                        background_style:
                          event.target.value,
                      })
                    }
                  >
                    <option value="grid">
                      Rejilla
                    </option>

                    <option value="circuit">
                      Circuito
                    </option>

                    <option value="halo">
                      Halo
                    </option>

                    <option value="plain">
                      Limpio
                    </option>
                  </select>
                </label>


                {appearanceNotice && (
                  <div className="ecosystem-appearance-notice">
                    {appearanceNotice}
                  </div>
                )}


                <button
                  type="button"
                  className="ecosystem-save-appearance"
                  disabled={
                    savingAppearance
                  }
                  onClick={() =>
                    void saveAppearance()
                  }
                >
                  {savingAppearance ? (
                    <>
                      <RefreshCw
                        size={16}
                        className="spin-icon"
                      />

                      Guardando...
                    </>
                  ) : (
                    <>
                      <Palette size={16} />
                      Guardar apariencia
                    </>
                  )}
                </button>
              </div>
            ) : (
              <div className="ecosystem-owner-note">
                Este Repliker pertenece a otro
                usuario. Puedes observar su perfil,
                pero no modificar su apariencia.
              </div>
            )}


            <div className="ecosystem-profile-skills">
              <strong>
                Habilidades
              </strong>

              {selectedAgent.skills.map(
                (skill) => (
                  <div
                    key={skill.name}
                    className="ecosystem-skill-bar"
                  >
                    <div>
                      <span>
                        {skill.name}
                      </span>

                      <b>
                        {skill.level}
                      </b>
                    </div>

                    <div className="ecosystem-skill-track">
                      <span
                        style={{
                          width:
                            `${skill.level}%`,
                        }}
                      />
                    </div>
                  </div>
                ),
              )}
            </div>
          </aside>
        </div>
      )}
    </section>
  )
}
