import {
  Palette,
  Radio,
  RefreshCw,
  X,
} from 'lucide-react'
import {
  useCallback,
  useEffect,
  useState,
} from 'react'

import { api } from '../api'
import ReplikerHumano from '../components/ReplikerHumano'
import PanelColaboracion from '../components/PanelColaboracion'
import ActividadProyectoEnVivo from '../components/ActividadProyectoEnVivo'
import CentroControlAgentes from '../components/CentroControlAgentes'
import EstudioRepliker from '../components/EstudioRepliker'
import BosqueRepliker from '../components/BosqueRepliker'
import type {
  ReplikerAppearance,
} from '../components/ReplikerHumano'

import '../styles/Ecosistema.css'
import '../styles/PulidoEcosistema.css'


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



const specialtyLabelsEs:
  Record<string, string> = {
    'Generalist':
      'Generalista',
    'Product / Requirements':
      'Producto y Requisitos',
    'Software Architect':
      'Arquitecto de Software',
    'UX Research':
      'Investigación de Experiencia de Usuario',
    'UI Designer':
      'Diseñador de Interfaz',
    'Frontend Developer':
      'Desarrollador de Interfaz',
    'Backend Developer':
      'Desarrollador de Servidor',
    'Database Engineer':
      'Ingeniero de Base de Datos',
    'Integration Specialist':
      'Especialista en Integraciones',
    'Security Engineer':
      'Ingeniero de Seguridad',
    'QA Engineer':
      'Ingeniero de Pruebas',
    'DevOps Engineer':
      'Ingeniero de Operaciones y Despliegue',
    'Accessibility Specialist':
      'Especialista en Accesibilidad',
    'SEO/Performance Specialist':
      'Especialista en Posicionamiento y Rendimiento',
    'Content/Copy Specialist':
      'Especialista en Contenido',
    'Final Reviewer':
      'Revisor Final',
  }


function specialtyLabelEs(
  value: string,
) {
  return (
    specialtyLabelsEs[value]
    ?? 'Especialidad personalizada'
  )
}


export default function Ecosistema({
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


  const loadSnapshot = useCallback(
    async (
      silent = false,
    ) => {
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
    },
    [],
  )


  useEffect(() => {
    const timer =
      window.setTimeout(
        () => {
          void loadSnapshot()
        },
        0,
      )

    return () => {
      window.clearTimeout(
        timer,
      )
    }
  }, [loadSnapshot])


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
      <section className="ecosystem-hero ecosystem-hero-bosque">
        <div>
          <div className="ecosystem-live-pill">
            <Radio size={14} />

            Ecosistema vivo
          </div>

          <h1>
            Bosque Repliker
          </h1>

          <p>
            Explora a los Repliker dentro de
            un entorno vivo. Observa quién está
            disponible, quién participa en una
            misión y cómo se forman colaboraciones
            alrededor de proyectos reales.
          </p>
        </div>

        <div className="ecosystem-hero-actions">
          <div className="ecosystem-auto-refresh">
            <span className="ecosystem-live-dot" />

            Actualización automática
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


      <BosqueRepliker
        agents={snapshot.agents}
        projects={snapshot.projects}
        events={snapshot.events}
        messages={snapshot.messages}
        selectedProjectId={
          selectedProjectId
        }
        onSelectProject={
          setSelectedProjectId
        }
        onSelectAgent={
          openAgent
        }
        specialtyLabel={
          specialtyLabelEs
        }
      />


      <section className="ecosystem-tools-area">
        <div className="ecosystem-tools-heading">
          <span>
            HERRAMIENTAS DEL ECOSISTEMA
          </span>

          <h2>
            Operaciones avanzadas
          </h2>

          <p>
            Configuración, supervisión y
            colaboración del ecosistema.
          </p>
        </div>


        <EstudioRepliker />


        <CentroControlAgentes
          selectedProjectId={
            selectedProjectId
          }
          currentUserId={
            currentUserId
          }
          currentUserRole={
            currentUserRole
          }
          projects={
            snapshot.projects
          }
        />


        <ActividadProyectoEnVivo
          currentUserId={
            currentUserId
          }
          selectedProjectId={
            selectedProjectId
          }
          projects={
            snapshot.projects
          }
          onRealtimeActivity={() => {
            void loadSnapshot(true)
          }}
        />


        <section className="ecosystem-bosque-support">
          <PanelColaboracion
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
              <ReplikerHumano
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
                {specialtyLabelEs(selectedAgent.specialty)}
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
                      Natural
                    </option>

                    <option value="premium">
                      Elegante
                    </option>

                    <option value="minimal">
                      Sencillo
                    </option>

                    <option value="neon">
                      Creativo
                    </option>

                    <option value="industrial">
                      Técnico
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
                      Ovalado
                    </option>

                    <option value="angular">
                      Definido
                    </option>

                    <option value="orb">
                      Redondeado
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
                      Amables
                    </option>

                    <option value="line">
                      Serenos
                    </option>

                    <option value="dual">
                      Enfocados
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
                      Gafas
                    </option>

                    <option value="headphones">
                      Auriculares
                    </option>

                    <option value="antenna">
                      Broche
                    </option>

                    <option value="halo">
                      Diadema
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
                      Bosque suave
                    </option>

                    <option value="circuit">
                      Degradado
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
