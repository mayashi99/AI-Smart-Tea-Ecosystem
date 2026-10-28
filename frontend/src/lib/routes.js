// Sidebar navigation and URL map. Legacy paths stay as aliases so existing
// bookmarks and printed passport QR codes keep working.
export const navItems = [
  { key: 'home', group: 'overview', label: 'Home', path: '/', icon: 'home', description: 'Overview of exports, forecasts and readiness.' },
  { key: 'dashboard', group: 'overview', label: 'Dashboard', path: '/dashboard', aliases: ['/auction-price'], icon: 'grid', description: 'LSTM auction price model results by growing zone.' },
  { key: 'market', group: 'intelligence', label: 'Market Analysis', path: '/market-analysis', aliases: ['/zone-intelligence'], icon: 'bars', description: 'Zone prices, buyer share and Zone Quality Score.' },
  { key: 'forecast', group: 'intelligence', label: 'Demand Forecast', path: '/demand-forecast', aliases: ['/export-demand'], icon: 'trend', description: '12-month ML export demand forecast.' },
  { key: 'usd-forecast', group: 'intelligence', label: 'USD/LKR Forecast', path: '/usd-forecast', icon: 'globe', description: 'Compare daily USD/LKR exchange-rate forecasts.' },
  { key: 'readiness', group: 'intelligence', label: 'Export Readiness', path: '/export-readiness', icon: 'clipboard', description: 'Explainable Export Readiness Index (ERI).' },
  { key: 'insights', group: 'intelligence', label: 'Trade Insights', path: '/trade-insights', aliases: ['/export-advisor'], icon: 'globe', description: 'Seasonality and the AI Export Advisor.' },
  { key: 'traceability', group: 'operations', label: 'Traceability', path: '/digital-passport', icon: 'shield', description: 'Tea Digital Passport and QR verification.' },
  { key: 'reports', group: 'operations', label: 'Reports', path: '/reports', icon: 'file', description: 'Download forecast, market and ledger reports.' },
  { key: 'settings', group: 'system', label: 'Settings', path: '/settings', icon: 'settings', description: 'Profile, defaults and system status.' },
  { key: 'user-management', group: 'system', label: 'User Management', path: '/user-management', icon: 'user', description: 'Manage accounts, roles and audit activity.' },
]

export const workspaceRoles = {
  seller: { path: '/seller', title: 'Seller workspace', intro: 'Prepare tea batches for export with clear readiness steps, forecast context and traceability.', links: [['Check export readiness', '/export-readiness', 'clipboard'], ['Register a tea batch', '/digital-passport', 'shield'], ['Explore growing zones', '/market-analysis', 'bars'], ['Get export advice', '/trade-insights', 'globe']] },
  'tea-board': { path: '/tea-board', title: 'Tea Board workspace', intro: 'Review export preparation signals, traceability records and market intelligence across tea batches.', links: [['Export readiness overview', '/export-readiness', 'clipboard'], ['Batch passport registry', '/digital-passport', 'shield'], ['Zone intelligence', '/market-analysis', 'bars'], ['Export demand forecast', '/demand-forecast', 'trend']] },
  buyer: { path: '/buyer', title: 'Buyer workspace', intro: 'Explore Sri Lankan tea market signals and review batch traceability before you source.', links: [['Verify a batch passport', '/digital-passport', 'shield'], ['Export demand outlook', '/demand-forecast', 'trend'], ['Auction price forecast', '/dashboard', 'grid'], ['Market zone intelligence', '/market-analysis', 'bars']] },
}

export function matchRoute(path) {
  const publicPassport = path.match(/^\/passport\/([A-Za-z0-9_-]{20,100})$/)
  if (publicPassport) return { key: 'public-passport', publicId: publicPassport[1] }
  if (path === '/login') return { key: 'login' }
  if (path === '/signup') return { key: 'signup' }
  if (path === '/super-admin-invite') return { key: 'super-admin-invite' }
  if (path === '/welcome') return { key: 'landing' }
  const item = navItems.find((nav) => nav.path === path || nav.aliases?.includes(path))
  if (item) return { key: item.key, item }
  const role = Object.keys(workspaceRoles).find((key) => workspaceRoles[key].path === path)
  if (role) return { key: 'workspace', role }
  return { key: 'not-found' }
}
