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
  { key: 'plant-density', group: 'plantation', label: 'Density', path: '/plant-density', icon: 'grid', description: 'Calculate recommended plantation density.' },
  { key: 'plantation-health', group: 'plantation', label: 'Health', path: '/plantation-health', icon: 'leaf', description: 'Analyse tea-plant health from field images.' },
  { key: 'intelligent-harvest-planning', group: 'plantation', label: 'Intelligent Harvest Planning', path: '/intelligent-harvest-planning', icon: 'calendar', description: 'Plan harvest timing using field, image and climate signals.' },
  { key: 'yield-trends', group: 'plantation', label: 'Yield Prediction', path: '/yield-trends', icon: 'trend', description: 'Review historical yield and forecast trends by grown type.' },
  { key: 'harvest-quality', group: 'plantation', label: 'Harvest Quality', path: '/harvest-quality', icon: 'check', description: 'Assess tea-leaf quality and harvest conditions.' },
  { key: 'settings', group: 'system', label: 'Settings', path: '/settings', icon: 'settings', description: 'Profile, defaults and system status.' },
]

export const component02Routes = [
  { key: 'plantation-hub', label: 'Plantation Hub', path: '/plantation-tools' },
  { key: 'yield-prediction', label: 'Yield Prediction', path: '/yield-prediction' },
  { key: 'yield-trends', label: 'Yield Prediction', path: '/yield-trends' },
  { key: 'harvest-quality', label: 'Harvest Quality', path: '/harvest-quality' },
  { key: 'plant-density', label: 'Density', path: '/plant-density' },
  { key: 'plantation-health', label: 'Health', path: '/plantation-health' },
  { key: 'harvest-readiness', label: 'Harvest Readiness', path: '/harvest-readiness' },
  { key: 'intelligent-harvest-planning', label: 'Intelligent Harvest Planning', path: '/intelligent-harvest-planning' },
]

export const workspaceRoles = {
  seller: { path: '/seller', title: 'Seller workspace', intro: 'Prepare tea batches for export with clear readiness steps, forecast context and traceability.', links: [['Check export readiness', '/export-readiness', 'clipboard'], ['Register a tea batch', '/digital-passport', 'shield'], ['Explore growing zones', '/market-analysis', 'bars'], ['Get export advice', '/trade-insights', 'globe']] },
  'tea-board': { path: '/tea-board', title: 'Tea Board workspace', intro: 'Review export preparation signals, traceability records and market intelligence across tea batches.', links: [['Export readiness overview', '/export-readiness', 'clipboard'], ['Batch passport registry', '/digital-passport', 'shield'], ['Zone intelligence', '/market-analysis', 'bars'], ['Export demand forecast', '/demand-forecast', 'trend']] },
  buyer: { path: '/buyer', title: 'Buyer workspace', intro: 'Explore Sri Lankan tea market signals and review batch traceability before you source.', links: [['Verify a batch passport', '/digital-passport', 'shield'], ['Export demand outlook', '/demand-forecast', 'trend'], ['Auction price forecast', '/dashboard', 'grid'], ['Market zone intelligence', '/market-analysis', 'bars']] },
}

export function matchRoute(path) {
  const item = [...navItems, ...component02Routes].find((nav) => nav.path === path || nav.aliases?.includes(path))
  if (item) return { key: item.key, item }
  const role = Object.keys(workspaceRoles).find((key) => workspaceRoles[key].path === path)
  if (role) return { key: 'workspace', role }
  return { key: 'not-found' }
}
