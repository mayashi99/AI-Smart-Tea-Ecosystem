export const roleLabels = {
  admin: 'Admin',
  export_manager: 'Export Manager',
  quality_officer: 'Quality & Compliance Officer',
  data_analyst: 'Data Analyst',
  farmer_seller: 'Farmer / Seller',
  viewer_buyer: 'Viewer / Buyer',
}

export const rolePageAccess = {
  admin: ['home', 'dashboard', 'market', 'forecast', 'usd-forecast', 'readiness', 'insights', 'traceability', 'reports', 'settings', 'user-management'],
  export_manager: ['home', 'dashboard', 'market', 'forecast', 'usd-forecast', 'readiness', 'insights', 'traceability', 'reports'],
  quality_officer: ['home', 'readiness', 'traceability', 'reports'],
  data_analyst: ['home', 'dashboard', 'market', 'forecast', 'usd-forecast', 'insights', 'reports'],
  farmer_seller: ['home', 'dashboard', 'readiness', 'traceability'],
  viewer_buyer: ['home', 'dashboard', 'market', 'forecast', 'usd-forecast', 'insights', 'reports'],
}

export function canAccessPage(role, pageKey) {
  return rolePageAccess[role]?.includes(pageKey) ?? false
}

export function navigationForRole(items, role) {
  return items.filter((item) => canAccessPage(role, item.key))
}
