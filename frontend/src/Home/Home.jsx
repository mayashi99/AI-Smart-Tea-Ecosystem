import { Link, NavLink } from 'react-router-dom'

function LeafMark({ className = '' }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="24"
      viewBox="0 0 24 24"
      width="24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M20.8 3.2C12.5 3.4 5.8 6.4 4.2 12.1 3.2 15.7 5.5 19 9 19.4c5.7.7 9-5.6 11.8-16.2Z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path
        d="M4.5 19.5C7.5 14.8 11 11.8 17 8"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  )
}

function ArrowIcon() {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height="18"
      viewBox="0 0 24 24"
      width="18"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M5 12h14m-6-6 6 6-6 6"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  )
}

function DensityIcon() {
  return (
    <svg aria-hidden="true" fill="none" height="28" viewBox="0 0 28 28" width="28" xmlns="http://www.w3.org/2000/svg">
      <path d="M5 22V9m6 13V5m6 17V11m6 11V7" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
      <path d="M3 22h22" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
      <path d="m4 9 4-3 4 3 4-4 4 3 4-2" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
    </svg>
  )
}

function HealthIcon() {
  return (
    <svg aria-hidden="true" fill="none" height="28" viewBox="0 0 28 28" width="28" xmlns="http://www.w3.org/2000/svg">
      <path d="M14 23S4 17.4 4 10.5A5.5 5.5 0 0 1 14 8a5.5 5.5 0 0 1 10 2.5C24 17.4 14 23 14 23Z" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
      <path d="M8.5 13h3l1.5-3 2.1 6 1.4-3H20" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
    </svg>
  )
}

const navigationClass = ({ isActive }) =>
  `rounded-full px-4 py-2 text-sm font-bold transition focus:outline-none focus:ring-4 focus:ring-emerald-500/20 ${
    isActive
      ? 'bg-emerald-700 text-white shadow-md shadow-emerald-900/15'
      : 'text-slate-600 hover:bg-emerald-50 hover:text-emerald-800'
  }`

function Home() {
  return (
    <main className="min-h-screen bg-[#f4f8f4] text-slate-900">
      <nav className="border-b border-emerald-950/10 bg-white/95 backdrop-blur" aria-label="Main navigation">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-5 px-4 py-4 sm:px-6 lg:px-8">
          <Link className="flex items-center gap-3 rounded-xl focus:outline-none focus:ring-4 focus:ring-emerald-500/20" to="/">
            <span className="rounded-xl bg-emerald-700 p-2.5 text-white shadow-md shadow-emerald-900/15"><LeafMark /></span>
            <span>
              <span className="block text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-700">AI Smart</span>
              <span className="block text-base font-black tracking-tight text-slate-950">Tea Ecosystem</span>
            </span>
          </Link>
          <div className="flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 p-1" role="list">
            <NavLink className={navigationClass} role="listitem" to="/plant-density">Density</NavLink>
            <NavLink className={navigationClass} role="listitem" to="/plantation-health">Health</NavLink>
          </div>
        </div>
      </nav>

      <section className="relative overflow-hidden border-b border-emerald-950/10 bg-emerald-950">
        <div className="absolute -right-24 -top-32 h-96 w-96 rounded-full bg-emerald-700/30 blur-3xl" />
        <div className="absolute -bottom-40 left-1/3 h-80 w-80 rounded-full bg-lime-500/10 blur-3xl" />
        <div className="relative mx-auto grid w-full max-w-7xl gap-10 px-4 py-16 sm:px-6 sm:py-24 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:px-8">
          <div className="max-w-2xl text-white">
            <p className="mb-4 text-xs font-bold uppercase tracking-[0.22em] text-emerald-300">Intelligent tools for better cultivation</p>
            <h1 className="text-4xl font-black leading-tight tracking-tight sm:text-6xl">Smarter decisions for every tea plantation.</h1>
            <p className="mt-6 max-w-xl text-base leading-8 text-emerald-100/75 sm:text-lg">Plan plantation density and assess crop health with practical AI-powered tools designed for Sri Lankan tea cultivation.</p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-emerald-400 px-5 text-sm font-black text-emerald-950 transition hover:bg-emerald-300 focus:outline-none focus:ring-4 focus:ring-emerald-300/30" to="/plantation-health">Explore plantation health <ArrowIcon /></Link>
              <Link className="inline-flex h-12 items-center justify-center rounded-xl border border-white/20 px-5 text-sm font-bold text-white transition hover:bg-white/10 focus:outline-none focus:ring-4 focus:ring-white/30" to="/plant-density">Plan plant density</Link>
            </div>
          </div>
          <div className="relative hidden min-h-72 lg:block">
            <div className="absolute inset-8 rounded-[2.5rem] border border-emerald-300/20 bg-emerald-900/60 p-5 shadow-2xl shadow-black/20 rotate-[-4deg]">
              <div className="flex items-center justify-between border-b border-white/10 pb-4"><span className="text-xs font-bold uppercase tracking-[0.16em] text-emerald-300">Field intelligence</span><span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-lg shadow-emerald-300/50" /></div>
              <div className="mt-7 grid grid-cols-2 gap-3">
                <div className="rounded-2xl bg-white/10 p-4"><p className="text-xs text-emerald-200/70">Plantation health</p><p className="mt-3 text-2xl font-black text-white">AI ready</p></div>
                <div className="rounded-2xl bg-emerald-400 p-4 text-emerald-950"><p className="text-xs font-bold text-emerald-950/70">Climate insight</p><p className="mt-3 text-2xl font-black">Live</p></div>
                <div className="col-span-2 rounded-2xl border border-emerald-300/15 bg-black/10 p-4"><div className="flex items-end gap-2"><span className="h-10 w-3 rounded-t bg-emerald-400" /><span className="h-16 w-3 rounded-t bg-lime-300" /><span className="h-12 w-3 rounded-t bg-emerald-500" /><span className="h-24 w-3 rounded-t bg-emerald-300" /><span className="h-20 w-3 rounded-t bg-lime-400" /><div className="ml-3"><p className="text-xs text-emerald-200/70">Evidence-based planning</p><p className="mt-1 font-bold text-white">Grow with confidence</p></div></div></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="mb-7 max-w-2xl">
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-emerald-700">Choose a tool</p>
          <h2 className="text-3xl font-black tracking-tight text-slate-950">Start with the decision in front of you.</h2>
          <p className="mt-3 text-sm leading-7 text-slate-500">Use the navigation above or select a module below to continue.</p>
        </div>
        <div className="grid gap-5 md:grid-cols-2">
          <Link className="group rounded-3xl border border-lime-900/10 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:border-emerald-300 hover:shadow-xl hover:shadow-emerald-950/10 focus:outline-none focus:ring-4 focus:ring-emerald-600/15 sm:p-8" to="/plant-density">
            <div className="flex items-start justify-between gap-5"><span className="rounded-2xl bg-lime-100 p-4 text-lime-800"><DensityIcon /></span><span className="rounded-full bg-lime-50 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-lime-800">Planning</span></div>
            <h3 className="mt-7 text-2xl font-black tracking-tight text-slate-950">Plant Density</h3>
            <p className="mt-3 max-w-md text-sm leading-7 text-slate-500">Estimate an optimized tea bush count using land area, spacing, terrain, and plantation zone.</p>
            <span className="mt-7 inline-flex items-center gap-2 text-sm font-black text-emerald-700 transition group-hover:gap-3">Open Density <ArrowIcon /></span>
          </Link>
          <Link className="group rounded-3xl border border-emerald-900/10 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:border-emerald-300 hover:shadow-xl hover:shadow-emerald-950/10 focus:outline-none focus:ring-4 focus:ring-emerald-600/15 sm:p-8" to="/plantation-health">
            <div className="flex items-start justify-between gap-5"><span className="rounded-2xl bg-emerald-100 p-4 text-emerald-800"><HealthIcon /></span><span className="rounded-full bg-emerald-50 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-emerald-800">AI analysis</span></div>
            <h3 className="mt-7 text-2xl font-black tracking-tight text-slate-950">Plantation Health</h3>
            <p className="mt-3 max-w-md text-sm leading-7 text-slate-500">Assess plantation health and climate stress using an image, location, and analysis date.</p>
            <span className="mt-7 inline-flex items-center gap-2 text-sm font-black text-emerald-700 transition group-hover:gap-3">Open Health <ArrowIcon /></span>
          </Link>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white px-4 py-6 text-center text-xs font-medium text-slate-500 sm:px-6 lg:px-8">AI Smart Tea Ecosystem · Sustainable insight for tea cultivation</footer>
    </main>
  )
}

export default Home
