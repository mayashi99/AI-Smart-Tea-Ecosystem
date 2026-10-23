import { clamp } from './globe'

// Landing intro: a drop with a tea leaf inside falls from a tea branch onto the
// globe, the globe lights up and spins, then its dots fly into the title.
// All times are milliseconds from the start of the intro.
export const T = {
  globeIn: [150, 1000],
  dropGrow: [500, 1350],
  fall: [1350, 2050], // impact at fall[1]
  reveal: [2050, 3050],
  spin: [2050, 5000],
  routes: [3300, 4800],
  morph: [5000, 6700],
  globeOut: [5000, 5700],
  titleIn: 6400,
  particlesOut: [6600, 7400],
  ready: 6900,
  horizonIn: [6800, 8400],
  end: 8400,
}

// The branch artwork is 640 × 360; the hanging leaf's tip sits at (330, 352).
export const BRANCH = { width: 640, height: 360, tipX: 330, tipY: 352 }

export const progress = (t, [from, to]) => clamp((t - from) / (to - from))
export const easeOutCubic = (x) => 1 - (1 - x) ** 3
export const easeInOutCubic = (x) => (x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2)
export const easeOutBack = (x) => 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2

export function introLayout(W, H) {
  const scale = Math.min(460, W * 0.8) / BRANCH.width
  const tipY = Math.max(BRANCH.tipY * scale * 0.95, H * 0.16)
  let R = Math.min(W * 0.3, H * 0.24)
  let cy = Math.max(H * 0.6, tipY + Math.max(90, H * 0.18) + R)
  if (cy + R > H - 12) {
    R = Math.max(60, (H - 12 - tipY - 90) / 2)
    cy = tipY + 90 + R
  }
  // Final "horizon" globe: a large planet rising from the bottom edge.
  const horizonR = Math.max(W * 0.7, H * 0.75)
  return {
    W, H, cx: W / 2, cy, R, tipY, scale,
    dropR: clamp(R * 0.085, 9, 19),
    horizonR,
    horizonCy: H * 0.62 + horizonR,
    branch: { left: W / 2 - BRANCH.tipX * scale, top: tipY - BRANCH.tipY * scale, width: BRANCH.width * scale },
  }
}

function leafPath(ctx, x, y, length, angle) {
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(angle)
  const w = length * 0.36
  ctx.beginPath()
  ctx.moveTo(0, -length / 2)
  ctx.bezierCurveTo(w, -length * 0.3, w * 0.9, length * 0.25, 0, length / 2)
  ctx.bezierCurveTo(-w * 0.9, length * 0.25, -w, -length * 0.3, 0, -length / 2)
  ctx.restore()
}

/** Teardrop with a tiny tea leaf refracted inside it. stretch elongates it while falling. */
export function drawDrop(ctx, x, y, r, stretch, time) {
  if (r <= 0.5) return
  const top = y - r * (1.35 + stretch)
  ctx.save()
  const halo = ctx.createRadialGradient(x, y, r * 0.5, x, y, r * 3)
  halo.addColorStop(0, 'rgba(196, 255, 222, 0.3)')
  halo.addColorStop(1, 'rgba(196, 255, 222, 0)')
  ctx.fillStyle = halo
  ctx.beginPath()
  ctx.arc(x, y, r * 3, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.moveTo(x, top)
  ctx.bezierCurveTo(x + r * 0.35, top + r * 0.65, x + r, y - r * 0.55, x + r, y)
  ctx.arc(x, y, r, 0, Math.PI)
  ctx.bezierCurveTo(x - r, y - r * 0.55, x - r * 0.35, top + r * 0.65, x, top)
  ctx.closePath()

  const body = ctx.createRadialGradient(x - r * 0.3, y - r * 0.25, r * 0.1, x, y, r * 1.2)
  body.addColorStop(0, 'rgba(236, 255, 244, 0.55)')
  body.addColorStop(0.55, 'rgba(150, 222, 186, 0.22)')
  body.addColorStop(1, 'rgba(40, 120, 84, 0.45)')
  ctx.fillStyle = body
  ctx.fill()
  ctx.save()
  ctx.clip()
  // The leaf inside, gently turning as the drop falls.
  leafPath(ctx, x, y + r * 0.1, r * 1.25, -0.6 + Math.sin(time / 260) * 0.25)
  const leaf = ctx.createLinearGradient(x - r, y - r, x + r, y + r)
  leaf.addColorStop(0, 'rgba(178, 222, 96, 0.95)')
  leaf.addColorStop(1, 'rgba(58, 128, 44, 0.95)')
  ctx.fillStyle = leaf
  ctx.fill()
  ctx.restore()
  ctx.lineWidth = Math.max(1, r / 10)
  ctx.strokeStyle = 'rgba(225, 255, 238, 0.75)'
  ctx.stroke()
  // Specular highlights.
  ctx.fillStyle = 'rgba(255, 255, 255, 0.85)'
  ctx.beginPath()
  ctx.ellipse(x - r * 0.42, y - r * 0.28, r * 0.16, r * 0.3, 0.5, 0, Math.PI * 2)
  ctx.fill()
  ctx.globalAlpha = 0.5
  ctx.beginPath()
  ctx.arc(x + r * 0.45, y + r * 0.42, r * 0.09, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

export function drawDroplet(ctx, x, y, r) {
  const g = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, 0, x, y, r)
  g.addColorStop(0, 'rgba(255, 255, 255, 0.95)')
  g.addColorStop(1, 'rgba(160, 230, 196, 0.35)')
  ctx.fillStyle = g
  ctx.beginPath()
  ctx.arc(x, y, r, 0, Math.PI * 2)
  ctx.fill()
}

export function makeSplash(layout) {
  const unit = layout.R / 220
  return Array.from({ length: 16 }, (_, index) => {
    const side = index % 2 ? 1 : -1
    return {
      vx: side * (40 + Math.random() * 170) * unit,
      vy: -(90 + Math.random() * 200) * unit,
      r: (1.2 + Math.random() * 2.4) * Math.max(0.7, unit),
    }
  })
}

/** Flash, ripple rings and droplets bouncing off the top of the globe. elapsed in ms since impact. */
export function drawSplash(ctx, splash, layout, elapsed) {
  const x = layout.cx
  const y = layout.cy - layout.R
  const R = layout.R
  ctx.save()
  const flash = 1 - clamp(elapsed / 650)
  if (flash > 0) {
    const g = ctx.createRadialGradient(x, y, 0, x, y, R * 0.55)
    g.addColorStop(0, `rgba(235, 255, 244, ${0.75 * flash})`)
    g.addColorStop(1, 'rgba(235, 255, 244, 0)')
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.arc(x, y, R * 0.55, 0, Math.PI * 2)
    ctx.fill()
  }
  for (let ring = 0; ring < 3; ring++) {
    const q = clamp((elapsed - ring * 140) / 950)
    if (q <= 0 || q >= 1) continue
    const rx = R * (0.08 + 0.85 * easeOutCubic(q))
    ctx.globalAlpha = (1 - q) * 0.7
    ctx.strokeStyle = 'rgb(206, 250, 226)'
    ctx.lineWidth = Math.max(1, R / 160) * (1 - q * 0.6)
    ctx.beginPath()
    ctx.ellipse(x, y, rx, rx * 0.24, 0, 0, Math.PI * 2)
    ctx.stroke()
  }
  const s = elapsed / 1000
  const gravity = 980 * (R / 220)
  for (const drop of splash) {
    const life = 1 - clamp(elapsed / 800)
    if (life <= 0) break
    ctx.globalAlpha = life
    drawDroplet(ctx, x + drop.vx * s, y + drop.vy * s + 0.5 * gravity * s * s, drop.r)
  }
  ctx.restore()
}

/**
 * Rasterise the title's words (elements marked data-word) exactly where the DOM
 * lays them out, and return sample points in viewport coordinates.
 */
export function sampleTitle(element, maxPoints = 3200) {
  const words = [...element.querySelectorAll('[data-word]')]
  if (!words.length) return { points: [], step: 4 }
  const style = getComputedStyle(words[0])
  const box = element.getBoundingClientRect()
  const pad = 12
  const width = Math.ceil(box.width) + pad * 2
  const height = Math.ceil(box.height) + pad * 2
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  ctx.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
  if ('letterSpacing' in ctx && style.letterSpacing !== 'normal') ctx.letterSpacing = style.letterSpacing
  ctx.fillStyle = '#fff'
  for (const word of words) {
    const rect = word.getBoundingClientRect()
    const metrics = ctx.measureText(word.textContent)
    const ascent = metrics.fontBoundingBoxAscent || rect.height * 0.8
    ctx.fillText(word.textContent, rect.left - box.left + pad, rect.top - box.top + pad + ascent)
  }
  const data = ctx.getImageData(0, 0, width, height).data
  let ink = 0
  for (let i = 3; i < data.length; i += 4) if (data[i] > 128) ink++
  const step = Math.max(2, Math.ceil(Math.sqrt(ink / maxPoints)))
  const points = []
  for (let y = 0; y < height; y += step) {
    for (let x = 0; x < width; x += step) {
      if (data[(y * width + x) * 4 + 3] > 128) points.push([box.left - pad + x, box.top - pad + y])
    }
  }
  return { points, step, left: box.left, width: box.width }
}

// Title gradient: mint → white → tea gold (matches .landing-title-main).
const PALETTE = [[208, 246, 224], [232, 252, 240], [255, 255, 255], [246, 236, 205], [232, 205, 140]]

/** Pair globe dots with title points (both sorted left→right so the globe "unrolls"). */
export function buildParticles(sources, sample) {
  const targets = sample.points.slice().sort((a, b) => a[0] - b[0])
  const from = sources.slice().sort((a, b) => a[0] - b[0])
  if (!targets.length || !from.length) return null
  const buckets = PALETTE.map(() => [])
  targets.forEach(([tx, ty], index) => {
    const [sx, sy] = from[Math.floor((index * from.length) / targets.length)]
    const dx = tx - sx
    const dy = ty - sy
    const bend = (Math.random() - 0.5) * 0.6
    const shade = clamp((tx - sample.left) / Math.max(1, sample.width), 0, 0.999)
    buckets[Math.floor(shade * PALETTE.length)].push({
      sx: sx + (Math.random() - 0.5) * 2,
      sy: sy + (Math.random() - 0.5) * 2,
      tx,
      ty,
      // Curved flight path: control point pushed sideways from the midpoint.
      qx: sx + dx / 2 - dy * bend,
      qy: sy + dy / 2 + dx * bend - Math.abs(dx) * 0.12,
      delay: Math.random() * 0.28,
    })
  })
  return { buckets, size: sample.step * 0.75 }
}

export function drawParticles(ctx, particles, morph, fade) {
  if (!particles || fade <= 0) return
  ctx.save()
  particles.buckets.forEach((bucket, index) => {
    const [r, g, b] = PALETTE[index]
    ctx.fillStyle = `rgb(${r}, ${g}, ${b})`
    for (const p of bucket) {
      const k = easeInOutCubic(clamp((morph - p.delay) / 0.72))
      const u = 1 - k
      const x = u * u * p.sx + 2 * u * k * p.qx + k * k * p.tx
      const y = u * u * p.sy + 2 * u * k * p.qy + k * k * p.ty
      const s = 1.6 + (particles.size - 1.6) * k
      ctx.globalAlpha = fade * (0.55 + 0.45 * k)
      ctx.fillRect(x - s / 2, y - s / 2, s, s)
    }
  })
  ctx.restore()
}
