import { AlertCircle, CheckCircle2, ArrowUpRight, RefreshCw, Leaf, ArrowRight } from './icons.jsx'
import { useLanguage } from '../locales/i18n.jsx'

// Components avoid any placeholder metrics: missing values render an em dash.
export const numberOrDash = (x, digits = 0) => (x === null || x === undefined || x === '' || !Number.isFinite(Number(x))) ? '—' : Number(x).toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })
export const percent = (x, digits = 1) => numberOrDash(x, digits) === '—' ? '—' : `${numberOrDash(x, digits)}%`
export const dateLabel = (value) => (typeof value === 'string' && value) ? value.slice(0, 10) : '—'
export const diseaseKey = (s) => String(s || '').toLowerCase()
export const labelLevel = (s) => { const level = String(s || '').replace(/^DEMO_/, '').toLowerCase(); return ['high','watch','info'].includes(level) ? level : 'info' }

export function Card({ children, className = '', ...rest }) { return <section className={`tg-card ${className}`} {...rest}>{children}</section> }
export function SectionHeading({ title, aside, sub }) { return <div className="tg-section-heading"><div><h2>{title}</h2>{sub && <p>{sub}</p>}</div>{aside}</div> }
export function ErrorState({ error, onRetry }) { const {t} = useLanguage(); return <div className="tg-state tg-error"><AlertCircle size={24}/><div>{error || t('apiOffline')}</div>{onRetry && <button type="button" className="tg-btn tg-secondary" onClick={onRetry}><RefreshCw size={15}/> {t('tryAgain')}</button>}</div> }
export function LoadingState() { const { t } = useLanguage(); return <div className="tg-state"><div className="tg-loader"/><span>{t('loading')}</span></div> }
export function EmptyState({ text }) { const { t } = useLanguage(); return <div className="tg-state"><Leaf size={24}/><span>{text || t('noData')}</span></div> }
export function StatusToast({ message, error = false }) { return message ? <div role="status" className={`tg-notice ${error ? 'bad' : 'good'}`}>{error ? <AlertCircle size={17}/> : <CheckCircle2 size={17}/>} {message}</div> : null }
export function Field({ label, children, hint }) { return <label className="tg-field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label> }
export function SelectField({ label, value, onChange, options, placeholder, disabled = false }) { return <Field label={label}><select value={value || ''} onChange={(e)=>onChange(e.target.value)} disabled={disabled}><option value="" disabled>{placeholder || label}</option>{options.map((opt)=>{ const id = typeof opt==='string'? opt: opt.value; const text = typeof opt==='string'?opt:opt.label; return <option value={id} key={id}>{text}</option>})}</select></Field> }
export function KpiCard({ label, value, icon:Icon, sub }) { return <div className="tg-kpi"><div className="tg-kpi-top"><span>{label}</span>{Icon && <Icon size={19}/>}</div><strong>{value ?? '—'}</strong>{sub && <small>{sub}</small>}</div> }
export function ActionLink({ children, onClick }) { return <button className="tg-link" type="button" onClick={onClick}>{children} <ArrowUpRight size={15}/></button> }
export function SectionList({ title, items, icon:Icon }) { return Array.isArray(items) && items.length ? <div className="tg-plan-section"><h3>{Icon && <Icon size={18}/>} {title}</h3><div className="tg-plan-items">{items.map((item,i)=><div key={i}><span className="tg-bullet"><ArrowRight size={13}/></span><p>{typeof item==='string' ? item : JSON.stringify(item)}</p></div>)}</div></div> : null }
