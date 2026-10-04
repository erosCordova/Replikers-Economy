import {
  BookOpen,
  Bot,
  BrainCircuit,
  CirclePlus,
  Code2,
  Globe2,
  EyeOff,
  Plus,
  RefreshCw,
  Save,
  ShieldCheck,
  Trash2,
  Wrench,
} from 'lucide-react'

import {
  useEffect,
  useMemo,
  useState,
} from 'react'

import { api } from '../api'

import '../styles/ReplikerStudio.css'


interface ReplikerSkill {
  id?: number
  name: string
  level: number
}


interface OwnedRepliker {
  id: number
  owner_id: number

  name: string
  specialty: string
  description: string

  base_price_credits: number

  is_system: boolean
  is_published: boolean
  published_at: string | null

  skills: ReplikerSkill[]
}


interface StudioTool {
  name: string
  label: string
  pack: string
  description: string
  risk: string
  permission_level: string
}


interface KnowledgeItem {
  id?: number
  title: string
  content: string
  enabled: boolean
}


interface RuleItem {
  id?: number
  title: string
  instruction: string
  priority: number
  enabled: boolean
}


interface ReplikerStudio {
  repliker_id: number
  owner_id: number

  name: string
  specialty: string
  description: string

  base_price_credits: number

  purpose: string
  personality: string
  communication_style: string
  instructions: string

  config_version: number

  skills: ReplikerSkill[]
  knowledge: KnowledgeItem[]
  rules: RuleItem[]

  tools: StudioTool[]

  explicit_tool_configuration: boolean
}


interface DeveloperModule {
  repliker_id: number

  enabled: boolean

  language: string

  filename: string

  entrypoint: string

  source_code: string

  checksum: string

  version: number
}


interface StudioDraft {
  name: string
  specialty: string
  description: string

  base_price_credits: number

  purpose: string
  personality: string
  communication_style: string
  instructions: string

  config_version: number

  skills: ReplikerSkill[]
  knowledge: KnowledgeItem[]
  rules: RuleItem[]

  tool_names: string[]
}


interface NewReplikerDraft {
  name: string
  specialty: string
  description: string
  base_price_credits: number
}


const specialtyOptions = [
  {
    value: 'Generalist',
    label: 'Generalista',
  },
  {
    value: 'Product / Requirements',
    label: 'Producto y Requisitos',
  },
  {
    value: 'Software Architect',
    label: 'Arquitecto de Software',
  },
  {
    value: 'UX Research',
    label: 'Investigación de Experiencia de Usuario',
  },
  {
    value: 'UI Designer',
    label: 'Diseñador de Interfaz',
  },
  {
    value: 'Frontend Developer',
    label: 'Desarrollador de Interfaz',
  },
  {
    value: 'Backend Developer',
    label: 'Desarrollador de Servidor',
  },
  {
    value: 'Database Engineer',
    label: 'Ingeniero de Base de Datos',
  },
  {
    value: 'Integration Specialist',
    label: 'Especialista en Integraciones',
  },
  {
    value: 'Security Engineer',
    label: 'Ingeniero de Seguridad',
  },
  {
    value: 'QA Engineer',
    label: 'Ingeniero de Pruebas',
  },
  {
    value: 'DevOps Engineer',
    label: 'Ingeniero de Operaciones y Despliegue',
  },
  {
    value: 'Accessibility Specialist',
    label: 'Especialista en Accesibilidad',
  },
  {
    value: 'SEO/Performance Specialist',
    label: 'Especialista en Posicionamiento y Rendimiento',
  },
  {
    value: 'Content/Copy Specialist',
    label: 'Especialista en Contenido',
  },
  {
    value: 'Final Reviewer',
    label: 'Revisor Final',
  },
]


const specialtyLabels =
  Object.fromEntries(
    specialtyOptions.map(
      (item) => [
        item.value,
        item.label,
      ],
    ),
  ) as Record<string, string>


function specialtyLabel(
  value: string,
) {
  return (
    specialtyLabels[value]
    ?? 'Especialidad personalizada'
  )
}


function studioToDraft(
  value: ReplikerStudio,
): StudioDraft {
  return {
    name:
      value.name,

    specialty:
      value.specialty,

    description:
      value.description,

    base_price_credits:
      value.base_price_credits,

    purpose:
      value.purpose,

    personality:
      value.personality,

    communication_style:
      value.communication_style,

    instructions:
      value.instructions,

    config_version:
      value.config_version,

    skills:
      value.skills.map(
        (item) => ({
          ...item,
        }),
      ),

    knowledge:
      value.knowledge.map(
        (item) => ({
          ...item,
        }),
      ),

    rules:
      value.rules.map(
        (item) => ({
          ...item,
        }),
      ),

    tool_names:
      value.tools.map(
        (tool) =>
          tool.name,
      ),
  }
}


const emptyNewRepliker:
  NewReplikerDraft = {
    name: '',
    specialty: 'Generalist',
    description: '',
    base_price_credits: 100,
  }


export default function ReplikerStudioPanel() {
  const [
    replikers,
    setReplikers,
  ] = useState<OwnedRepliker[]>([])

  const [
    selectedId,
    setSelectedId,
  ] = useState<number | null>(
    null,
  )

  const [
    draft,
    setDraft,
  ] = useState<StudioDraft | null>(
    null,
  )

  const [
    developer,
    setDeveloper,
  ] = useState<DeveloperModule | null>(
    null,
  )

  const [
    catalog,
    setCatalog,
  ] = useState<StudioTool[]>([])

  const [
    loading,
    setLoading,
  ] = useState(true)

  const [
    loadingStudio,
    setLoadingStudio,
  ] = useState(false)

  const [
    saving,
    setSaving,
  ] = useState(false)

  const [
    publishing,
    setPublishing,
  ] = useState(false)

  const [
    creating,
    setCreating,
  ] = useState(false)

  const [
    showCreate,
    setShowCreate,
  ] = useState(false)

  const [
    notice,
    setNotice,
  ] = useState('')

  const [
    newRepliker,
    setNewRepliker,
  ] = useState<NewReplikerDraft>({
    ...emptyNewRepliker,
  })


  const selectedRepliker =
    useMemo(
      () =>
        replikers.find(
          (item) =>
            item.id === selectedId,
        )
        ?? null,
      [
        replikers,
        selectedId,
      ],
    )


  async function loadBase() {
    setLoading(true)
    setNotice('')

    try {
      const [
        ownedResponse,
        toolResponse,
      ] = await Promise.all([
        api.get<OwnedRepliker[]>(
          '/replikers/mine',
        ),
        api.get<StudioTool[]>(
          '/agentic/tools',
        ),
      ])

      const rows =
        ownedResponse.data

      setReplikers(
        rows,
      )

      setCatalog(
        toolResponse.data,
      )

      setSelectedId(
        (current) => {
          if (
            current !== null
            && rows.some(
              (item) =>
                item.id === current,
            )
          ) {
            return current
          }

          return (
            rows[0]?.id
            ?? null
          )
        },
      )

    } catch {
      setNotice(
        'No fue posible cargar '
        + 'el Taller de Replikers.',
      )

    } finally {
      setLoading(false)
    }
  }


  async function loadStudio(
    replikerId: number,
  ) {
    setLoadingStudio(true)
    setNotice('')

    try {
      const [
        response,
        developerResponse,
      ] = await Promise.all([
        api.get<ReplikerStudio>(
          `/replikers/${replikerId}/studio`,
        ),
        api.get<DeveloperModule>(
          `/replikers/${replikerId}/developer`,
        ),
      ])

      setDraft(
        studioToDraft(
          response.data,
        ),
      )

      setDeveloper(
        developerResponse.data,
      )

    } catch {
      setDraft(null)
      setDeveloper(null)

      setNotice(
        'No fue posible cargar '
        + 'la configuración del Repliker.',
      )

    } finally {
      setLoadingStudio(false)
    }
  }


  useEffect(
    () => {
      const timer =
        window.setTimeout(
          () => {
            void loadBase()
          },
          0,
        )

      return () =>
        window.clearTimeout(
          timer,
        )
    },
    [],
  )


  useEffect(
    () => {
      const timer =
        window.setTimeout(
          () => {
            if (
              selectedId === null
            ) {
              setDraft(null)
              return
            }

            void loadStudio(
              selectedId,
            )
          },
          0,
        )

      return () =>
        window.clearTimeout(
          timer,
        )
    },
    [selectedId],
  )


  async function createRepliker() {
    const name =
      newRepliker.name.trim()

    if (!name) {
      setNotice(
        'Escribe un nombre para el Repliker.',
      )
      return
    }

    setCreating(true)
    setNotice('')

    try {
      const response =
        await api.post<OwnedRepliker>(
          '/replikers',
          {
            name,
            specialty:
              newRepliker.specialty,
            description:
              newRepliker
                .description
                .trim(),
            base_price_credits:
              newRepliker
                .base_price_credits,
            skills: [],
          },
        )

      const created =
        response.data

      setReplikers(
        (current) => [
          created,
          ...current.filter(
            (item) =>
              item.id
              !== created.id,
          ),
        ],
      )

      setNewRepliker({
        ...emptyNewRepliker,
      })

      setShowCreate(false)

      setSelectedId(
        created.id,
      )

      setNotice(
        'Repliker creado correctamente. '
        + 'Ya puedes configurarlo.',
      )

    } catch {
      setNotice(
        'No fue posible crear '
        + 'el Repliker.',
      )

    } finally {
      setCreating(false)
    }
  }


  async function saveStudio() {
    if (
      selectedId === null
      || draft === null
    ) {
      return
    }

    if (
      !draft.name.trim()
    ) {
      setNotice(
        'El Repliker necesita un nombre.',
      )
      return
    }

    if (
      draft.tool_names.length
      === 0
    ) {
      setNotice(
        'Selecciona al menos '
        + 'una herramienta.',
      )
      return
    }

    const skills =
      draft.skills
        .map(
          (item) => ({
            name:
              item.name.trim(),
            level:
              item.level,
          }),
        )
        .filter(
          (item) =>
            item.name.length > 0,
        )

    const knowledge =
      draft.knowledge
        .map(
          (item) => ({
            title:
              item.title.trim(),
            content:
              item.content.trim(),
            enabled:
              item.enabled,
          }),
        )
        .filter(
          (item) =>
            item.title.length > 0
            && item.content.length > 0,
        )

    const rules =
      draft.rules
        .map(
          (item) => ({
            title:
              item.title.trim(),
            instruction:
              item
                .instruction
                .trim(),
            priority:
              item.priority,
            enabled:
              item.enabled,
          }),
        )
        .filter(
          (item) =>
            item.title.length > 0
            && item.instruction.length > 0,
        )

    setSaving(true)
    setNotice('')

    try {
      const response =
        await api.put<ReplikerStudio>(
          `/replikers/${selectedId}/studio`,
          {
            name:
              draft.name.trim(),

            specialty:
              draft.specialty,

            description:
              draft.description.trim(),

            base_price_credits:
              draft.base_price_credits,

            purpose:
              draft.purpose.trim(),

            personality:
              draft.personality.trim(),

            communication_style:
              draft
                .communication_style
                .trim(),

            instructions:
              draft.instructions.trim(),

            skills,
            knowledge,
            rules,

            tool_names:
              draft.tool_names,
          },
        )

      const updated =
        response.data

      if (developer !== null) {
        const developerResponse =
          await api.put<DeveloperModule>(
            `/replikers/${selectedId}/developer`,
            {
              enabled:
                developer.enabled,
              source_code:
                developer.source_code,
            },
          )

        setDeveloper(
          developerResponse.data,
        )
      }

      setDraft(
        studioToDraft(
          updated,
        ),
      )

      setReplikers(
        (current) =>
          current.map(
            (item) =>
              item.id
              === selectedId
                ? {
                    ...item,
                    name:
                      updated.name,
                    specialty:
                      updated.specialty,
                    description:
                      updated.description,
                    base_price_credits:
                      updated
                        .base_price_credits,
                    skills:
                      updated.skills,
                  }
                : item,
          ),
      )

      setNotice(
        'Configuración guardada. '
        + 'El comportamiento del Repliker '
        + 'ya utiliza estos datos.',
      )

    } catch {
      setNotice(
        'No fue posible guardar '
        + 'la configuración.',
      )

    } finally {
      setSaving(false)
    }
  }


  async function updatePublication(
    published: boolean,
  ) {
    if (
      selectedId === null
      || selectedRepliker === null
    ) {
      return
    }

    setPublishing(true)
    setNotice('')

    try {
      const response =
        await api.put<OwnedRepliker>(
          `/replikers/${selectedId}/publication`,
          {
            published,
          },
        )

      const updated =
        response.data

      setReplikers(
        (current) =>
          current.map(
            (item) =>
              item.id === updated.id
                ? updated
                : item,
          ),
      )

      setNotice(
        published
          ? (
              'Repliker publicado. '
              + 'Ya forma parte del ecosistema '
              + 'y puede recibir nuevas oportunidades.'
            )
          : (
              'Repliker retirado del ecosistema. '
              + 'No recibirá nuevas oportunidades, '
              + 'pero conserva sus compromisos actuales.'
            ),
      )

    } catch {
      setNotice(
        published
          ? (
              'No fue posible publicar el Repliker. '
              + 'Guarda una descripción y al menos '
              + 'una habilidad antes de publicarlo.'
            )
          : (
              'No fue posible retirar '
              + 'el Repliker del ecosistema.'
            ),
      )

    } finally {
      setPublishing(false)
    }
  }


  function toggleTool(
    toolName: string,
  ) {
    setDraft(
      (current) => {
        if (!current) {
          return current
        }

        const active =
          current
            .tool_names
            .includes(
              toolName,
            )

        return {
          ...current,

          tool_names:
            active
              ? current
                  .tool_names
                  .filter(
                    (item) =>
                      item
                      !== toolName,
                  )
              : [
                  ...current
                    .tool_names,
                  toolName,
                ],
        }
      },
    )
  }


  return (
    <section
      className="repliker-studio"
    >
      <div
        className="repliker-studio-glow one"
      />

      <div
        className="repliker-studio-glow two"
      />

      <header
        className="repliker-studio-header"
      >
        <div>
          <div
            className="repliker-studio-eyebrow"
          >
            <BrainCircuit
              size={17}
            />

            Taller de Replikers
          </div>

          <h2>
            Diseña cómo trabaja
            tu Repliker
          </h2>

          <p>
            Configura identidad,
            habilidades, conocimiento,
            reglas y herramientas.
            Estos datos modifican
            su comportamiento real.
          </p>
        </div>

        <div
          className="repliker-studio-header-actions"
        >
          <button
            type="button"
            className="studio-button secondary"
            onClick={() =>
              void loadBase()
            }
            disabled={
              loading
            }
          >
            <RefreshCw
              size={16}
              className={
                loading
                  ? 'studio-spin'
                  : ''
              }
            />

            Actualizar
          </button>

          <button
            type="button"
            className="studio-button primary"
            onClick={() =>
              setShowCreate(
                (value) =>
                  !value,
              )
            }
          >
            <CirclePlus
              size={17}
            />

            Nuevo Repliker
          </button>
        </div>
      </header>


      {notice && (
        <div
          className="repliker-studio-notice"
        >
          {notice}
        </div>
      )}


      {showCreate && (
        <div
          className="studio-create-card"
        >
          <div
            className="studio-section-heading"
          >
            <Bot size={19} />

            <div>
              <strong>
                Crear Repliker
              </strong>

              <span>
                Empieza con la identidad
                básica y personalízalo
                después.
              </span>
            </div>
          </div>

          <div
            className="studio-form-grid"
          >
            <label>
              <span>
                Nombre
              </span>

              <input
                value={
                  newRepliker.name
                }
                onChange={
                  (event) =>
                    setNewRepliker(
                      (current) => ({
                        ...current,
                        name:
                          event
                            .target
                            .value,
                      }),
                    )
                }
                placeholder="Nombre del Repliker"
              />
            </label>

            <label>
              <span>
                Especialidad
              </span>

              <select
                value={
                  newRepliker
                    .specialty
                }
                onChange={
                  (event) =>
                    setNewRepliker(
                      (current) => ({
                        ...current,
                        specialty:
                          event
                            .target
                            .value,
                      }),
                    )
                }
              >
                {specialtyOptions.map(
                  (item) => (
                    <option
                      key={
                        item.value
                      }
                      value={
                        item.value
                      }
                    >
                      {item.label}
                    </option>
                  ),
                )}
              </select>
            </label>

            <label>
              <span>
                Precio base
                en créditos
              </span>

              <input
                type="number"
                min={1}
                value={
                  newRepliker
                    .base_price_credits
                }
                onChange={
                  (event) =>
                    setNewRepliker(
                      (current) => ({
                        ...current,
                        base_price_credits:
                          Math.max(
                            1,
                            Number(
                              event
                                .target
                                .value,
                            )
                            || 1,
                          ),
                      }),
                    )
                }
              />
            </label>

            <label
              className="studio-span-two"
            >
              <span>
                Descripción
              </span>

              <textarea
                rows={3}
                value={
                  newRepliker
                    .description
                }
                onChange={
                  (event) =>
                    setNewRepliker(
                      (current) => ({
                        ...current,
                        description:
                          event
                            .target
                            .value,
                      }),
                    )
                }
                placeholder="Describe qué tipo de trabajo realizará."
              />
            </label>
          </div>

          <div
            className="studio-inline-actions"
          >
            <button
              type="button"
              className="studio-button secondary"
              onClick={() =>
                setShowCreate(false)
              }
            >
              Cancelar
            </button>

            <button
              type="button"
              className="studio-button primary"
              disabled={
                creating
              }
              onClick={() =>
                void createRepliker()
              }
            >
              <Plus size={16} />

              {creating
                ? 'Creando...'
                : 'Crear Repliker'}
            </button>
          </div>
        </div>
      )}


      <div
        className="studio-workspace"
      >
        <aside
          className="studio-sidebar"
        >
          <div
            className="studio-sidebar-title"
          >
            Mis Replikers
          </div>

          {loading ? (
            <div
              className="studio-empty"
            >
              Cargando...
            </div>

          ) : replikers.length
            === 0 ? (
              <div
                className="studio-empty"
              >
                Todavía no tienes
                Replikers propios.
              </div>

            ) : (
              <div
                className="studio-repliker-list"
              >
                {replikers.map(
                  (item) => (
                    <button
                      key={
                        item.id
                      }
                      type="button"
                      className={
                        selectedId
                        === item.id
                          ? 'active'
                          : ''
                      }
                      onClick={() =>
                        setSelectedId(
                          item.id,
                        )
                      }
                    >
                      <div
                        className="studio-repliker-icon"
                      >
                        <Bot size={18} />
                      </div>

                      <div>
                        <strong>
                          {item.name}
                        </strong>

                        <span>
                          {specialtyLabel(
                            item.specialty,
                          )}
                        </span>
                      </div>
                    </button>
                  ),
                )}
              </div>
            )}
        </aside>


        <main
          className="studio-editor"
        >
          {selectedId === null ? (
            <div
              className="studio-empty-editor"
            >
              <Bot size={36} />

              <strong>
                Selecciona o crea
                un Repliker
              </strong>

              <span>
                Aquí aparecerán todas
                sus opciones de configuración.
              </span>
            </div>

          ) : loadingStudio ? (
            <div
              className="studio-empty-editor"
            >
              <RefreshCw
                size={30}
                className="studio-spin"
              />

              <strong>
                Cargando configuración...
              </strong>
            </div>

          ) : draft === null ? (
            <div
              className="studio-empty-editor"
            >
              No fue posible abrir
              este Repliker.
            </div>

          ) : (
            <>
              <div
                className="studio-editor-head"
              >
                <div>
                  <span>
                    Repliker seleccionado
                  </span>

                  <h3>
                    {draft.name}
                  </h3>

                  <p>
                    {specialtyLabel(
                      draft.specialty,
                    )}
                  </p>
                </div>

                <div
                  className="studio-editor-badges"
                >
                  <div
                    className={
                      selectedRepliker
                        ?.is_published
                        ? (
                            'studio-publication-badge '
                            + 'published'
                          )
                        : (
                            'studio-publication-badge '
                            + 'draft'
                          )
                    }
                  >
                    {selectedRepliker
                      ?.is_published
                      ? 'Publicado'
                      : 'Borrador'}
                  </div>

                  <div
                    className="studio-version"
                  >
                    {draft.config_version
                      > 0
                      ? `Versión ${draft.config_version}`
                      : 'Configuración inicial'}
                  </div>
                </div>
              </div>


              <section
                className="studio-card"
              >
                <div
                  className="studio-section-heading"
                >
                  <Bot size={19} />

                  <div>
                    <strong>
                      Identidad
                    </strong>

                    <span>
                      Define quién es
                      este Repliker.
                    </span>
                  </div>
                </div>

                <div
                  className="studio-form-grid"
                >
                  <label>
                    <span>
                      Nombre
                    </span>

                    <input
                      value={
                        draft.name
                      }
                      onChange={
                        (event) =>
                          setDraft({
                            ...draft,
                            name:
                              event
                                .target
                                .value,
                          })
                      }
                    />
                  </label>

                  <label>
                    <span>
                      Especialidad
                    </span>

                    <select
                      value={
                        draft.specialty
                      }
                      onChange={
                        (event) =>
                          setDraft({
                            ...draft,
                            specialty:
                              event
                                .target
                                .value,
                          })
                      }
                    >
                      {!specialtyLabels[
                        draft.specialty
                      ] && (
                        <option
                          value={
                            draft.specialty
                          }
                        >
                          Especialidad personalizada
                        </option>
                      )}

                      {specialtyOptions.map(
                        (item) => (
                          <option
                            key={
                              item.value
                            }
                            value={
                              item.value
                            }
                          >
                            {item.label}
                          </option>
                        ),
                      )}
                    </select>
                  </label>

                  <label>
                    <span>
                      Precio base
                      en créditos
                    </span>

                    <input
                      type="number"
                      min={1}
                      value={
                        draft
                          .base_price_credits
                      }
                      onChange={
                        (event) =>
                          setDraft({
                            ...draft,
                            base_price_credits:
                              Math.max(
                                1,
                                Number(
                                  event
                                    .target
                                    .value,
                                )
                                || 1,
                              ),
                          })
                      }
                    />
                  </label>

                  <label
                    className="studio-span-two"
                  >
                    <span>
                      Descripción
                    </span>

                    <textarea
                      rows={3}
                      value={
                        draft.description
                      }
                      onChange={
                        (event) =>
                          setDraft({
                            ...draft,
                            description:
                              event
                                .target
                                .value,
                          })
                      }
                    />
                  </label>
                </div>
              </section>


              <section
                className="studio-card"
              >
                <div
                  className="studio-section-heading"
                >
                  <BrainCircuit
                    size={19}
                  />

                  <div>
                    <strong>
                      Comportamiento
                    </strong>

                    <span>
                      Modifica cómo piensa,
                      decide y se comunica.
                    </span>
                  </div>
                </div>

                <div
                  className="studio-form-grid"
                >
                  <label
                    className="studio-span-two"
                  >
                    <span>
                      Propósito
                    </span>

                    <textarea
                      rows={3}
                      value={
                        draft.purpose
                      }
                      onChange={
                        (event) =>
                          setDraft({
                            ...draft,
                            purpose:
                              event
                                .target
                                .value,
                          })
                      }
                      placeholder="Cuál es su objetivo principal."
                    />
                  </label>

                  <label>
                    <span>
                      Personalidad
                    </span>

                    <textarea
                      rows={4}
                      value={
                        draft.personality
                      }
                      onChange={
                        (event) =>
                          setDraft({
                            ...draft,
                            personality:
                              event
                                .target
                                .value,
                          })
                      }
                      placeholder="Analítico, creativo, cuidadoso..."
                    />
                  </label>

                  <label>
                    <span>
                      Estilo de comunicación
                    </span>

                    <textarea
                      rows={4}
                      value={
                        draft
                          .communication_style
                      }
                      onChange={
                        (event) =>
                          setDraft({
                            ...draft,
                            communication_style:
                              event
                                .target
                                .value,
                          })
                      }
                      placeholder="Claro, breve, técnico..."
                    />
                  </label>

                  <label
                    className="studio-span-two"
                  >
                    <span>
                      Instrucciones
                      del propietario
                    </span>

                    <textarea
                      rows={5}
                      value={
                        draft.instructions
                      }
                      onChange={
                        (event) =>
                          setDraft({
                            ...draft,
                            instructions:
                              event
                                .target
                                .value,
                          })
                      }
                      placeholder="Indicaciones permanentes para su forma de trabajar."
                    />
                  </label>
                </div>
              </section>


              <section
                className="studio-card"
              >
                <div
                  className="studio-section-heading"
                >
                  <BrainCircuit
                    size={19}
                  />

                  <div>
                    <strong>
                      Habilidades
                    </strong>

                    <span>
                      Capacidades que
                      el mercado utilizará
                      para evaluarlo.
                    </span>
                  </div>
                </div>

                <div
                  className="studio-list"
                >
                  {draft.skills.map(
                    (skill, index) => (
                      <div
                        className="studio-skill-row"
                        key={
                          `${index}-${skill.id ?? 'nuevo'}`
                        }
                      >
                        <input
                          value={
                            skill.name
                          }
                          onChange={
                            (event) => {
                              const next =
                                draft.skills.map(
                                  (
                                    current,
                                    currentIndex,
                                  ) =>
                                    currentIndex
                                    === index
                                      ? {
                                          ...current,
                                          name:
                                            event
                                              .target
                                              .value,
                                        }
                                      : current,
                                )

                              setDraft({
                                ...draft,
                                skills:
                                  next,
                              })
                            }
                          }
                          placeholder="Nombre de la habilidad"
                        />

                        <div
                          className="studio-level"
                        >
                          <input
                            type="range"
                            min={0}
                            max={100}
                            value={
                              skill.level
                            }
                            onChange={
                              (event) => {
                                const next =
                                  draft.skills.map(
                                    (
                                      current,
                                      currentIndex,
                                    ) =>
                                      currentIndex
                                      === index
                                        ? {
                                            ...current,
                                            level:
                                              Number(
                                                event
                                                  .target
                                                  .value,
                                              ),
                                          }
                                        : current,
                                  )

                                setDraft({
                                  ...draft,
                                  skills:
                                    next,
                                })
                              }
                            }
                          />

                          <strong>
                            {skill.level}
                          </strong>
                        </div>

                        <button
                          type="button"
                          className="studio-icon-button danger"
                          onClick={() =>
                            setDraft({
                              ...draft,
                              skills:
                                draft
                                  .skills
                                  .filter(
                                    (
                                      _,
                                      currentIndex,
                                    ) =>
                                      currentIndex
                                      !== index,
                                  ),
                            })
                          }
                          aria-label="Eliminar habilidad"
                        >
                          <Trash2
                            size={16}
                          />
                        </button>
                      </div>
                    ),
                  )}

                  <button
                    type="button"
                    className="studio-add-row"
                    onClick={() =>
                      setDraft({
                        ...draft,
                        skills: [
                          ...draft.skills,
                          {
                            name: '',
                            level: 50,
                          },
                        ],
                      })
                    }
                  >
                    <Plus size={15} />

                    Añadir habilidad
                  </button>
                </div>
              </section>


              <section
                className="studio-card"
              >
                <div
                  className="studio-section-heading"
                >
                  <BookOpen
                    size={19}
                  />

                  <div>
                    <strong>
                      Conocimiento
                    </strong>

                    <span>
                      Información propia
                      que podrá utilizar
                      durante su trabajo.
                    </span>
                  </div>
                </div>

                <div
                  className="studio-list"
                >
                  {draft.knowledge.map(
                    (item, index) => (
                      <div
                        className="studio-knowledge-row"
                        key={
                          `${index}-${item.id ?? 'nuevo'}`
                        }
                      >
                        <div
                          className="studio-row-top"
                        >
                          <input
                            value={
                              item.title
                            }
                            onChange={
                              (event) => {
                                const next =
                                  draft
                                    .knowledge
                                    .map(
                                      (
                                        current,
                                        currentIndex,
                                      ) =>
                                        currentIndex
                                        === index
                                          ? {
                                              ...current,
                                              title:
                                                event
                                                  .target
                                                  .value,
                                            }
                                          : current,
                                    )

                                setDraft({
                                  ...draft,
                                  knowledge:
                                    next,
                                })
                              }
                            }
                            placeholder="Título del conocimiento"
                          />

                          <label
                            className="studio-switch-label"
                          >
                            <input
                              type="checkbox"
                              checked={
                                item.enabled
                              }
                              onChange={
                                (event) => {
                                  const next =
                                    draft
                                      .knowledge
                                      .map(
                                        (
                                          current,
                                          currentIndex,
                                        ) =>
                                          currentIndex
                                          === index
                                            ? {
                                                ...current,
                                                enabled:
                                                  event
                                                    .target
                                                    .checked,
                                              }
                                            : current,
                                      )

                                  setDraft({
                                    ...draft,
                                    knowledge:
                                      next,
                                  })
                                }
                              }
                            />

                            Activo
                          </label>

                          <button
                            type="button"
                            className="studio-icon-button danger"
                            onClick={() =>
                              setDraft({
                                ...draft,
                                knowledge:
                                  draft
                                    .knowledge
                                    .filter(
                                      (
                                        _,
                                        currentIndex,
                                      ) =>
                                        currentIndex
                                        !== index,
                                    ),
                              })
                            }
                            aria-label="Eliminar conocimiento"
                          >
                            <Trash2
                              size={16}
                            />
                          </button>
                        </div>

                        <textarea
                          rows={5}
                          value={
                            item.content
                          }
                          onChange={
                            (event) => {
                              const next =
                                draft
                                  .knowledge
                                  .map(
                                    (
                                      current,
                                      currentIndex,
                                    ) =>
                                      currentIndex
                                      === index
                                        ? {
                                            ...current,
                                            content:
                                              event
                                                .target
                                                .value,
                                          }
                                        : current,
                                  )

                              setDraft({
                                ...draft,
                                knowledge:
                                  next,
                              })
                            }
                          }
                          placeholder="Información que debe conocer este Repliker."
                        />
                      </div>
                    ),
                  )}

                  <button
                    type="button"
                    className="studio-add-row"
                    onClick={() =>
                      setDraft({
                        ...draft,
                        knowledge: [
                          ...draft.knowledge,
                          {
                            title: '',
                            content: '',
                            enabled: true,
                          },
                        ],
                      })
                    }
                  >
                    <Plus size={15} />

                    Añadir conocimiento
                  </button>
                </div>
              </section>


              <section
                className="studio-card"
              >
                <div
                  className="studio-section-heading"
                >
                  <ShieldCheck
                    size={19}
                  />

                  <div>
                    <strong>
                      Reglas personales
                    </strong>

                    <span>
                      Directrices propias
                      subordinadas a la
                      seguridad del sistema.
                    </span>
                  </div>
                </div>

                <div
                  className="studio-list"
                >
                  {draft.rules.map(
                    (item, index) => (
                      <div
                        className="studio-rule-row"
                        key={
                          `${index}-${item.id ?? 'nuevo'}`
                        }
                      >
                        <div
                          className="studio-row-top"
                        >
                          <input
                            value={
                              item.title
                            }
                            onChange={
                              (event) => {
                                const next =
                                  draft
                                    .rules
                                    .map(
                                      (
                                        current,
                                        currentIndex,
                                      ) =>
                                        currentIndex
                                        === index
                                          ? {
                                              ...current,
                                              title:
                                                event
                                                  .target
                                                  .value,
                                            }
                                          : current,
                                    )

                                setDraft({
                                  ...draft,
                                  rules:
                                    next,
                                })
                              }
                            }
                            placeholder="Nombre de la regla"
                          />

                          <label
                            className="studio-priority"
                          >
                            <span>
                              Prioridad
                            </span>

                            <input
                              type="number"
                              min={0}
                              max={100}
                              value={
                                item.priority
                              }
                              onChange={
                                (event) => {
                                  const value =
                                    Math.min(
                                      100,
                                      Math.max(
                                        0,
                                        Number(
                                          event
                                            .target
                                            .value,
                                        )
                                        || 0,
                                      ),
                                    )

                                  const next =
                                    draft
                                      .rules
                                      .map(
                                        (
                                          current,
                                          currentIndex,
                                        ) =>
                                          currentIndex
                                          === index
                                            ? {
                                                ...current,
                                                priority:
                                                  value,
                                              }
                                            : current,
                                      )

                                  setDraft({
                                    ...draft,
                                    rules:
                                      next,
                                  })
                                }
                              }
                            />
                          </label>

                          <label
                            className="studio-switch-label"
                          >
                            <input
                              type="checkbox"
                              checked={
                                item.enabled
                              }
                              onChange={
                                (event) => {
                                  const next =
                                    draft
                                      .rules
                                      .map(
                                        (
                                          current,
                                          currentIndex,
                                        ) =>
                                          currentIndex
                                          === index
                                            ? {
                                                ...current,
                                                enabled:
                                                  event
                                                    .target
                                                    .checked,
                                              }
                                            : current,
                                      )

                                  setDraft({
                                    ...draft,
                                    rules:
                                      next,
                                  })
                                }
                              }
                            />

                            Activa
                          </label>

                          <button
                            type="button"
                            className="studio-icon-button danger"
                            onClick={() =>
                              setDraft({
                                ...draft,
                                rules:
                                  draft
                                    .rules
                                    .filter(
                                      (
                                        _,
                                        currentIndex,
                                      ) =>
                                        currentIndex
                                        !== index,
                                    ),
                              })
                            }
                            aria-label="Eliminar regla"
                          >
                            <Trash2
                              size={16}
                            />
                          </button>
                        </div>

                        <textarea
                          rows={4}
                          value={
                            item.instruction
                          }
                          onChange={
                            (event) => {
                              const next =
                                draft
                                  .rules
                                  .map(
                                    (
                                      current,
                                      currentIndex,
                                    ) =>
                                      currentIndex
                                      === index
                                        ? {
                                            ...current,
                                            instruction:
                                              event
                                                .target
                                                .value,
                                          }
                                        : current,
                                  )

                              setDraft({
                                ...draft,
                                rules:
                                  next,
                              })
                            }
                          }
                          placeholder="Indica cómo debe actuar."
                        />
                      </div>
                    ),
                  )}

                  <button
                    type="button"
                    className="studio-add-row"
                    onClick={() =>
                      setDraft({
                        ...draft,
                        rules: [
                          ...draft.rules,
                          {
                            title: '',
                            instruction: '',
                            priority: 50,
                            enabled: true,
                          },
                        ],
                      })
                    }
                  >
                    <Plus size={15} />

                    Añadir regla
                  </button>
                </div>
              </section>


              <section
                className="studio-card"
              >
                <div
                  className="studio-section-heading"
                >
                  <Wrench size={19} />

                  <div>
                    <strong>
                      Herramientas
                    </strong>

                    <span>
                      Selecciona qué
                      capacidades del sistema
                      puede utilizar.
                    </span>
                  </div>
                </div>

                <div
                  className="studio-tool-grid"
                >
                  {catalog.map(
                    (tool) => {
                      const active =
                        draft
                          .tool_names
                          .includes(
                            tool.name,
                          )

                      return (
                        <button
                          key={
                            tool.name
                          }
                          type="button"
                          className={
                            active
                              ? 'studio-tool active'
                              : 'studio-tool'
                          }
                          onClick={() =>
                            toggleTool(
                              tool.name,
                            )
                          }
                        >
                          <div>
                            <Wrench
                              size={17}
                            />

                            <strong>
                              {tool.label}
                            </strong>
                          </div>

                          <p>
                            {tool.description}
                          </p>

                          <span>
                            {active
                              ? 'Permitida'
                              : 'Desactivada'}
                          </span>
                        </button>
                      )
                    },
                  )}
                </div>
              </section>


              <section
                className="studio-card"
              >
                <div
                  className="studio-section-heading"
                >
                  <Code2 size={19} />

                  <div>
                    <strong>
                      Modo desarrollador
                    </strong>

                    <span>
                      Añade lógica propia
                      sin ampliar los permisos
                      del Repliker.
                    </span>
                  </div>
                </div>

                {developer === null ? (
                  <div
                    className="studio-empty"
                  >
                    Cargando módulo...
                  </div>

                ) : (
                  <div
                    className="studio-developer"
                  >
                    <label
                      className="studio-developer-toggle"
                    >
                      <input
                        type="checkbox"
                        checked={
                          developer.enabled
                        }
                        onChange={
                          (event) =>
                            setDeveloper({
                              ...developer,
                              enabled:
                                event
                                  .target
                                  .checked,
                            })
                        }
                      />

                      <div>
                        <strong>
                          Activar código personalizado
                        </strong>

                        <span>
                          Solo se ejecutará
                          dentro del entorno
                          seguro del Repliker.
                        </span>
                      </div>
                    </label>

                    <div
                      className="studio-code-note"
                    >
                      <ShieldCheck
                        size={16}
                      />

                      El código no tiene
                      acceso directo al sistema,
                      red, secretos ni comandos
                      externos. Debe definir
                      una función principal
                      que reciba los datos
                      de trabajo.
                    </div>

                    <textarea
                      className="studio-code-editor"
                      spellCheck={false}
                      rows={16}
                      value={
                        developer.source_code
                      }
                      onChange={
                        (event) =>
                          setDeveloper({
                            ...developer,
                            source_code:
                              event
                                .target
                                .value,
                          })
                      }
                      placeholder={
                        'def run(data):\n'
                        + '    return data'
                      }
                    />

                    <div
                      className="studio-developer-meta"
                    >
                      <span>
                        {developer.version > 0
                          ? `Versión ${developer.version}`
                          : 'Sin guardar'}
                      </span>

                      <span>
                        {developer.checksum
                          ? 'Código validado'
                          : 'Pendiente de validación'}
                      </span>
                    </div>
                  </div>
                )}
              </section>


              <div
                className="studio-save-bar"
              >
                <div>
                  <strong>
                    {selectedRepliker
                      ?.name
                      ?? draft.name}
                  </strong>

                  <span>
                    Los cambios afectan
                    las próximas decisiones
                    y ejecuciones del Repliker.
                  </span>
                </div>

                <div
                  className="studio-save-actions"
                >
                  <button
                    type="button"
                    className={
                      selectedRepliker
                        ?.is_published
                        ? 'studio-button secondary large'
                        : 'studio-button publish large'
                    }
                    disabled={
                      saving
                      || publishing
                    }
                    onClick={() =>
                      void updatePublication(
                        !selectedRepliker
                          ?.is_published,
                      )
                    }
                  >
                    {selectedRepliker
                      ?.is_published
                      ? (
                          <EyeOff
                            size={17}
                          />
                        )
                      : (
                          <Globe2
                            size={17}
                          />
                        )}

                    {publishing
                      ? 'Actualizando...'
                      : (
                          selectedRepliker
                            ?.is_published
                            ? 'Retirar del ecosistema'
                            : 'Publicar en el ecosistema'
                        )}
                  </button>

                <button
                  type="button"
                  className="studio-button primary large"
                  disabled={
                    saving
                  }
                  onClick={() =>
                    void saveStudio()
                  }
                >
                  <Save size={17} />

                  {saving
                    ? 'Guardando...'
                    : 'Guardar configuración'}
                </button>
                </div>
              </div>
            </>
          )}
        </main>
      </div>
    </section>
  )
}
