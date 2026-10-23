import { isLand } from './worldMask'

// Holographic dotted globe drawn on a 2D canvas: land dots, graticule and gold
// trade routes from Colombo to Sri Lanka's main tea export markets.
const DEG = Math.PI / 180
const TAU = Math.PI * 2

export const ORIGIN = { name: 'Colombo', lat: 6.93, lon: 79.85 }
export const MARKETS = [
  { name: 'London', lat: 51.5, lon: -0.13 },
  { name: 'Hamburg', lat: 53.55, lon: 9.99 },
  { name: 'Moscow', lat: 55.75, lon: 37.62 },
  { name: 'Istanbul', lat: 41.01, lon: 28.98 },
  { name: 'Baghdad', lat: 33.31, lon: 44.37 },
  { name: 'Tehran', lat: 35.69, lon: 51.39 },
  { name: 'Dubai', lat: 25.2, lon: 55.27 },
  { name: 'Shanghai', lat: 31.23, lon: 121.47 },
  { name: 'Tokyo', lat: 35.68, lon: 139.69 },
  { name: 'Sydney', lat: -33.87, lon: 151.21 },
  { name: 'New York', lat: 40.71, lon: -74.0 },
]

export const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value))

export function toVec(lat, lon) {
  const la = lat * DEG
  const lo = lon * DEG
  return [Math.cos(la) * Math.sin(lo), Math.sin(la), Math.cos(la) * Math.cos(lo)]
}

/** Spin angle that turns the given longitude to face the viewer. */
export const spinFacing = (lon) => -lon * DEG

function arc(a, b, steps = 64) {
  const omega = Math.acos(clamp(a[0] * b[0] + a[1] * b[1] + a[2] * b[2], -1, 1))
  const lift = 0.05 + omega * 0.15
  const sin = Math.sin(omega)
  const points = []
  for (let i = 0; i <= steps; i++) {
    const f = i / steps
    const wa = Math.sin((1 - f) * omega) / sin
    const wb = Math.sin(f * omega) / sin
    const h = 1 + lift * Math.sin(Math.PI * f)
    points.push([(a[0] * wa + b[0] * wb) * h, (a[1] * wa + b[1] * wb) * h, (a[2] * wa + b[2] * wb) * h])
  }
  return points
}

const cache = new Map()

/** Evenly spread sample points (Fibonacci sphere), keeping only those on land. */
export function buildGlobe(samples = 14000) {
  if (cache.has(samples)) return cache.get(samples)
  const golden = Math.PI * (3 - Math.sqrt(5))
  const dots = []
  for (let i = 0; i < samples; i++) {
    const y = 1 - (2 * (i + 0.5)) / samples
    const r = Math.sqrt(1 - y * y)
    const x = r * Math.sin(golden * i)
    const z = r * Math.cos(golden * i)
    if (isLand(Math.asin(y) / DEG, Math.atan2(x, z) / DEG)) dots.push(x, y, z)
  }
  const graticule = []
  for (let lon = -180; lon < 180; lon += 20) {
    const line = []
    for (let lat = -90; lat <= 90; lat += 3) line.push(toVec(lat, lon))
    graticule.push(line)
  }
  for (let lat = -60; lat <= 60; lat += 20) {
    const line = []
    for (let lon = -180; lon <= 180; lon += 3) line.push(toVec(lat, lon))
    graticule.push(line)
  }
  const origin = toVec(ORIGIN.lat, ORIGIN.lon)
  const globe = {
    dots: new Float32Array(dots),
    graticule,
    origin,
    routes: MARKETS.map((market) => arc(origin, toVec(market.lat, market.lon))),
  }
  cache.set(samples, globe)
  return globe
}

/** Model → view space: spin about the polar axis, then tilt the north pole toward the viewer. */
function viewer(spin, tilt) {
  const cs = Math.cos(spin)
  const ss = Math.sin(spin)
  const ct = Math.cos(tilt)
  const st = Math.sin(tilt)
  return (x, y, z, out) => {
    const x1 = x * cs + z * ss
    const z1 = -x * ss + z * cs
    out[0] = x1
    out[1] = y * ct - z1 * st
    out[2] = y * st + z1 * ct
    return out
  }
}

// A point above the surface is hidden only when it is behind the sphere's disc.
const visible = (p) => p[2] > 0 || p[0] * p[0] + p[1] * p[1] > 1

/** Screen positions of the land dots currently facing the viewer. */
export function projectFrontDots(globe, { cx, cy, R, spin, tilt = 0.36 }) {
  const view = viewer(spin, tilt)
  const p = [0, 0, 0]
  const out = []
  const d = globe.dots
  for (let i = 0; i < d.length; i += 3) {
    view(d[i], d[i + 1], d[i + 2], p)
    if (p[2] > 0.05) out.push([cx + R * p[0], cy - R * p[1], p[2]])
  }
  return out
}

/**
 * Draw the globe.
 * - lit: 0..1 brightness of the shell (graticule, rim) before the dots light up
 * - reveal: angle (radians) from the top of the sphere within which land dots are shown; null = all
 * - routes: 0..1 growth of the trade routes; time (seconds) drives the travelling pulses
 * - routeLift / routeAlpha: flatten and dim the arcs (e.g. on a large background globe)
 */
export function drawGlobe(ctx, globe, options) {
  const { cx, cy, R, spin, tilt = 0.36, alpha = 1, lit = 1, reveal = null, routes = 1, time = 0, backDots = true, dotScale = 1, routeLift = 1, routeAlpha = 1 } = options
  if (alpha <= 0.002 || R <= 1) return
  const view = viewer(spin, tilt)
  const p = [0, 0, 0]

  ctx.save()

  // Atmosphere and translucent body.
  ctx.globalAlpha = alpha
  let gradient = ctx.createRadialGradient(cx, cy, R * 0.86, cx, cy, R * 1.3)
  gradient.addColorStop(0, `rgba(118, 224, 172, ${0.05 + 0.17 * lit})`)
  gradient.addColorStop(1, 'rgba(118, 224, 172, 0)')
  ctx.fillStyle = gradient
  ctx.beginPath()
  ctx.arc(cx, cy, R * 1.3, 0, TAU)
  ctx.fill()

  gradient = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.42, R * 0.08, cx, cy, R)
  gradient.addColorStop(0, 'rgba(46, 108, 78, 0.5)')
  gradient.addColorStop(0.65, 'rgba(12, 44, 31, 0.62)')
  gradient.addColorStop(1, 'rgba(4, 22, 15, 0.8)')
  ctx.fillStyle = gradient
  ctx.beginPath()
  ctx.arc(cx, cy, R, 0, TAU)
  ctx.fill()

  // Graticule: far side faint, near side brighter.
  ctx.lineWidth = Math.max(0.6, Math.min(1.2, R / 380))
  for (const front of [false, true]) {
    ctx.beginPath()
    for (const line of globe.graticule) {
      let px = 0
      let py = 0
      let pz = 0
      line.forEach((v, index) => {
        view(v[0], v[1], v[2], p)
        const x = cx + R * p[0]
        const y = cy - R * p[1]
        if (index > 0 && (pz + p[2] > 0) === front) {
          ctx.moveTo(px, py)
          ctx.lineTo(x, y)
        }
        px = x
        py = y
        pz = p[2]
      })
    }
    ctx.strokeStyle = front ? `rgba(176, 236, 206, ${0.07 + 0.11 * lit})` : `rgba(176, 236, 206, ${0.02 + 0.04 * lit})`
    ctx.stroke()
  }

  // Land dots with depth shading; the reveal wavefront glows as it sweeps across.
  const d = globe.dots
  const size = clamp(R / 210, 1, 2.1) * dotScale
  ctx.fillStyle = 'rgb(210, 248, 227)'
  for (let i = 0; i < d.length; i += 3) {
    view(d[i], d[i + 1], d[i + 2], p)
    const front = p[2] > 0
    if (!front && !backDots) continue
    let a = front ? 0.22 + 0.78 * p[2] : 0.07
    let s = front ? size * (0.65 + 0.45 * p[2]) : size * 0.6
    if (reveal != null) {
      const angle = Math.acos(clamp(p[1], -1, 1))
      if (angle > reveal) continue
      const edge = reveal - angle
      if (edge < 0.3 && reveal < Math.PI) {
        a = Math.min(1, a + (1 - edge / 0.3) * 0.9)
        s *= 1 + (1 - edge / 0.3) * 0.8
      }
    }
    ctx.globalAlpha = alpha * a
    ctx.fillRect(cx + R * p[0] - s / 2, cy - R * p[1] - s / 2, s, s)
  }

  // Rim light.
  ctx.globalAlpha = alpha * (0.35 + 0.65 * lit)
  gradient = ctx.createLinearGradient(cx - R, cy - R, cx + R, cy + R)
  gradient.addColorStop(0, 'rgba(206, 255, 228, 0.6)')
  gradient.addColorStop(0.5, 'rgba(206, 255, 228, 0.06)')
  gradient.addColorStop(1, 'rgba(206, 255, 228, 0.28)')
  ctx.strokeStyle = gradient
  ctx.lineWidth = Math.max(1, R / 200)
  ctx.beginPath()
  ctx.arc(cx, cy, R, 0, TAU)
  ctx.stroke()

  if (routes > 0) drawRoutes(ctx, globe, liftedView(view, routeLift), { cx, cy, R, alpha: alpha * routeAlpha, routes, time })
  ctx.restore()
}

// Scale each arc point's height above the surface by `lift` before projecting.
function liftedView(view, lift) {
  if (lift === 1) return view
  return (x, y, z, out) => {
    const length = Math.hypot(x, y, z)
    const f = (1 + (length - 1) * lift) / length
    return view(x * f, y * f, z * f, out)
  }
}

function drawRoutes(ctx, globe, view, { cx, cy, R, alpha, routes, time }) {
  const p = [0, 0, 0]
  const width = clamp(R / 170, 1, 2.4)
  const count = globe.routes.length

  globe.routes.forEach((points, k) => {
    const grow = clamp((routes - (k / count) * 0.45) / 0.55)
    const last = Math.floor(grow * (points.length - 1))
    if (last < 1) return

    ctx.beginPath()
    let wasVisible = false
    for (let i = 0; i <= last; i++) {
      const v = points[i]
      view(v[0], v[1], v[2], p)
      const isVisible = visible(p)
      const x = cx + R * p[0]
      const y = cy - R * p[1]
      if (isVisible && wasVisible) ctx.lineTo(x, y)
      else if (isVisible) ctx.moveTo(x, y)
      wasVisible = isVisible
    }
    ctx.globalAlpha = alpha * 0.6
    ctx.strokeStyle = 'rgb(232, 205, 140)'
    ctx.lineWidth = width
    ctx.stroke()

    // Growing head while drawing in, then a pulse that travels Colombo → market.
    const head = grow < 1 ? last : Math.floor(((time * 0.32 + k * 0.137) % 1) * (points.length - 1))
    for (let j = 0; j < 6; j++) {
      const v = points[Math.max(0, head - j * 2)]
      view(v[0], v[1], v[2], p)
      if (!visible(p)) continue
      ctx.globalAlpha = alpha * (1 - j / 6) * 0.9
      ctx.fillStyle = j === 0 ? '#fff6dc' : 'rgb(236, 210, 145)'
      ctx.beginPath()
      ctx.arc(cx + R * p[0], cy - R * p[1], width * (j === 0 ? 1.5 : 1.1 - j * 0.12), 0, TAU)
      ctx.fill()
    }

    // Destination marker.
    if (grow >= 1) {
      const v = points[points.length - 1]
      view(v[0], v[1], v[2], p)
      if (p[2] > 0) {
        ctx.globalAlpha = alpha * 0.85
        ctx.fillStyle = 'rgb(240, 222, 170)'
        ctx.beginPath()
        ctx.arc(cx + R * p[0], cy - R * p[1], width * 1.3, 0, TAU)
        ctx.fill()
      }
    }
  })

  // Colombo hub with an expanding pulse ring.
  const o = globe.origin
  view(o[0], o[1], o[2], p)
  if (p[2] > 0) {
    const x = cx + R * p[0]
    const y = cy - R * p[1]
    const phase = (time * 0.7) % 1
    ctx.globalAlpha = alpha * (1 - phase) * 0.8
    ctx.strokeStyle = 'rgb(240, 214, 150)'
    ctx.lineWidth = Math.max(1, width * 0.7)
    ctx.beginPath()
    ctx.arc(x, y, width * (2 + phase * 7), 0, TAU)
    ctx.stroke()
    ctx.globalAlpha = alpha
    ctx.fillStyle = '#fff3d1'
    ctx.beginPath()
    ctx.arc(x, y, width * 2, 0, TAU)
    ctx.fill()
  }
}
