import { useEffect, useRef, useState } from 'react'

interface Props {
  onCapture: (file: File) => void
}

/** Rear-camera photo capture using the browser's MediaDevices API — replaces
 * the old Streamlit custom HTML component with a plain React equivalent. */
export default function CameraCapture({ onCapture }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const unmountedRef = useRef(false)
  const [active, setActive] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    return () => {
      unmountedRef.current = true
      stop()
    }
  }, [])

  async function start() {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' } },
        audio: false,
      })
      // The component may have unmounted (or capture been cancelled) while
      // getUserMedia was pending — don't leave the camera running unseen.
      if (unmountedRef.current) {
        stream.getTracks().forEach((t) => t.stop())
        return
      }
      streamRef.current = stream
      // videoRef is already attached (video element is always rendered, just
      // hidden) so this never silently no-ops before the element exists.
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setActive(true)
    } catch (e) {
      setError('Could not access camera: ' + (e as Error).message)
    }
  }

  function stop() {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setActive(false)
  }

  function snap() {
    const video = videoRef.current
    if (!video) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    ctx?.drawImage(video, 0, 0)
    canvas.toBlob(
      (blob) => {
        if (blob) onCapture(new File([blob], 'camera_photo.jpg', { type: 'image/jpeg' }))
        stop()
      },
      'image/jpeg',
      0.92,
    )
  }

  if (error) return <div className="alert error">{error}</div>

  return (
    <div>
      {!active && (
        <button type="button" className="btn secondary" onClick={start}>Start Camera</button>
      )}
      {/* Always mounted (just hidden) so videoRef exists before start() runs —
          conditionally mounting this broke capture: the ref was still null at
          the moment srcObject was assigned. */}
      <div style={{ display: active ? 'block' : 'none' }}>
        <video
          ref={videoRef}
          style={{ width: '100%', borderRadius: 'var(--radius-md)', border: '1px solid var(--line)' }}
          playsInline
          muted
        />
        <div className="row" style={{ marginTop: 'var(--space-3)' }}>
          <button type="button" className="btn" onClick={snap}>Capture</button>
          <button type="button" className="btn secondary" onClick={stop}>Cancel</button>
        </div>
      </div>
    </div>
  )
}
