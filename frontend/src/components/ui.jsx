import Icon from './Icon'
import { navigate } from '../lib/router'

export function Link({ to, onClick, children, ...props }) {
  function handleClick(event) {
    onClick?.(event)
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    navigate(to)
  }
  return <a href={to} onClick={handleClick} {...props}>{children}</a>
}

export function PageHeader({ eyebrow, title, description, note, actions }) {
  return (
    <header className="page-hero">
      <div className="page-hero-copy">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-hero-description">{description}</p>}
      </div>
      {(note || actions) && (
        <div className="page-hero-aside">
          {actions && <div className="page-hero-actions">{actions}</div>}
          {note && <aside className="info-note"><Icon name="info" size={22} /><p>{note}</p></aside>}
        </div>
      )}
    </header>
  )
}

export function StepHeading({ number, icon, title, description, actions }) {
  return (
    <div className="card-heading">
      {number != null ? <span className="step-number">{number}</span> : icon ? <span className="card-heading-icon"><Icon name={icon} /></span> : null}
      <div className="card-heading-copy"><h2>{title}</h2>{description && <p>{description}</p>}</div>
      {actions && <div className="card-heading-actions">{actions}</div>}
    </div>
  )
}

export function Card({ number, icon, title, description, actions, className = '', children, ...props }) {
  return (
    <section className={`panel card ${className}`} {...props}>
      {title && <StepHeading number={number} icon={icon} title={title} description={description} actions={actions} />}
      {children}
    </section>
  )
}

export function StatCard({ icon, label, value, hint, trend, tone = 'green', to }) {
  const content = (
    <>
      <span className={`stat-icon tone-${tone}`}><Icon name={icon} size={22} /></span>
      <div className="stat-copy">
        <span className="stat-label">{label}</span>
        <strong className="stat-value">{value}</strong>
        {(trend != null || hint) && (
          <span className="stat-hint">
            {trend != null && Number.isFinite(trend) && <b className={trend >= 0 ? 'trend-up' : 'trend-down'}><Icon name={trend >= 0 ? 'arrowUp' : 'arrowDown'} size={13} strokeWidth={2.6} />{Math.abs(trend).toFixed(1)}%</b>}
            {hint}
          </span>
        )}
      </div>
    </>
  )
  return to ? <Link className="stat-card panel is-link" to={to}>{content}</Link> : <article className="stat-card panel">{content}</article>
}

export function ProgressBar({ value, tone = 'green' }) {
  return <i className={`progress tone-${tone}`}><b style={{ width: `${Math.max(0, Math.min(100, value || 0))}%` }} /></i>
}

export function LoadingState({ label = 'Loading…', compact = false }) {
  return <div className={`state-box ${compact ? 'is-compact' : ''}`} role="status"><span className="spinner" aria-hidden="true" />{label}</div>
}

export function ErrorState({ message, onRetry, compact = false }) {
  return (
    <div className={`state-box is-error ${compact ? 'is-compact' : ''}`} role="alert">
      <Icon name="alert" size={22} />
      <span>{message}</span>
      {onRetry && <button type="button" className="btn btn-ghost btn-sm" onClick={onRetry}><Icon name="refresh" size={15} />Retry</button>}
    </div>
  )
}

export function StatusPill({ ok, children }) {
  return <span className={`status-pill ${ok ? 'is-ready' : 'is-missing'}`}>{children}</span>
}
