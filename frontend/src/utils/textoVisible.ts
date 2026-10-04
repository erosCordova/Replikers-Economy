interface HerramientaVisible {
  nombre: string
  descripcion: string
}


const HERRAMIENTAS:
  Record<string, HerramientaVisible> = {
    inspect_repliker_profile: {
      nombre:
        'Inspeccionar perfil',

      descripcion:
        'Consulta el perfil real del Repliker, '
        + 'sus habilidades, reputación y experiencia.',
    },

    inspect_project: {
      nombre:
        'Inspeccionar proyecto',

      descripcion:
        'Consulta los datos y límites reales '
        + 'del proyecto.',
    },

    inspect_task: {
      nombre:
        'Inspeccionar tarea',

      descripcion:
        'Consulta requisitos, presupuesto, '
        + 'complejidad y criterios de la tarea.',
    },

    inspect_tool_permissions: {
      nombre:
        'Inspeccionar permisos',

      descripcion:
        'Permite conocer exactamente qué '
        + 'herramientas tiene autorizadas.',
    },

    evaluate_skill_coverage: {
      nombre:
        'Evaluar habilidades',

      descripcion:
        'Compara las habilidades del Repliker '
        + 'con las exigidas por la tarea.',
    },
  }


const VALORES_EXACTOS:
  Record<string, string> = {
    activity:
      'Actividad',

    message:
      'Mensaje',

    workflow:
      'Flujo de trabajo',

    economy:
      'Economía',

    system:
      'Sistema',

    project:
      'Proyecto',

    task:
      'Tarea',

    working:
      'Trabajando',

    running:
      'En ejecución',

    available:
      'Disponible',

    completed:
      'Completado',

    failed:
      'Fallido',

    pending:
      'Pendiente',

    retry:
      'Reintento',

    review:
      'Revisión',

    qa:
      'Pruebas',
  }


const REEMPLAZOS:
  Array<[RegExp, string]> = [
    [
      /Repliker Economy/gi,
      'Repliker Economía',
    ],
    [
      /\bReplikers\b/g,
      'Repliker',
    ],
    [
      /\bFrontend Developer\b/gi,
      'Desarrollador de Interfaz',
    ],
    [
      /\bBackend Developer\b/gi,
      'Desarrollador de Servidor',
    ],
    [
      /\bDatabase Engineer\b/gi,
      'Ingeniero de Base de Datos',
    ],
    [
      /\bSecurity Engineer\b/gi,
      'Ingeniero de Seguridad',
    ],
    [
      /\bSoftware Architect\b/gi,
      'Arquitecto de Software',
    ],
    [
      /\bIntegration Specialist\b/gi,
      'Especialista en Integraciones',
    ],
    [
      /\bAccessibility Specialist\b/gi,
      'Especialista en Accesibilidad',
    ],
    [
      /\bContent\/Copy Specialist\b/gi,
      'Especialista en Contenido',
    ],
    [
      /\bFinal Reviewer\b/gi,
      'Revisor Final',
    ],
    [
      /\bGeneralist\b/gi,
      'Generalista',
    ],
    [
      /\bLangChain\b/gi,
      'motor de agentes',
    ],
    [
      /\bLangGraph\b/gi,
      'orquestador',
    ],
    [
      /\bMarketplace\b/gi,
      'Mercado',
    ],
    [
      /\bBackend\b/gi,
      'Servidor',
    ],
    [
      /\bFrontend\b/gi,
      'Interfaz',
    ],
    [
      /\bWorkspace\b/gi,
      'Espacio de trabajo',
    ],
    [
      /\bAgentic\b/gi,
      'de agentes',
    ],
    [
      /\bQuality Assurance\b/gi,
      'Control de calidad',
    ],
    [
      /\bQA\b/g,
      'Pruebas',
    ],
    [
      /\bRetries\b/gi,
      'Reintentos',
    ],
    [
      /\bRetry\b/gi,
      'Reintento',
    ],
    [
      /\bTools\b/gi,
      'Herramientas',
    ],
    [
      /\bTool\b/gi,
      'Herramienta',
    ],
    [
      /\bTask\b/gi,
      'Tarea',
    ],
    [
      /\bProject\b/gi,
      'Proyecto',
    ],
    [
      /\bStatus\b/gi,
      'Estado',
    ],
    [
      /\bReview\b/gi,
      'Revisión',
    ],
    [
      /\bReviewer\b/gi,
      'Revisor',
    ],
    [
      /\bWorkflow\b/gi,
      'Flujo de trabajo',
    ],
  ]


export function textoSistemaVisible(
  value:
    string
    | null
    | undefined,
  fallback = '',
) {
  const original =
    value?.trim() ?? ''

  if (!original) {
    return fallback
  }

  const exacto =
    VALORES_EXACTOS[
      original.toLowerCase()
    ]

  if (exacto) {
    return exacto
  }

  let visible =
    original

  for (
    const [
      patron,
      reemplazo,
    ]
    of REEMPLAZOS
  ) {
    visible =
      visible.replace(
        patron,
        reemplazo,
      )
  }

  return visible
}


export function nombreHerramientaVisible(
  name: string,
  label?: string | null,
) {
  return (
    HERRAMIENTAS[name]?.nombre
    ??
    textoSistemaVisible(
      label ?? name,
      'Herramienta',
    )
  )
}


export function descripcionHerramientaVisible(
  name: string,
  description?: string | null,
) {
  return (
    HERRAMIENTAS[name]?.descripcion
    ??
    textoSistemaVisible(
      description,
      'Herramienta autorizada.',
    )
  )
}
