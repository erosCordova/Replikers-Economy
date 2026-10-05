import {
  ImagePlus,
} from 'lucide-react'

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


function tamanoVisible(
  value:
    | 'small'
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
  const tamano =
    tamanoVisible(size)

  const avatarUrl =
    appearance.avatar_url?.trim()
    || ''


  if (avatarUrl) {
    return (
      <div
        className={[
          'repliker-ai-avatar',
          'repliker-foto',
          `repliker-foto-${tamano}`,
          active
            ? 'repliker-foto-activo'
            : '',
        ].join(' ')}
        title={name}
      >
        <img
          className="repliker-foto-imagen"
          src={avatarUrl}
          alt={`Foto de ${name}`}
        />

        <span
          className={[
            'repliker-foto-estado',
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
        'repliker-foto',
        'repliker-foto-vacia',
        `repliker-foto-${tamano}`,
        active
          ? 'repliker-foto-activo'
          : '',
      ].join(' ')}
      title={`${name} - Agregar foto`}
      role="img"
      aria-label={`${name} sin foto. Agregar foto.`}
    >
      <ImagePlus
        className="repliker-foto-icono"
        aria-hidden="true"
      />

      {size !== 'small' && (
        <span className="repliker-foto-texto">
          Agregar foto
        </span>
      )}

      <span
        className={[
          'repliker-foto-estado',
          active
            ? 'activo'
            : '',
        ].join(' ')}
        aria-hidden="true"
      />
    </div>
  )
}
