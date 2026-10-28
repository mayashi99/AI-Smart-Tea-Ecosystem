import { useEffect, useRef } from 'react'
import { ORIGIN, buildGlobe, drawGlobe, spinFacing } from '../lib/globe'

/** Self-sizing spinning globe with trade routes; pauses while hidden (zero size). */
export default function GlobeCanvas({ samples = 14000, tilt = 0.32, className = '' }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const globe = buildGlobe(samples)
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    const start = performance.now()
    let width = 0
    let height = 0
    let dpr = 1
    let raf = 0

    function draw(now) {
      raf = 0
      if (!width || !height) return
      const t = reduced ? 0 : (now - start) / 1000
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, width, height)
      drawGlobe(ctx, globe, {
        cx: width / 2,
        cy: height / 2,
        R: Math.min(width, height) * 0.38,
        routeLift: 0.6,
        spin: spinFacing(ORIGIN.lon) - 0.6 + t * 0.14,
        tilt,
        time: reduced ? 0.6 : t,
        routes: reduced ? 1 : Math.min(1, t / 2.4),
      })
      if (!reduced) raf = requestAnimationFrame(draw)
    }

    const observer = new ResizeObserver(() => {
      const rect = canvas.getBoundingClientRect()
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = rect.width
      height = rect.height
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      if (!raf) draw(performance.now())
    })
    observer.observe(canvas)

    return () => {
      cancelAnimationFrame(raf)
      observer.disconnect()
    }
  }, [samples, tilt])

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />
}
