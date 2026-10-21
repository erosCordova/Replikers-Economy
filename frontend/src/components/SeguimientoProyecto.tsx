import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'

import type {
  CSSProperties,
} from 'react'

import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  FileCheck2,
  FolderKanban,
  ListChecks,
  PackageCheck,
  RefreshCw,
  ShieldCheck,
  Users,
  WalletCards,
  XCircle,
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
  vera_completed_at: string | null
  client_decision: string
  client_comment: string
  client_decided_at: string | null
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
    client_decision_review_attempt: number | null
    client_decided_at: string | null
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
  | 'project'
  | 'tasks'
  | 'team'
  | 'tests'
  | 'delivery'
  | 'budget'


interface Props {
  projectId: number
  projectTitle: string
  onClose: () => void
}


interface PhaseItem {
  id: string
  label: string
  progress: number
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
    id: 'project',
    label: 'Proyecto',
  },
  {
    id: 'tasks',
    label: 'Tareas',
  },
  {
    id: 'team',
    label: 'Equipo',
  },
  {
    id: 'tests',
    label: 'QA',
  },
  {
    id: 'delivery',
    label: 'Entregas',
  },
  {
    id: 'budget',
    label: 'Economía',
  },
]


const statusLabels:
  Record<string, string> = {
    draft:
      'Borrador',

    planned:
      'Planificada',

    planning:
      'Planificando',

    pending:
      'Pendiente',

    assigned:
      'Asignada',

    active:
      'Activa',

    contracted:
      'Contratada',

    executing:
      'En desarrollo',

    running:
      'En desarrollo',

    completed:
      'Completada',

    prepared:
      'Preparada',

    passed:
      'Aprobada',

    approved:
      'Aprobada',

    failed:
      'Fallida',

    needs_review:
      'En revisión',

    corrections_requested:
      'Correcciones solicitadas',

    correcting:
      'En corrección',

    awaiting_final_review:
      'Esperando a Vera',

    unpaid:
      'Sin financiar',

    partially_funded:
      'Financiado parcialmente',

    funded:
      'Financiado',

    escrowed:
      'Financiado',

    paid:
      'Pagado',

    settled:
      'Liquidado',
  }


function specialtyLabel(
  value: string,
) {
  const labels:
    Record<string, string> = {
      'Generalist':
        'Generalista',

      'Product / Requirements':
        'Producto y requisitos',

      'Software Architect':
        'Arquitectura de software',

      'UX Research':
        'Investigación UX',

      'UI Designer':
        'Diseño de interfaz',

      'Frontend Developer':
        'Frontend',

      'Backend Developer':
        'Backend',

      'Database Engineer':
        'Base de datos',

      'Integration Specialist':
        'Integraciones',

      'Security Engineer':
        'Seguridad',

      'QA Engineer':
        'QA y pruebas',

      'DevOps Engineer':
        'DevOps',

      'Accessibility Specialist':
        'Accesibilidad',

      'SEO/Performance Specialist':
        'SEO y rendimiento',

      'Content/Copy Specialist':
        'Contenido',

      'Final Reviewer':
        'Revisión final',
    }

  return (
    labels[value]
    ?? value
    ?? 'Especialista'
  )
}


function statusLabel(
  value?: string | null,
) {
  if (!value) {
    return 'Pendiente'
  }

  return (
    statusLabels[
      value
        .trim()
        .toLowerCase()
    ]
    ?? value
  )
}


function statusTone(
  value?: string | null,
) {
  const status =
    (
      value
      ?? ''
    )
      .toLowerCase()

  if (
    [
      'completed',
      'passed',
      'approved',
      'active',
      'paid',
      'settled',
    ].includes(status)
  ) {
    return 'success'
  }

  if (
    [
      'failed',
      'blocked',
      'cancelled',
      'canceled',
    ].includes(status)
  ) {
    return 'danger'
  }

  if (
    [
      'needs_review',
      'corrections_requested',
      'correcting',
      'awaiting_final_review',
    ].includes(status)
  ) {
    return 'warning'
  }

  if (
    [
      'running',
      'executing',
      'assigned',
      'contracted',
      'prepared',
      'planning',
    ].includes(status)
  ) {
    return 'info'
  }

  return 'muted'
}


function money(
  cents: number | null,
  currency: string,
) {
  if (
    cents === null
    || cents === undefined
  ) {
    return 'No definido'
  }

  return new Intl.NumberFormat(
    'es-PE',
    {
      style: 'currency',
      currency:
        currency || 'PEN',
    },
  ).format(
    cents / 100,
  )
}


function percent(
  value: number,
) {
  return Math.max(
    0,
    Math.min(
      100,
      Math.round(
        value,
      ),
    ),
  )
}


function dateLabel(
  value?: string | null,
) {
  if (!value) {
    return 'Pendiente'
  }

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
      dateStyle: 'medium',
      timeStyle: 'short',
    },
  ).format(date)
}


function relativeDate(
  value: string,
) {
  const date =
    new Date(value)

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return ''
  }

  const diff =
    Date.now()
    - date.getTime()

  const minutes =
    Math.floor(
      diff
      / 60000,
    )

  if (
    minutes < 60
  ) {
    return (
      minutes <= 1
        ? 'hace un momento'
        : `hace ${minutes} min`
    )
  }

  const hours =
    Math.floor(
      minutes / 60,
    )

  if (
    hours < 24
  ) {
    return (
      hours === 1
        ? 'hace 1 hora'
        : `hace ${hours} horas`
    )
  }

  const days =
    Math.floor(
      hours / 24,
    )

  return (
    days === 1
      ? 'hace 1 día'
      : `hace ${days} días`
  )
}


function errorMessage(
  error: unknown,
) {
  if (
    axios.isAxiosError(
      error,
    )
  ) {
    const detail =
      error
        .response
        ?.data
        ?.detail

    if (
      typeof detail
      === 'string'
    ) {
      return detail
    }
  }

  return (
    'No se pudo cargar '
    + 'el proyecto.'
  )
}


function incidentTone(
  severity: string,
) {
  const value =
    severity
      .toLowerCase()

  if (
    value.includes('high')
    || value.includes('alta')
    || value.includes('critical')
    || value.includes('crítica')
  ) {
    return 'danger'
  }

  if (
    value.includes('medium')
    || value.includes('media')
  ) {
    return 'warning'
  }

  return 'info'
}


function phaseState(
  phase: PhaseItem,
  currentStage: string,
) {
  if (
    phase.progress >= 1
  ) {
    return 'completed'
  }

  if (
    phase.id === currentStage
    || (
      phase.progress > 0
      && phase.progress < 1
    )
  ) {
    return 'active'
  }

  return 'pending'
}


function phaseIcon(
  state: string,
) {
  if (
    state === 'completed'
  ) {
    return (
      <CheckCircle2
        size={18}
      />
    )
  }

  if (
    state === 'active'
  ) {
    return (
      <Activity
        size={17}
      />
    )
  }

  return (
    <span className="project-phase-dot" />
  )
}


function tabIcon(
  tab: Tab,
) {
  const props = {
    size: 17,
  }

  switch (tab) {
    case 'summary':
      return (
        <FolderKanban
          {...props}
        />
      )

    case 'project':
      return (
        <Activity
          {...props}
        />
      )

    case 'tasks':
      return (
        <ListChecks
          {...props}
        />
      )

    case 'team':
      return (
        <Users
          {...props}
        />
      )

    case 'tests':
      return (
        <ShieldCheck
          {...props}
        />
      )

    case 'delivery':
      return (
        <PackageCheck
          {...props}
        />
      )

    case 'budget':
      return (
        <WalletCards
          {...props}
        />
      )
  }
}


export default function SeguimientoProyecto({
  projectId,
  projectTitle,
  onClose,
}: Props) {
  const [
    tab,
    setTab,
  ] = useState<Tab>(
    'summary',
  )

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
        } catch (
          requestError
        ) {
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
            void loadTracking(
              true,
            )
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
        'Describe claramente qué deseas corregir.',
      )

      return
    }

    setSubmittingDecision(
      true,
    )

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
          : 'Solicitud de corrección enviada.',
      )

      await loadTracking(
        true,
      )
    } catch (
      requestError
    ) {
      setDecisionError(
        errorMessage(
          requestError,
        ),
      )
    } finally {
      setSubmittingDecision(
        false,
      )
    }
  }


  const phases =
    useMemo(
      () => {
        if (!tracking) {
          return []
        }

        const marketProgress =
          tracking
            .progress_basis
            .contracting > 0
            ? 1
            : tracking
                .progress_basis
                .planning >= 1
              ? 0.4
              : 0

        return [
          {
            id:
              'planning',
            label:
              'Planificación',
            progress:
              tracking
                .progress_basis
                .planning,
          },
          {
            id:
              'market',
            label:
              'Mercado',
            progress:
              marketProgress,
          },
          {
            id:
              'contracting',
            label:
              'Contratación',
            progress:
              tracking
                .progress_basis
                .contracting,
          },
          {
            id:
              'execution',
            label:
              'Ejecución',
            progress:
              tracking
                .progress_basis
                .execution,
          },
          {
            id:
              'qa',
            label:
              'QA',
            progress:
              tracking
                .progress_basis
                .qa,
          },
          {
            id:
              'final_review',
            label:
              'Vera',
            progress:
              tracking
                .progress_basis
                .final_review,
          },
          {
            id:
              'delivery',
            label:
              'Entrega',
            progress:
              tracking
                .delivery
                .ready
                ? 1
                : 0,
          },
        ] satisfies PhaseItem[]
      },
      [
        tracking,
      ],
    )


  if (
    loading
  ) {
    return (
      <section className="project-workspace-state">
        <RefreshCw
          size={28}
          className="tracking-spin"
        />

        <h3>
          Preparando espacio del proyecto
        </h3>

        <p>
          Cargando información real del proyecto...
        </p>
      </section>
    )
  }


  if (
    error
    || !tracking
  ) {
    return (
      <section className="project-workspace-state error">
        <AlertTriangle
          size={30}
        />

        <h3>
          No se pudo abrir el proyecto
        </h3>

        <p>
          {error}
        </p>

        <button
          type="button"
          onClick={() =>
            void loadTracking()
          }
        >
          <RefreshCw
            size={17}
          />
          Reintentar
        </button>

        <button
          type="button"
          className="secondary"
          onClick={onClose}
        >
          <ArrowLeft
            size={17}
          />
          Volver
        </button>
      </section>
    )
  }


  const qaTotal =
    Math.max(
      tracking.qa.latest_reviews,
      tracking.qa.passed
      + tracking.qa.failed
      + tracking.qa.pending,
    )


  const qaPercent =
    qaTotal > 0
      ? percent(
          (
            tracking.qa.passed
            / qaTotal
          )
          * 100,
        )
      : 0


  const budgetLimit =
    tracking
      .budget
      .budget_limit_cents


  const budgetPercent =
    budgetLimit
    && budgetLimit > 0
      ? percent(
          (
            tracking
              .budget
              .contracted_cents
            / budgetLimit
          )
          * 100,
        )
      : 0


  const healthIsGood =
    tracking
      .report
      .incidents_total === 0
    && tracking
      .qa
      .failed === 0


  const healthLabel =
    healthIsGood
      ? 'Saludable'
      : tracking
          .report
          .incidents_total > 0
        ? 'Requiere atención'
        : 'En seguimiento'


  const progressStyle = {
    '--project-progress':
      `${percent(
        tracking.progress_percent,
      )}%`,
  } as CSSProperties


  return (
    <section className="project-workspace">
      <header className="project-workspace-header">
        <div>
          <button
            type="button"
            className="project-back"
            onClick={onClose}
          >
            <ArrowLeft
              size={17}
            />
            Proyectos
          </button>

          <div className="project-title-row">
            <div>
              <span className="project-overline">
                PROYECTO #{tracking.project_id}
              </span>

              <h1>
                {
                  tracking.project_title
                  || projectTitle
                }
              </h1>
            </div>

            <span
              className={
                `project-status-main `
                + statusTone(
                  tracking.project_status,
                )
              }
            >
              <span />
              {statusLabel(
                tracking.project_status,
              )}
            </span>
          </div>
        </div>

        <button
          type="button"
          className="project-refresh"
          onClick={() =>
            void loadTracking()
          }
        >
          <RefreshCw
            size={17}
          />
          Actualizar
        </button>
      </header>


      <section className="project-overview-grid">
        <article className="project-card project-progress-card">
          <span className="project-card-label">
            Progreso del proyecto
          </span>

          <div className="project-progress-content">
            <div
              className="project-progress-ring"
              style={progressStyle}
            >
              <div>
                <strong>
                  {tracking.progress_percent}%
                </strong>

                <span>
                  completado
                </span>
              </div>
            </div>

            <div className="project-progress-details">
              <div>
                <span className="legend-dot cyan" />
                <span>
                  Tareas completadas
                </span>

                <strong>
                  {
                    tracking.tasks.completed
                  }
                  /
                  {
                    tracking.tasks.total
                  }
                </strong>
              </div>

              <div>
                <span className="legend-dot violet" />
                <span>
                  QA aprobadas
                </span>

                <strong>
                  {
                    tracking.qa.passed
                  }
                  /
                  {
                    qaTotal
                  }
                </strong>
              </div>

              <div>
                <span className="legend-dot amber" />
                <span>
                  Archivos de entrega
                </span>

                <strong>
                  {
                    tracking.delivery
                      .files_count
                  }
                </strong>
              </div>
            </div>
          </div>
        </article>


        <article className="project-card project-stage-card">
          <div className="project-card-heading">
            <div>
              <span className="project-card-label">
                Etapa actual del proyecto
              </span>

              <h2>
                {tracking.stage_label}
              </h2>

              <p>
                {tracking.next_action}
              </p>
            </div>

            <Activity
              size={25}
            />
          </div>

          <div className="project-stage-mini">
            {phases.map(
              (
                phase,
                index,
              ) => {
                const state =
                  phaseState(
                    phase,
                    tracking.stage,
                  )

                return (
                  <div
                    className={
                      `project-mini-phase ${state}`
                    }
                    key={phase.id}
                  >
                    <div className="project-mini-phase-top">
                      <span className="project-mini-node">
                        {phaseIcon(
                          state,
                        )}
                      </span>

                      {index <
                        phases.length
                        - 1 && (
                        <span className="project-mini-line" />
                      )}
                    </div>

                    <strong>
                      {phase.label}
                    </strong>

                    <small>
                      {state === 'completed'
                        ? 'Completada'
                        : state === 'active'
                          ? 'En curso'
                          : 'Pendiente'}
                    </small>
                  </div>
                )
              },
            )}
          </div>
        </article>


        <article
          className={
            `project-card project-health-card ${
              healthIsGood
                ? 'healthy'
                : 'attention'
            }`
          }
        >
          <div className="health-icon">
            <Activity
              size={26}
            />
          </div>

          <span className="project-card-label">
            Estado general
          </span>

          <h2>
            {healthLabel}
          </h2>

          <p>
            {
              tracking.report.summary
              || (
                healthIsGood
                  ? 'El proyecto avanza sin incidencias críticas.'
                  : 'Existen elementos que requieren seguimiento.'
              )
            }
          </p>
        </article>
      </section>


      <section className="project-kpi-grid">
        <article className="project-kpi blue">
          <div>
            <ListChecks
              size={21}
            />
          </div>

          <section>
            <strong>
              {tracking.tasks.completed}
              /
              {tracking.tasks.total}
            </strong>

            <span>
              Tareas completadas
            </span>

            <div className="mini-progress">
              <i
                style={{
                  width:
                    tracking.tasks.total > 0
                      ? `${
                          percent(
                            (
                              tracking.tasks.completed
                              / tracking.tasks.total
                            )
                            * 100,
                          )
                        }%`
                      : '0%',
                }}
              />
            </div>
          </section>
        </article>


        <article className="project-kpi violet">
          <div>
            <ShieldCheck
              size={21}
            />
          </div>

          <section>
            <strong>
              {tracking.qa.passed}
              /
              {qaTotal}
            </strong>

            <span>
              QA aprobadas
            </span>

            <div className="mini-progress">
              <i
                style={{
                  width:
                    `${qaPercent}%`,
                }}
              />
            </div>
          </section>
        </article>


        <article className="project-kpi amber">
          <div>
            <Users
              size={21}
            />
          </div>

          <section>
            <strong>
              {tracking.team.total}
            </strong>

            <span>
              Replikers activos
            </span>

            <div className="project-avatar-stack">
              {tracking
                .team
                .members
                .slice(
                  0,
                  4,
                )
                .map(
                  (
                    member,
                  ) => (
                    <span
                      key={
                        member
                          .repliker_id
                      }
                      title={
                        member.name
                      }
                    >
                      {
                        member
                          .name
                          .slice(
                            0,
                            1,
                          )
                          .toUpperCase()
                      }
                    </span>
                  ),
                )}
            </div>
          </section>
        </article>


        <article className="project-kpi green">
          <div>
            <CircleDollarSign
              size={21}
            />
          </div>

          <section>
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

            <span>
              Presupuesto contratado
            </span>

            <div className="mini-progress">
              <i
                style={{
                  width:
                    `${budgetPercent}%`,
                }}
              />
            </div>
          </section>
        </article>
      </section>


      <nav className="project-tabs">
        {tabs.map(
          (
            item,
          ) => (
            <button
              type="button"
              key={item.id}
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
              {tabIcon(
                item.id,
              )}

              {item.label}
            </button>
          ),
        )}
      </nav>


      <div className="project-tab-content">
        {tab === 'summary' && (
          <>
            <section className="project-summary-layout">
              <article className="project-panel project-task-preview">
                <div className="project-panel-heading">
                  <div>
                    <span>
                      TRABAJO DEL PROYECTO
                    </span>

                    <h3>
                      Tareas
                    </h3>
                  </div>

                  <button
                    type="button"
                    onClick={() =>
                      setTab(
                        'tasks',
                      )
                    }
                  >
                    Ver todas
                  </button>
                </div>

                <div className="project-task-table">
                  <div className="project-task-table-head">
                    <span>
                      Tarea
                    </span>

                    <span>
                      Especialidad
                    </span>

                    <span>
                      Estado
                    </span>

                    <span>
                      Presupuesto
                    </span>
                  </div>

                  {tracking
                    .tasks
                    .items
                    .slice(
                      0,
                      6,
                    )
                    .map(
                      (
                        task,
                      ) => (
                        <article
                          className="project-task-row"
                          key={
                            task.id
                          }
                        >
                          <div>
                            <span className="project-task-number">
                              {String(
                                task.id,
                              ).padStart(
                                2,
                                '0',
                              )}
                            </span>

                            <strong>
                              {
                                task.title
                              }
                            </strong>
                          </div>

                          <span>
                            {specialtyLabel(
                              task.required_specialty,
                            )}
                          </span>

                          <span
                            className={
                              `project-pill ${
                                statusTone(
                                  task.status,
                                )
                              }`
                            }
                          >
                            {statusLabel(
                              task.status,
                            )}
                          </span>

                          <strong>
                            {money(
                              task.max_budget_cents,
                              tracking
                                .budget
                                .currency,
                            )}
                          </strong>
                        </article>
                      ),
                    )}
                </div>
              </article>


              <aside className="project-summary-side">
                <article className="project-panel">
                  <div className="project-panel-heading">
                    <div>
                      <span>
                        EQUIPO
                      </span>

                      <h3>
                        Replikers
                      </h3>
                    </div>

                    <button
                      type="button"
                      onClick={() =>
                        setTab(
                          'team',
                        )
                      }
                    >
                      Ver equipo
                    </button>
                  </div>

                  <div className="project-team-preview">
                    {tracking
                      .team
                      .members
                      .length === 0 ? (
                      <div className="project-empty-small">
                        Aún no hay especialistas contratados.
                      </div>
                    ) : (
                      tracking
                        .team
                        .members
                        .slice(
                          0,
                          4,
                        )
                        .map(
                          (
                            member,
                          ) => (
                            <div
                              key={
                                member
                                  .repliker_id
                              }
                            >
                              <span className="project-person-avatar">
                                {
                                  member
                                    .name
                                    .slice(
                                      0,
                                      1,
                                    )
                                    .toUpperCase()
                                }
                              </span>

                              <section>
                                <strong>
                                  {
                                    member
                                      .name
                                  }
                                </strong>

                                <small>
                                  {specialtyLabel(
                                    member.specialty,
                                  )}
                                </small>
                              </section>

                              <span
                                className={
                                  `project-pill ${
                                    statusTone(
                                      member.status,
                                    )
                                  }`
                                }
                              >
                                {statusLabel(
                                  member.status,
                                )}
                              </span>
                            </div>
                          ),
                        )
                    )}
                  </div>
                </article>


                <article className="project-panel project-qa-preview">
                  <div className="project-panel-heading">
                    <div>
                      <span>
                        CALIDAD
                      </span>

                      <h3>
                        QA y alertas
                      </h3>
                    </div>

                    <button
                      type="button"
                      onClick={() =>
                        setTab(
                          'tests',
                        )
                      }
                    >
                      Ver QA
                    </button>
                  </div>

                  <div className="qa-summary-numbers">
                    <div>
                      <CheckCircle2
                        size={19}
                      />

                      <strong>
                        {
                          tracking
                            .qa
                            .passed
                        }
                      </strong>

                      <span>
                        aprobadas
                      </span>
                    </div>

                    <div>
                      <XCircle
                        size={19}
                      />

                      <strong>
                        {
                          tracking
                            .qa
                            .failed
                        }
                      </strong>

                      <span>
                        fallidas
                      </span>
                    </div>
                  </div>

                  {tracking
                    .report
                    .incidents
                    .slice(
                      0,
                      2,
                    )
                    .map(
                      (
                        incident,
                        index,
                      ) => (
                        <div
                          className={
                            `project-alert-row ${
                              incidentTone(
                                incident.severity,
                              )
                            }`
                          }
                          key={
                            `${incident.kind}-${index}`
                          }
                        >
                          <AlertTriangle
                            size={17}
                          />

                          <section>
                            <strong>
                              {
                                incident.title
                              }
                            </strong>

                            <small>
                              {
                                incident.detail
                              }
                            </small>
                          </section>
                        </div>
                      ),
                    )}
                </article>
              </aside>
            </section>


            <article className="project-panel project-delivery-readiness">
              <div>
                <PackageCheck
                  size={23}
                />

                <section>
                  <span>
                    PREPARACIÓN PARA ENTREGA FINAL
                  </span>

                  <h3>
                    {tracking.delivery.ready
                      ? 'Proyecto listo para entregar'
                      : 'Entrega en preparación'}
                  </h3>
                </section>
              </div>

              <div className="delivery-checks">
                <span
                  className={
                    tracking.tasks.completed
                    === tracking.tasks.total
                    && tracking.tasks.total > 0
                      ? 'done'
                      : ''
                  }
                >
                  <CheckCircle2
                    size={16}
                  />
                  Desarrollo
                </span>

                <span
                  className={
                    tracking.qa.failed === 0
                    && tracking.qa.passed > 0
                      ? 'done'
                      : ''
                  }
                >
                  <ShieldCheck
                    size={16}
                  />
                  QA
                </span>

                <span
                  className={
                    tracking.delivery
                      .vera_approved
                      ? 'done'
                      : ''
                  }
                >
                  <CheckCircle2
                    size={16}
                  />
                  Vera
                </span>

                <span
                  className={
                    tracking.delivery.ready
                      ? 'done'
                      : ''
                  }
                >
                  <PackageCheck
                    size={16}
                  />
                  Entrega
                </span>
              </div>

              <button
                type="button"
                onClick={() =>
                  setTab(
                    'delivery',
                  )
                }
              >
                Ver entrega
              </button>
            </article>
          </>
        )}


        {tab === 'project' && (
          <section className="project-detail-grid">
            <article className="project-panel project-phase-panel">
              <div className="project-panel-heading">
                <div>
                  <span>
                    CICLO DE VIDA
                  </span>

                  <h3>
                    Avance por etapas
                  </h3>
                </div>
              </div>

              <div className="project-phase-list">
                {phases.map(
                  (
                    phase,
                    index,
                  ) => {
                    const state =
                      phaseState(
                        phase,
                        tracking.stage,
                      )

                    return (
                      <article
                        className={
                          `project-phase-row ${state}`
                        }
                        key={
                          phase.id
                        }
                      >
                        <span className="phase-index">
                          {
                            state
                            === 'completed'
                              ? (
                                <CheckCircle2
                                  size={19}
                                />
                              )
                              : index + 1
                          }
                        </span>

                        <div>
                          <strong>
                            {
                              phase.label
                            }
                          </strong>

                          <span>
                            {state ===
                            'completed'
                              ? 'Completada'
                              : state ===
                                'active'
                                ? 'En curso'
                                : 'Pendiente'}
                          </span>
                        </div>

                        <div className="phase-bar">
                          <i
                            style={{
                              width:
                                `${
                                  percent(
                                    phase.progress
                                    * 100,
                                  )
                                }%`,
                            }}
                          />
                        </div>

                        <strong>
                          {
                            percent(
                              phase.progress
                              * 100,
                            )
                          }%
                        </strong>
                      </article>
                    )
                  },
                )}
              </div>
            </article>


            <article className="project-panel">
              <div className="project-panel-heading">
                <div>
                  <span>
                    ACTIVIDAD
                  </span>

                  <h3>
                    Historial reciente
                  </h3>
                </div>
              </div>

              <div className="project-activity-list">
                {tracking
                  .recent_activity
                  .length === 0 ? (
                  <div className="project-empty-small">
                    No hay actividad registrada.
                  </div>
                ) : (
                  tracking
                    .recent_activity
                    .slice(
                      0,
                      12,
                    )
                    .map(
                      (
                        item,
                      ) => (
                        <article
                          key={
                            item.id
                          }
                        >
                          <span className="activity-node" />

                          <div>
                            <strong>
                              {
                                item.title
                              }
                            </strong>

                            <p>
                              {
                                item.description
                              }
                            </p>
                          </div>

                          <small>
                            {relativeDate(
                              item.created_at,
                            )}
                          </small>
                        </article>
                      ),
                    )
                  )}
              </div>
            </article>
          </section>
        )}


        {tab === 'tasks' && (
          <article className="project-panel project-all-tasks">
            <div className="project-panel-heading">
              <div>
                <span>
                  EJECUCIÓN
                </span>

                <h3>
                  Todas las tareas
                </h3>
              </div>

              <strong>
                {tracking.tasks.total}
                {' '}
                tareas
              </strong>
            </div>

            <div className="project-task-table">
              <div className="project-task-table-head">
                <span>
                  Tarea
                </span>

                <span>
                  Especialidad
                </span>

                <span>
                  Estado
                </span>

                <span>
                  Presupuesto
                </span>
              </div>

              {tracking
                .tasks
                .items
                .map(
                  (
                    task,
                  ) => (
                    <article
                      className="project-task-row"
                      key={
                        task.id
                      }
                    >
                      <div>
                        <span className="project-task-number">
                          {String(
                            task.id,
                          ).padStart(
                            2,
                            '0',
                          )}
                        </span>

                        <strong>
                          {
                            task.title
                          }
                        </strong>
                      </div>

                      <span>
                        {specialtyLabel(
                          task.required_specialty,
                        )}
                      </span>

                      <span
                        className={
                          `project-pill ${
                            statusTone(
                              task.status,
                            )
                          }`
                        }
                      >
                        {statusLabel(
                          task.status,
                        )}
                      </span>

                      <strong>
                        {money(
                          task.max_budget_cents,
                          tracking
                            .budget
                            .currency,
                        )}
                      </strong>
                    </article>
                  ),
                )}
            </div>
          </article>
        )}


        {tab === 'team' && (
          <section className="project-team-grid">
            {tracking
              .team
              .members
              .length === 0 ? (
              <article className="project-panel project-empty-large">
                <Users
                  size={36}
                />

                <h3>
                  Aún no hay Replikers contratados
                </h3>

                <p>
                  El equipo aparecerá aquí cuando se completen las contrataciones.
                </p>
              </article>
            ) : (
              tracking
                .team
                .members
                .map(
                  (
                    member,
                  ) => (
                    <article
                      className="project-panel project-member-card"
                      key={
                        member
                          .repliker_id
                      }
                    >
                      <span className="project-person-avatar large">
                        {
                          member
                            .name
                            .slice(
                              0,
                              1,
                            )
                            .toUpperCase()
                        }
                      </span>

                      <div>
                        <h3>
                          {
                            member.name
                          }
                        </h3>

                        <p>
                          {specialtyLabel(
                            member.specialty,
                          )}
                        </p>
                      </div>

                      <span
                        className={
                          `project-pill ${
                            statusTone(
                              member.status,
                            )
                          }`
                        }
                      >
                        {statusLabel(
                          member.status,
                        )}
                      </span>

                      <div className="member-stats">
                        <span>
                          Contratos activos
                        </span>

                        <strong>
                          {
                            member
                              .active_contracts
                          }
                        </strong>
                      </div>

                      {member
                        .is_final_reviewer && (
                        <div className="vera-badge">
                          <ShieldCheck
                            size={16}
                          />
                          Revisión final
                        </div>
                      )}
                    </article>
                  ),
                )
            )}
          </section>
        )}


        {tab === 'tests' && (
          <section className="project-qa-layout">
            <article className="project-panel qa-score-panel">
              <span>
                ESTADO DE QA
              </span>

              <h2>
                {qaPercent}%
              </h2>

              <p>
                de las revisiones actuales han sido aprobadas
              </p>

              <div className="qa-large-bar">
                <i
                  style={{
                    width:
                      `${qaPercent}%`,
                  }}
                />
              </div>

              <div className="qa-count-grid">
                <div>
                  <CheckCircle2
                    size={18}
                  />

                  <strong>
                    {
                      tracking
                        .qa
                        .passed
                    }
                  </strong>

                  <span>
                    Aprobadas
                  </span>
                </div>

                <div>
                  <XCircle
                    size={18}
                  />

                  <strong>
                    {
                      tracking
                        .qa
                        .failed
                    }
                  </strong>

                  <span>
                    Fallidas
                  </span>
                </div>

                <div>
                  <Clock3
                    size={18}
                  />

                  <strong>
                    {
                      tracking
                        .qa
                        .pending
                    }
                  </strong>

                  <span>
                    Pendientes
                  </span>
                </div>
              </div>
            </article>


            <article className="project-panel">
              <div className="project-panel-heading">
                <div>
                  <span>
                    INCIDENCIAS
                  </span>

                  <h3>
                    Problemas detectados
                  </h3>
                </div>

                <strong>
                  {
                    tracking
                      .report
                      .incidents_total
                  }
                </strong>
              </div>

              <div className="project-incidents-list">
                {tracking
                  .report
                  .incidents
                  .length === 0 ? (
                  <div className="project-empty-small success">
                    <CheckCircle2
                      size={20}
                    />

                    No existen incidencias abiertas.
                  </div>
                ) : (
                  tracking
                    .report
                    .incidents
                    .map(
                      (
                        incident,
                        index,
                      ) => (
                        <article
                          className={
                            `project-incident ${
                              incidentTone(
                                incident.severity,
                              )
                            }`
                          }
                          key={
                            `${incident.kind}-${index}`
                          }
                        >
                          <AlertTriangle
                            size={19}
                          />

                          <div>
                            <strong>
                              {
                                incident.title
                              }
                            </strong>

                            <p>
                              {
                                incident.detail
                              }
                            </p>

                            {incident.task_title && (
                              <small>
                                Tarea: {
                                  incident.task_title
                                }
                              </small>
                            )}
                          </div>
                        </article>
                      ),
                    )
                  )}
              </div>
            </article>
          </section>
        )}


        {tab === 'budget' && (
          <section className="project-economy">
            <article className="project-panel economy-main">
              <div className="economy-heading">
                <div>
                  <span>
                    ECONOMÍA DEL PROYECTO
                  </span>

                  <h3>
                    Presupuesto
                  </h3>
                </div>

                <WalletCards
                  size={26}
                />
              </div>

              <strong className="economy-total">
                {money(
                  tracking
                    .budget
                    .contracted_cents,
                  tracking
                    .budget
                    .currency,
                )}
              </strong>

              <span>
                contratado de {
                  money(
                    tracking
                      .budget
                      .budget_limit_cents,
                    tracking
                      .budget
                      .currency,
                  )
                }
              </span>

              <div className="economy-bar">
                <i
                  style={{
                    width:
                      `${budgetPercent}%`,
                  }}
                />
              </div>
            </article>

            <div className="economy-grid">
              <article className="project-panel">
                <span>
                  Límite
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

              <article className="project-panel">
                <span>
                  Cotización R00
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

              <article className="project-panel">
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

              <article className="project-panel">
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

              <article className="project-panel">
                <span>
                  Ganancias Replikers
                </span>

                <strong>
                  {money(
                    tracking
                      .budget
                      .earnings_cents,
                    tracking
                      .budget
                      .currency,
                  )}
                </strong>
              </article>

              <article className="project-panel">
                <span>
                  Comisión
                </span>

                <strong>
                  {money(
                    tracking
                      .budget
                      .commission_cents,
                    tracking
                      .budget
                      .currency,
                  )}
                </strong>
              </article>
            </div>
          </section>
        )}


        {tab === 'delivery' && (
          <section className="project-delivery-layout">
            <article className="project-panel delivery-main-card">
              <div className="delivery-status-icon">
                <PackageCheck
                  size={34}
                />
              </div>

              <span>
                ENTREGA DEL PROYECTO
              </span>

              <h2>
                {tracking.delivery.ready
                  ? 'Lista para el cliente'
                  : 'En preparación'}
              </h2>

              <p>
                {
                  tracking.delivery.message
                }
              </p>

              <div className="delivery-status-grid">
                <div>
                  <span>
                    Versión
                  </span>

                  <strong>
                    {
                      tracking
                        .delivery
                        .version
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    Vera
                  </span>

                  <strong>
                    {
                      tracking
                        .delivery
                        .vera_approved
                        ? 'Aprobada'
                        : statusLabel(
                            tracking
                              .delivery
                              .vera_status,
                          )
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    Archivos
                  </span>

                  <strong>
                    {
                      tracking
                        .delivery
                        .files_count
                    }
                  </strong>
                </div>

                <div>
                  <span>
                    Correcciones
                  </span>

                  <strong>
                    {
                      tracking
                        .delivery
                        .corrections_requested
                    }
                  </strong>
                </div>
              </div>
            </article>


            {tracking.final_review && (
              <article className="project-panel vera-review-card">
                <div>
                  <ShieldCheck
                    size={25}
                  />

                  <section>
                    <span>
                      REVISIÓN DE VERA
                    </span>

                    <h3>
                      {statusLabel(
                        tracking
                          .final_review
                          .status,
                      )}
                    </h3>
                  </section>
                </div>

                <strong>
                  {
                    tracking
                      .final_review
                      .score
                    ?? '—'
                  }
                  /100
                </strong>

                <p>
                  {
                    tracking
                      .final_review
                      .summary
                  }
                </p>
              </article>
            )}


            <article className="project-panel">
              <div className="project-panel-heading">
                <div>
                  <span>
                    ARCHIVOS
                  </span>

                  <h3>
                    Entregables
                  </h3>
                </div>

                <strong>
                  {
                    tracking
                      .delivery
                      .files_count
                  }
                </strong>
              </div>

              <div className="delivery-file-list">
                {tracking
                  .delivery
                  .files
                  .length === 0 ? (
                  <div className="project-empty-small">
                    Todavía no hay archivos listos para entregar.
                  </div>
                ) : (
                  tracking
                    .delivery
                    .files
                    .map(
                      (
                        file,
                      ) => (
                        <article
                          key={
                            file
                              .artifact_id
                          }
                        >
                          <FileCheck2
                            size={19}
                          />

                          <div>
                            <strong>
                              {
                                file
                                  .relative_path
                              }
                            </strong>

                            <span>
                              {
                                file
                                  .media_type
                              }
                            </span>
                          </div>

                          <small>
                            {
                              file
                                .size_bytes
                            } bytes
                          </small>
                        </article>
                      ),
                    )
                  )}
              </div>
            </article>


            <article className="project-panel">
              <div className="project-panel-heading">
                <div>
                  <span>
                    HISTORIAL
                  </span>

                  <h3>
                    Versiones
                  </h3>
                </div>

                <strong>
                  {
                    tracking
                      .delivery
                      .versions_total
                  }
                </strong>
              </div>

              <div className="delivery-version-list">
                {tracking
                  .delivery
                  .history
                  .length === 0 ? (
                  <div className="project-empty-small">
                    La primera versión aparecerá cuando exista una entrega aprobada.
                  </div>
                ) : (
                  tracking
                    .delivery
                    .history
                    .slice()
                    .reverse()
                    .map(
                      (
                        version,
                      ) => (
                        <article
                          key={
                            version
                              .review_id
                          }
                          className={
                            version
                              .is_current
                              ? 'current'
                              : ''
                          }
                        >
                          <div>
                            <strong>
                              {
                                version
                                  .version
                              }
                            </strong>

                            <span>
                              Vera: {
                                version
                                  .score
                                ?? '—'
                              }/100
                            </span>
                          </div>

                          <span
                            className={
                              `project-pill ${
                                statusTone(
                                  version.status,
                                )
                              }`
                            }
                          >
                            {version.is_current
                              ? 'Actual'
                              : statusLabel(
                                  version.status,
                                )}
                          </span>

                          <p>
                            {
                              version
                                .summary
                            }
                          </p>

                          <small>
                            {dateLabel(
                              version
                                .vera_completed_at,
                            )}
                          </small>
                        </article>
                      ),
                    )
                  )}
              </div>
            </article>


            <article className="project-panel client-decision-card">
              <span>
                DECISIÓN DEL CLIENTE
              </span>

              <h3>
                Revisión de la entrega
              </h3>

              {tracking
                .delivery
                .client_decision
                === 'accepted' ? (
                <div className="client-result success">
                  <CheckCircle2
                    size={22}
                  />

                  <div>
                    <strong>
                      Entrega aceptada
                    </strong>

                    <p>
                      {
                        tracking
                          .delivery
                          .client_comment
                      }
                    </p>
                  </div>
                </div>
              ) : tracking
                  .delivery
                  .client_decision
                  === 'corrections_requested'
                  && !tracking
                    .delivery
                    .client_action_required ? (
                <div className="client-result warning">
                  <Clock3
                    size={22}
                  />

                  <div>
                    <strong>
                      Correcciones solicitadas
                    </strong>

                    <p>
                      {
                        tracking
                          .delivery
                          .client_comment
                      }
                    </p>
                  </div>
                </div>
              ) : tracking
                  .delivery
                  .client_action_required ? (
                <>
                  <p>
                    Revisa la entrega y decide si cumple con lo solicitado.
                  </p>

                  <textarea
                    value={
                      decisionComment
                    }
                    maxLength={
                      4000
                    }
                    placeholder="Escribe un comentario para la entrega..."
                    onChange={(
                      event,
                    ) => {
                      setDecisionComment(
                        event
                          .target
                          .value,
                      )

                      setDecisionError(
                        '',
                      )

                      setDecisionSuccess(
                        '',
                      )
                    }}
                  />

                  {decisionError && (
                    <div className="project-form-alert danger">
                      {
                        decisionError
                      }
                    </div>
                  )}

                  {decisionSuccess && (
                    <div className="project-form-alert success">
                      {
                        decisionSuccess
                      }
                    </div>
                  )}

                  <div className="client-decision-actions">
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

                      Aceptar entrega
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
                      Solicitar correcciones
                    </button>
                  </div>
                </>
              ) : (
                <p>
                  Esta opción se habilitará cuando Vera apruebe la entrega.
                </p>
              )}
            </article>
          </section>
        )}
      </div>
    </section>
  )
}
