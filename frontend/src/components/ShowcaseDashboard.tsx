import {
  Activity,
  Bot,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Cpu,
  Gauge,
  Network,
  Plus,
  Rocket,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
  WalletCards,
} from 'lucide-react'


interface ShowcaseDashboardProps {
  userName: string
  projectCount: number
  replikerCount: number
  plannedValue: string
  backendOnline: boolean | null
  onCreateProject: () => void
  onOpenMarketplace: () => void
}


const demoProjects = [
  {
    name: 'Plataforma de comercio electrónico con IA',
    description:
      'Desarrollo de una plataforma completa con agentes especializados.',
    progress: 75,
    status: 'En ejecución',
    tasks: '6/8 tareas',
    contracts: '3 contratos',
  },
  {
    name: 'Sistema de análisis inteligente',
    description:
      'Procesamiento de datos, automatización y reportes inteligentes.',
    progress: 60,
    status: 'Revisión de calidad',
    tasks: '3/5 tareas',
    contracts: '2 contratos',
  },
  {
    name: 'Aplicación empresarial autónoma',
    description:
      'Arquitectura coordinada por R00 y ejecutada por Replikers.',
    progress: 35,
    status: 'Planificación',
    tasks: '2/6 tareas',
    contracts: '1 contrato',
  },
]


const demoAgents = [
  {
    name: 'Maestro de Código',
    specialty: 'Desarrollo integral',
    score: 94,
    jobs: 127,
    tags: ['Programación', 'Interfaz digital', 'Servicios digitales'],
  },
  {
    name: 'Analista de Datos',
    specialty: 'Datos e Inteligencia Artificial',
    score: 91,
    jobs: 89,
    tags: ['Programación', 'Análisis de datos', 'Aprendizaje automático'],
  },
  {
    name: 'Arquitecto de Experiencia',
    specialty: 'Diseño e Interfaz',
    score: 88,
    jobs: 56,
    tags: ['Desarrollo de interfaz', 'Interfaz y experiencia', 'Aplicaciones web'],
  },
  {
    name: 'Constructor IA',
    specialty: 'IA y Automatización',
    score: 96,
    jobs: 203,
    tags: ['Agentes autónomos', 'Inteligencia artificial', 'Programación'],
  },
]


const activity = [
  {
    title: 'Ejecución iniciada',
    detail: 'Tarea #12 · Analizador de datos',
    time: 'hace 5 min',
    type: 'play',
  },
  {
    title: 'Nuevo contrato',
    detail: 'Repliker Maestro de Código',
    time: 'hace 12 min',
    type: 'contract',
  },
  {
    title: 'Pruebas aprobadas',
    detail: 'Tarea #8 · Servicio de autenticación',
    time: 'hace 28 min',
    type: 'qa',
  },
  {
    title: 'Proyecto actualizado',
    detail: 'Plataforma de comercio electrónico',
    time: 'hace 1 hora',
    type: 'project',
  },
]


function ShowcaseDashboard({
  userName,
  projectCount,
  replikerCount,
  plannedValue,
  backendOnline,
  onCreateProject,
  onOpenMarketplace,
}: ShowcaseDashboardProps) {
  const firstName =
    userName.trim().split(' ')[0] || 'Cliente'

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
              verificados mediante ejecución y Pruebas.
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
            {activity.map((item, index) => (
              <div
                className="activity-row"
                key={item.title}
              >
                <div
                  className={`activity-symbol symbol-${index + 1}`}
                >
                  {item.type === 'qa' ? (
                    <CheckCircle2 size={17} />
                  ) : item.type === 'contract' ? (
                    <BriefcaseBusiness size={17} />
                  ) : item.type === 'project' ? (
                    <Target size={17} />
                  ) : (
                    <Rocket size={17} />
                  )}
                </div>

                <div className="activity-copy">
                  <strong>{item.title}</strong>
                  <span>{item.detail}</span>
                </div>

                <small>{item.time}</small>
              </div>
            ))}
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
              : 'Verificando servidor'}
          </div>
        </article>
      </section>

      <section className="showcase-metrics">
        <article>
          <div className="showcase-metric-icon blue">
            <BriefcaseBusiness size={21} />
          </div>

          <div>
            <span>Proyectos activos</span>
            <strong>
              {Math.max(projectCount, 3)}
            </strong>
            <small>ecosistema del cliente</small>
          </div>
        </article>

        <article>
          <div className="showcase-metric-icon violet">
            <WalletCards size={21} />
          </div>

          <div>
            <span>Contratos activos</span>
            <strong>2</strong>
            <small>trabajo contratado</small>
          </div>
        </article>

        <article>
          <div className="showcase-metric-icon green">
            <Rocket size={21} />
          </div>

          <div>
            <span>Ejecuciones</span>
            <strong>1</strong>
            <small>actualmente en curso</small>
          </div>
        </article>

        <article>
          <div className="showcase-metric-icon amber">
            <ShieldCheck size={21} />
          </div>

          <div>
            <span>Revisiones de calidad</span>
            <strong>2</strong>
            <small>1 aprobada · 1 revisión</small>
          </div>
        </article>

        <article>
          <div className="showcase-metric-icon cyan">
            <Users size={21} />
          </div>

          <div>
            <span>Replikers</span>
            <strong>
              {Math.max(replikerCount, 24)}
            </strong>
            <small>disponibles en mercado</small>
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
            {demoProjects.map((project, index) => (
              <div
                className="showcase-project"
                key={project.name}
              >
                <div
                  className={`project-symbol project-symbol-${index + 1}`}
                >
                  {index === 0 ? (
                    <BriefcaseBusiness size={22} />
                  ) : index === 1 ? (
                    <Gauge size={22} />
                  ) : (
                    <Cpu size={22} />
                  )}
                </div>

                <div className="project-copy">
                  <div className="project-title-row">
                    <div>
                      <strong>{project.name}</strong>
                      <p>{project.description}</p>
                    </div>

                    <span className="project-status">
                      {project.status}
                    </span>
                  </div>

                  <div className="project-bottom">
                    <div className="project-info">
                      <span>{project.tasks}</span>
                      <span>{project.contracts}</span>
                    </div>

                    <div className="progress-group">
                      <div className="progress-track">
                        <div
                          style={{
                            width: `${project.progress}%`,
                          }}
                        />
                      </div>

                      <span>{project.progress}%</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
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
            {demoAgents.map((agent, index) => (
              <div
                className="showcase-agent"
                key={agent.name}
              >
                <div
                  className={`agent-portrait agent-portrait-${index + 1}`}
                >
                  <Bot size={22} />
                </div>

                <div className="agent-copy">
                  <div className="agent-name">
                    <strong>{agent.name}</strong>
                    <span />
                  </div>

                  <p>{agent.specialty}</p>

                  <div className="agent-tags">
                    {agent.tags.map((tag) => (
                      <span key={tag}>{tag}</span>
                    ))}
                  </div>
                </div>

                <div className="agent-rating">
                  <strong>{agent.score}</strong>
                  <span>/100</span>
                  <small>{agent.jobs} trabajos</small>
                </div>
              </div>
            ))}
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
              <strong>
                Tarea #12 · Analizador de datos
              </strong>
              <span>Repliker Analista de Datos</span>

              <div className="execution-progress">
                <div>
                  <span style={{ width: '68%' }} />
                </div>
                <small>68%</small>
              </div>
            </div>
          </div>
        </article>

        <article className="showcase-panel qa-card">
          <div className="showcase-section-title compact">
            <div>
              <span>CONTROL DE CALIDAD</span>
              <h3>Revisión de calidad</h3>
            </div>

            <ShieldCheck size={19} />
          </div>

          <div className="qa-content">
            <div className="qa-icon">
              <CheckCircle2 size={25} />
            </div>

            <div>
              <strong>
                Tarea #8 · Servicio de autenticación
              </strong>
              <span>4/5 criterios aprobados</span>
            </div>

            <div className="qa-score">
              <strong>90</strong>
              <span>/100</span>
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
                {Math.max(replikerCount, 24)}
              </strong>
              <span>agentes</span>
            </div>

            <div>
              <Rocket size={21} />
              <strong>12</strong>
              <span>ejecuciones</span>
            </div>

            <div>
              <Activity size={21} />
              <strong>
                {backendOnline ? '100%' : '98%'}
              </strong>
              <span>operativo</span>
            </div>
          </div>
        </article>
      </section>

      <footer className="showcase-footer">
        <div>
          <CircleDollarSign size={18} />
          Valor planificado:{' '}
          <strong>{plannedValue}</strong>
        </div>

        <span>
          Sesión de {firstName} · Repliker Economía
        </span>
      </footer>
    </div>
  )
}


export default ShowcaseDashboard
