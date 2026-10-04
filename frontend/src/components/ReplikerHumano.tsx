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
  ['#f4c7a1', '#d89b72'],
  ['#e8b58c', '#c9825c'],
  ['#d79a70', '#b56f4e'],
  ['#bd7b55', '#95583f'],
  ['#996044', '#75412f'],
  ['#75452f', '#563022'],
]


const COLORES_CABELLO = [
  '#241a17',
  '#3f2a20',
  '#6b442d',
  '#8a5a3b',
  '#c28b55',
  '#161b2a',
  '#523b59',
]


const COLORES_IRIS = [
  '#315c76',
  '#4c6f3f',
  '#654631',
  '#3b445e',
  '#755538',
  '#2f5f5d',
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

  const estilo = {
    '--repliker-principal':
      principal,

    '--repliker-secundario':
      secundario,

    '--repliker-piel':
      piel[0],

    '--repliker-piel-sombra':
      piel[1],

    '--repliker-cabello':
      cabello,

    '--repliker-iris':
      iris,

    '--repliker-retardo':
      `${(hash % 8) * -0.16}s`,
  } as CSSProperties


  if (appearance.avatar_url) {
    return (
      <div
        className={[
          'repliker-ai-avatar',
          `avatar-${size}`,
          'repliker-humano',
          `repliker-humano-${tamano}`,
          `repliker-fondo-${fondo}`,
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


  return (
    <div
      className={[
        'repliker-ai-avatar',
        `avatar-${size}`,
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
      aria-label={`Representacion de ${name}`}
    >
      <div
        className="repliker-humano-fondo"
        aria-hidden="true"
      />

      <div
        className="repliker-humano-aura"
        aria-hidden="true"
      />

      <div
        className="repliker-humano-busto"
        aria-hidden="true"
      >
        <div className="repliker-humano-torso">
          <span className="repliker-humano-camisa" />

          <span className="repliker-humano-solapa izquierda" />

          <span className="repliker-humano-solapa derecha" />
        </div>

        <div className="repliker-humano-cuello" />

        <span className="repliker-humano-oreja izquierda" />

        <span className="repliker-humano-oreja derecha" />

        <div
          className={[
            'repliker-humano-cara',
            `repliker-rostro-${rostro}`,
          ].join(' ')}
        >
          <div
            className={[
              'repliker-humano-cabello',
              `repliker-cabello-${varianteCabello}`,
            ].join(' ')}
          >
            <span />
            <span />
            <span />
          </div>

          <div className="repliker-humano-cejas">
            <span />
            <span />
          </div>

          <div
            className={[
              'repliker-humano-ojos',
              `repliker-mirada-${mirada}`,
            ].join(' ')}
          >
            <span>
              <i />
            </span>

            <span>
              <i />
            </span>
          </div>

          <span className="repliker-humano-nariz" />

          <span className="repliker-humano-boca" />

          {appearance.accessory ===
            'visor' && (
            <div className="repliker-humano-gafas">
              <span />
              <i />
              <span />
            </div>
          )}

          {appearance.accessory ===
            'antenna' && (
            <span className="repliker-humano-broche" />
          )}

          {appearance.accessory ===
            'halo' && (
            <span className="repliker-humano-diadema" />
          )}
        </div>

        {appearance.accessory ===
          'headphones' && (
          <div className="repliker-humano-auriculares">
            <span className="izquierda" />
            <span className="derecha" />
          </div>
        )}
      </div>

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
