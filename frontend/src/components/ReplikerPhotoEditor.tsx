import {
  ImagePlus,
  LoaderCircle,
  Trash2,
} from 'lucide-react'

import {
  useState,
} from 'react'

import { api } from '../api'

import ReplikerHumano from './ReplikerHumano'

import '../styles/ReplikerPhotoEditor.css'


interface ReplikerPhotoEditorProps {
  replikerId: number
  name: string
  avatarUrl: string | null

  onChange:
    (value: string | null) => void
}


interface PhotoResponse {
  repliker_id: number
  avatar_url: string | null
}


const ALLOWED_TYPES =
  new Set([
    'image/jpeg',
    'image/png',
    'image/webp',
  ])


const MAX_SOURCE_BYTES =
  8 * 1024 * 1024


function loadImage(
  source: string,
) {
  return new Promise<
    HTMLImageElement
  >(
    (resolve, reject) => {
      const image =
        new Image()

      image.onload = () =>
        resolve(image)

      image.onerror = () =>
        reject(
          new Error(
            'No se pudo leer la imagen.',
          ),
        )

      image.src = source
    },
  )
}


async function optimizeImage(
  file: File,
): Promise<string> {
  if (
    !ALLOWED_TYPES.has(
      file.type,
    )
  ) {
    throw new Error(
      'Usa una imagen JPG, PNG o WebP.',
    )
  }

  if (
    file.size
    > MAX_SOURCE_BYTES
  ) {
    throw new Error(
      'La imagen original no puede '
      + 'superar 8 MB.',
    )
  }

  const objectUrl =
    URL.createObjectURL(
      file,
    )

  try {
    const image =
      await loadImage(
        objectUrl,
      )

    const outputSize = 512

    const canvas =
      document.createElement(
        'canvas',
      )

    canvas.width =
      outputSize

    canvas.height =
      outputSize

    const context =
      canvas.getContext(
        '2d',
      )

    if (!context) {
      throw new Error(
        'No se pudo preparar '
        + 'la imagen.',
      )
    }

    const sourceWidth =
      image.naturalWidth

    const sourceHeight =
      image.naturalHeight

    if (
      sourceWidth <= 0
      || sourceHeight <= 0
    ) {
      throw new Error(
        'La imagen no es válida.',
      )
    }

    const sourceRatio =
      sourceWidth
      / sourceHeight

    let sourceX = 0
    let sourceY = 0
    let cropWidth =
      sourceWidth
    let cropHeight =
      sourceHeight

    if (sourceRatio > 1) {
      cropWidth =
        sourceHeight

      sourceX =
        (
          sourceWidth
          - cropWidth
        )
        / 2

    } else if (
      sourceRatio < 1
    ) {
      cropHeight =
        sourceWidth

      sourceY =
        (
          sourceHeight
          - cropHeight
        )
        / 2
    }

    context.drawImage(
      image,
      sourceX,
      sourceY,
      cropWidth,
      cropHeight,
      0,
      0,
      outputSize,
      outputSize,
    )

    let result =
      canvas.toDataURL(
        'image/webp',
        0.84,
      )

    if (
      result.length
      > 760_000
    ) {
      result =
        canvas.toDataURL(
          'image/webp',
          0.65,
        )
    }

    return result

  } finally {
    URL.revokeObjectURL(
      objectUrl,
    )
  }
}


export default function ReplikerPhotoEditor({
  replikerId,
  name,
  avatarUrl,
  onChange,
}: ReplikerPhotoEditorProps) {
  const [
    busy,
    setBusy,
  ] = useState(false)

  const [
    message,
    setMessage,
  ] = useState('')


  async function selectPhoto(
    file: File | undefined,
  ) {
    if (!file) {
      return
    }

    setBusy(true)
    setMessage('')

    try {
      const imageDataUrl =
        await optimizeImage(
          file,
        )

      const response =
        await api.put<PhotoResponse>(
          `/replikers/${replikerId}/photo`,
          {
            image_data_url:
              imageDataUrl,
          },
        )

      onChange(
        response.data.avatar_url,
      )

      setMessage(
        'Foto actualizada correctamente.',
      )

    } catch (
      error
    ) {
      const fallback =
        error instanceof Error
          ? error.message
          : (
              'No fue posible '
              + 'actualizar la foto.'
            )

      setMessage(
        fallback,
      )

    } finally {
      setBusy(false)
    }
  }


  async function removePhoto() {
    setBusy(true)
    setMessage('')

    try {
      const response =
        await api.delete<PhotoResponse>(
          `/replikers/${replikerId}/photo`,
        )

      onChange(
        response.data.avatar_url,
      )

      setMessage(
        'Foto eliminada.',
      )

    } catch {
      setMessage(
        'No fue posible eliminar '
        + 'la foto.',
      )

    } finally {
      setBusy(false)
    }
  }


  return (
    <div
      className="repliker-photo-editor"
    >
      <ReplikerHumano
        name={name}
        size="large"
        active
        appearance={{
          avatar_style: 'none',
          primary_color: '#ffffff',
          secondary_color: '#ffffff',
          face_type: 'none',
          eye_style: 'none',
          accessory: 'none',
          background_style: 'plain',
          avatar_url:
            avatarUrl,
        }}
      />

      <div
        className="repliker-photo-editor-info"
      >
        <strong>
          Foto de identificación
        </strong>

        <span>
          Elige una imagen para reconocer
          visualmente a este Repliker.
        </span>

        <small>
          JPG, PNG o WebP. La imagen se
          ajustará automáticamente a
          512 × 512.
        </small>

        <div
          className="repliker-photo-editor-actions"
        >
          <label
            className={[
              'repliker-photo-editor-button',
              'primary',
              busy
                ? 'disabled'
                : '',
            ].join(' ')}
          >
            {busy ? (
              <LoaderCircle
                size={16}
                className="photo-spin"
              />
            ) : (
              <ImagePlus
                size={16}
              />
            )}

            {avatarUrl
              ? 'Cambiar foto'
              : 'Agregar foto'}

            <input
              type="file"
              accept={
                'image/jpeg,'
                + 'image/png,'
                + 'image/webp'
              }
              disabled={busy}
              onChange={
                (event) => {
                  const file =
                    event
                      .currentTarget
                      .files?.[0]

                  void selectPhoto(
                    file,
                  )

                  event.currentTarget
                    .value = ''
                }
              }
            />
          </label>

          {avatarUrl && (
            <button
              type="button"
              className={
                'repliker-photo-editor-button danger'
              }
              disabled={busy}
              onClick={() =>
                void removePhoto()
              }
            >
              <Trash2 size={16} />

              Eliminar foto
            </button>
          )}
        </div>

        {message && (
          <p
            className="repliker-photo-editor-message"
          >
            {message}
          </p>
        )}
      </div>
    </div>
  )
}
