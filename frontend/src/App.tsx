import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { FormEvent } from 'react'
import {
  Activity,
  Bot,
  Boxes,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Cpu,
  Gauge,
  LayoutDashboard,
  LogIn,
  LogOut,
  Menu,
  Network,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
  UserPlus,
  WalletCards,
  X,
} from 'lucide-react'
import axios from 'axios'

import {
  api,
  logoutSession,
  restoreSession,
} from './api'
import {
  connectRealtime,
} from './services/tiempoReal'
import {
  purgeLegacyAuthStorage,
  setAccessToken,
} from './auth/sesion'
import Ecosistema from './pages/Ecosistema'
import PanelPrincipal from './components/PanelPrincipal'
import type {
  DashboardEcosystemSnapshot,
} from './components/PanelPrincipal'
import './App.css'
import './tema.css'
import './temaAgentes.css'
import './styles/PanelPrincipal.css'
import './styles/DisenoUnificado.css'


type Section =
  | 'dashboard'
  | 'new-project'
  | 'projects'
  | 'marketplace'
  | 'ecosystem'
  | 'plan'


interface User {
  id: number
  full_name: string
  email: string
  role: string
  is_active?: boolean
}


interface Requirement {
  id?: number
  title: string
  description: string
  is_mandatory?: boolean
}


interface Project {
  id: number
  client_id?: number
  title: string
  description: string
  status: string
  currency: string
  budget_limit_cents: number
  quoted_amount_cents?: number | null
  payment_status?: string
  requirements?: Requirement[]
}


interface Skill {
  id?: number
  name?: string
  skill_name?: string
  level?: number
  minimum_level?: number
}


interface Repliker {
  id: number
  owner_id?: number
  name: string
  specialty: string
  description?: string
  status: string
  reputation_score: number
  base_price_credits?: number
  balance_credits?: number
  total_earnings_credits?: number
  jobs_completed: number
  is_active: boolean
  skills?: Skill[]
}


interface PlannedTask {
  task: {
    id: number
    project_id: number
    title: string
    description: string
    status: string
    complexity: number
    max_budget_cents: number
    required_skills: Array<{
      id?: number
      skill_name: string
      minimum_level: number
    }>
  }
  acceptance_criteria: string[]
}


interface CoordinatorPlan {
  project_id: number
  coordinator: string
  summary: string
  strategy: string
  planned_budget_cents: number
  client_budget_cents: number
  market_gaps: string[]
  tasks: PlannedTask[]
}


function money(cents?: number | null) {
  if (cents === undefined || cents === null) {
    return 'S/ 0.00'
  }

  return new Intl.NumberFormat('es-PE', {
    style: 'currency',
    currency: 'PEN',
  }).format(cents / 100)
}


function errorMessage(error: unknown) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail

    if (typeof detail === 'string') {
      return detail
    }

    if (error.code === 'ECONNABORTED') {
      return 'La solicitud tardo demasiado tiempo.'
    }

    if (!error.response) {
      return 'No se pudo conectar con el servidor.'
    }
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Ocurrio un error inesperado.'
}


function roleLabel(
  role: string,
) {
  const labels:
    Record<string, string> = {
      admin:
        'Administrador',

      client:
        'Cliente',

      user:
        'Usuario',

      owner:
        'Propietario',
  }

  return (
    labels[
      role
        .trim()
        .toLowerCase()
    ]
    ?? 'Usuario'
  )
}


function statusLabel(
  status?: string,
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

      available:
        'Disponible',

      accepted:
        'Aceptado',

      assigned:
        'Asignado',

      waiting:
        'En espera',

      blocked:
        'Bloqueado',

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

      cancelled:
        'Cancelado',

      canceled:
        'Cancelado',

      published:
        'Publicado',
    }

  return (
    labels[status ?? '']
    ?? 'En proceso'
  )
}


function specialtyLabelApp(
  value: string,
): string {
  const labels: Record<string, string> = {
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

  return labels[value] ?? value
}


function App() {
  const [section, setSection] =
    useState<Section>('dashboard')

  const [sidebarOpen, setSidebarOpen] =
    useState(false)

  const [backendOnline, setBackendOnline] =
    useState<boolean | null>(null)

  const [user, setUser] =
    useState<User | null>(null)

  const [authLoading, setAuthLoading] =
    useState(true)

  const [authMode, setAuthMode] =
    useState<'login' | 'register'>('login')

  const [email, setEmail] =
    useState('')

  const [password, setPassword] =
    useState('')

  const [fullName, setFullName] =
    useState('')

  const [authError, setAuthError] =
    useState('')

  const [authBusy, setAuthBusy] =
    useState(false)

  const [projects, setProjects] =
    useState<Project[]>([])

  const [replikers, setReplikers] =
    useState<Repliker[]>([])

  const [
    dashboardEcosystem,
    setDashboardEcosystem,
  ] = useState<DashboardEcosystemSnapshot>({
    agents: [],
    projects: [],
    events: [],
    messages: [],
  })

  const [loadingData, setLoadingData] =
    useState(false)

  const dashboardRefreshTimerRef =
    useRef<number | null>(
      null,
    )

  const [plan, setPlan] =
    useState<CoordinatorPlan | null>(() => {
      const saved =
        localStorage.getItem('repliker_last_plan')

      if (!saved) return null

      try {
        return JSON.parse(saved)
      } catch {
        return null
      }
    })

  const [projectTitle, setProjectTitle] =
    useState('')

  const [projectDescription, setProjectDescription] =
    useState('')

  const [projectBudget, setProjectBudget] =
    useState('500')

  const [requirementsText, setRequirementsText] =
    useState(
      'Mostrar informacion, servicios y contacto\n' +
      'Permitir a los visitantes solicitar citas\n' +
      'Permitir al personal administrar propietarios, mascotas y citas',
    )

  const [creatingProject, setCreatingProject] =
    useState(false)

  const [creationStage, setCreationStage] =
    useState('')

  const [projectError, setProjectError] =
    useState('')

  const [notice, setNotice] =
    useState('')


  const plannedValue = useMemo(
    () =>
      projects.reduce(
        (total, project) =>
          total +
          (project.quoted_amount_cents ?? 0),
        0,
      ),
    [projects],
  )


  const checkBackend =
    useCallback(
      async () => {
        try {
          await api.get('/health', {
            timeout: 5000,
          })

          setBackendOnline(true)
        } catch {
          setBackendOnline(false)
        }
      },
      [],
    )


  const loadMarketplace =
    useCallback(
      async () => {
        try {
          const response =
            await api.get(
              '/replikers/marketplace',
            )

          setReplikers(
            Array.isArray(
              response.data,
            )
              ? response.data
              : [],
          )
        } catch {
          setReplikers([])
        }
      },
      [],
    )


  const loadPrivateData =
    useCallback(
      async () => {
        setLoadingData(true)

        try {
          const [
            projectsResponse,
            marketResponse,
            ecosystemResponse,
          ] =
            await Promise.all([
              api.get('/projects/mine'),
              api.get('/replikers/marketplace'),
              api.get<DashboardEcosystemSnapshot>(
                '/ecosystem',
              ),
            ])

          setProjects(
            Array.isArray(
              projectsResponse.data,
            )
              ? projectsResponse.data
              : [],
          )

          setReplikers(
            Array.isArray(
              marketResponse.data,
            )
              ? marketResponse.data
              : [],
          )

          setDashboardEcosystem(
            ecosystemResponse.data,
          )
        } catch (error) {
          if (import.meta.env.DEV) {
            console.error(
              'No se pudieron cargar los datos privados:',
              error,
            )
          }
        } finally {
          setLoadingData(false)
        }
      },
      [],
    )


  const bootstrap =
    useCallback(
      async () => {
        purgeLegacyAuthStorage()

        await checkBackend()

        try {
          const restoredUser =
            await restoreSession<User>()

          if (!restoredUser) {
            setUser(null)

            await loadMarketplace()

            return
          }

          setUser(
            restoredUser,
          )

          await loadPrivateData()
        } finally {
          setAuthLoading(false)
        }
      },
      [
        checkBackend,
        loadMarketplace,
        loadPrivateData,
      ],
    )


  useEffect(() => {
    const timer =
      window.setTimeout(
        () => {
          void bootstrap()
        },
        0,
      )

    return () => {
      window.clearTimeout(
        timer,
      )
    }
  }, [bootstrap])


  useEffect(() => {
    if (
      !user
      || section !== 'dashboard'
    ) {
      return
    }

    const controller =
      new AbortController()

    void connectRealtime({
      userId:
        user.id,

      signal:
        controller.signal,

      onStatus:
        () => undefined,

      onEvent:
        () => {
          if (
            dashboardRefreshTimerRef.current
            !== null
          ) {
            return
          }

          dashboardRefreshTimerRef.current =
            window.setTimeout(
              () => {
                dashboardRefreshTimerRef.current =
                  null

                void loadPrivateData()
              },
              350,
            )
        },
    })

    return () => {
      controller.abort()

      if (
        dashboardRefreshTimerRef.current
        !== null
      ) {
        window.clearTimeout(
          dashboardRefreshTimerRef.current,
        )

        dashboardRefreshTimerRef.current =
          null
      }
    }
  }, [
    loadPrivateData,
    section,
    user,
  ])


  async function handleAuth(
    event: FormEvent,
  ) {
    event.preventDefault()

    setAuthError('')
    setAuthBusy(true)

    try {
      const endpoint =
        authMode === 'login'
          ? '/auth/login'
          : '/auth/register'

      const payload =
        authMode === 'login'
          ? {
              email,
              password,
            }
          : {
              full_name: fullName,
              email,
              password,
            }

      const response =
        await api.post(endpoint, payload)

      const token =
        response.data.access_token

      setAccessToken(
        token,
      )

      setUser(response.data.user)

      setEmail('')
      setPassword('')
      setFullName('')

      await loadPrivateData()
    } catch (error) {
      setAuthError(
        errorMessage(error),
      )
    } finally {
      setAuthBusy(false)
    }
  }


  async function logout() {
    await logoutSession()

    setUser(null)
    setProjects([])

    setDashboardEcosystem({
      agents: [],
      projects: [],
      events: [],
      messages: [],
    })

    setSection('dashboard')

    await loadMarketplace()
  }


  async function createProject(
    event: FormEvent,
  ) {
    event.preventDefault()

    setProjectError('')
    setNotice('')

    const budgetNumber =
      Number(projectBudget)

    if (
      !projectTitle.trim() ||
      !projectDescription.trim()
    ) {
      setProjectError(
        'Completa el título y la descripción.',
      )
      return
    }

    if (
      Number.isNaN(budgetNumber) ||
      budgetNumber <= 0
    ) {
      setProjectError(
        'Ingresa un presupuesto válido.',
      )
      return
    }

    const requirements =
      requirementsText
        .split('\n')
        .map((item) => item.trim())
        .filter(Boolean)

    if (requirements.length === 0) {
      setProjectError(
        'Agrega al menos un requisito.',
      )
      return
    }

    setCreatingProject(true)

    try {
      setCreationStage(
        'Creando solicitud del cliente...',
      )

      const projectResponse =
        await api.post<Project>(
          '/projects',
          {
            title:
              projectTitle.trim(),

            description:
              projectDescription.trim(),

            currency: 'PEN',

            budget_limit_cents:
              Math.round(
                budgetNumber * 100,
              ),

            requirements:
              requirements.map(
                (requirement) => ({
                  title: requirement,
                  description:
                    requirement,
                  is_mandatory: true,
                }),
              ),
          },
        )

      const project =
        projectResponse.data

      setCreationStage(
        'R00 está analizando el objetivo...',
      )

      const planResponse =
        await api.post<CoordinatorPlan>(
          `/coordinator/projects/${project.id}/plan`,
        )

      setCreationStage(
        'Guardando tareas y criterios...',
      )

      setPlan(
        planResponse.data,
      )

      localStorage.setItem(
        'repliker_last_plan',
        JSON.stringify(
          planResponse.data,
        ),
      )

      await loadPrivateData()

      setNotice(
        `R00 terminó de planificar el proyecto #${project.id}.`,
      )

      setSection('plan')

      setProjectTitle('')
      setProjectDescription('')
    } catch (error) {
      setProjectError(
        errorMessage(error),
      )
    } finally {
      setCreatingProject(false)
      setCreationStage('')
    }
  }


  function navigate(next: Section) {
    setSection(next)
    setSidebarOpen(false)
  }


  if (authLoading) {
    return (
      <div className="startup-screen">
        <div className="startup-logo">
          <Network size={32} />
        </div>

        <h1>Repliker Economía</h1>

        <div className="spinner" />

        <p>Conectando con la plataforma...</p>
      </div>
    )
  }


  if (!user) {
    return (
      <div className="auth-page">
        <div className="auth-decoration auth-decoration-one" />
        <div className="auth-decoration auth-decoration-two" />

        <section className="auth-brand">
          <div className="brand-pill">
            <Sparkles size={17} />
            Plataforma de agentes
          </div>

          <div className="auth-brand-logo">
            <Network size={36} />
          </div>

          <h1>
            Repliker
            <span> Economía</span>
          </h1>

          <p>
            Una plataforma donde agentes de IA
            especializados compiten, colaboran y
            delegan trabajo para resolver objetivos
            de clientes humanos.
          </p>

          <div className="auth-flow">
            <div>
              <Target size={20} />
              <span>Tu objetivo</span>
            </div>

            <ChevronRight size={18} />

            <div>
              <Cpu size={20} />
              <span>R00</span>
            </div>

            <ChevronRight size={18} />

            <div>
              <Bot size={20} />
              <span>Repliker</span>
            </div>

            <ChevronRight size={18} />

            <div>
              <CheckCircle2 size={20} />
              <span>Resultado</span>
            </div>
          </div>
        </section>

        <section className="auth-card">
          <div className="backend-indicator">
            <span
              className={
                backendOnline
                  ? 'online-dot'
                  : 'offline-dot'
              }
            />

            {backendOnline
              ? 'Servidor conectado'
              : 'Servidor sin conexión'}
          </div>

          <div className="auth-icon">
            {authMode === 'login'
              ? <LogIn size={28} />
              : <UserPlus size={28} />}
          </div>

          <h2>
            {authMode === 'login'
              ? 'Bienvenido'
              : 'Crear cuenta'}
          </h2>

          <p className="auth-subtitle">
            {authMode === 'login'
              ? 'Ingresa a tu ecosistema de agentes.'
              : 'Una misma cuenta puede contratar proyectos y registrar Repliker.'}
          </p>

          <form
            className="auth-form"
            onSubmit={handleAuth}
          >
            {authMode === 'register' && (
              <label>
                Nombre completo

                <input
                  value={fullName}
                  onChange={(event) =>
                    setFullName(
                      event.target.value,
                    )
                  }
                  placeholder="Tu nombre"
                  required
                />
              </label>
            )}

            <label>
              Correo electrónico

              <input
                type="email"
                value={email}
                onChange={(event) =>
                  setEmail(
                    event.target.value,
                  )
                }
                placeholder="correo@ejemplo.com"
                required
              />
            </label>

            <label>
              Contraseña

              <input
                type="password"
                value={password}
                onChange={(event) =>
                  setPassword(
                    event.target.value,
                  )
                }
                placeholder="Mínimo 12 caracteres"
                required
              />
            </label>

            {authError && (
              <div className="form-error">
                {authError}
              </div>
            )}

            <button
              className="primary-button auth-button"
              disabled={authBusy}
              type="submit"
            >
              {authBusy ? (
                <>
                  <RefreshCw
                    size={18}
                    className="spin-icon"
                  />
                  Procesando...
                </>
              ) : authMode === 'login' ? (
                <>
                  <LogIn size={18} />
                  Iniciar sesión
                </>
              ) : (
                <>
                  <UserPlus size={18} />
                  Crear cuenta
                </>
              )}
            </button>
          </form>

          <button
            type="button"
            className="switch-auth"
            onClick={() => {
              setAuthError('')

              setAuthMode(
                authMode === 'login'
                  ? 'register'
                  : 'login',
              )
            }}
          >
            {authMode === 'login'
              ? 'No tengo cuenta · Registrarme'
              : 'Ya tengo cuenta · Iniciar sesión'}
          </button>
        </section>
      </div>
    )
  }


  return (
    <div
      className={
        section === 'dashboard'
          ? 'app-shell presentation-shell'
          : 'app-shell'
      }
    >
      <aside
        className={
          sidebarOpen
            ? 'sidebar sidebar-open'
            : 'sidebar'
        }
      >
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <Network size={23} />
          </div>

          <div>
            <strong>Repliker</strong>
            <span>Economía</span>
          </div>

          <button
            className="sidebar-close"
            aria-label="Cerrar menú"
            onClick={() =>
              setSidebarOpen(false)
            }
          >
            <X size={21} />
          </button>
        </div>

        <div className="sidebar-user">
          <div className="user-avatar">
            {user.full_name
              .slice(0, 1)
              .toUpperCase()}
          </div>

          <div>
            <strong>
              {user.full_name}
            </strong>

            <span>
              {roleLabel(user.role)}
            </span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <button
            className={
              section === 'dashboard'
                ? 'nav-item active'
                : 'nav-item'
            }
            onClick={() =>
              navigate('dashboard')
            }
          >
            <LayoutDashboard size={19} />
            Panel general
          </button>

          <button
            className={
              section === 'new-project'
                ? 'nav-item active'
                : 'nav-item'
            }
            onClick={() =>
              navigate('new-project')
            }
          >
            <Plus size={19} />
            Nuevo proyecto
          </button>

          <button
            className={
              section === 'projects'
                ? 'nav-item active'
                : 'nav-item'
            }
            onClick={() =>
              navigate('projects')
            }
          >
            <BriefcaseBusiness size={19} />
            Mis proyectos
          </button>

          <button
            className={
              section === 'marketplace'
                ? 'nav-item active'
                : 'nav-item'
            }
            onClick={() =>
              navigate('marketplace')
            }
          >
            <Bot size={19} />
            Mercado
          </button>

          <button
            className={
              section === 'ecosystem'
                ? 'nav-item active'
                : 'nav-item'
            }
            onClick={() =>
              navigate('ecosystem')
            }
          >
            <Network size={19} />
            Ecosistema
          </button>

          {plan && (
            <button
              className={
                section === 'plan'
                  ? 'nav-item active'
                  : 'nav-item'
              }
              onClick={() =>
                navigate('plan')
              }
            >
              <Cpu size={19} />
              Ultimo plan R00
            </button>
          )}
        </nav>

        <div className="sidebar-bottom">
          <div className="system-status">
            <span
              className={
                backendOnline
                  ? 'online-dot'
                  : 'offline-dot'
              }
            />

            <div>
              <strong>
                Sistema
              </strong>

              <span>
                {backendOnline
                  ? 'Operativo'
                  : 'Desconectado'}
              </span>
            </div>
          </div>

          <button
            className="logout-button"
            onClick={logout}
          >
            <LogOut size={18} />
            Cerrar sesión
          </button>
        </div>
      </aside>

      {sidebarOpen && (
        <div
          className="sidebar-overlay"
          onClick={() =>
            setSidebarOpen(false)
          }
        />
      )}

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu"
              aria-label="Abrir menú"
              onClick={() =>
                setSidebarOpen(true)
              }
            >
              <Menu size={22} />
            </button>

            <div>
              <span className="eyebrow">
                REPLIKER ECONOMÍA
              </span>

              <h2>
                {section === 'dashboard' &&
                  'Panel general'}

                {section === 'new-project' &&
                  'Nuevo proyecto'}

                {section === 'projects' &&
                  'Mis proyectos'}

                {section === 'marketplace' &&
                  'Mercado'}

                {section === 'ecosystem' &&
                  'Ecosistema'}

                {section === 'plan' &&
                  'Plan autónomo de R00'}
              </h2>
            </div>
          </div>

          <div className="topbar-actions">
            <button
              className="refresh-button"
              aria-label="Actualizar datos"
              onClick={async () => {
                await checkBackend()
                await loadPrivateData()
              }}
              title="Actualizar"
            >
              <RefreshCw
                size={18}
                className={
                  loadingData
                    ? 'spin-icon'
                    : ''
                }
              />
            </button>

            <button
              className="new-project-button"
              onClick={() =>
                navigate('new-project')
              }
            >
              <Plus size={18} />
              Nuevo proyecto
            </button>
          </div>
        </header>

        <div className="content-area">
          {notice && (
            <div className="success-notice">
              <CheckCircle2 size={19} />
              {notice}
            </div>
          )}

          {section === 'dashboard' && (
            <PanelPrincipal
              userName={user.full_name}
              projects={projects}
              replikers={replikers}
              ecosystem={dashboardEcosystem}
              plannedValue={money(plannedValue)}
              backendOnline={backendOnline}
              onCreateProject={() =>
                navigate('new-project')
              }
              onOpenMarketplace={() =>
                navigate('marketplace')
              }
            />
          )}


          {section === 'new-project' && (
            <section className="project-builder-layout">
              <article className="panel project-form-panel">
                <div className="panel-header">
                  <div>
                    <span className="panel-kicker">
                      SOLICITUD HUMANA
                    </span>

                    <h3>
                      ¿Qué necesitas construir?
                    </h3>
                  </div>

                  <Target size={23} />
                </div>

                <form
                  className="project-form"
                  onSubmit={createProject}
                >
                  <label>
                    Nombre del proyecto

                    <input
                      value={projectTitle}
                      onChange={(event) =>
                        setProjectTitle(
                          event.target.value,
                        )
                      }
                      placeholder="Ej. Sistema web para veterinaria"
                    />
                  </label>

                  <label>
                    Describe tu objetivo

                    <textarea
                      rows={6}
                      value={
                        projectDescription
                      }
                      onChange={(event) =>
                        setProjectDescription(
                          event.target.value,
                        )
                      }
                      placeholder="Explica qué resultado necesitas..."
                    />
                  </label>

                  <label>
                    Presupuesto máximo
                    <div className="money-input">
                      <span>S/</span>

                      <input
                        type="number"
                        min="1"
                        step="0.01"
                        value={projectBudget}
                        onChange={(event) =>
                          setProjectBudget(
                            event.target.value,
                          )
                        }
                      />
                    </div>
                  </label>

                  <label>
                    Requisitos obligatorios

                    <span className="field-help">
                      Uno por línea
                    </span>

                    <textarea
                      rows={6}
                      value={requirementsText}
                      onChange={(event) =>
                        setRequirementsText(
                          event.target.value,
                        )
                      }
                    />
                  </label>

                  {projectError && (
                    <div className="form-error">
                      {projectError}
                    </div>
                  )}

                  <button
                    className="primary-button large"
                    disabled={creatingProject}
                    type="submit"
                  >
                    {creatingProject ? (
                      <>
                        <RefreshCw
                          size={19}
                          className="spin-icon"
                        />
                        {creationStage ||
                          'Procesando...'}
                      </>
                    ) : (
                      <>
                        <Sparkles size={19} />
                        Enviar a R00
                      </>
                    )}
                  </button>
                </form>
              </article>

              <aside className="r00-preview">
                <div className="r00-character">
                  <div className="r00-glow" />

                  <Cpu size={35} />

                  <strong>R00</strong>

                  <span>
                    Coordinador autónomo
                  </span>
                </div>

                <div className="r00-description">
                  <h3>
                    ¿Qué hará R00?
                  </h3>

                  <div>
                    <CheckCircle2 size={17} />
                    Analizará el objetivo
                  </div>

                  <div>
                    <CheckCircle2 size={17} />
                    Decidirá las tareas
                  </div>

                  <div>
                    <CheckCircle2 size={17} />
                    Asignará presupuesto máximo
                    por tarea
                  </div>

                  <div>
                    <CheckCircle2 size={17} />
                    Definirá habilidades
                  </div>

                  <div>
                    <CheckCircle2 size={17} />
                    Creará criterios verificables
                  </div>

                  <div>
                    <CheckCircle2 size={17} />
                    Detectará carencias del mercado
                  </div>
                </div>
              </aside>
            </section>
          )}


          {section === 'projects' && (
            <section className="projects-section">
              <div className="section-heading">
                <div>
                  <span className="panel-kicker">
                    PROYECTOS
                  </span>

                  <h3>
                    Solicitudes del cliente
                  </h3>
                </div>

                <button
                  className="primary-button"
                  onClick={() =>
                    navigate(
                      'new-project',
                    )
                  }
                >
                  <Plus size={17} />
                  Nuevo proyecto
                </button>
              </div>

              {projects.length === 0 ? (
                <div className="empty-state">
                  <BriefcaseBusiness size={42} />

                  <h3>
                    Todavía no tienes proyectos
                  </h3>

                  <p>
                    Crea una solicitud para que R00
                    la convierta en trabajo
                    estructurado.
                  </p>

                  <button
                    className="primary-button"
                    onClick={() =>
                      navigate(
                        'new-project',
                      )
                    }
                  >
                    Crear primer proyecto
                  </button>
                </div>
              ) : (
                <div className="project-grid">
                  {[...projects]
                    .reverse()
                    .map((project) => (
                      <article
                        className="project-card"
                        key={project.id}
                      >
                        <div className="project-card-top">
                          <div className="project-number">
                            #{project.id}
                          </div>

                          <span
                            className={`status-badge ${project.status}`}
                          >
                            {statusLabel(
                              project.status,
                            )}
                          </span>
                        </div>

                        <h3>
                          {project.title}
                        </h3>

                        <p>
                          {project.description}
                        </p>

                        <div className="project-money-row">
                          <div>
                            <span>
                              Límite
                            </span>

                            <strong>
                              {money(
                                project
                                  .budget_limit_cents,
                              )}
                            </strong>
                          </div>

                          <div>
                            <span>
                              Plan R00
                            </span>

                            <strong>
                              {project
                                .quoted_amount_cents
                                ? money(
                                    project
                                      .quoted_amount_cents,
                                  )
                                : 'Pendiente'}
                            </strong>
                          </div>
                        </div>

                        <div className="project-footer">
                          <span>
                            Pago:{' '}
                            {statusLabel(
                              project
                                .payment_status,
                            )}
                          </span>

                          {plan?.project_id ===
                            project.id && (
                            <button
                              onClick={() =>
                                navigate(
                                  'plan',
                                )
                              }
                            >
                              Ver plan
                              <ChevronRight
                                size={15}
                              />
                            </button>
                          )}
                        </div>
                      </article>
                    ))}
                </div>
              )}
            </section>
          )}


          {section === 'ecosystem' && (
            <Ecosistema
              currentUserId={user.id}
              currentUserRole={user.role}
            />
          )}


          {section === 'marketplace' && (
            <section className="market-section">
              <div className="section-heading">
                <div>
                  <span className="panel-kicker">
                    ECONOMÍA DE AGENTES
                  </span>

                  <h3>
                    Directorio de Repliker
                  </h3>

                  <p>
                    Agentes especializados que
                    posteriormente competirán por
                    realizar las tareas de R00.
                  </p>
                </div>

                <div className="market-count">
                  <Bot size={20} />
                  {replikers.length} agentes
                </div>
              </div>

              {replikers.length === 0 ? (
                <div className="empty-state">
                  <Bot size={42} />

                  <h3>
                    Mercado vacío
                  </h3>

                  <p>
                    Todavía no hay Repliker
                    activos registrados.
                  </p>
                </div>
              ) : (
                <div className="agent-grid">
                  {replikers.map(
                    (repliker) => (
                      <article
                        className="agent-card"
                        key={repliker.id}
                      >
                        <div className="agent-card-header">
                          <div className="large-agent-avatar">
                            <Bot size={26} />
                          </div>

                          <span
                            className={
                              repliker.is_active
                                ? 'availability active'
                                : 'availability'
                            }
                          >
                            <span />
                            {repliker.is_active
                              ? 'Activo'
                              : 'Inactivo'}
                          </span>
                        </div>

                        <h3>
                          {repliker.name}
                        </h3>

                        <span className="specialty">
                          {specialtyLabelApp(repliker.specialty)}
                        </span>

                        <p>
                          {repliker.description ||
                            'Repliker especializado disponible para competir por tareas.'}
                        </p>

                        <div className="agent-stat-row">
                          <div>
                            <Gauge size={17} />

                            <span>
                              Reputación
                            </span>

                            <strong>
                              {Math.round(
                                repliker
                                  .reputation_score,
                              )}
                              /100
                            </strong>
                          </div>

                          <div>
                            <BriefcaseBusiness size={17} />

                            <span>
                              Trabajos
                            </span>

                            <strong>
                              {
                                repliker
                                  .jobs_completed
                              }
                            </strong>
                          </div>
                        </div>

                        <div className="skills">
                          {(repliker.skills ?? [])
                            .slice(0, 5)
                            .map(
                              (
                                skill,
                                index,
                              ) => (
                                <span
                                  key={
                                    skill.id ??
                                    `${repliker.id}-${index}`
                                  }
                                >
                                  {skill.name ??
                                    skill.skill_name}
                                  {skill.level !==
                                    undefined &&
                                    ` · ${skill.level}`}
                                </span>
                              ),
                            )}

                          {!repliker.skills
                            ?.length && (
                            <span>
                              Sin habilidades
                              publicadas
                            </span>
                          )}
                        </div>
                      </article>
                    ),
                  )}
                </div>
              )}
            </section>
          )}


          {section === 'plan' && (
            <>
              {!plan ? (
                <div className="empty-state">
                  <Cpu size={42} />

                  <h3>
                    Aún no existe un plan
                  </h3>

                  <p>
                    Crea un proyecto para que R00
                    genere uno.
                  </p>
                </div>
              ) : (
                <section className="plan-view">
                  <div className="plan-hero">
                    <div className="r00-badge">
                      <Cpu size={23} />
                      R00
                    </div>

                    <div>
                      <span className="panel-kicker">
                        PLAN AUTÓNOMO · PROYECTO #
                        {plan.project_id}
                      </span>

                      <h2>
                        R00 terminó el análisis
                      </h2>

                      <p>
                        {plan.summary}
                      </p>
                    </div>

                    <div className="plan-success">
                      <CheckCircle2 size={23} />
                      Plan guardado
                    </div>
                  </div>

                  <div className="plan-money-grid">
                    <div>
                      <WalletCards size={21} />

                      <span>
                        Presupuesto máximo
                      </span>

                      <strong>
                        {money(
                          plan.client_budget_cents,
                        )}
                      </strong>
                    </div>

                    <div>
                      <CircleDollarSign size={21} />

                      <span>
                        Estimación R00
                      </span>

                      <strong>
                        {money(
                          plan.planned_budget_cents,
                        )}
                      </strong>
                    </div>

                    <div>
                      <ShieldCheck size={21} />

                      <span>
                        Sin comprometer
                      </span>

                      <strong>
                        {money(
                          plan.client_budget_cents -
                            plan.planned_budget_cents,
                        )}
                      </strong>
                    </div>

                    <div>
                      <Boxes size={21} />

                      <span>
                        Tareas creadas
                      </span>

                      <strong>
                        {plan.tasks.length}
                      </strong>
                    </div>
                  </div>

                  <article className="strategy-card">
                    <div>
                      <Network size={22} />
                    </div>

                    <section>
                      <span>
                        ESTRATEGIA DE R00
                      </span>

                      <p>
                        {plan.strategy}
                      </p>
                    </section>
                  </article>

                  <div className="plan-section-heading">
                    <div>
                      <span className="panel-kicker">
                        DESCOMPOSICIÓN
                      </span>

                      <h3>
                        Tareas creadas autónomamente
                      </h3>
                    </div>

                    <span>
                      {plan.tasks.length}{' '}
                      tareas
                    </span>
                  </div>

                  <div className="task-list">
                    {plan.tasks.map(
                      (item, index) => {
                        const task =
                          item.task

                        return (
                          <article
                            className="task-card"
                            key={task.id}
                          >
                            <div className="task-number">
                              {String(
                                index + 1,
                              ).padStart(2, '0')}
                            </div>

                            <div className="task-content">
                              <div className="task-heading">
                                <div>
                                  <h3>
                                    {
                                      task.title
                                    }
                                  </h3>

                                  <p>
                                    {
                                      task.description
                                    }
                                  </p>
                                </div>

                                <span className="status-badge planned">
                                  {statusLabel(
                                    task.status,
                                  )}
                                </span>
                              </div>

                              <div className="task-metrics">
                                <div>
                                  <CircleDollarSign
                                    size={17}
                                  />

                                  <span>
                                    Presupuesto
                                  </span>

                                  <strong>
                                    {money(
                                      task
                                        .max_budget_cents,
                                    )}
                                  </strong>
                                </div>

                                <div>
                                  <Gauge
                                    size={17}
                                  />

                                  <span>
                                    Complejidad
                                  </span>

                                  <strong>
                                    {
                                      task.complexity
                                    }
                                    /100
                                  </strong>
                                </div>
                              </div>

                              <div className="task-columns">
                                <div>
                                  <h4>
                                    Habilidades
                                    requeridas
                                  </h4>

                                  <div className="skills">
                                    {task.required_skills.map(
                                      (
                                        skill,
                                        skillIndex,
                                      ) => (
                                        <span
                                          key={
                                            skill.id ??
                                            skillIndex
                                          }
                                        >
                                          {
                                            skill.skill_name
                                          }{' '}
                                          ·{' '}
                                          {
                                            skill.minimum_level
                                          }+
                                        </span>
                                      ),
                                    )}
                                  </div>
                                </div>

                                <div>
                                  <h4>
                                    Criterios de
                                    aceptación
                                  </h4>

                                  <div className="criteria-list">
                                    {item.acceptance_criteria.map(
                                      (
                                        criterion,
                                        criterionIndex,
                                      ) => (
                                        <div
                                          key={
                                            criterionIndex
                                          }
                                        >
                                          <CheckCircle2
                                            size={16}
                                          />

                                          <span>
                                            {
                                              criterion
                                            }
                                          </span>
                                        </div>
                                      ),
                                    )}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </article>
                        )
                      },
                    )}
                  </div>

                  <article className="market-gap-card">
                    <div className="market-gap-icon">
                      <Activity size={22} />
                    </div>

                    <div>
                      <span className="panel-kicker">
                        CAPACIDADES FALTANTES
                      </span>

                      <h3>
                        Capacidades faltantes
                      </h3>

                      {plan.market_gaps.length >
                      0 ? (
                        <div className="gap-tags">
                          {plan.market_gaps.map(
                            (
                              gap,
                              index,
                            ) => (
                              <span
                                key={index}
                              >
                                {gap}
                              </span>
                            ),
                          )}
                        </div>
                      ) : (
                        <p>
                          El mercado actual cubre
                          todas las habilidades
                          necesarias.
                        </p>
                      )}
                    </div>
                  </article>

                  <div className="next-phase-card">
                    <div>
                      <Bot size={29} />
                    </div>

                    <section>
                      <span>
                        SIGUIENTE FASE
                      </span>

                      <h3>
                        Mercado autónomo de ofertas
                      </h3>

                      <p>
                        Los Repliker analizarán estas
                        tareas y decidiran por si mismos
                        si ofertar, cuánto cobrar,
                        cuánto tardarán o si prefieren
                        rechazarlas.
                      </p>
                    </section>

                    <ChevronRight size={22} />
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
