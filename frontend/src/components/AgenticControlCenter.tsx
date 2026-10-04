import {
  Activity,
  Bot,
  BrainCircuit,
  CheckCircle2,
  Circle,
  Cpu,
  GitBranch,
  Minus,
  RefreshCw,
  Save,
  Settings2,
  ShieldCheck,
  Sparkles,
  Wrench,
} from 'lucide-react'

import { useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'

import { api } from '../api'

import '../styles/AgenticControlCenter.css'


interface AgenticTool {
  name: string
  label: string
  pack: string
  description: string
  risk: string
  permission_level: string
}


interface AgentToolProfile {
  repliker_id: number
  repliker_name: string
  owner_id: number
  specialty: string
  explicit_configuration: boolean
  tools: AgenticTool[]
}


interface AgenticRuntime {
  framework: string
  langchain_version: string
  langgraph_version: string
  provider: string
  model: string
  tool_count: number
  default_tools: string[]
  graph_nodes: string[]
}


interface GraphNode {
  name: string
  label: string
  status: string
}


interface AgenticActivity {
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


interface AgenticSnapshot {
  project_id: number
  project_title: string
  project_status: string
  payment_status: string

  framework: string
  langchain_version: string
  langgraph_version: string
  provider: string
  model: string

  current_node: string
  next_action: string
  has_delegations: boolean

  nodes: GraphNode[]

  agents: AgentToolProfile[]

  recent_activity: AgenticActivity[]
}


interface EcosystemProjectLite {
  id: number
  title: string
  status: string
}


interface Props {
  selectedProjectId:
    | number
    | 'all'

  currentUserId: number

  currentUserRole: string

  projects: EcosystemProjectLite[]
}



const visibleSpecialties:
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


function visibleSpecialty(
  value: string,
) {
  return (
    visibleSpecialties[value]
    ?? 'Especialidad personalizada'
  )
}


function nodeIcon(
  node: GraphNode,
) {
  if (
    node.status
    === 'complete'
  ) {
    return (
      <CheckCircle2
        size={18}
      />
    )
  }

  if (
    node.status
    === 'active'
  ) {
    return (
      <Sparkles
        size={18}
      />
    )
  }

  if (
    node.status
    === 'skipped'
  ) {
    return (
      <Minus
        size={18}
      />
    )
  }

  return (
    <Circle
      size={16}
    />
  )
}


function nodeStatusLabel(
  status: string,
) {
  switch (status) {
    case 'complete':
      return 'Completado'

    case 'active':
      return 'Activo'

    case 'skipped':
      return 'Omitido'

    default:
      return 'Pendiente'
  }
}


function visibleStatus(
  value: string,
) {
  const labels:
    Record<string, string> = {
      draft:
        'Borrador',

      planned:
        'Planificado',

      planning:
        'Planificando',

      open:
        'Abierto',

      market:
        'En mercado',

      contracted:
        'Contratado',

      executing:
        'En ejecución',

      running:
        'En ejecución',

      qa:
        'En pruebas',

      awaiting_final_review:
        'En revisión final',

      correcting:
        'En corrección',

      completed:
        'Completado',

      failed:
        'Fallido',

      pending:
        'Pendiente',

      active:
        'Activo',

      funded:
        'Financiado',

      reserved:
        'Reservado',

      paid:
        'Pagado',

      settled:
        'Liquidado',

      unpaid:
        'Sin pagar',

      blocked:
        'Bloqueado',

      waiting:
        'En espera',

      accepted:
        'Aceptado',

      assigned:
        'Asignado',

      cancelled:
        'Cancelado',

      canceled:
        'Cancelado',
    }

  return (
    labels[
      value
        .trim()
        .toLowerCase()
    ]
    ?? 'En proceso'
  )
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

  return (
    new Intl.DateTimeFormat(
      'es-PE',
      {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      },
    )
    .format(date)
  )
}


export default function AgenticControlCenter({
  selectedProjectId,
  currentUserId,
  currentUserRole,
  projects,
}: Props) {
  const [
    runtime,
    setRuntime,
  ] =
    useState<AgenticRuntime | null>(
      null,
    )

  const [
    catalog,
    setCatalog,
  ] =
    useState<AgenticTool[]>([])

  const [
    snapshot,
    setSnapshot,
  ] =
    useState<AgenticSnapshot | null>(
      null,
    )

  const [
    loading,
    setLoading,
  ] =
    useState(false)

  const [
    refreshing,
    setRefreshing,
  ] =
    useState(false)

  const [
    error,
    setError,
  ] =
    useState('')

  const [
    notice,
    setNotice,
  ] =
    useState('')

  const [
    editingAgentId,
    setEditingAgentId,
  ] =
    useState<number | null>(
      null,
    )

  const [
    toolDraft,
    setToolDraft,
  ] =
    useState<string[]>([])

  const [
    savingTools,
    setSavingTools,
  ] =
    useState(false)


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


  const load = useCallback(
    async (
      silent = false,
    ) => {
      if (silent) {
        setRefreshing(true)
      } else {
        setLoading(true)
      }

      try {
        const [
          runtimeResponse,
          catalogResponse,
        ] =
          await Promise.all([
            api.get<AgenticRuntime>(
              '/agentic/runtime',
            ),

            api.get<AgenticTool[]>(
              '/agentic/tools',
            ),
          ])

        setRuntime(
          runtimeResponse.data,
        )

        setCatalog(
          catalogResponse.data,
        )

        if (
          selectedProjectId
          === 'all'
        ) {
          setSnapshot(null)
          setError('')

          return
        }

        const snapshotResponse =
          await api.get<AgenticSnapshot>(
            `/agentic/projects/${selectedProjectId}`,
          )

        setSnapshot(
          snapshotResponse.data,
        )

        setError('')

      } catch {
        setError(
          'No fue posible cargar '
          + 'el Centro de control autónomo.',
        )

      } finally {
        setLoading(false)
        setRefreshing(false)
      }
    },
    [selectedProjectId],
  )


  useEffect(
    () => {
      const timer =
        window.setTimeout(
          () => {
            setEditingAgentId(
              null,
            )

            setToolDraft([])

            setNotice('')

            void load()
          },
          0,
        )

      return () => {
        window.clearTimeout(
          timer,
        )
      }
    },
    [load],
  )


  function canEdit(
    profile: AgentToolProfile,
  ) {
    return (
      profile.owner_id
      === currentUserId
      ||
      currentUserRole
      === 'admin'
    )
  }


  function startEdit(
    profile: AgentToolProfile,
  ) {
    setEditingAgentId(
      profile.repliker_id,
    )

    setToolDraft(
      profile.tools.map(
        (tool) =>
          tool.name,
      ),
    )

    setNotice('')
  }


  function toggleTool(
    toolName: string,
  ) {
    setToolDraft(
      (current) => {
        if (
          current.includes(
            toolName,
          )
        ) {
          return current.filter(
            (name) =>
              name
              !== toolName,
          )
        }

        return [
          ...current,
          toolName,
        ]
      },
    )
  }


  async function saveTools(
    replikerId: number,
  ) {
    if (
      toolDraft.length
      === 0
    ) {
      setNotice(
        'El Repliker debe conservar '
        + 'al menos una herramienta.',
      )

      return
    }

    setSavingTools(true)
    setNotice('')

    try {
      const response =
        await api.put<AgentToolProfile>(
          `/agentic/replikers/${replikerId}/tools`,
          {
            tool_names:
              toolDraft,
          },
        )

      setSnapshot(
        (current) => {
          if (!current) {
            return current
          }

          return {
            ...current,

            agents:
              current.agents.map(
                (profile) =>
                  profile.repliker_id
                  === replikerId
                    ? response.data
                    : profile,
              ),
          }
        },
      )

      setEditingAgentId(
        null,
      )

      setNotice(
        'Configuración de herramientas '
        + 'guardada correctamente.',
      )

    } catch {
      setNotice(
        'No fue posible guardar '
        + 'las herramientas del Repliker.',
      )

    } finally {
      setSavingTools(false)
    }
  }


  return (
    <section
      className="agentic-control-center"
    >
      <div
        className="agentic-glow agentic-glow-one"
      />

      <div
        className="agentic-glow agentic-glow-two"
      />


      <header
        className="agentic-header"
      >
        <div>
          <div
            className="agentic-eyebrow"
          >
            <BrainCircuit
              size={16}
            />

            Centro de control autónomo
          </div>

          <h2>
            Economía de agentes
            en tiempo real
          </h2>

          <p>
            Observa cómo cada Repliker
            utiliza sus herramientas
            y cómo el sistema organiza
            el flujo completo del proyecto.
          </p>
        </div>


        <div
          className="agentic-header-right"
        >
          <div
            className="agentic-online"
          >
            <span />

            Núcleo autónomo activo
          </div>

          <button
            type="button"
            className="agentic-refresh"
            disabled={
              refreshing
            }
            onClick={() =>
              void load(true)
            }
          >
            <RefreshCw
              size={16}
              className={
                refreshing
                  ? 'agentic-spin'
                  : ''
              }
            />

            Actualizar
          </button>
        </div>
      </header>


      {error && (
        <div
          className="agentic-alert error"
        >
          {error}
        </div>
      )}


      {notice && (
        <div
          className="agentic-alert success"
        >
          {notice}
        </div>
      )}


      <div
        className="agentic-runtime-grid"
      >
        <article>
          <div
            className="agentic-runtime-icon violet"
          >
            <BrainCircuit
              size={21}
            />
          </div>

          <div>
            <span>
              Agentes
            </span>

            <strong>
              Motor autónomo
            </strong>

            <small>
              {runtime
                ? `v${runtime.langchain_version}`
                : 'Cargando...'}
            </small>
          </div>
        </article>


        <article>
          <div
            className="agentic-runtime-icon blue"
          >
            <GitBranch
              size={21}
            />
          </div>

          <div>
            <span>
              Orquestación
            </span>

            <strong>
              Orquestador autónomo
            </strong>

            <small>
              {runtime
                ? `v${runtime.langgraph_version}`
                : 'Cargando...'}
            </small>
          </div>
        </article>


        <article>
          <div
            className="agentic-runtime-icon cyan"
          >
            <Cpu
              size={21}
            />
          </div>

          <div>
            <span>
              Modelo IA
            </span>

            <strong>
              Modelo activo
            </strong>

            <small>
              Configurado
            </small>
          </div>
        </article>


        <article>
          <div
            className="agentic-runtime-icon green"
          >
            <Wrench
              size={21}
            />
          </div>

          <div>
            <span>
              Registro de herramientas
            </span>

            <strong>
              {runtime?.tool_count
                ?? 0}
              {' '}
              herramientas
            </strong>

            <small>
              Permisos controlados
            </small>
          </div>
        </article>
      </div>


      {selectedProjectId === 'all' ? (
        <section
          className="agentic-select-project"
        >
          <div
            className="agentic-select-icon"
          >
            <Sparkles
              size={25}
            />
          </div>

          <div>
            <strong>
              Selecciona un proyecto
            </strong>

            <p>
              Elige un proyecto en el filtro
              del ecosistema para visualizar
              su grafo, Replikers, herramientas
              y actividad de agentes.
            </p>
          </div>
        </section>

      ) : loading && !snapshot ? (
        <section
          className="agentic-loading"
        >
          <div
            className="agentic-loader"
          />

          Analizando el flujo de agentes...
        </section>

      ) : snapshot ? (
        <>
          <section
            className="agentic-project-strip"
          >
            <div>
              <span>
                Proyecto activo
              </span>

              <strong>
                {snapshot.project_title}
              </strong>
            </div>

            <div
              className="agentic-project-tags"
            >
              <span>
                {visibleStatus(snapshot.project_status)}
              </span>

              <span>
                {visibleStatus(snapshot.payment_status)}
              </span>

              {snapshot.has_delegations && (
                <span
                  className="delegation"
                >
                  Delegación activa
                </span>
              )}
            </div>
          </section>


          <section
            className="agentic-stage-card"
          >
            <div
              className="agentic-stage-main"
            >
              <div
                className="agentic-stage-icon"
              >
                <Activity
                  size={23}
                />
              </div>

              <div>
                <span>
                  Nodo actual
                </span>

                <strong>
                  {
                    snapshot.nodes.find(
                      (node) =>
                        node.name
                        === snapshot.current_node,
                    )?.label
                    ?? 'Etapa en proceso'
                  }
                </strong>
              </div>
            </div>

            <div
              className="agentic-next-action"
            >
              <span>
                Siguiente acción
              </span>

              <p>
                {snapshot.next_action}
              </p>
            </div>
          </section>


          <section
            className="agentic-section"
          >
            <div
              className="agentic-section-title"
            >
              <div>
                <GitBranch
                  size={18}
                />

                <strong>
                  Flujo del proyecto
                </strong>
              </div>

              <span>
                {
                  snapshot.nodes.filter(
                    (node) =>
                      node.status
                      === 'complete',
                  ).length
                }
                /
                {
                  snapshot.nodes.length
                }
                {' '}
                etapas completadas
              </span>
            </div>


            <div
              className="agentic-pipeline"
            >
              {snapshot.nodes.map(
                (
                  node,
                  index,
                ) => (
                  <div
                    className={
                      `agentic-node ${node.status}`
                    }
                    key={node.name}
                  >
                    <div
                      className="agentic-node-circle"
                    >
                      {nodeIcon(node)}
                    </div>

                    <div
                      className="agentic-node-copy"
                    >
                      <strong>
                        {node.label}
                      </strong>

                      <span>
                        {
                          nodeStatusLabel(
                            node.status,
                          )
                        }
                      </span>
                    </div>

                    {index
                      < snapshot.nodes.length - 1
                      && (
                        <div
                          className="agentic-node-line"
                        />
                      )}
                  </div>
                ),
              )}
            </div>
          </section>


          <section
            className="agentic-section"
          >
            <div
              className="agentic-section-title"
            >
              <div>
                <Bot
                  size={19}
                />

                <strong>
                  Replikers conectados
                </strong>
              </div>

              <span>
                {snapshot.agents.length}
                {' '}
                agentes involucrados
              </span>
            </div>


            {snapshot.agents.length === 0 ? (
              <div
                className="agentic-empty"
              >
                Todavía no hay Replikers
                vinculados a este proyecto.
              </div>

            ) : (
              <div
                className="agentic-agent-grid"
              >
                {snapshot.agents.map(
                  (profile) => {
                    const editing =
                      editingAgentId
                      === profile.repliker_id

                    return (
                      <article
                        key={
                          profile.repliker_id
                        }
                        className="agentic-agent-card"
                      >
                        <div
                          className="agentic-agent-top"
                        >
                          <div
                            className="agentic-agent-avatar"
                          >
                            <Bot
                              size={22}
                            />
                          </div>

                          <div
                            className="agentic-agent-name"
                          >
                            <strong>
                              {profile.repliker_name}
                            </strong>

                            <span>
                              {visibleSpecialty(profile.specialty)}
                            </span>
                          </div>

                          <div
                            className="agentic-langchain-pill"
                          >
                            Motor autónomo
                          </div>
                        </div>


                        <div
                          className="agentic-tool-list"
                        >
                          {profile.tools.map(
                            (tool) => (
                              <span
                                key={
                                  tool.name
                                }
                              >
                                <Wrench
                                  size={12}
                                />

                                {tool.label}
                              </span>
                            ),
                          )}
                        </div>


                        <div
                          className="agentic-agent-footer"
                        >
                          <div>
                            <ShieldCheck
                              size={15}
                            />

                            {
                              profile
                                .explicit_configuration
                                ? 'Configuración propia'
                                : 'Conjunto predeterminado'
                            }
                          </div>

                          {canEdit(profile) && (
                            <button
                              type="button"
                              onClick={() => {
                                if (editing) {
                                  setEditingAgentId(
                                    null,
                                  )
                                } else {
                                  startEdit(
                                    profile,
                                  )
                                }
                              }}
                            >
                              <Settings2
                                size={14}
                              />

                              {editing
                                ? 'Cerrar'
                                : 'Configurar'}
                            </button>
                          )}
                        </div>


                        {editing && (
                          <div
                            className="agentic-tool-editor"
                          >
                            <div
                              className="agentic-tool-editor-title"
                            >
                              Herramientas permitidas
                            </div>

                            <div
                              className="agentic-tool-editor-grid"
                            >
                              {catalog.map(
                                (tool) => {
                                  const enabled =
                                    toolDraft.includes(
                                      tool.name,
                                    )

                                  return (
                                    <button
                                      type="button"
                                      key={
                                        tool.name
                                      }
                                      className={
                                        enabled
                                          ? 'selected'
                                          : ''
                                      }
                                      onClick={() =>
                                        toggleTool(
                                          tool.name,
                                        )
                                      }
                                    >
                                      <span>
                                        Herramienta autorizada
                                      </span>

                                      <strong>
                                        {tool.label}
                                      </strong>

                                      <small>
                                        {
                                          tool.description
                                        }
                                      </small>
                                    </button>
                                  )
                                },
                              )}
                            </div>

                            <button
                              type="button"
                              className="agentic-save"
                              disabled={
                                savingTools
                              }
                              onClick={() =>
                                void saveTools(
                                  profile.repliker_id,
                                )
                              }
                            >
                              <Save
                                size={15}
                              />

                              {savingTools
                                ? 'Guardando...'
                                : 'Guardar configuración'}
                            </button>
                          </div>
                        )}
                      </article>
                    )
                  },
                )}
              </div>
            )}
          </section>


          <section
            className="agentic-section"
          >
            <div
              className="agentic-section-title"
            >
              <div>
                <Activity
                  size={18}
                />

                <strong>
                  Actividad reciente
                </strong>
              </div>

              <span>
                Supervisión del sistema
              </span>
            </div>


            {snapshot
              .recent_activity
              .length === 0 ? (
                <div
                  className="agentic-empty"
                >
                  No hay actividad registrada
                  todavía.
                </div>

              ) : (
                <div
                  className="agentic-activity-list"
                >
                  {snapshot
                    .recent_activity
                    .slice(0, 10)
                    .map(
                      (event) => (
                        <article
                          key={event.id}
                        >
                          <div
                            className="agentic-activity-dot"
                          />

                          <div
                            className="agentic-activity-copy"
                          >
                            <div>
                              <strong>
                                {event.title}
                              </strong>

                              <span>
                                {
                                  dateTimeLabel(
                                    event.created_at,
                                  )
                                }
                              </span>
                            </div>

                            <p>
                              {
                                event.description
                              }
                            </p>
                          </div>
                        </article>
                      ),
                    )}
                </div>
              )}
          </section>
        </>

      ) : (
        <section
          className="agentic-empty"
        >
          No existe información agéntica
          disponible para este proyecto.
        </section>
      )}


      {currentProject && (
        <div
          className="agentic-project-footer"
        >
          <BrainCircuit
            size={15}
          />

          Observando:
          {' '}
          <strong>
            {currentProject.title}
          </strong>
        </div>
      )}
    </section>
  )
}
