import {
  useCallback,
  useEffect,
  useState,
} from 'react'

import {
  Activity,
  CheckCircle2,
  CircleDollarSign,
  ClipboardCheck,
  Clock3,
  ListChecks,
  PackageCheck,
  RefreshCw,
  Users,
  X,
} from 'lucide-react'

import axios from 'axios'

import { api } from '../api'

import '../styles/SeguimientoProyecto.css'


interface TrackingTask {
  id: number
  title: string
  status: string
  required_specialty: string
  max_budget_cents: number | null
}


interface TrackingTeamMember {
  repliker_id: number
  name: string
  specialty: string
  status: string
  active_contracts: number
  is_final_reviewer: boolean
}


interface TrackingActivity {
  id: number
  task_id: number | null
  repliker_id: number | null
  actor_type: string
  event_type: string
  title: string
  description: string
  created_at: string
}


interface TrackingFinalReview {
  id: number
  attempt_number: number
  status: string
  score: number | null
  summary: string
  corrections_count: number
  reviewer_repliker_id: number | null
  reviewer_name: string | null
  completed_at: string | null
}


interface TrackingIncident {
  kind: string
  severity: string
  title: string
  detail: string
  task_id: number | null
  task_title: string | null
}


interface TrackingDeliveryFile {
  artifact_id: number
  workspace_id: number
  task_id: number | null
  relative_path: string
  media_type: string
  size_bytes: number
  sha256: string
}


interface TrackingDeliveryVersion {
  version: string

  review_id: number
  review_attempt: number

  score: number | null
  summary: string

  vera_completed_at:
    string | null

  client_decision: string
  client_comment: string

  client_decided_at:
    string | null

  status: string
  is_current: boolean
}


interface ProjectTracking {
  project_id: number
  project_title: string
  project_status: string

  stage: string
  stage_label: string
  next_action: string

  progress_percent: number

  progress_basis: {
    planning: number
    contracting: number
    execution: number
    qa: number
    final_review: number
  }

  tasks: {
    total: number
    completed: number
    active: number
    pending: number
    items: TrackingTask[]
  }

  qa: {
    reviews_total: number
    latest_reviews: number
    passed: number
    failed: number
    pending: number
  }

  team: {
    total: number
    members: TrackingTeamMember[]
  }

  budget: {
    currency: string
    budget_limit_cents: number | null
    quoted_amount_cents: number | null
    contracted_cents: number
    funded_cents: number
    earnings_cents: number
    commission_cents: number
    remaining_budget_cents: number | null
    payment_status: string
  }

  final_review: TrackingFinalReview | null

  report: {
    status: string
    summary: string
    progress_percent: number
    tasks_total: number
    tasks_completed: number
    qa_passed: number
    qa_failed: number
    incidents_total: number
    incidents: TrackingIncident[]
  }

  delivery: {
    version: string
    review_attempt: number | null

    versions_total: number
    history: TrackingDeliveryVersion[]

    ready: boolean
    technical_ready: boolean
    status: string

    client_decision: string
    client_comment: string
    client_decision_review_attempt:
      number | null
    client_decided_at:
      string | null
    client_action_required: boolean

    vera_approved: boolean
    vera_status: string
    corrections_requested: number
    files_count: number
    total_size_bytes: number
    files: TrackingDeliveryFile[]
    message: string
  }

  recent_activity: TrackingActivity[]
}


type Tab =
  | 'summary'
  | 'progress'
  | 'activity'
  | 'tests'
  | 'team'
  | 'budget'
  | 'delivery'


interface Props {
  projectId: number
  projectTitle: string
  onClose: () => void
}


const tabs: Array<{
  id: Tab
  label: string
}> = [
  {
    id: 'summary',
    label: 'Resumen',
  },
  {
    id: 'progress',
    label: 'Avance',
  },
  {
    id: 'activity',
    label: 'Actividad',
  },
  {
    id: 'tests',
    label: 'Pruebas',
  },
  {
    id: 'team',
    label: 'Equipo',
  },
  {
    id: 'budget',
    label: 'Presupuesto',
  },
  {
    id: 'delivery',
    label: 'Entrega',
  },
]


const progressLabels: Record<
  string,
  string
> = {
  planning:
    'Planificación',

  contracting:
    'Contratación',

  execution:
    'Ejecución',

  qa:
    'Pruebas',

  final_review:
    'Revisión final',
}


const statusLabels: Record<
  string,
  string
> = {
  draft:
    'Borrador',

  planned:
    'Planificado',

  pending:
    'Pendiente',

  active:
    'Activo',

  executing:
    'En ejecución',

  running:
    'En ejecución',

  completed:
    'Completado',

  prepared:
    'Preparado',

  passed:
    'Aprobado',

  approved:
    'Aprobado',

  failed:
    'Fallido',

  needs_review:
    'Requiere revisión',

  corrections_requested:
    'Correcciones solicitadas',

  correcting:
    'En corrección',

  unpaid:
    'Sin financiar',

  partially_funded:
    'Financiado parcialmente',

  escrowed:
    'Financiado',
}



function specialtyLabel(
  value: string,
) {
  const labels:
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

  return (
    labels[value]
    ?? 'Especialista'
  )
}


function statusLabel(
  value: string,
) {
  return (
    statusLabels[
      value.toLowerCase()
    ]
    ?? 'En proceso'
  )
}


function money(
  cents: number | null,
  currency: string,
) {
  if (cents === null) {
    return 'No definido'
  }

  return new Intl.NumberFormat(
    'es-PE',
    {
      style: 'currency',
      currency,
    },
  ).format(
    cents / 100,
  )
}


function dateLabel(
  value: string,
) {
  const date =
    new Date(value)

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return 'Fecha no disponible'
  }

  return new Intl.DateTimeFormat(
    'es-PE',
    {
      dateStyle: 'short',
      timeStyle: 'short',
    },
  ).format(date)
}


function errorMessage(
  error: unknown,
) {
  if (
    axios.isAxiosError(error)
  ) {
    const detail =
      error.response?.data?.detail

    if (
      typeof detail === 'string'
    ) {
      return detail
    }
  }

  return (
    'No se pudo cargar '
    + 'el seguimiento del proyecto.'
  )
}


export default function SeguimientoProyecto({
  projectId,
  projectTitle,
  onClose,
}: Props) {
  const [
    tab,
    setTab,
  ] = useState<Tab>('summary')

  const [
    tracking,
    setTracking,
  ] = useState<ProjectTracking | null>(
    null,
  )

  const [
    loading,
    setLoading,
  ] = useState(true)

  const [
    error,
    setError,
  ] = useState('')

  const [
    decisionComment,
    setDecisionComment,
  ] = useState('')

  const [
    submittingDecision,
    setSubmittingDecision,
  ] = useState(false)

  const [
    decisionError,
    setDecisionError,
  ] = useState('')

  const [
    decisionSuccess,
    setDecisionSuccess,
  ] = useState('')


  const loadTracking =
    useCallback(
      async (
        silent = false,
      ) => {
        if (!silent) {
          setLoading(true)
        }

        setError('')

        try {
          const response =
            await api.get<ProjectTracking>(
              `/projects/${projectId}/tracking`,
            )

          setTracking(
            response.data,
          )
        } catch (requestError) {
          setError(
            errorMessage(
              requestError,
            ),
          )
        } finally {
          if (!silent) {
            setLoading(false)
          }
        }
      },
      [
        projectId,
      ],
    )


  useEffect(
    () => {
      void loadTracking()

      const interval =
        window.setInterval(
          () => {
            void loadTracking(true)
          },
          15000,
        )

      return () => {
        window.clearInterval(
          interval,
        )
      }
    },
    [
      loadTracking,
    ],
  )


  async function submitDecision(
    decision:
      | 'accepted'
      | 'corrections_requested',
  ) {
    const comment =
      decisionComment.trim()

    if (
      decision
      === 'corrections_requested'
      && comment.length < 5
    ) {
      setDecisionError(
        'Describe qué deseas corregir.',
      )

      return
    }

    setSubmittingDecision(true)
    setDecisionError('')
    setDecisionSuccess('')

    try {
      await api.post(
        `/projects/${projectId}/delivery-decision`,
        {
          decision,
          comment,
        },
      )

      setDecisionComment('')

      setDecisionSuccess(
        decision === 'accepted'
          ? 'Entrega aceptada correctamente.'
          : 'Solicitud de corrección enviada a R00.',
      )

      await loadTracking(true)
    } catch (requestError) {
      setDecisionError(
        errorMessage(
          requestError,
        ),
      )
    } finally {
      setSubmittingDecision(false)
    }
  }


  return (
    <div
      className="tracking-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Seguimiento del proyecto"
    >
      <div className="tracking-window">
        <header className="tracking-header">
          <div>
            <span className="tracking-kicker">
              SEGUIMIENTO DEL PROYECTO
            </span>

            <h2>
              {tracking?.project_title
                ?? projectTitle}
            </h2>

            <p>
              Información real del trabajo,
              pruebas, equipo y presupuesto.
            </p>
          </div>

          <div className="tracking-header-actions">
            <button
              type="button"
              className="tracking-refresh"
              onClick={() =>
                void loadTracking()
              }
              aria-label="Actualizar seguimiento"
            >
              <RefreshCw
                size={18}
              />
            </button>

            <button
              type="button"
              className="tracking-close"
              onClick={onClose}
              aria-label="Cerrar seguimiento"
            >
              <X size={20} />
            </button>
          </div>
        </header>

        {loading && (
          <div className="tracking-loading">
            <RefreshCw
              size={24}
              className="tracking-spin"
            />

            Cargando seguimiento...
          </div>
        )}

        {!loading && error && (
          <div className="tracking-error">
            {error}
          </div>
        )}

        {!loading
        && !error
        && tracking && (
          <>
            <section className="tracking-progress-hero">
              <div className="tracking-percentage">
                <strong>
                  {tracking.progress_percent}%
                </strong>

                <span>
                  avance real
                </span>
              </div>

              <div className="tracking-progress-copy">
                <div className="tracking-stage-row">
                  <span>
                    Etapa actual
                  </span>

                  <strong>
                    {tracking.stage_label}
                  </strong>
                </div>

                <div className="tracking-main-bar">
                  <div
                    style={{
                      width:
                        `${tracking.progress_percent}%`,
                    }}
                  />
                </div>

                <p>
                  {tracking.next_action}
                </p>
              </div>
            </section>

            <nav className="tracking-tabs">
              {tabs.map(
                (item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={
                      tab === item.id
                        ? 'active'
                        : ''
                    }
                    onClick={() =>
                      setTab(
                        item.id,
                      )
                    }
                  >
                    {item.label}
                  </button>
                ),
              )}
            </nav>

            <div className="tracking-content">
              {tab === 'summary' && (
                <section className="tracking-summary">
                  <div className="tracking-metric-grid">
                    <article>
                      <ListChecks
                        size={21}
                      />

                      <span>
                        Tareas
                      </span>

                      <strong>
                        {
                          tracking
                            .tasks
                            .completed
                        }
                        /
                        {
                          tracking
                            .tasks
                            .total
                        }
                      </strong>
                    </article>

                    <article>
                      <ClipboardCheck
                        size={21}
                      />

                      <span>
                        Pruebas aprobadas
                      </span>

                      <strong>
                        {
                          tracking
                            .qa
                            .passed
                        }
                      </strong>
                    </article>

                    <article>
                      <Users
                        size={21}
                      />

                      <span>
                        Equipo
                      </span>

                      <strong>
                        {
                          tracking
                            .team
                            .total
                        }
                      </strong>
                    </article>

                    <article>
                      <CircleDollarSign
                        size={21}
                      />

                      <span>
                        Contratado
                      </span>

                      <strong>
                        {money(
                          tracking
                            .budget
                            .contracted_cents,
                          tracking
                            .budget
                            .currency,
                        )}
                      </strong>
                    </article>
                  </div>

                  <article className="tracking-report-card">
                    <span>
                      REPORTE DEL PROYECTO
                    </span>

                    <h3>
                      {tracking.report.status ===
                      'estable'
                        ? 'Sin incidencias críticas'
                        : 'Requiere atención'}
                    </h3>

                    <p>
                      {tracking.report.summary}
                    </p>

                    <strong>
                      {
                        tracking.report
                          .incidents_total
                      }{' '}
                      incidencia(s)
                    </strong>
                  </article>

                  <article className="tracking-status-card">
                    <div>
                      <Activity
                        size={22}
                      />
                    </div>

                    <section>
                      <span>
                        ESTADO ACTUAL
                      </span>

                      <h3>
                        {
                          tracking
                            .stage_label
                        }
                      </h3>

                      <p>
                        {
                          tracking
                            .next_action
                        }
                      </p>
                    </section>
                  </article>
                </section>
              )}

              {tab === 'progress' && (
                <section className="tracking-progress-section">
                  <h3>
                    Avance por etapa
                  </h3>

                  {Object.entries(
                    tracking.progress_basis,
                  ).map(
                    (
                      [
                        key,
                        value,
                      ],
                    ) => {
                      const percent =
                        Math.round(
                          value
                          * 100,
                        )

                      return (
                        <div
                          className="tracking-stage"
                          key={key}
                        >
                          <div>
                            <span>
                              {
                                progressLabels[
                                  key
                                ]
                                ?? key
                              }
                            </span>

                            <strong>
                              {percent}%
                            </strong>
                          </div>

                          <div className="tracking-stage-bar">
                            <div
                              style={{
                                width:
                                  `${percent}%`,
                              }}
                            />
                          </div>
                        </div>
                      )
                    },
                  )}

                  <div className="tracking-task-list">
                    {tracking.tasks.items.map(
                      (task) => (
                        <article
                          key={task.id}
                        >
                          <div>
                            <strong>
                              {task.title}
                            </strong>

                            <span>
                              {specialtyLabel(task.required_specialty)}
                            </span>
                          </div>

                          <span className="tracking-status-pill">
                            {statusLabel(
                              task.status,
                            )}
                          </span>
                        </article>
                      ),
                    )}
                  </div>
                </section>
              )}

              {tab === 'activity' && (
                <section className="tracking-activity-section">
                  {tracking
                    .recent_activity
                    .length === 0 ? (
                    <div className="tracking-empty">
                      <Activity
                        size={30}
                      />

                      Aún no hay actividad registrada.
                    </div>
                  ) : (
                    tracking
                      .recent_activity
                      .map(
                        (event) => (
                          <article
                            key={
                              event.id
                            }
                            className="tracking-activity-item"
                          >
                            <div className="tracking-activity-dot" />

                            <section>
                              <strong>
                                {
                                  event
                                    .title
                                }
                              </strong>

                              <p>
                                {
                                  event
                                    .description
                                }
                              </p>

                              <span>
                                {dateLabel(
                                  event
                                    .created_at,
                                )}
                              </span>
                            </section>
                          </article>
                        ),
                      )
                  )}
                </section>
              )}

              {tab === 'tests' && (
                <section className="tracking-tests-section">
                  <div className="tracking-metric-grid">
                    <article>
                      <CheckCircle2
                        size={21}
                      />

                      <span>
                        Aprobadas
                      </span>

                      <strong>
                        {
                          tracking
                            .qa
                            .passed
                        }
                      </strong>
                    </article>

                    <article>
                      <Clock3
                        size={21}
                      />

                      <span>
                        Pendientes
                      </span>

                      <strong>
                        {
                          tracking
                            .qa
                            .pending
                        }
                      </strong>
                    </article>

                    <article>
                      <X
                        size={21}
                      />

                      <span>
                        Fallidas
                      </span>

                      <strong>
                        {
                          tracking
                            .qa
                            .failed
                        }
                      </strong>
                    </article>
                  </div>

                  <div className="tracking-incidents">
                    <h3>
                      Incidencias
                    </h3>

                    {tracking.report.incidents.length ===
                    0 ? (
                      <div className="tracking-empty compact">
                        No hay incidencias abiertas.
                      </div>
                    ) : (
                      tracking.report.incidents.map(
                        (
                          incident,
                          index,
                        ) => (
                          <article
                            key={
                              `${incident.kind}-${index}`
                            }
                            className="tracking-incident"
                          >
                            <div>
                              <strong>
                                {incident.title}
                              </strong>

                              {incident.task_title && (
                                <span>
                                  {
                                    incident
                                      .task_title
                                  }
                                </span>
                              )}
                            </div>

                            <p>
                              {incident.detail}
                            </p>
                          </article>
                        ),
                      )
                    )}
                  </div>

                  <article className="tracking-vera-card">
                    <span>
                      REVISIÓN FINAL DE VERA
                    </span>

                    {tracking.final_review ? (
                      <>
                        <h3>
                          {statusLabel(
                            tracking
                              .final_review
                              .status,
                          )}
                        </h3>

                        <p>
                          {
                            tracking
                              .final_review
                              .summary
                            ||
                            'Revisión registrada sin resumen.'
                          }
                        </p>

                        <div>
                          <span>
                            Puntuación
                          </span>

                          <strong>
                            {
                              tracking
                                .final_review
                                .score
                              ?? 'Pendiente'
                            }
                          </strong>
                        </div>
                      </>
                    ) : (
                      <>
                        <h3>
                          Pendiente
                        </h3>

                        <p>
                          Vera todavía no ha realizado
                          la revisión final.
                        </p>
                      </>
                    )}
                  </article>
                </section>
              )}

              {tab === 'team' && (
                <section className="tracking-team-grid">
                  {tracking
                    .team
                    .members
                    .length === 0 ? (
                    <div className="tracking-empty">
                      <Users
                        size={30}
                      />

                      Aún no hay Repliker contratados.
                    </div>
                  ) : (
                    tracking
                      .team
                      .members
                      .map(
                        (member) => (
                          <article
                            key={
                              member
                                .repliker_id
                            }
                          >
                            <div className="tracking-avatar">
                              {
                                member
                                  .name
                                  .slice(
                                    0,
                                    1,
                                  )
                              }
                            </div>

                            <div>
                              <strong>
                                {
                                  member
                                    .name
                                }
                              </strong>

                              <span>
                                {specialtyLabel(member.specialty)}
                              </span>

                              {member
                                .is_final_reviewer && (
                                <small>
                                  Vera · revisión final
                                </small>
                              )}
                            </div>
                          </article>
                        ),
                      )
                  )}
                </section>
              )}

              {tab === 'budget' && (
                <section className="tracking-budget-grid">
                  <article>
                    <span>
                      Presupuesto máximo
                    </span>

                    <strong>
                      {money(
                        tracking
                          .budget
                          .budget_limit_cents,
                        tracking
                          .budget
                          .currency,
                      )}
                    </strong>
                  </article>

                  <article>
                    <span>
                      Cotización
                    </span>

                    <strong>
                      {money(
                        tracking
                          .budget
                          .quoted_amount_cents,
                        tracking
                          .budget
                          .currency,
                      )}
                    </strong>
                  </article>

                  <article>
                    <span>
                      Contratado
                    </span>

                    <strong>
                      {money(
                        tracking
                          .budget
                          .contracted_cents,
                        tracking
                          .budget
                          .currency,
                      )}
                    </strong>
                  </article>

                  <article>
                    <span>
                      Financiado
                    </span>

                    <strong>
                      {money(
                        tracking
                          .budget
                          .funded_cents,
                        tracking
                          .budget
                          .currency,
                      )}
                    </strong>
                  </article>

                  <article>
                    <span>
                      Disponible
                    </span>

                    <strong>
                      {money(
                        tracking
                          .budget
                          .remaining_budget_cents,
                        tracking
                          .budget
                          .currency,
                      )}
                    </strong>
                  </article>

                  <article>
                    <span>
                      Estado del pago
                    </span>

                    <strong>
                      {statusLabel(
                        tracking
                          .budget
                          .payment_status,
                      )}
                    </strong>
                  </article>
                </section>
              )}

              {tab === 'delivery' && (
                <section className="tracking-delivery-section">
                  <PackageCheck
                    size={42}
                  />

                  <span
                    className={
                      tracking.delivery.ready
                        ? 'tracking-delivery-ready'
                        : ''
                    }
                  >
                    {tracking.delivery.ready
                      ? 'LISTO PARA ENTREGA'
                      : 'ENTREGA PENDIENTE'}
                  </span>

                  <h3>
                    Versión {
                      tracking.delivery.version
                    }
                  </h3>

                  <p>
                    {
                      tracking.delivery.message
                    }
                  </p>

                  <div className="tracking-delivery-metrics">
                    <article>
                      <span>
                        Vera
                      </span>

                      <strong>
                        {
                          tracking.delivery
                            .vera_approved
                          ? 'Aprobado'
                          : statusLabel(
                              tracking.delivery
                                .vera_status,
                            )
                        }
                      </strong>
                    </article>

                    <article>
                      <span>
                        Archivos
                      </span>

                      <strong>
                        {
                          tracking.delivery
                            .files_count
                        }
                      </strong>
                    </article>

                    <article>
                      <span>
                        Correcciones
                      </span>

                      <strong>
                        {
                          tracking.delivery
                            .corrections_requested
                        }
                      </strong>
                    </article>
                  </div>

                  <div className="tracking-version-history">
                    <div className="tracking-version-heading">
                      <div>
                        <span>
                          HISTORIAL DE VERSIONES
                        </span>

                        <h3>
                          Evolución de la entrega
                        </h3>
                      </div>

                      <strong>
                        {
                          tracking.delivery
                            .versions_total
                        }{' '}
                        versión(es)
                      </strong>
                    </div>

                    {tracking.delivery.history.length ===
                    0 ? (
                      <div className="tracking-empty compact">
                        La primera versión aparecerá
                        cuando Vera apruebe una
                        entrega.
                      </div>
                    ) : (
                      <div className="tracking-version-list">
                        {tracking.delivery.history
                          .slice()
                          .reverse()
                          .map(
                            (version) => (
                              <article
                                key={
                                  version
                                    .review_id
                                }
                                className={
                                  version.is_current
                                    ? 'current'
                                    : ''
                                }
                              >
                                <div className="tracking-version-top">
                                  <strong>
                                    {
                                      version
                                        .version
                                    }
                                  </strong>

                                  {version.is_current && (
                                    <span>
                                      Versión actual
                                    </span>
                                  )}
                                </div>

                                <div className="tracking-version-details">
                                  <span>
                                    Vera
                                  </span>

                                  <strong>
                                    {version.score ??
                                      'Sin puntuación'}
                                  </strong>
                                </div>

                                {version.summary && (
                                  <p>
                                    {
                                      version
                                        .summary
                                    }
                                  </p>
                                )}

                                <div className="tracking-version-footer">
                                  <span>
                                    {version.client_decision ===
                                    'accepted'
                                      ? 'Aceptada por el cliente'
                                      : version.client_decision ===
                                        'corrections_requested'
                                        ? 'El cliente solicitó correcciones'
                                        : 'Esperando decisión del cliente'}
                                  </span>

                                  {version.vera_completed_at && (
                                    <small>
                                      {dateLabel(
                                        version
                                          .vera_completed_at,
                                      )}
                                    </small>
                                  )}
                                </div>

                                {version.client_comment && (
                                  <blockquote>
                                    {
                                      version
                                        .client_comment
                                    }
                                  </blockquote>
                                )}
                              </article>
                            ),
                          )}
                      </div>
                    )}
                  </div>

                  <div className="tracking-delivery-files">
                    <h3>
                      Archivos generados
                    </h3>

                    {tracking.delivery.files.length ===
                    0 ? (
                      <div className="tracking-empty compact">
                        Todavía no hay archivos
                        registrados para entregar.
                      </div>
                    ) : (
                      tracking.delivery.files.map(
                        (file) => (
                          <article
                            key={
                              file.artifact_id
                            }
                          >
                            <div>
                              <strong>
                                {
                                  file
                                    .relative_path
                                }
                              </strong>

                              <span>
                                Archivo generado
                              </span>
                            </div>

                            <small>
                              {
                                file.size_bytes
                              } bytes
                            </small>
                          </article>
                        ),
                      )
                    )}
                  </div>

                  <div className="tracking-client-decision">
                    <span>
                      DECISIÓN DEL CLIENTE
                    </span>

                    <h3>
                      Revisión de la entrega
                    </h3>

                    {tracking.delivery.client_decision ===
                    'accepted' ? (
                      <div className="tracking-client-result accepted">
                        <CheckCircle2
                          size={21}
                        />

                        <div>
                          <strong>
                            Entrega aceptada
                          </strong>

                          <p>
                            {
                              tracking.delivery
                                .client_comment
                            }
                          </p>
                        </div>
                      </div>
                    ) : tracking.delivery
                        .client_decision ===
                        'corrections_requested'
                        && !tracking.delivery
                          .client_action_required ? (
                      <div className="tracking-client-result corrections">
                        <Clock3
                          size={21}
                        />

                        <div>
                          <strong>
                            Correcciones solicitadas
                          </strong>

                          <p>
                            {
                              tracking.delivery
                                .client_comment
                            }
                          </p>
                        </div>
                      </div>
                    ) : tracking.delivery
                        .client_action_required ? (
                      <>
                        <p>
                          Revisa esta versión y
                          decide si cumple con lo
                          solicitado.
                        </p>

                        <textarea
                          className="tracking-client-comment"
                          value={decisionComment}
                          maxLength={4000}
                          placeholder={
                            'Comentario opcional al aceptar. '
                            + 'Si solicitas correcciones, '
                            + 'describe claramente los cambios.'
                          }
                          onChange={(event) => {
                            setDecisionComment(
                              event.target.value,
                            )

                            setDecisionError('')
                            setDecisionSuccess('')
                          }}
                        />

                        {decisionError && (
                          <div className="tracking-decision-alert error">
                            {decisionError}
                          </div>
                        )}

                        {decisionSuccess && (
                          <div className="tracking-decision-alert success">
                            {decisionSuccess}
                          </div>
                        )}

                        <div className="tracking-decision-actions">
                          <button
                            type="button"
                            className="accept"
                            disabled={
                              submittingDecision
                            }
                            onClick={() =>
                              void submitDecision(
                                'accepted',
                              )
                            }
                          >
                            <CheckCircle2
                              size={17}
                            />

                            {submittingDecision
                              ? 'Procesando...'
                              : 'Aceptar entrega'}
                          </button>

                          <button
                            type="button"
                            className="correction"
                            disabled={
                              submittingDecision
                            }
                            onClick={() =>
                              void submitDecision(
                                'corrections_requested',
                              )
                            }
                          >
                            Solicitar corrección
                          </button>
                        </div>
                      </>
                    ) : (
                      <p>
                        Esta decisión se habilitará
                        cuando Vera apruebe la
                        versión final del proyecto.
                      </p>
                    )}
                  </div>

                </section>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
