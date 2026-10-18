export const formatNumber = (value, digits = 2) =>
  new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value ?? 0)

export const formatDate = (value) =>
  new Intl.DateTimeFormat('en', { month: 'short', year: 'numeric' }).format(new Date(value))

export const formatMonth = (value) =>
  new Intl.DateTimeFormat('en', { month: 'short' }).format(new Date(value))

export const formatCompact = (value) =>
  new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value ?? 0)

export const formatTonnes = (kg, digits = 1) => `${formatNumber((kg ?? 0) / 1000, digits)} t`

export const pctChange = (current, previous) => (previous ? ((current - previous) / previous) * 100 : 0)

export const sum = (rows, key) => rows.reduce((total, row) => total + Number(row[key] || 0), 0)

function csvCell(value) {
  if (value == null) return ''
  const text = typeof value === 'object' ? JSON.stringify(value) : String(value)
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export function toCSV(rows, columns) {
  const keys = columns || [...new Set(rows.flatMap((row) => Object.keys(row)))]
  return [keys.join(','), ...rows.map((row) => keys.map((key) => csvCell(row[key])).join(','))].join('\n')
}

export function downloadFile(filename, content, type = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
