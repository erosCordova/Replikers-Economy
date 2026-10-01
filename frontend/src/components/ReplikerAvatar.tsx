import type { CSSProperties } from 'react'


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


interface ReplikerAvatarProps {
  appearance: ReplikerAppearance
  name: string
  size?: 'small' | 'medium' | 'large'
  active?: boolean
}


const AUTO_PALETTES = [
  ['#2563eb', '#22d3ee'],
  ['#7c3aed', '#ec4899'],
  ['#0f766e', '#34d399'],
  ['#ea580c', '#fbbf24'],
  ['#4338ca', '#38bdf8'],
  ['#be123c', '#fb7185'],
]


function nameHash(
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


function usesDefaultColors(
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


export default function ReplikerAvatar({
  appearance,
  name,
  size = 'medium',
  active = false,
}: ReplikerAvatarProps) {
  const hash =
    nameHash(name)

  const palette =
    AUTO_PALETTES[
      hash % AUTO_PALETTES.length
    ]

  const automatic =
    usesDefaultColors(appearance)

  const primaryColor =
    automatic
      ? palette[0]
      : appearance.primary_color

  const secondaryColor =
    automatic
      ? palette[1]
      : appearance.secondary_color

  const style = {
    '--avatar-primary':
      primaryColor,

    '--avatar-secondary':
      secondaryColor,

    '--avatar-delay':
      `${(hash % 8) * -0.18}s`,
  } as CSSProperties


  const automaticVariant =
    automatic
      ? `avatar-auto-${hash % 4}`
      : 'avatar-customized'


  if (appearance.avatar_url) {
    return (
      <div
        className={[
          'repliker-ai-avatar',
          `avatar-${size}`,
          automaticVariant,
        ].join(' ')}
        style={style}
        title={name}
      >
        <img
          className="repliker-avatar-image"
          src={appearance.avatar_url}
          alt={`Avatar de ${name}`}
        />

        <span
          className={
            active
              ? 'avatar-status online'
              : 'avatar-status'
          }
        />
      </div>
    )
  }


  return (
    <div
      className={[
        'repliker-ai-avatar',
        `avatar-${size}`,
        `avatar-style-${appearance.avatar_style}`,
        `avatar-background-${appearance.background_style}`,
        `avatar-face-${appearance.face_type}`,
        automaticVariant,
        active
          ? 'avatar-agent-active'
          : '',
      ].join(' ')}
      style={style}
      title={name}
    >
      <div className="avatar-atmosphere" />

      <div className="avatar-grid-layer" />

      <div className="avatar-energy-ring" />

      {appearance.accessory ===
        'halo' && (
        <div className="avatar-halo" />
      )}

      {appearance.accessory ===
        'antenna' && (
        <div className="avatar-antenna">
          <span />
        </div>
      )}

      {appearance.accessory ===
        'headphones' && (
        <>
          <div className="avatar-headphone-band" />

          <div className="avatar-headphone left" />

          <div className="avatar-headphone right" />
        </>
      )}


      <div className="avatar-neck" />


      <div className="avatar-head">
        <div className="avatar-temple left" />

        <div className="avatar-temple right" />

        <div className="avatar-face-panel">
          <div
            className={
              `avatar-eyes eyes-${appearance.eye_style}`
            }
          >
            <span />
            <span />
          </div>

          <div className="avatar-nose" />

          <div className="avatar-mouth">
            <span />
            <span />
            <span />
          </div>
        </div>


        {appearance.accessory ===
          'visor' && (
          <div className="avatar-visor" />
        )}


        <div className="avatar-core">
          <span />
        </div>
      </div>


      <div className="avatar-shoulders">
        <div className="avatar-shoulder left" />

        <div className="avatar-chest-core" />

        <div className="avatar-shoulder right" />
      </div>


      <span
        className={
          active
            ? 'avatar-status online'
            : 'avatar-status'
        }
      />
    </div>
  )
}
