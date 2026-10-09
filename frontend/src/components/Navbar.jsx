import { Link, NavLink } from 'react-router-dom'

function LeafMark({ className = '' }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height="28"
      viewBox="0 0 24 24"
      width="28"
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

const navigationClass = ({ isActive }) =>
  `whitespace-nowrap rounded-full px-3 py-2.5 text-sm font-bold transition focus:outline-none focus:ring-4 focus:ring-emerald-500/20 sm:px-5 ${
    isActive
      ? 'bg-emerald-700 text-white shadow-md shadow-emerald-900/15'
      : 'text-slate-600 hover:bg-emerald-50 hover:text-emerald-800'
  }`

function Navbar() {
  return (
    <nav className="sticky top-0 z-50 border-b border-emerald-950/10 bg-white/95 backdrop-blur" aria-label="Main navigation">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-5 px-4 py-4 sm:px-6 lg:px-8">
        <Link className="flex items-center gap-3 rounded-xl focus:outline-none focus:ring-4 focus:ring-emerald-500/20" to="/">
          <span className="rounded-2xl bg-emerald-700 p-3 text-white shadow-md shadow-emerald-900/15"><LeafMark /></span>
          <span>
            <span className="block text-[10px] font-bold uppercase tracking-[0.22em] text-emerald-700">AI Smart</span>
            <span className="block text-xl font-black tracking-tight text-slate-950">Tea Ecosystem</span>
          </span>
        </Link>
        <div className="flex flex-wrap items-center gap-1 rounded-3xl border border-slate-200 bg-slate-50 p-1 sm:rounded-full" role="list">
          <NavLink className={navigationClass} role="listitem" to="/plant-density">Density</NavLink>
          <NavLink className={navigationClass} role="listitem" to="/plantation-health">Health</NavLink>
          <NavLink className={navigationClass} role="listitem" to="/harvest-readiness">Harvest Readiness</NavLink>
        </div>
      </div>
    </nav>
  )
}

export default Navbar
