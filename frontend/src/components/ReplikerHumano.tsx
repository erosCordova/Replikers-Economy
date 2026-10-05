import type {
  CSSProperties,
} from 'react'

import '../styles/ReplikerHumano.css'


export interface ReplikerAppearance {
  avatar_style: string
  primary_color: string
  secondary_color: string
  face_type: string
  eye_style: string
  accessory: string
  background_style: string
  avatar_url?: string | null
}


interface ReplikerHumanoProps {
  appearance: ReplikerAppearance
  name: string
  size?: 'small' | 'medium' | 'large'
  active?: boolean
}


const PALETAS = [
  ['#2563eb', '#22d3ee'],
  ['#7c3aed', '#ec4899'],
  ['#0f766e', '#34d399'],
  ['#ea580c', '#fbbf24'],
  ['#4338ca', '#38bdf8'],
  ['#be123c', '#fb7185'],
]


const TONOS_PIEL = [
  {
    base: '#f1c7a8',
    sombra: '#cf9872',
    luz: '#ffe2cc',
    labios: '#ad6d68',
  },
  {
    base: '#e7b38b',
    sombra: '#bd7d59',
    luz: '#f9d1b1',
    labios: '#a76260',
  },
  {
    base: '#d69a70',
    sombra: '#aa6748',
    luz: '#eeb993',
    labios: '#965553',
  },
  {
    base: '#bb7b57',
    sombra: '#8f5139',
    luz: '#d59974',
    labios: '#824c4a',
  },
  {
    base: '#976044',
    sombra: '#6f3d2c',
    luz: '#b67a59',
    labios: '#704344',
  },
  {
    base: '#74462f',
    sombra: '#4f2c20',
    luz: '#926044',
    labios: '#643d3d',
  },
]


const COLORES_CABELLO = [
  '#171311',
  '#2b211c',
  '#4a3025',
  '#6b432d',
  '#8a5d3d',
  '#b17a48',
  '#1c2230',
]


const COLORES_IRIS = [
  '#355f78',
  '#4c7041',
  '#674936',
  '#3e495f',
  '#76573b',
  '#305f5c',
]


function hashNombre(
  value: string,
) {
  let hash = 0

  for (
    let index = 0;
    index < value.length;
    index += 1
  ) {
    hash =
      (
        (hash << 5)
        - hash
        + value.charCodeAt(index)
      ) | 0
  }

  return Math.abs(hash)
}


function usaColoresPredeterminados(
  appearance: ReplikerAppearance,
) {
  return (
    appearance.primary_color
      .toLowerCase() === '#2563eb'
    &&
    appearance.secondary_color
      .toLowerCase() === '#06b6d4'
  )
}


function formaRostro(
  value: string,
) {
  switch (
    value
      .trim()
      .toLowerCase()
  ) {
    case 'angular':
      return 'definido'

    case 'orb':
      return 'redondeado'

    default:
      return 'ovalado'
  }
}


function estiloMirada(
  value: string,
) {
  switch (
    value
      .trim()
      .toLowerCase()
  ) {
    case 'line':
      return 'serena'

    case 'dual':
      return 'enfocada'

    default:
      return 'amable'
  }
}


function estiloVestimenta(
  value: string,
) {
  switch (
    value
      .trim()
      .toLowerCase()
  ) {
    case 'premium':
      return 'elegante'

    case 'minimal':
      return 'sencilla'

    case 'neon':
      return 'creativa'

    case 'industrial':
      return 'tecnica'

    default:
      return 'natural'
  }
}


function estiloFondo(
  value: string,
) {
  switch (
    value
      .trim()
      .toLowerCase()
  ) {
    case 'circuit':
      return 'degradado'

    case 'halo':
      return 'luz'

    case 'plain':
      return 'limpio'

    default:
      return 'bosque'
  }
}


function tamanoVisible(
  value:
    'small'
    | 'medium'
    | 'large',
) {
  switch (value) {
    case 'small':
      return 'pequeno'

    case 'large':
      return 'grande'

    default:
      return 'mediano'
  }
}


function rostroPath(
  rostro: string,
) {
  if (rostro === 'definido') {
    return (
      'M38 28 ' +
      'C48 18 72 18 82 28 ' +
      'C91 38 89 60 82 75 ' +
      'C76 88 68 96 60 98 ' +
      'C52 96 44 88 38 75 ' +
      'C31 60 29 38 38 28Z'
    )
  }

  if (rostro === 'redondeado') {
    return (
      'M37 31 ' +
      'C44 19 76 19 83 31 ' +
      'C91 43 88 67 80 81 ' +
      'C74 91 67 96 60 96 ' +
      'C53 96 46 91 40 81 ' +
      'C32 67 29 43 37 31Z'
    )
  }

  return (
    'M38 28 ' +
    'C46 17 74 17 82 28 ' +
    'C90 41 87 66 79 82 ' +
    'C73 92 66 98 60 98 ' +
    'C54 98 47 92 41 82 ' +
    'C33 66 30 41 38 28Z'
  )
}


function cabelloPath(
  variante: number,
) {
  switch (variante) {
    case 0:
      return (
        'M34 42 ' +
        'C33 25 43 14 60 13 ' +
        'C76 12 88 23 87 40 ' +
        'C78 31 72 29 61 29 ' +
        'C49 29 42 33 34 42Z'
      )

    case 1:
      return (
        'M33 45 ' +
        'C29 27 42 14 59 13 ' +
        'C75 12 87 22 89 37 ' +
        'C82 31 75 29 68 29 ' +
        'C56 29 48 34 43 43 ' +
        'C39 44 36 45 33 45Z'
      )

    case 2:
      return (
        'M32 43 ' +
        'C34 22 45 14 62 14 ' +
        'C77 14 88 25 87 43 ' +
        'C82 34 75 31 66 30 ' +
        'C54 30 46 34 39 42 ' +
        'C37 42 35 42 32 43Z'
      )

    case 3:
      return (
        'M32 45 ' +
        'C29 27 40 14 58 13 ' +
        'C78 12 90 25 88 45 ' +
        'C82 36 75 32 66 31 ' +
        'C54 30 45 35 39 45Z'
      )

    case 4:
      return (
        'M35 39 ' +
        'C38 21 48 15 62 15 ' +
        'C76 15 85 24 86 38 ' +
        'C78 31 71 29 62 29 ' +
        'C51 29 43 32 35 39Z'
      )

    default:
      return (
        'M33 44 ' +
        'C31 26 43 14 60 14 ' +
        'C79 14 89 27 87 44 ' +
        'C80 34 73 30 63 29 ' +
        'C52 29 43 34 37 43Z'
      )
  }
}


export default function ReplikerHumano({
  appearance,
  name,
  size = 'medium',
  active = false,
}: ReplikerHumanoProps) {
  const hash =
    hashNombre(name)

  const automatico =
    usaColoresPredeterminados(
      appearance,
    )

  const paleta =
    PALETAS[
      hash % PALETAS.length
    ]

  const principal =
    automatico
      ? paleta[0]
      : appearance.primary_color

  const secundario =
    automatico
      ? paleta[1]
      : appearance.secondary_color

  const piel =
    TONOS_PIEL[
      hash % TONOS_PIEL.length
    ]

  const cabello =
    COLORES_CABELLO[
      (hash * 3)
      % COLORES_CABELLO.length
    ]

  const iris =
    COLORES_IRIS[
      (hash * 5)
      % COLORES_IRIS.length
    ]

  const varianteCabello =
    hash % 6

  const rostro =
    formaRostro(
      appearance.face_type,
    )

  const mirada =
    estiloMirada(
      appearance.eye_style,
    )

  const vestimenta =
    estiloVestimenta(
      appearance.avatar_style,
    )

  const fondo =
    estiloFondo(
      appearance.background_style,
    )

  const tamano =
    tamanoVisible(size)

  const idSeguro =
    `repliker-${hash}`

  const estilo = {
    '--repliker-principal':
      principal,

    '--repliker-secundario':
      secundario,

    '--repliker-retardo':
      `${(hash % 8) * -0.16}s`,
  } as CSSProperties


  if (appearance.avatar_url) {
    return (
      <div
        className={[
          'repliker-ai-avatar',
          'repliker-humano',
          `repliker-humano-${tamano}`,
          active
            ? 'repliker-humano-activo'
            : '',
        ].join(' ')}
        style={estilo}
        title={name}
      >
        <img
          className="repliker-humano-imagen"
          src={appearance.avatar_url}
          alt={`Retrato de ${name}`}
        />

        <span
          className={[
            'repliker-humano-estado',
            active
              ? 'activo'
              : '',
          ].join(' ')}
          aria-hidden="true"
        />
      </div>
    )
  }


  const ojoY =
    mirada === 'serena'
      ? 49
      : 47

  const cejaY =
    mirada === 'enfocada'
      ? 39
      : 40

  const ojoRy =
    mirada === 'serena'
      ? 2.5
      : 3.4


  return (
    <div
      className={[
        'repliker-ai-avatar',
        'repliker-humano',
        `repliker-humano-${tamano}`,
        `repliker-fondo-${fondo}`,
        `repliker-vestimenta-${vestimenta}`,
        active
          ? 'repliker-humano-activo'
          : '',
      ].join(' ')}
      style={estilo}
      title={name}
      role="img"
      aria-label={`Representación de ${name}`}
    >
      <svg
        className="repliker-retrato"
        viewBox="0 0 120 120"
        aria-hidden="true"
      >
        <defs>
          <linearGradient
            id={`${idSeguro}-fondo`}
            x1="0"
            y1="0"
            x2="1"
            y2="1"
          >
            <stop
              offset="0%"
              stopColor={principal}
              stopOpacity="0.16"
            />

            <stop
              offset="100%"
              stopColor={secundario}
              stopOpacity="0.06"
            />
          </linearGradient>

          <linearGradient
            id={`${idSeguro}-piel`}
            x1="0"
            y1="0"
            x2="1"
            y2="1"
          >
            <stop
              offset="0%"
              stopColor={piel.luz}
            />

            <stop
              offset="48%"
              stopColor={piel.base}
            />

            <stop
              offset="100%"
              stopColor={piel.sombra}
            />
          </linearGradient>

          <linearGradient
            id={`${idSeguro}-ropa`}
            x1="0"
            y1="0"
            x2="1"
            y2="1"
          >
            <stop
              offset="0%"
              stopColor={principal}
            />

            <stop
              offset="100%"
              stopColor={secundario}
            />
          </linearGradient>

          <radialGradient
            id={`${idSeguro}-iris`}
            cx="45%"
            cy="42%"
            r="60%"
          >
            <stop
              offset="0%"
              stopColor="#111827"
            />

            <stop
              offset="38%"
              stopColor={iris}
            />

            <stop
              offset="100%"
              stopColor="#111827"
            />
          </radialGradient>

          <filter
            id={`${idSeguro}-sombra`}
            x="-20%"
            y="-20%"
            width="140%"
            height="150%"
          >
            <feDropShadow
              dx="0"
              dy="3"
              stdDeviation="3"
              floodColor="#14261d"
              floodOpacity="0.18"
            />
          </filter>

          <filter
            id={`${idSeguro}-suave`}
            x="-20%"
            y="-20%"
            width="140%"
            height="140%"
          >
            <feGaussianBlur
              stdDeviation="1.4"
            />
          </filter>
        </defs>

        <rect
          width="120"
          height="120"
          rx="24"
          fill={`url(#${idSeguro}-fondo)`}
        />

        <circle
          cx="93"
          cy="23"
          r="28"
          fill={secundario}
          opacity="0.06"
        />

        <circle
          cx="21"
          cy="92"
          r="35"
          fill={principal}
          opacity="0.05"
        />

        <ellipse
          cx="60"
          cy="108"
          rx="41"
          ry="14"
          fill="#173426"
          opacity="0.08"
          filter={`url(#${idSeguro}-suave)`}
        />

        <path
          d="M24 120 C27 94 40 83 60 83 C80 83 93 94 96 120Z"
          fill={`url(#${idSeguro}-ropa)`}
          filter={`url(#${idSeguro}-sombra)`}
        />

        <path
          d="M45 85 L60 101 L75 85 L70 120 L50 120Z"
          fill="#ffffff"
          opacity="0.92"
        />

        <path
          d="M40 88 L54 101 L47 108 L34 95Z"
          fill="#ffffff"
          opacity="0.18"
        />

        <path
          d="M80 88 L66 101 L73 108 L86 95Z"
          fill="#ffffff"
          opacity="0.18"
        />

        <path
          d="M52 74 C53 83 54 87 60 90 C66 87 67 83 68 74Z"
          fill={`url(#${idSeguro}-piel)`}
        />

        <ellipse
          cx="35"
          cy="53"
          rx="5"
          ry="9"
          fill={piel.base}
        />

        <ellipse
          cx="85"
          cy="53"
          rx="5"
          ry="9"
          fill={piel.base}
        />

        <ellipse
          cx="35"
          cy="53"
          rx="2"
          ry="5"
          fill={piel.sombra}
          opacity="0.28"
        />

        <ellipse
          cx="85"
          cy="53"
          rx="2"
          ry="5"
          fill={piel.sombra}
          opacity="0.28"
        />

        <path
          d={rostroPath(rostro)}
          fill={`url(#${idSeguro}-piel)`}
          filter={`url(#${idSeguro}-sombra)`}
        />

        <path
          d="M42 60 C48 64 52 65 60 65 C68 65 72 64 78 60"
          fill="none"
          stroke={piel.sombra}
          strokeWidth="1"
          opacity="0.16"
          strokeLinecap="round"
        />

        <path
          d={cabelloPath(varianteCabello)}
          fill={cabello}
        />

        <path
          d="M39 33 C48 24 72 22 83 34"
          fill="none"
          stroke="#ffffff"
          strokeWidth="2"
          opacity="0.06"
          strokeLinecap="round"
        />

        <path
          d={
            mirada === 'enfocada'
              ? 'M43 40 Q49 37 54 39'
              : 'M43 40 Q49 39 54 40'
          }
          fill="none"
          stroke={cabello}
          strokeWidth="2.2"
          strokeLinecap="round"
          opacity="0.82"
        />

        <path
          d={
            mirada === 'enfocada'
              ? 'M66 39 Q72 37 78 40'
              : 'M66 40 Q72 39 78 40'
          }
          fill="none"
          stroke={cabello}
          strokeWidth="2.2"
          strokeLinecap="round"
          opacity="0.82"
        />

        <ellipse
          cx="49"
          cy={ojoY}
          rx="7"
          ry={ojoRy}
          fill="#fffdfb"
        />

        <ellipse
          cx="71"
          cy={ojoY}
          rx="7"
          ry={ojoRy}
          fill="#fffdfb"
        />

        <circle
          cx="49"
          cy={ojoY}
          r="2.7"
          fill={`url(#${idSeguro}-iris)`}
        />

        <circle
          cx="71"
          cy={ojoY}
          r="2.7"
          fill={`url(#${idSeguro}-iris)`}
        />

        <circle
          cx="49.8"
          cy={ojoY - 0.8}
          r="0.7"
          fill="#ffffff"
          opacity="0.9"
        />

        <circle
          cx="71.8"
          cy={ojoY - 0.8}
          r="0.7"
          fill="#ffffff"
          opacity="0.9"
        />

        <path
          d="M60 49 C58 56 57 60 59 62 C60 63 62 63 64 62"
          fill="none"
          stroke={piel.sombra}
          strokeWidth="1.3"
          strokeLinecap="round"
          opacity="0.58"
        />

        <path
          d="M53 70 Q60 74 67 70"
          fill="none"
          stroke={piel.labios}
          strokeWidth="1.8"
          strokeLinecap="round"
        />

        <path
          d="M55 72 Q60 74 65 72"
          fill="none"
          stroke="#ffffff"
          strokeWidth="0.65"
          strokeLinecap="round"
          opacity="0.35"
        />

        <ellipse
          cx="43"
          cy="60"
          rx="6"
          ry="3"
          fill="#d86f78"
          opacity="0.08"
        />

        <ellipse
          cx="77"
          cy="60"
          rx="6"
          ry="3"
          fill="#d86f78"
          opacity="0.08"
        />

        {appearance.accessory ===
          'visor' && (
          <g>
            <rect
              x="39"
              y={cejaY + 4}
              width="18"
              height="10"
              rx="4"
              fill="none"
              stroke={principal}
              strokeWidth="1.8"
              opacity="0.82"
            />

            <rect
              x="63"
              y={cejaY + 4}
              width="18"
              height="10"
              rx="4"
              fill="none"
              stroke={principal}
              strokeWidth="1.8"
              opacity="0.82"
            />

            <path
              d={`M57 ${cejaY + 9} H63`}
              stroke={principal}
              strokeWidth="1.6"
            />
          </g>
        )}

        {appearance.accessory ===
          'headphones' && (
          <g>
            <path
              d="M35 47 C36 24 84 24 85 47"
              fill="none"
              stroke={principal}
              strokeWidth="4"
              strokeLinecap="round"
            />

            <rect
              x="31"
              y="46"
              width="7"
              height="18"
              rx="3"
              fill={principal}
            />

            <rect
              x="82"
              y="46"
              width="7"
              height="18"
              rx="3"
              fill={principal}
            />
          </g>
        )}

        {appearance.accessory ===
          'halo' && (
          <ellipse
            cx="60"
            cy="18"
            rx="22"
            ry="5"
            fill="none"
            stroke={secundario}
            strokeWidth="2"
            opacity="0.75"
          />
        )}

        {appearance.accessory ===
          'antenna' && (
          <g>
            <path
              d="M79 24 L89 14"
              stroke={principal}
              strokeWidth="2"
              strokeLinecap="round"
            />

            <circle
              cx="91"
              cy="12"
              r="3"
              fill={secundario}
            />
          </g>
        )}
      </svg>

      <span
        className={[
          'repliker-humano-estado',
          active
            ? 'activo'
            : '',
        ].join(' ')}
        aria-hidden="true"
      />
    </div>
  )
}
