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

import type {
  CSSProperties,
} from 'react'

import ReplikerHumano from './ReplikerHumano'

import type {
  ReplikerAppearance,
} from './ReplikerHumano'

import '../styles/BosqueRepliker.css'


interface AgenteBosque {
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


interface ProyectoBosque {
  id: number
  title: string
  status: string

  task_count: number
  agents_involved: number
}


interface EventoBosque {
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


interface MensajeBosque {
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
  agents: AgenteBosque[]
  projects: ProyectoBosque[]
  events: EventoBosque[]
  messages: MensajeBosque[]

  selectedProjectId:
    number | 'all'

  onSelectProject:
    (
      value:
        number | 'all',
    ) => void

  onSelectAgent:
    (
      agent: AgenteBosque,
    ) => void

  specialtyLabel:
    (
      value: string,
    ) => string
}


type EstadoHabitante =
  | 'incorporando'
  | 'mision'
  | 'colaborando'
  | 'revision'
  | 'completado'
  | 'disponible'
  | 'espera'
  | 'reposo'


interface PosicionBosque {
  x: number
  y: number
}


function normalizar(
  value: string,
) {
  return (
    value
      .trim()
      .toLowerCase()
  )
}


function tiempoEvento(
  value: string,
) {
  const time =
    new Date(value).getTime()

  return Number.isNaN(time)
    ? 0
    : time
}


function esEventoReciente(
  value: string,
) {
  const time =
    tiempoEvento(value)

  if (time === 0) {
    return false
  }

  return (
    Date.now() - time
    < 90_000
  )
}


function tiempoRelativo(
  value: string,
) {
  const time =
    tiempoEvento(value)

  if (time === 0) {
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


function estaTrabajando(
  agent: AgenteBosque,
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
      normalizar(
        agent.status,
      ),
    )
  )
}


function estaDisponible(
  agent: AgenteBosque,
) {
  return (
    agent.is_active
    &&
    agent.current_project_id
      === null
    &&
    !estaTrabajando(agent)
    &&
    [
      '',
      'available',
      'ready',
    ].includes(
      normalizar(
        agent.status,
      ),
    )
  )
}


function etiquetaProyecto(
  value: string,
) {
  const labels:
    Record<string, string> = {
      draft:
        'Borrador',

      planned:
        'Planificado',

      planning:
        'En planificación',

      open:
        'Abierto',

      market:
        'Buscando especialistas',

      contracted:
        'Contratado',

      executing:
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
    }

  return (
    labels[
      normalizar(value)
    ]
    ??
    'En proceso'
  )
}


function etiquetaEvento(
  event: EventoBosque,
) {
  const labels:
    Record<string, string> = {
      task_started:
        'Comenzó una tarea',

      work_started:
        'Comenzó a trabajar',

      task_executing:
        'Ejecutando una tarea',

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

      final_review_started:
        'Revisión final iniciada',

      final_review_completed:
        'Revisión final completada',
    }

  return (
    labels[
      normalizar(
        event.event_type,
      )
    ]
    ??
    'Actividad registrada'
  )
}


function posicionEnClaro(
  index: number,
  total: number,
): PosicionBosque {
  if (total <= 1) {
    return {
      x: 50,
      y: 22,
    }
  }

  const angle =
    (
      -Math.PI / 2
      +
      (
        Math.PI
        * 2
        * index
      )
      / total
    )

  const useOuterRing =
    total > 8
    &&
    index % 2 === 1

  const radiusX =
    useOuterRing
      ? 41
      : total > 5
        ? 36
        : 32

  const radiusY =
    useOuterRing
      ? 35
      : total > 5
        ? 31
        : 27

  return {
    x:
      50
      +
      Math.cos(angle)
      * radiusX,

    y:
      50
      +
      Math.sin(angle)
      * radiusY,
  }
}


function claseEstado(
  state: EstadoHabitante,
) {
  return (
    `estado-${state}`
  )
}


function etiquetaEstado(
  state: EstadoHabitante,
) {
  switch (state) {
    case 'incorporando':
      return 'Entrando a misión'

    case 'mision':
      return 'En misión'

    case 'colaborando':
      return 'Colaborando'

    case 'revision':
      return 'En revisión'

    case 'completado':
      return 'Trabajo completado'

    case 'disponible':
      return 'Disponible'

    case 'espera':
      return 'En espera'

    default:
      return 'En reposo'
  }
}


export default function BosqueRepliker({
  agents,
  projects,
  events,
  messages,
  selectedProjectId,
  onSelectProject,
  onSelectAgent,
  specialtyLabel,
}: Props) {
  const eventosOrdenados =
    [...events].sort(
      (first, second) =>
        tiempoEvento(
          second.created_at,
        )
        -
        tiempoEvento(
          first.created_at,
        ),
    )


  const proyectoPorId =
    new Map<
      number,
      ProyectoBosque
    >(
      projects.map(
        (project) => [
          project.id,
          project,
        ],
      ),
    )


  const ultimoEventoAgente =
    new Map<
      number,
      EventoBosque
    >()


  const ultimoEventoProyecto =
    new Map<
      number,
      EventoBosque
    >()


  eventosOrdenados.forEach(
    (event) => {
      if (
        event.repliker_id
          !== null
        &&
        !ultimoEventoAgente.has(
          event.repliker_id,
        )
      ) {
        ultimoEventoAgente.set(
          event.repliker_id,
          event,
        )
      }

      if (
        event.project_id
          !== null
        &&
        !ultimoEventoProyecto.has(
          event.project_id,
        )
      ) {
        ultimoEventoProyecto.set(
          event.project_id,
          event,
        )
      }
    },
  )


  const eventosRecientes =
    eventosOrdenados.filter(
      (event) =>
        esEventoReciente(
          event.created_at,
        ),
    )


  const senalesRecientes =
    eventosOrdenados
      .filter(
        (event) =>
          event.repliker_id
            !== null,
      )
      .slice(
        0,
        6,
      )


  const mensajesPorProyecto =
    new Map<
      number,
      MensajeBosque[]
    >()


  const enlacesVistos =
    new Set<string>()


  ;[...messages]
    .sort(
      (first, second) =>
        tiempoEvento(
          second.created_at,
        )
        -
        tiempoEvento(
          first.created_at,
        ),
    )
    .forEach(
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
          enlacesVistos.has(key)
        ) {
          return
        }

        enlacesVistos.add(key)

        const current =
          mensajesPorProyecto.get(
            message.project_id,
          )
          ?? []

        if (
          current.length >= 5
        ) {
          return
        }

        mensajesPorProyecto.set(
          message.project_id,
          [
            ...current,
            message,
          ],
        )
      },
    )


  function nombreAgente(
    replikerId:
      number | null,
  ) {
    if (
      replikerId === null
    ) {
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


  function estadoHabitante(
    agent: AgenteBosque,
  ): EstadoHabitante {
    if (!agent.is_active) {
      return 'reposo'
    }

    const project =
      agent.current_project_id
        === null
        ? undefined
        : proyectoPorId.get(
            agent.current_project_id,
          )

    const projectStatus =
      project
        ? normalizar(
            project.status,
          )
        : ''

    if (
      projectStatus ===
        'completed'
    ) {
      return 'completado'
    }

    if (
      [
        'qa',
        'awaiting_final_review',
        'correcting',
      ].includes(
        projectStatus,
      )
    ) {
      return 'revision'
    }

    const event =
      ultimoEventoAgente.get(
        agent.id,
      )

    if (
      event
      &&
      esEventoReciente(
        event.created_at,
      )
    ) {
      const eventType =
        normalizar(
          event.event_type,
        )

      if (
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
      ) {
        return 'incorporando'
      }

      if (
        eventType.includes(
          'completed',
        )
        &&
        agent.current_project_id
          === null
      ) {
        return 'completado'
      }
    }

    if (
      agent.current_project_id
        !== null
    ) {
      const teammates =
        agents.filter(
          (other) =>
            other.current_project_id
            === agent.current_project_id,
        ).length

      return (
        teammates > 1
          ? 'colaborando'
          : 'mision'
      )
    }

    if (
      estaDisponible(agent)
    ) {
      return 'disponible'
    }

    return 'espera'
  }


  const disponibles =
    agents.filter(
      (agent) =>
        estadoHabitante(agent)
        === 'disponible',
    )


  const enEspera =
    agents.filter(
      (agent) =>
        estadoHabitante(agent)
        === 'espera',
    )


  const enReposo =
    agents.filter(
      (agent) =>
        estadoHabitante(agent)
        === 'reposo',
    )


  const proyectosConocidos =
    new Set(
      projects.map(
        (project) =>
          project.id,
      ),
    )


  const enTransito =
    agents.filter(
      (agent) =>
        agent.is_active
        &&
        agent.current_project_id
          !== null
        &&
        !proyectosConocidos.has(
          agent.current_project_id,
        ),
    )


  const trabajando =
    agents.filter(
      (agent) => {
        const state =
          estadoHabitante(agent)

        return (
          state === 'mision'
          ||
          state === 'colaborando'
          ||
          state === 'incorporando'
          ||
          state === 'revision'
        )
      },
    )


  const colaborando =
    agents.filter(
      (agent) =>
        estadoHabitante(agent)
        === 'colaborando',
    )


  const revisando =
    agents.filter(
      (agent) =>
        estadoHabitante(agent)
        === 'revision',
    )


  const pulso =
    eventosRecientes.length >= 5
      ? 'intenso'
      : eventosRecientes.length >= 2
        ? 'activo'
        : eventosRecientes.length === 1
          ? 'suave'
          : 'tranquilo'


  function etiquetaPulso() {
    switch (pulso) {
      case 'intenso':
        return 'Actividad intensa'

      case 'activo':
        return 'Actividad sostenida'

      case 'suave':
        return 'Actividad reciente'

      default:
        return 'Bosque tranquilo'
    }
  }


  function renderHabitanteLibre(
    agent: AgenteBosque,
  ) {
    const state =
      estadoHabitante(agent)

    const event =
      ultimoEventoAgente.get(
        agent.id,
      )

    return (
      <button
        type="button"
        key={agent.id}
        className={[
          'bosque-habitante-libre',
          claseEstado(state),
          event
          &&
          esEventoReciente(
            event.created_at,
          )
            ? 'actividad-reciente'
            : '',
        ].join(' ')}
        onClick={() =>
          onSelectAgent(agent)
        }
        aria-label={
          `${agent.name}. ` +
          `${specialtyLabel(agent.specialty)}. ` +
          `${etiquetaEstado(state)}.`
        }
      >
        <span className="bosque-avatar-libre">
          <ReplikerHumano
            appearance={
              agent.appearance
            }
            name={agent.name}
            size="medium"
            active={
              state !== 'reposo'
              &&
              state !== 'espera'
            }
          />
        </span>

        <span className="bosque-habitante-info">
          <strong>
            {agent.name}
          </strong>

          <small>
            {specialtyLabel(
              agent.specialty,
            )}
          </small>

          <em
            className={
              claseEstado(state)
            }
          >
            {etiquetaEstado(
              state,
            )}
          </em>

          {agent.current_task_id
            !== null && (
            <span>
              Tarea #{agent.current_task_id}
            </span>
          )}
        </span>
      </button>
    )
  }


  return (
    <section className="bosque-repliker">
      <header className="bosque-cabecera">
        <div>
          <span className="bosque-kicker">
            <Radio size={14} />

            ECOSISTEMA VIVO
          </span>

          <h2>
            Bosque Repliker
          </h2>

          <p>
            Los Repliker habitan el bosque,
            se reúnen alrededor de proyectos
            reales y cambian de zona según su
            trabajo actual.
          </p>
        </div>

        <div className="bosque-red-activa">
          <span />

          Red activa

          <strong>
            {agents.length}
          </strong>
        </div>
      </header>


      <section
        className={
          `bosque-pulso ${pulso}`
        }
      >
        <div className="bosque-pulso-icono">
          <span />

          <Activity size={17} />
        </div>

        <div>
          <small>
            Pulso del bosque
          </small>

          <strong>
            {etiquetaPulso()}
          </strong>
        </div>

        <div className="bosque-pulso-datos">
          <span>
            {eventosRecientes.length}
            {' '}
            señales recientes
          </span>

          <span>
            {eventosOrdenados[0]
              ? tiempoRelativo(
                  eventosOrdenados[0]
                    .created_at,
                )
              : 'Sin actividad reciente'}
          </span>
        </div>
      </section>


      <section className="bosque-resumen">
        <article>
          <Activity size={18} />

          <div>
            <strong>
              {trabajando.length}
            </strong>

            <span>
              En misión
            </span>
          </div>
        </article>

        <article>
          <Network size={18} />

          <div>
            <strong>
              {colaborando.length}
            </strong>

            <span>
              Colaborando
            </span>
          </div>
        </article>

        <article>
          <Route size={18} />

          <div>
            <strong>
              {revisando.length}
            </strong>

            <span>
              En revisión
            </span>
          </div>
        </article>

        <article>
          <Sparkles size={18} />

          <div>
            <strong>
              {disponibles.length}
            </strong>

            <span>
              Disponibles
            </span>
          </div>
        </article>
      </section>


      <section className="bosque-senales">
        <div className="bosque-senales-titulo">
          <Radio size={14} />

          <span>
            Señales recientes
          </span>
        </div>

        {senalesRecientes.length === 0 ? (
          <div className="bosque-senales-vacio">
            Esperando nueva actividad
          </div>
        ) : (
          <div className="bosque-senales-lista">
            {senalesRecientes.map(
              (event) => (
                <article
                  key={event.id}
                  className={
                    esEventoReciente(
                      event.created_at,
                    )
                      ? 'reciente'
                      : ''
                  }
                >
                  <span />

                  <div>
                    <strong>
                      {nombreAgente(
                        event.repliker_id,
                      )}
                    </strong>

                    <small>
                      {etiquetaEvento(
                        event,
                      )}
                    </small>
                  </div>

                  <time>
                    {tiempoRelativo(
                      event.created_at,
                    )}
                  </time>
                </article>
              ),
            )}
          </div>
        )}
      </section>


      <div className="bosque-mundo">
        <div
          className="bosque-luz luz-uno"
          aria-hidden="true"
        />

        <div
          className="bosque-luz luz-dos"
          aria-hidden="true"
        />

        <div
          className="bosque-luz luz-tres"
          aria-hidden="true"
        />

        <div
          className="bosque-montanas"
          aria-hidden="true"
        />

        <div
          className="bosque-suelo"
          aria-hidden="true"
        />

        <div
          className="bosque-sendero"
          aria-hidden="true"
        />


        <div
          className="bosque-arbol arbol-uno"
          aria-hidden="true"
        >
          <i />
          <span />
        </div>

        <div
          className="bosque-arbol arbol-dos"
          aria-hidden="true"
        >
          <i />
          <span />
        </div>

        <div
          className="bosque-arbol arbol-tres"
          aria-hidden="true"
        >
          <i />
          <span />
        </div>

        <div
          className="bosque-arbol arbol-cuatro"
          aria-hidden="true"
        >
          <i />
          <span />
        </div>

        <div
          className="bosque-arbol arbol-cinco"
          aria-hidden="true"
        >
          <i />
          <span />
        </div>

        <div
          className="bosque-arbol arbol-seis"
          aria-hidden="true"
        >
          <i />
          <span />
        </div>


        <section className="bosque-zona-proyectos">
          <header className="bosque-zona-cabecera">
            <div>
              <BriefcaseBusiness
                size={18}
              />

              <div>
                <strong>
                  Claros de proyectos
                </strong>

                <span>
                  Cada claro representa un
                  proyecto real.
                </span>
              </div>
            </div>

            <b>
              {projects.length}
            </b>
          </header>


          {projects.length === 0 ? (
            <div className="bosque-claro-vacio">
              <BriefcaseBusiness
                size={27}
              />

              <strong>
                El bosque está esperando
                su primera misión
              </strong>

              <span>
                Cuando exista un proyecto,
                aquí aparecerá su claro y
                los Repliker asignados.
              </span>
            </div>
          ) : (
            <div className="bosque-proyectos">
              {projects.map(
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

                  const faded =
                    selectedProjectId
                      !== 'all'
                    &&
                    !selected

                  const projectEvent =
                    ultimoEventoProyecto.get(
                      project.id,
                    )

                  const projectRecent =
                    Boolean(
                      projectEvent
                      &&
                      esEventoReciente(
                        projectEvent
                          .created_at,
                      ),
                    )

                  const projectMessages =
                    mensajesPorProyecto.get(
                      project.id,
                    )
                    ?? []

                  const positions =
                    members.map(
                      (_, index) =>
                        posicionEnClaro(
                          index,
                          members.length,
                        ),
                    )

                  const positionById =
                    new Map<
                      number,
                      PosicionBosque
                    >(
                      members.map(
                        (member, index) => [
                          member.id,
                          positions[index],
                        ],
                      ),
                    )

                  return (
                    <article
                      key={project.id}
                      className={[
                        'bosque-claro-proyecto',
                        selected
                          ? 'seleccionado'
                          : '',
                        faded
                          ? 'atenuado'
                          : '',
                        projectRecent
                          ? 'actividad-reciente'
                          : '',
                      ].join(' ')}
                    >
                      <div
                        className="bosque-claro-brillo"
                        aria-hidden="true"
                      />

                      <div
                        className="bosque-claro-hojas"
                        aria-hidden="true"
                      />


                      <svg
                        className="bosque-conexiones"
                        viewBox="0 0 100 100"
                        preserveAspectRatio="none"
                        aria-hidden="true"
                      >
                        {positions.map(
                          (
                            position,
                            index,
                          ) => (
                            <line
                              key={
                                `asignacion-${members[index].id}`
                              }
                              className="conexion-asignacion"
                              x1="50"
                              y1="50"
                              x2={position.x}
                              y2={position.y}
                            />
                          ),
                        )}

                        {projectMessages.map(
                          (message) => {
                            const start =
                              message
                                .sender_repliker_id
                                === null
                                ? undefined
                                : positionById.get(
                                    message
                                      .sender_repliker_id,
                                  )

                            const end =
                              message
                                .receiver_repliker_id
                                === null
                                ? undefined
                                : positionById.get(
                                    message
                                      .receiver_repliker_id,
                                  )

                            if (
                              !start
                              ||
                              !end
                            ) {
                              return null
                            }

                            return (
                              <line
                                key={
                                  `mensaje-${message.id}`
                                }
                                className={
                                  esEventoReciente(
                                    message.created_at,
                                  )
                                    ? 'conexion-mensaje reciente'
                                    : 'conexion-mensaje'
                                }
                                x1={start.x}
                                y1={start.y}
                                x2={end.x}
                                y2={end.y}
                              />
                            )
                          },
                        )}
                      </svg>


                      <button
                        type="button"
                        className="bosque-nucleo-proyecto"
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
                                `Quitar selección de ${project.title}`
                              )
                            : (
                                `Seleccionar ${project.title}`
                              )
                        }
                      >
                        <span className="bosque-nucleo-anillo" />

                        <span className="bosque-nucleo-icono">
                          <BriefcaseBusiness
                            size={20}
                          />
                        </span>

                        <small>
                          Proyecto #{project.id}
                        </small>

                        <strong>
                          {project.title}
                        </strong>

                        <em>
                          {etiquetaProyecto(
                            project.status,
                          )}
                        </em>

                        {projectRecent && (
                          <span className="bosque-ahora">
                            <Radio
                              size={10}
                            />

                            Actividad ahora
                          </span>
                        )}
                      </button>


                      <div className="bosque-miembros-proyecto">
                        {members.length === 0 ? (
                          <div className="bosque-sin-miembros">
                            <Users
                              size={19}
                            />

                            <span>
                              Esperando asignaciones
                            </span>
                          </div>
                        ) : (
                          members.map(
                            (
                              agent,
                              index,
                            ) => {
                              const position =
                                positions[index]

                              const state =
                                estadoHabitante(
                                  agent,
                                )

                              const event =
                                ultimoEventoAgente.get(
                                  agent.id,
                                )

                              const style = {
                                left:
                                  `${position.x}%`,

                                top:
                                  `${position.y}%`,

                                '--habitante-retardo':
                                  `${index * .08}s`,
                              } as CSSProperties

                              return (
                                <button
                                  type="button"
                                  key={agent.id}
                                  className={[
                                    'bosque-habitante',
                                    claseEstado(
                                      state,
                                    ),
                                    event
                                    &&
                                    esEventoReciente(
                                      event.created_at,
                                    )
                                      ? 'actividad-reciente'
                                      : '',
                                  ].join(' ')}
                                  style={style}
                                  onClick={() =>
                                    onSelectAgent(
                                      agent,
                                    )
                                  }
                                  aria-label={
                                    `${agent.name}. ` +
                                    `${specialtyLabel(agent.specialty)}. ` +
                                    `${etiquetaEstado(state)}.`
                                  }
                                >
                                  <span className="bosque-habitante-avatar">
                                    <ReplikerHumano
                                      appearance={
                                        agent
                                          .appearance
                                      }
                                      name={
                                        agent.name
                                      }
                                      size="medium"
                                      active={
                                        state !==
                                          'reposo'
                                        &&
                                        state !==
                                          'espera'
                                      }
                                    />
                                  </span>

                                  <span className="bosque-habitante-etiqueta">
                                    <strong>
                                      {agent.name}
                                    </strong>

                                    <small>
                                      {specialtyLabel(
                                        agent
                                          .specialty,
                                      )}
                                    </small>

                                    <em>
                                      {etiquetaEstado(
                                        state,
                                      )}
                                    </em>

                                    {agent
                                      .current_task_id
                                      !== null && (
                                      <span>
                                        Tarea #
                                        {
                                          agent
                                            .current_task_id
                                        }
                                      </span>
                                    )}
                                  </span>
                                </button>
                              )
                            },
                          )
                        )}
                      </div>


                      {projectMessages.length >
                        0 && (
                        <div className="bosque-comunicaciones">
                          <div className="bosque-comunicaciones-titulo">
                            <MessageCircle
                              size={12}
                            />

                            Comunicación real
                          </div>

                          <div>
                            {projectMessages.map(
                              (message) => (
                                <span
                                  key={
                                    message.id
                                  }
                                  className={
                                    esEventoReciente(
                                      message.created_at,
                                    )
                                      ? 'reciente'
                                      : ''
                                  }
                                >
                                  <strong>
                                    {nombreAgente(
                                      message
                                        .sender_repliker_id,
                                    )}
                                  </strong>

                                  <ArrowRight
                                    size={10}
                                  />

                                  <strong>
                                    {nombreAgente(
                                      message
                                        .receiver_repliker_id,
                                    )}
                                  </strong>
                                </span>
                              ),
                            )}
                          </div>
                        </div>
                      )}


                      <footer className="bosque-proyecto-pie">
                        <span>
                          {
                            project
                              .task_count
                          }
                          {' '}
                          tareas
                        </span>

                        <span>
                          {
                            project
                              .agents_involved
                          }
                          {' '}
                          participantes
                        </span>
                      </footer>
                    </article>
                  )
                },
              )}
            </div>
          )}
        </section>


        <section className="bosque-zona-libre">
          <header className="bosque-zona-cabecera">
            <div>
              <Sparkles
                size={18}
              />

              <div>
                <strong>
                  Claro disponible
                </strong>

                <span>
                  Repliker preparados para
                  una nueva misión.
                </span>
              </div>
            </div>

            <b>
              {disponibles.length}
            </b>
          </header>


          <div className="bosque-pradera">
            {disponibles.length ===
              0 ? (
              <div className="bosque-claro-vacio compacto">
                <Activity
                  size={23}
                />

                <strong>
                  Sin Repliker disponibles
                </strong>

                <span>
                  Los Repliker libres
                  aparecerán aquí.
                </span>
              </div>
            ) : (
              <div className="bosque-habitantes-libres">
                {disponibles.map(
                  renderHabitanteLibre,
                )}
              </div>
            )}
          </div>


          {enEspera.length > 0 && (
            <div className="bosque-subzona espera">
              <div className="bosque-subzona-titulo">
                <Clock3
                  size={14}
                />

                <strong>
                  En espera
                </strong>

                <span>
                  {enEspera.length}
                </span>
              </div>

              <div className="bosque-subzona-personas">
                {enEspera.map(
                  renderHabitanteLibre,
                )}
              </div>
            </div>
          )}


          {enTransito.length > 0 && (
            <div className="bosque-subzona transito">
              <div className="bosque-subzona-titulo">
                <Route
                  size={14}
                />

                <strong>
                  En tránsito
                </strong>

                <span>
                  {enTransito.length}
                </span>
              </div>

              <div className="bosque-subzona-personas">
                {enTransito.map(
                  renderHabitanteLibre,
                )}
              </div>
            </div>
          )}


          {enReposo.length > 0 && (
            <div className="bosque-subzona reposo">
              <div className="bosque-subzona-titulo">
                <Clock3
                  size={14}
                />

                <strong>
                  En reposo
                </strong>

                <span>
                  {enReposo.length}
                </span>
              </div>

              <div className="bosque-subzona-personas">
                {enReposo.map(
                  renderHabitanteLibre,
                )}
              </div>
            </div>
          )}
        </section>
      </div>


      <footer className="bosque-leyenda">
        <span>
          <i className="incorporando" />
          Entrando a misión
        </span>

        <span>
          <i className="mision" />
          En misión
        </span>

        <span>
          <i className="colaborando" />
          Colaborando
        </span>

        <span>
          <i className="revision" />
          En revisión
        </span>

        <span>
          <i className="disponible" />
          Disponible
        </span>

        <span>
          <i className="espera" />
          En espera
        </span>
      </footer>
    </section>
  )
}
