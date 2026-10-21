import { useEffect, useRef, useState } from 'react'
import Icon from '../components/Icon'
import { Link } from '../components/ui'
import { useAuth } from '../lib/auth-context'
import { ORIGIN, buildGlobe, clamp, drawGlobe, projectFrontDots, spinFacing } from '../lib/globe'
import {
  T, buildParticles, drawDrop, drawDroplet, drawParticles, drawSplash, easeInOutCubic, easeOutBack,
  easeOutCubic, introLayout, makeSplash, progress, sampleTitle,
} from '../lib/landingScene'
import teaExportLogo from '../assets/teaexport-logo.png'

const INTRO_KEY = 'teaexport.introPlayed'
const INTRO_TILT = 0.36
const HORIZON_TILT = -0.62
const SPIN_END = spinFacing(ORIGIN.lon) + 0.25
const SPIN_START = SPIN_END - Math.PI * 2.3

const features = [
  { icon: 'trend', title: 'Demand forecasting', text: '12-month ML export demand outlook by market.' },
  { icon: 'bars', title: 'Market intelligence', text: 'Auction prices, buyers and zone quality signals.' },
  { icon: 'clipboard', title: 'Export readiness', text: 'An explainable readiness index for every batch.' },
  { icon: 'shield', title: 'Digital tea passport', text: 'QR-verified, hash-linked batch traceability.' },
]

const prefersReducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

function introAlreadyPlayed() {
  try {
    return window.sessionStorage.getItem(INTRO_KEY) === '1'
  } catch {
    return false
  }
}

function markIntroPlayed() {
  try {
    window.sessionStorage.setItem(INTRO_KEY, '1')
  } catch {
    // Storage unavailable: the intro simply plays again next time.
  }
}

function introSpin(t) {
  if (t < T.spin[0]) return SPIN_START + (t / T.spin[0]) * 0.12
  if (t < T.spin[1]) return SPIN_START + 0.12 + (SPIN_END - SPIN_START - 0.12) * easeInOutCubic(progress(t, T.spin))
  return SPIN_END + (t - T.spin[1]) * 0.00012
}

function TeaLeaf({ shade = 'a' }) {
  return (
    <g>
      <path d="M0 0C46 22 52 120 0 200C-52 120-46 22 0 0Z" fill={`url(#leaf-${shade})`} />
      <path d="M0 0C46 22 52 120 0 200C-52 120-46 22 0 0Z" fill="url(#leaf-sheen)" />
      <path d="M0 0C46 22 52 120 0 200C-52 120-46 22 0 0Z" fill="none" stroke="rgb(214 240 160 / 45%)" strokeWidth="1.6" strokeDasharray="2 6" />
      <path d="M0 4Q4 100 0 194" fill="none" stroke="rgb(226 246 184 / 70%)" strokeWidth="2.2" strokeLinecap="round" />
      <g fill="none" stroke="rgb(222 244 178 / 38%)" strokeWidth="1.3" strokeLinecap="round">
        <path d="M1 30Q12 38 24 56M-1 30Q-12 38-24 56" />
        <path d="M1 62Q15 72 29 92M-1 62Q-15 72-29 92" />
        <path d="M1 96Q14 106 27 128M-1 96Q-14 106-27 128" />
        <path d="M1 128Q10 138 17 156M-1 128Q-10 138-17 156" />
        <path d="M1 156Q6 166 10 180M-1 156Q-6 166-10 180" />
      </g>
    </g>
  )
}

/** Tea branch ("two leaves and a bud") with the hanging leaf whose tip releases the drop. */
function TeaBranch() {
  return (
    <svg className="landing-branch" viewBox="0 0 640 360" aria-hidden="true">
      <defs>
        <linearGradient id="leaf-a" x1="0" y1="0" x2="0.5" y2="1">
          <stop offset="0" stopColor="#b5df63" />
          <stop offset="0.55" stopColor="#6aa936" />
          <stop offset="1" stopColor="#2f6d22" />
        </linearGradient>
        <linearGradient id="leaf-b" x1="0" y1="0" x2="0.4" y2="1">
          <stop offset="0" stopColor="#7fb446" />
          <stop offset="1" stopColor="#264f1c" />
        </linearGradient>
        <linearGradient id="leaf-sheen" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#fff" stopOpacity="0" />
          <stop offset="0.38" stopColor="#fff" stopOpacity="0.16" />
          <stop offset="0.5" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="stem" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#6d8f3a" />
          <stop offset="0.45" stopColor="#7c3b2b" />
          <stop offset="1" stopColor="#4a2419" />
        </linearGradient>
        <radialGradient id="dew" cx="0.35" cy="0.35" r="0.7">
          <stop offset="0" stopColor="#fff" stopOpacity="0.95" />
          <stop offset="1" stopColor="#c6efd8" stopOpacity="0.25" />
        </radialGradient>
        <filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="3" /></filter>
      </defs>
      {/* Out-of-focus leaf behind the branch. */}
      <g transform="translate(560 30) rotate(-50) scale(0.72)" filter="url(#soft)" opacity="0.7"><TeaLeaf shade="b" /></g>
      <path d="M680 18C580 36 486 72 404 94C352 108 300 112 248 104C186 94 136 72 84 60" fill="none" stroke="url(#stem)" strokeWidth="7" strokeLinecap="round" />
      <path d="M318 110Q322 124 322 142" fill="none" stroke="#5a2a1d" strokeWidth="4" strokeLinecap="round" />
      <g transform="translate(450 84) rotate(-125) scale(0.78)"><TeaLeaf /></g>
      <g transform="translate(212 100) rotate(40) scale(0.72)"><TeaLeaf shade="b" /></g>
      {/* Two leaves and a bud at the tip of the shoot. */}
      <g transform="translate(118 68) rotate(155) scale(0.48)"><TeaLeaf /></g>
      <g transform="translate(86 60) rotate(108) scale(0.32 0.42)"><TeaLeaf /></g>
      <g className="landing-branch-hang">
        <g transform="translate(322 142) rotate(-2.2) scale(1.05)"><TeaLeaf /></g>
      </g>
      <circle cx="420" cy="138" r="5" fill="url(#dew)" />
      <circle cx="232" cy="150" r="3.5" fill="url(#dew)" />
      <circle cx="300" cy="212" r="3" fill="url(#dew)" />
    </svg>
  )
}

export default function LandingPage() {
  const { user } = useAuth()
  const stageRef = useRef(null)
  const canvasRef = useRef(null)
  const titleRef = useRef(null)
  const [run, setRun] = useState(() => ({ id: 0, intro: !introAlreadyPlayed() && !prefersReducedMotion() }))
  const [stage, setStage] = useState(run.intro ? 'intro' : 'ready')

  useEffect(() => {
    const canvas = canvasRef.current
    const root = stageRef.current
    const ctx = canvas.getContext('2d')
    const reduced = prefersReducedMotion()
    const intro = run.intro
    const small = buildGlobe(16000)
    const large = buildGlobe(52000)
    let layout = null
    let dpr = 1
    let raf = 0
    let splash = null
    let particles = null
    const start = performance.now()
    const timers = []

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      layout = introLayout(window.innerWidth, window.innerHeight)
      canvas.width = Math.round(layout.W * dpr)
      canvas.height = Math.round(layout.H * dpr)
      const { left, top, width } = layout.branch
      root.style.setProperty('--branch-left', `${left}px`)
      root.style.setProperty('--branch-top', `${top}px`)
      root.style.setProperty('--branch-width', `${width}px`)
      if (reduced) frame(performance.now())
    }

    function frame(now) {
      // Without the intro the horizon globe still rises in; reduced motion shows the final frame.
      const t = intro ? now - start : reduced ? T.end : T.horizonIn[0] + (now - start)
      const L = layout
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, L.W, L.H)

      if (intro && t < T.globeOut[1]) {
        const out = easeInOutCubic(progress(t, T.globeOut))
        const lit = progress(t, [T.fall[1] - 150, T.reveal[1]])
        drawGlobe(ctx, small, {
          cx: L.cx,
          cy: L.cy,
          R: L.R * (1 - out * 0.18),
          spin: introSpin(t),
          tilt: INTRO_TILT,
          alpha: easeOutCubic(progress(t, T.globeIn)) * (1 - out),
          lit,
          reveal: t < T.fall[1] ? -1 : easeOutCubic(progress(t, T.reveal)) * Math.PI * 1.05,
          routes: progress(t, T.routes),
          time: t / 1000,
        })
      }

      if (intro && t < T.fall[1] + 120) {
        const tipY = L.tipY
        const r = L.dropR * easeOutBack(progress(t, T.dropGrow))
        const impactY = L.cy - L.R
        const fall = progress(t, T.fall)
        if (t < T.fall[1]) {
          const wobble = t < T.fall[0] ? Math.sin(t / 90) * 0.06 * (1 - progress(t, T.dropGrow)) : 0
          const y = tipY + r * 1.3 + (impactY - r - tipY - r * 1.3) * fall * fall
          drawDrop(ctx, L.cx, y, r, wobble + fall * 0.55, t)
        }
        // Two smaller droplets shaken loose behind the main drop.
        ;[[110, 0.32], [210, 0.2]].forEach(([lag, size]) => {
          const p = clamp((t - T.fall[0] - lag) / (T.fall[1] - T.fall[0]))
          const y = tipY + 4 + (impactY - tipY) * p * p
          if (p > 0 && y < impactY) drawDroplet(ctx, L.cx, y, L.dropR * size)
        })
      }

      if (intro && t >= T.fall[1] && t < T.fall[1] + 1200) {
        splash ||= makeSplash(L)
        drawSplash(ctx, splash, L, t - T.fall[1])
      }

      if (intro && t >= T.morph[0] && t < T.particlesOut[1]) {
        if (!particles && titleRef.current) {
          const sources = projectFrontDots(small, { cx: L.cx, cy: L.cy, R: L.R, spin: introSpin(t), tilt: INTRO_TILT })
          particles = buildParticles(sources, sampleTitle(titleRef.current)) || { buckets: [] }
        }
        drawParticles(ctx, particles, progress(t, T.morph), 1 - progress(t, T.particlesOut))
      }

      const rise = easeOutCubic(progress(t, T.horizonIn))
      if (rise > 0) {
        drawGlobe(ctx, large, {
          cx: L.cx,
          cy: L.horizonCy + (1 - rise) * L.horizonR * 0.45,
          R: L.horizonR,
          spin: spinFacing(ORIGIN.lon - 30) + (reduced ? 0 : (t - T.horizonIn[0]) * 0.00004),
          tilt: HORIZON_TILT,
          alpha: rise * 0.92,
          backDots: false,
          routes: rise,
          routeLift: 0.22,
          routeAlpha: 0.55,
          time: reduced ? 0.6 : t / 1000,
        })
      }

      if (!reduced) raf = requestAnimationFrame(frame)
    }

    resize()
    window.addEventListener('resize', resize)
    if (!reduced) raf = requestAnimationFrame(frame)

    if (intro) {
      markIntroPlayed()
      window.scrollTo(0, 0)
      document.body.classList.add('no-scroll')
      timers.push(window.setTimeout(() => setStage('title'), T.titleIn))
      timers.push(window.setTimeout(() => {
        setStage('ready')
        document.body.classList.remove('no-scroll')
      }, T.ready))
    }

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      timers.forEach((timer) => window.clearTimeout(timer))
      document.body.classList.remove('no-scroll')
    }
  }, [run])

  useEffect(() => {
    if (stage !== 'intro') return undefined
    const onKey = (event) => {
      if (event.key !== 'Escape') return
      setRun((current) => ({ id: current.id + 1, intro: false }))
      setStage('ready')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [stage])

  function skipIntro() {
    setRun((current) => ({ id: current.id + 1, intro: false }))
    setStage('ready')
  }

  function replayIntro() {
    setRun((current) => ({ id: current.id + 1, intro: true }))
    setStage('intro')
  }

  return (
    <main ref={stageRef} className="landing" data-stage={stage}>
      <div className="landing-bokeh" aria-hidden="true"><i /><i /><i /><i /><i /><i /></div>
      {stage === 'intro' && <TeaBranch key={run.id} />}
      <canvas ref={canvasRef} className="landing-canvas" aria-hidden="true" />

      <header className="landing-nav landing-reveal" style={{ '--d': '0ms' }}>
        <Link to="/" className="landing-brand">
          <img src={teaExportLogo} alt="" />
          <span><strong>CeylonTea IQ</strong><small>Sri Lanka Tea Intelligence</small></span>
        </Link>
        <nav className="landing-nav-actions" aria-label="Account">
          {user ? (
            <Link to="/" className="btn landing-btn-primary">Open workspace<Icon name="arrowRight" size={17} /></Link>
          ) : (
            <>
              <Link to="/login" className="btn landing-btn-ghost">Sign in</Link>
              <Link to="/signup" className="btn landing-btn-primary landing-nav-cta">Create account</Link>
            </>
          )}
        </nav>
      </header>

      <section className="landing-hero" aria-labelledby="landing-title">
        <h1 id="landing-title" ref={titleRef} className="landing-title">
          <span className="landing-kicker landing-reveal" style={{ '--d': '0ms' }}>
            <Icon name="leaf" size={15} />AI Smart · Ceylon Tea Intelligence
          </span>
          <span className="landing-title-main"><span data-word="">CeylonTea</span> <span data-word="">IQ</span></span>
        </h1>
        <p className="landing-tagline landing-reveal" style={{ '--d': '120ms' }}>
          From the estate to every export market — forecast demand, read auction prices, check export
          readiness and prove each batch&apos;s journey in one intelligent workspace.
        </p>
        <div className="landing-cta landing-reveal" style={{ '--d': '220ms' }}>
          <Link to={user ? '/' : '/signup'} className="btn landing-btn-primary landing-btn-lg">
            {user ? 'Open workspace' : 'Get started'}<Icon name="arrowRight" size={18} />
          </Link>
          {!user && <Link to="/login" className="btn landing-btn-glass landing-btn-lg">Sign in</Link>}
        </div>
      </section>

      <ul className="landing-features" aria-label="Platform modules">
        {features.map((feature, index) => (
          <li key={feature.title} className="landing-feature landing-reveal" style={{ '--d': `${320 + index * 90}ms` }}>
            <span className="landing-feature-icon"><Icon name={feature.icon} size={20} /></span>
            <span><strong>{feature.title}</strong><small>{feature.text}</small></span>
          </li>
        ))}
      </ul>

      <footer className="landing-footer landing-reveal" style={{ '--d': '700ms' }}>
        <span>© {new Date().getFullYear()} CeylonTea IQ · Sri Lanka</span>
        {!prefersReducedMotion() && (
          <button type="button" className="landing-text-button" onClick={replayIntro}>
            <Icon name="refresh" size={14} />Replay intro
          </button>
        )}
      </footer>

      {stage === 'intro' && (
        <button type="button" className="landing-skip" onClick={skipIntro}>
          Skip intro<Icon name="arrowRight" size={15} />
        </button>
      )}
    </main>
  )
}
