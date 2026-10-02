import { useEffect, useRef, useState } from 'react'

interface Props {
  onCapture: (file: File) => void
}

type Quality = 'min' | 'mid' | 'max'

// Mirrors the resolution presets from the old Streamlit camera component.
const QUALITY_PRESETS: Record<Quality, { width: number; height: number; megapixels: string }> = {
  min: { width: 1920, height: 1440, megapixels: '2.8MP' },
  mid: { width: 3024, height: 2268, megapixels: '6.9MP' },
  max: { width: 4032, height: 3024, megapixels: '12MP' },
}

const QUALITY_STORAGE_KEY = 'hoaCameraQuality'

function loadSavedQuality(): Quality {
  try {
    const saved = window.localStorage.getItem(QUALITY_STORAGE_KEY)
    if (saved === 'min' || saved === 'mid' || saved === 'max') return saved
  } catch {
    // localStorage can be unavailable in private browsing — fall through
  }
  return 'min'
}

// `zoom` is a non-standard (but widely supported) MediaStreamTrack capability
// not yet in the TS DOM lib — these extend the official types to cover it.
interface ZoomCapability { min: number; max: number; step?: number }
interface CameraCapabilities extends MediaTrackCapabilities { zoom?: ZoomCapability }
interface CameraSettings extends MediaTrackSettings { zoom?: number }
interface CameraConstraintSet extends MediaTrackConstraintSet { zoom?: number }

interface ZoomState { min: number; max: number; step: number; value: number }

/** Rear-camera photo capture using the browser's MediaDevices API — replaces
 * the old Streamlit custom HTML component with a plain React equivalent.
 * Starts automatically (no separate "Start Camera" step) and carries over
 * the zoom/quality/flip controls and auto-scroll-into-view behavior from the
 * original Streamlit camera component. */
export default function CameraCapture({ onCapture }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const unmountedRef = useRef(false)
  const scrollPendingRef = useRef(false)

  const [active, setActive] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment')
  const [quality, setQuality] = useState<Quality>(loadSavedQuality)
  const [zoom, setZoom] = useState<ZoomState | null>(null)

  useEffect(() => {
    void start(facingMode, quality)
    return () => {
      unmountedRef.current = true
      stop()
    }
    // Only ever runs once, on mount — start the rear camera immediately so
    // the user never has to press a redundant "Start Camera" button.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function start(mode: 'environment' | 'user', q: Quality) {
    setError(null)
    stop()
    const preset = QUALITY_PRESETS[q]
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: mode },
          width: { ideal: preset.width },
          height: { ideal: preset.height },
        },
        audio: false,
      })
      // The component may have unmounted (or capture been cancelled) while
      // getUserMedia was pending — don't leave the camera running unseen.
      if (unmountedRef.current) {
        stream.getTracks().forEach((t) => t.stop())
        return
      }
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setActive(true)
      setupZoom(stream)
      // Scroll the preview into view once it has a frame — on mobile the
      // camera starts below the fold and was otherwise easy to miss.
      scrollPendingRef.current = true
      setTimeout(() => {
        if (scrollPendingRef.current && !unmountedRef.current) {
          scrollPendingRef.current = false
          containerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }, 400)
    } catch (e) {
      setActive(false)
      setError('Could not access camera: ' + (e as Error).message)
    }
  }

  function setupZoom(stream: MediaStream) {
    const track = stream.getVideoTracks()[0]
    const capabilities = track?.getCapabilities?.() as CameraCapabilities | undefined
    const zoomCap = capabilities?.zoom
    if (track && zoomCap && zoomCap.max > zoomCap.min) {
      const settings = track.getSettings() as CameraSettings
      setZoom({
        min: zoomCap.min,
        max: zoomCap.max,
        step: zoomCap.step || (zoomCap.max - zoomCap.min) / 200,
        value: settings.zoom ?? zoomCap.min,
      })
    } else {
      setZoom(null)
    }
  }

  function applyZoom(value: number) {
    const track = streamRef.current?.getVideoTracks()[0]
    if (!track || !zoom) return
    const clamped = Math.min(zoom.max, Math.max(zoom.min, value))
    setZoom({ ...zoom, value: clamped })
    const constraint: CameraConstraintSet = { zoom: clamped }
    track.applyConstraints({ advanced: [constraint] }).catch(() => {})
  }

  function changeQuality(q: Quality) {
    if (q === quality) return
    setQuality(q)
    try {
      window.localStorage.setItem(QUALITY_STORAGE_KEY, q)
    } catch {
      // Non-fatal — the setting just won't persist across sessions
    }
    void start(facingMode, q)
  }

  function flip() {
    const next = facingMode === 'environment' ? 'user' : 'environment'
    setFacingMode(next)
    void start(next, quality)
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

  if (error) {
    return (
      <div className="alert error">
        <span>{error}</span>
        <button type="button" className="btn secondary" onClick={() => void start(facingMode, quality)}>Retry</button>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="camera-shell">
      {!active && <div className="camera-status">Starting camera…</div>}

      <video
        ref={videoRef}
        style={{ width: '100%', borderRadius: 'var(--radius-md)', border: '1px solid var(--line)', display: active ? 'block' : 'none' }}
        playsInline
        muted
      />

      {active && (
        <>
          <div className="row camera-controls">
            <button type="button" className="btn" onClick={snap}>📷 Capture</button>
            <button type="button" className="btn secondary" onClick={flip}>🔄 Flip</button>
            <button type="button" className="btn secondary" onClick={stop}>Cancel</button>
          </div>

          {zoom && (
            <div className="camera-zoom-row">
              <span className="camera-zoom-label">🔍 {zoom.value.toFixed(1)}×</span>
              <input
                type="range"
                className="camera-zoom-slider"
                min={zoom.min}
                max={zoom.max}
                step={zoom.step}
                value={zoom.value}
                onChange={(e) => applyZoom(parseFloat(e.target.value))}
                aria-label="Camera zoom"
              />
            </div>
          )}

          <div className="camera-quality-row">
            <span className="camera-quality-label">Quality:</span>
            {(Object.keys(QUALITY_PRESETS) as Quality[]).map((q) => (
              <button
                key={q}
                type="button"
                className={`camera-quality-btn ${quality === q ? 'active' : ''}`}
                title={QUALITY_PRESETS[q].megapixels}
                onClick={() => changeQuality(q)}
              >
                {q === 'min' ? 'Min' : q === 'mid' ? 'Mid' : 'Max'}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

