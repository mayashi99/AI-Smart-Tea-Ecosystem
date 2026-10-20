import Icon from '../components/Icon'
import { Card, Link, PageHeader, StatCard } from '../components/ui'
import { useAuth } from '../lib/auth-context'
import { navigationForRole, roleLabels } from '../lib/permissions'
import { navItems } from '../lib/routes'
import { endpoints, useApi } from '../services/api'

const roleIntros = {
  admin: 'Manage the platform, users, traceability, and tea export intelligence from one workspace.',
  export_manager: 'Plan exports with market intelligence, monthly forecasts, readiness checks, and batch traceability.',
  quality_officer: 'Review export readiness, record evidence-backed quality checks, and verify batch documentation.',
  data_analyst: 'Explore market signals, forecasting outputs, model performance, and analytics reports.',
  farmer_seller: 'Manage your tea batches, follow traceability events, and track export-readiness requirements.',
  viewer_buyer: 'Explore approved market intelligence and reports, and verify public tea passports using QR codes.',
}

export default function HomePage() {
  const { user } = useAuth()
  const farmer = user?.role === 'farmer_seller'
  const passports = useApi(endpoints.passports, { enabled: farmer })
  const links = navigationForRole(navItems.filter((item) => item.key !== 'home'), user?.role)

  return (
    <div className="page-stack">
      <section className="home-hero panel role-home-hero">
        <div className="home-hero-copy">
          <p className="eyebrow">TeaExportAI · Sri Lanka Tea Intelligence</p>
          <h1>Welcome, {user?.display_name || 'Tea Export Partner'}</h1>
          <p>{roleIntros[user?.role] || 'Welcome to the Sri Lanka tea export intelligence workspace.'}</p>
          <span className="chip role-badge">{roleLabels[user?.role]}</span>
        </div>
      </section>

      {farmer && (
        <section className="stat-grid" aria-label="Your tea batches">
          <StatCard icon="package" tone="teal" label="Your batch passports" value={passports.data ? passports.data.passports.length : passports.error ? 'Unavailable' : '…'} hint={passports.error || 'Only batches assigned to your account are shown'} to="/digital-passport" />
          <StatCard icon="shield" label="Traceability status" value={passports.data ? (passports.data.ledger_valid ? 'Verified' : 'Needs review') : '…'} hint="Hash-chain integrity status" to="/digital-passport" />
        </section>
      )}

      <section>
        <PageHeader eyebrow="Your workspace" title="Available modules" description="These pages are available to your account role. Access is checked by the application and backend." />
        <div className="quick-grid">
          {links.map((item) => (
            <Link key={item.key} to={item.path} className="quick-card panel">
              <span className="stat-icon tone-green"><Icon name={item.icon} size={22} /></span>
              <strong>{item.label}</strong>
              <p>{item.description}</p>
              <span className="quick-arrow"><Icon name="arrowRight" size={18} /></span>
            </Link>
          ))}
        </div>
      </section>

      {user?.role === 'viewer_buyer' && (
        <Card icon="shield" title="Verify a public tea passport" description="Use the public link from a batch QR code to review its published traceability timeline.">
          <p className="field-hint">Public passports are read-only and do not require sign-in. Private seller details and internal evidence are not included.</p>
        </Card>
      )}
    </div>
  )
}
