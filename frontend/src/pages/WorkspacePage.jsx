import Icon from '../components/Icon'
import { Link, PageHeader } from '../components/ui'
import { navItems, workspaceRoles } from '../lib/routes'

export default function WorkspacePage({ role }) {
  const page = workspaceRoles[role]
  const describe = (href) => navItems.find((item) => item.path === href)?.description

  return (
    <div className="page-stack">
      <PageHeader eyebrow="TeaExportAI · Sri Lanka Tea Intelligence" title={page.title} description={page.intro} />
      <section className="quick-grid is-two">
        {page.links.map(([label, href, icon]) => (
          <Link className="quick-card panel" to={href} key={href}>
            <span className="stat-icon tone-green"><Icon name={icon} size={22} /></span>
            <span className="eyebrow">Open workspace</span>
            <strong>{label}</strong>
            <p>{describe(href)}</p>
            <span className="quick-arrow"><Icon name="arrowRight" size={18} /></span>
          </Link>
        ))}
      </section>
      <div className="chip-row">
        <span className="muted-line">Switch workspace:</span>
        {Object.entries(workspaceRoles).filter(([key]) => key !== role).map(([key, other]) => <Link key={key} className="chip chip-button" to={other.path}>{other.title}</Link>)}
      </div>
    </div>
  )
}
