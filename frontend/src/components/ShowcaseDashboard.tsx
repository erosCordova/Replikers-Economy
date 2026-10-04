import {
  Activity,
  Bot,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Cpu,
  Network,
  Plus,
  Rocket,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
} from 'lucide-react'


interface DashboardProject {
  id: number
  title: string
  description: string
  status: string
}


interface DashboardSkill {
  id?: number
  name?: string
  skill_name?: string
  level?: number
}


interface DashboardRepliker {
  id: number
  name: string
  specialty: string
  status: string
  reputation_score: number
  jobs_completed: number
  is_active: boolean
  skills?: DashboardSkill[]
}


interface EcosystemAgent {
  id: number
  name: string
  specialty: string
  status: string
  reputation_score: number
  jobs_completed: number
  is_active: boolean

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


interface EcosystemMessage {
  id: number
}


export interface DashboardEcosystemSnapshot {
  agents: EcosystemAgent[]
  projects: EcosystemProject[]
  events: ActivityEvent[]
  messages: EcosystemMessage[]
}


interface ShowcaseDashboardProps {
  userName: string

  projects: DashboardProject[]
  replikers: DashboardRepliker[]

  ecosystem: DashboardEcosystemSnapshot

  plannedValue: string
  backendOnline: boolean | null

  onCreateProject: () => void
  onOpenMarketplace: () => void
}


const specialtyLabels:
  Record<string, string> = {
    Generalist:
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


const projectStatusLabels:
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

    blocked:
      'Bloqueado',

    cancelled:
      'Cancelado',

    canceled:
      'Cancelado',
  }


function visibleSpecialty(
  value: string,
) {
  return (
    specialtyLabels[value]
    ?? 'Especialidad personalizada'
  )
}


function projectStatusLabel(
  value: string,
) {
  return (
    projectStatusLabels[
      value.toLowerCase()
    ]
    ?? 'En proceso'
  )
}


function isWorking(
  agent: EcosystemAgent,
) {
  const status =
    agent.status.toLowerCase()

  return (
    agent.current_project_id !== null
    || [
      'working',
      'busy',
      'assigned',
      'executing',
      'running',
    ].includes(status)
  )
}


function relativeTime(
  value: string,
) {
  const date =
    new Date(value)

  const milliseconds =
    Date.now()
    - date.getTime()

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return 'Fecha no disponible'
  }

  const minutes =
    Math.max(
      0,
      Math.floor(
        milliseconds
        / 60000,
      ),
    )

  if (minutes < 1) {
    return 'ahora'
  }

  if (minutes < 60) {
    return (
      `hace ${minutes} `
      + (
        minutes === 1
          ? 'minuto'
          : 'minutos'
      )
    )
  }

  const hours =
    Math.floor(
      minutes / 60,
    )

  if (hours < 24) {
    return (
      `hace ${hours} `
      + (
        hours === 1
          ? 'hora'
          : 'horas'
      )
    )
  }

  const days =
    Math.floor(
      hours / 24,
    )

  return (
    `hace ${days} `
    + (
      days === 1
        ? 'día'
        : 'días'
    )
  )
}


function skillLabel(
  skill: DashboardSkill,
) {
  return (
    skill.name
    ?? skill.skill_name
    ?? 'Habilidad'
  )
}


function eventKind(
  event: ActivityEvent,
) {
  const text =
    (
      event.event_type
      + ' '
      + event.title
    ).toLowerCase()

  if (
    text.includes('qa')
    || text.includes('review')
    || text.includes('calidad')
  ) {
    return 'quality'
  }

  if (
    text.includes('contract')
    || text.includes('contrato')
  ) {
    return 'contract'
  }

  if (
    text.includes('project')
    || text.includes('proyecto')
    || text.includes('plan')
  ) {
    return 'project'
  }

  return 'activity'
}


function ShowcaseDashboard({
  userName,
  projects,
  replikers,
  ecosystem,
  plannedValue,
  backendOnline,
  onCreateProject,
  onOpenMarketplace,
}: ShowcaseDashboardProps) {
  const firstName =
    userName
      .trim()
      .split(' ')[0]
    || 'Cliente'


  const visibleProjects =
    projects.slice(
      0,
      3,
    )


  const featuredReplikers =
    [...replikers]
      .filter(
        (repliker) =>
          repliker.is_active,
      )
      .sort(
        (a, b) =>
          (
            b.reputation_score
            - a.reputation_score
          )
          || (
            b.jobs_completed
            - a.jobs_completed
          ),
      )
      .slice(
        0,
        4,
      )


  const sortedActivity =
    [...ecosystem.events]
      .sort(
        (a, b) =>
          new Date(
            b.created_at,
          ).getTime()
          - new Date(
            a.created_at,
          ).getTime(),
      )


  const recentActivity =
    sortedActivity.slice(
      0,
      4,
    )


  const workingAgents =
    ecosystem.agents.filter(
      isWorking,
    )


  const currentWork =
    workingAgents[0]
    ?? null


  const latestQualityEvent =
    sortedActivity.find(
      (event) =>
        eventKind(event)
        === 'quality',
    )
    ?? null


  const taskCount =
    ecosystem.projects.reduce(
      (
        total,
        project,
      ) =>
        total
        + project.task_count,
      0,
    )


  function projectMetadata(
    projectId: number,
  ) {
    return (
      ecosystem.projects.find(
        (project) =>
          project.id
          === projectId,
      )
      ?? null
    )
  }


  function projectName(
    projectId: number | null,
  ) {
    if (
      projectId === null
    ) {
      return ''
    }

    return (
      projects.find(
        (project) =>
          project.id
          === projectId,
      )?.title
      ?? ecosystem.projects.find(
        (project) =>
          project.id
          === projectId,
      )?.title
      ?? `Proyecto #${projectId}`
    )
  }


  return (
    <div className="showcase-dashboard">
      <section className="showcase-grid-top">
        <article className="showcase-hero">
          <div className="showcase-hero-copy">
            <div className="showcase-pill">
              <Sparkles size={15} />
              Economía de agentes autónomos
            </div>

            <h1>
              Bienvenido a{' '}
              <span>Replikers</span>
            </h1>

            <h2>
              Tu ecosistema de agentes de IA autónomos
            </h2>

            <p>
              Publica proyectos, coordina trabajo con R00,
              contrata Replikers y recibe resultados
              verificados mediante ejecución y pruebas.
            </p>

            <div className="showcase-hero-actions">
              <button
                type="button"
                className="showcase-primary"
                onClick={onCreateProject}
              >
                <Plus size={18} />
                Crear proyecto
              </button>

              <button
                type="button"
                className="showcase-secondary"
                onClick={onOpenMarketplace}
              >
                <Bot size={18} />
                Explorar mercado
              </button>
            </div>
          </div>

          <div className="showcase-ai-scene">
            <div className="ai-orbit orbit-a" />
            <div className="ai-orbit orbit-b" />

            <div className="ai-core-glow" />

            <div className="ai-core">
              <Cpu size={58} />
              <strong>R00</strong>
              <span>Coordinador IA</span>
            </div>

            <div className="floating-agent agent-a">
              <Bot size={22} />
            </div>

            <div className="floating-agent agent-b">
              <ShieldCheck size={21} />
            </div>

            <div className="floating-agent agent-c">
              <Network size={21} />
            </div>
          </div>
        </article>

        <article className="showcase-activity-card">
          <div className="showcase-section-title">
            <div>
              <span>EN VIVO</span>
              <h3>Actividad del ecosistema</h3>
            </div>

            <Activity size={20} />
          </div>

          <div className="activity-list">
            {recentActivity.length === 0 ? (
              <div className="activity-row">
                <div className="activity-symbol">
                  <Activity size={17} />
                </div>

                <div className="activity-copy">
                  <strong>
                    Sin actividad registrada
                  </strong>

                  <span>
                    Las acciones reales aparecerán aquí.
                  </span>
                </div>
              </div>
            ) : (
              recentActivity.map(
                (
                  item,
                  index,
                ) => {
                  const kind =
                    eventKind(item)

                  return (
                    <div
                      className="activity-row"
                      key={item.id}
                    >
                      <div
                        className={
                          `activity-symbol symbol-${index + 1}`
                        }
                      >
                        {kind === 'quality' ? (
                          <CheckCircle2 size={17} />
                        ) : kind === 'contract' ? (
                          <BriefcaseBusiness size={17} />
                        ) : kind === 'project' ? (
                          <Target size={17} />
                        ) : (
                          <Rocket size={17} />
                        )}
                      </div>

                      <div className="activity-copy">
                        <strong>
                          {item.title}
                        </strong>

                        <span>
                          {item.description
                            || (
                              item.project_id
                                ? projectName(
                                    item.project_id,
                                  )
                                : 'Actividad del sistema'
                            )}
                        </span>
                      </div>

                      <small>
                        {relativeTime(
                          item.created_at,
                        )}
                      </small>
                    </div>
                  )
                },
              )
            )}
          </div>

          <div className="live-status">
            <span
              className={
                backendOnline
                  ? 'live-dot online'
                  : 'live-dot'
              }
            />

            {backendOnline
              ? 'Servidor conectado'
              : 'Servidor sin conexión'}
          </div>
        </article>
      </section>


      <section className="showcase-metrics">
        <article>
          <div className="showcase-metric-icon blue">
            <BriefcaseBusiness size={21} />
          </div>

          <div>
            <span>Proyectos</span>
            <strong>
              {projects.length}
            </strong>
            <small>
              registrados en tu cuenta
            </small>
          </div>
        </article>

        <article>
          <div className="showcase-metric-icon violet">
            <Users size={21} />
          </div>

          <div>
            <span>Replikers</span>
            <strong>
              {replikers.length}
            </strong>
            <small>
              publicados en el mercado
            </small>
          </div>
        </article>

        <article>
          <div className="showcase-metric-icon green">
            <Rocket size={21} />
          </div>

          <div>
            <span>Trabajando</span>
            <strong>
              {workingAgents.length}
            </strong>
            <small>
              Replikers con actividad
            </small>
          </div>
        </article>

        <article>
          <div className="showcase-metric-icon amber">
            <Activity size={21} />
          </div>

          <div>
            <span>Actividad</span>
            <strong>
              {ecosystem.events.length}
            </strong>
            <small>
              eventos registrados
            </small>
          </div>
        </article>

        <article>
          <div className="showcase-metric-icon cyan">
            <Network size={21} />
          </div>

          <div>
            <span>Comunicaciones</span>
            <strong>
              {ecosystem.messages.length}
            </strong>
            <small>
              mensajes operativos
            </small>
          </div>
        </article>
      </section>


      <section className="showcase-main-grid">
        <article className="showcase-panel projects-panel">
          <div className="showcase-section-title">
            <div>
              <span>PROYECTOS</span>
              <h3>Mis proyectos</h3>
            </div>

            <button
              type="button"
              onClick={onCreateProject}
            >
              Crear nuevo
              <ChevronRight size={15} />
            </button>
          </div>

          <div className="showcase-project-list">
            {visibleProjects.length === 0 ? (
              <div className="showcase-project">
                <div className="project-symbol">
                  <BriefcaseBusiness size={22} />
                </div>

                <div className="project-copy">
                  <div className="project-title-row">
                    <div>
                      <strong>
                        Aún no tienes proyectos
                      </strong>

                      <p>
                        Crea un proyecto para comenzar.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              visibleProjects.map(
                (
                  project,
                  index,
                ) => {
                  const metadata =
                    projectMetadata(
                      project.id,
                    )

                  return (
                    <div
                      className="showcase-project"
                      key={project.id}
                    >
                      <div
                        className={
                          `project-symbol project-symbol-${index + 1}`
                        }
                      >
                        {index === 0 ? (
                          <BriefcaseBusiness size={22} />
                        ) : index === 1 ? (
                          <Target size={22} />
                        ) : (
                          <Cpu size={22} />
                        )}
                      </div>

                      <div className="project-copy">
                        <div className="project-title-row">
                          <div>
                            <strong>
                              {project.title}
                            </strong>

                            <p>
                              {project.description}
                            </p>
                          </div>

                          <span className="project-status">
                            {projectStatusLabel(
                              project.status,
                            )}
                          </span>
                        </div>

                        <div className="project-bottom">
                          <div className="project-info">
                            <span>
                              {metadata
                                ? `${metadata.task_count} tareas`
                                : 'Tareas no registradas'}
                            </span>

                            <span>
                              {metadata
                                ? `${metadata.agents_involved} Replikers`
                                : 'Sin asignaciones registradas'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                },
              )
            )}
          </div>
        </article>


        <article className="showcase-panel agents-panel">
          <div className="showcase-section-title">
            <div>
              <span>MERCADO</span>
              <h3>Replikers destacados</h3>
            </div>

            <button
              type="button"
              onClick={onOpenMarketplace}
            >
              Ver mercado
              <ChevronRight size={15} />
            </button>
          </div>

          <div className="showcase-agent-list">
            {featuredReplikers.length === 0 ? (
              <div className="showcase-agent">
                <div className="agent-portrait">
                  <Bot size={22} />
                </div>

                <div className="agent-copy">
                  <div className="agent-name">
                    <strong>
                      Sin Replikers publicados
                    </strong>
                  </div>

                  <p>
                    El mercado aún no tiene publicaciones.
                  </p>
                </div>
              </div>
            ) : (
              featuredReplikers.map(
                (
                  agent,
                  index,
                ) => (
                  <div
                    className="showcase-agent"
                    key={agent.id}
                  >
                    <div
                      className={
                        `agent-portrait agent-portrait-${index + 1}`
                      }
                    >
                      <Bot size={22} />
                    </div>

                    <div className="agent-copy">
                      <div className="agent-name">
                        <strong>
                          {agent.name}
                        </strong>
                        <span />
                      </div>

                      <p>
                        {visibleSpecialty(
                          agent.specialty,
                        )}
                      </p>

                      <div className="agent-tags">
                        {(agent.skills ?? [])
                          .slice(
                            0,
                            3,
                          )
                          .map(
                            (
                              skill,
                              skillIndex,
                            ) => (
                              <span
                                key={
                                  skill.id
                                  ?? `${agent.id}-${skillIndex}`
                                }
                              >
                                {skillLabel(
                                  skill,
                                )}
                              </span>
                            ),
                          )}

                        {(agent.skills ?? []).length === 0 && (
                          <span>
                            Sin habilidades públicas
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="agent-rating">
                      <strong>
                        {agent.reputation_score}
                      </strong>

                      <span>/100</span>

                      <small>
                        {agent.jobs_completed}{' '}
                        {agent.jobs_completed === 1
                          ? 'trabajo'
                          : 'trabajos'}
                      </small>
                    </div>
                  </div>
                ),
              )
            )}
          </div>
        </article>
      </section>


      <section className="showcase-bottom-grid">
        <article className="showcase-panel execution-card">
          <div className="showcase-section-title compact">
            <div>
              <span>EJECUCIÓN</span>
              <h3>Trabajo en curso</h3>
            </div>

            <Rocket size={19} />
          </div>

          <div className="execution-content">
            <div className="execution-icon">
              <Bot size={23} />
            </div>

            <div>
              {currentWork ? (
                <>
                  <strong>
                    {currentWork.current_activity
                      || (
                        currentWork.current_task_id
                          ? `Tarea #${currentWork.current_task_id}`
                          : 'Actividad en curso'
                      )}
                  </strong>

                  <span>
                    Repliker {currentWork.name}
                  </span>

                  {currentWork.current_project_id && (
                    <small>
                      {projectName(
                        currentWork.current_project_id,
                      )}
                    </small>
                  )}
                </>
              ) : (
                <>
                  <strong>
                    Sin trabajo en curso
                  </strong>

                  <span>
                    No hay Replikers ejecutando tareas.
                  </span>
                </>
              )}
            </div>
          </div>
        </article>


        <article className="showcase-panel qa-card">
          <div className="showcase-section-title compact">
            <div>
              <span>CONTROL DE CALIDAD</span>
              <h3>Última revisión registrada</h3>
            </div>

            <ShieldCheck size={19} />
          </div>

          <div className="qa-content">
            <div className="qa-icon">
              <CheckCircle2 size={25} />
            </div>

            <div>
              {latestQualityEvent ? (
                <>
                  <strong>
                    {latestQualityEvent.title}
                  </strong>

                  <span>
                    {latestQualityEvent.description
                      || 'Revisión registrada por el sistema'}
                  </span>

                  <small>
                    {relativeTime(
                      latestQualityEvent.created_at,
                    )}
                  </small>
                </>
              ) : (
                <>
                  <strong>
                    Sin revisiones registradas
                  </strong>

                  <span>
                    Todavía no existen eventos de calidad.
                  </span>
                </>
              )}
            </div>
          </div>
        </article>


        <article className="showcase-panel ecosystem-card">
          <div className="showcase-section-title compact">
            <div>
              <span>SISTEMA</span>
              <h3>Estado del ecosistema</h3>
            </div>

            <Activity size={19} />
          </div>

          <div className="ecosystem-stats">
            <div>
              <Users size={21} />

              <strong>
                {replikers.length}
              </strong>

              <span>
                en mercado
              </span>
            </div>

            <div>
              <Target size={21} />

              <strong>
                {taskCount}
              </strong>

              <span>
                tareas
              </span>
            </div>

            <div>
              <Activity size={21} />

              <strong>
                {backendOnline
                  ? 'Sí'
                  : 'No'}
              </strong>

              <span>
                servidor
              </span>
            </div>
          </div>
        </article>
      </section>


      <footer className="showcase-footer">
        <div>
          <CircleDollarSign size={18} />
          Valor planificado:{' '}
          <strong>
            {plannedValue}
          </strong>
        </div>

        <span>
          Sesión de {firstName} · Repliker Economía
        </span>
      </footer>
    </div>
  )
}


export default ShowcaseDashboard
