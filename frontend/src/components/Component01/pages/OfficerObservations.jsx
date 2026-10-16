import { useState } from 'react'
import { Save, Eye, AlertTriangle } from '../ui/icons.jsx'
import { useLanguage } from '../locales/i18n.jsx'
import { post } from '../services/api.js'
import { useRemote } from '../hooks/useRemote.js'
import { Card, EmptyState, ErrorState, Field, LoadingState, SectionHeading, SelectField, StatusToast, numberOrDash, percent } from '../ui/Widgets.jsx'
import ForecastPanels from '../ui/ForecastPanels.jsx'

export default function OfficerObservations({blocks,diseases,forecast,setForecast,focusBlock,setFocusBlock,focusDisease,setFocusDisease}) {
  const {t,diseaseName}=useLanguage()
  const [inspected,setInspected]=useState('100')
  const [symptomatic,setSymptomatic]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [reloadHistory,setReloadHistory]=useState(0)
  const currentStatus=useRemote('/api/forecast/assisted/status')
  const history=useRemote(`/api/forecast/assisted/observations?limit=25`)
  const block=focusBlock||blocks[0]||''
  const disease=focusDisease||diseases[0]||''
  const n=Number(inspected),m=Number(symptomatic)
  const valid=block&&disease&&inspected.trim()!==''&&symptomatic.trim()!==''&&Number.isInteger(n)&&Number.isInteger(m)&&n>=1&&n<=1000000&&m>=0&&m<=n
  const payload=()=>({block_id:block,disease,inspected_bushes:n,symptomatic_bushes:m})
  const submit=async(save)=>{if(!valid)return;setBusy(true);setError('');setNotice('');try{const output=await post(save?'/api/forecast/assisted/recalculate':'/api/forecast/assisted/preview',payload());setForecast(output);setNotice(t(save?'observationSaved':'observationPreview'));if(save){setReloadHistory(v=>v+1);history.reload()}}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <div className="tg-stack">{!currentStatus.loading&&!currentStatus.data?.ready&&<Card><div className="tg-info-line"><AlertTriangle size={16}/><span>{currentStatus.error || currentStatus.data?.missing_or_invalid_data || 'Historical context or model files are unavailable. Please contact your system administrator.'}</span></div></Card>}<div className="tg-two-cols tg-form-result">
    <Card><SectionHeading title={t('assessment')}/><div className="tg-form-grid"><SelectField label={t('selectBlock')} options={blocks} value={block} onChange={setFocusBlock}/><SelectField label={t('selectDisease')} options={diseases.map(d=>({value:d,label:diseaseName(d)}))} value={disease} onChange={setFocusDisease}/><Field label={t('inspected')}><input type="number" min="1" max="1000000" step="1" value={inspected} onChange={e=>setInspected(e.target.value)}/></Field><Field label={t('symptomatic')}><input type="number" min="0" max={inspected||undefined} step="1" value={symptomatic} onChange={e=>setSymptomatic(e.target.value)}/></Field></div><div className="tg-info-line"><AlertTriangle size={16}/>{t('incidenceNote')}</div><div className="tg-inline-actions"><button disabled={!valid||busy||!currentStatus.data?.ready} className="tg-btn tg-secondary" onClick={()=>submit(false)}><Eye size={17}/>{busy?t('saving'):t('previewForecast')}</button><button disabled={!valid||busy||!currentStatus.data?.ready} className="tg-btn tg-primary" onClick={()=>submit(true)}><Save size={17}/>{busy?t('saving'):t('saveForecast')}</button></div><StatusToast message={error||notice} error={Boolean(error)}/></Card>
    <Card><SectionHeading title={t('observedIncidence')}/><div className="tg-inspection-reading"><strong>{valid?percent(100*m/n):'—'}</strong><span>{t('observedIncidence')}</span></div><div className="tg-inspection-metrics"><div><span>{t('inspected')}</span><b>{valid?numberOrDash(n):'—'}</b></div><div><span>{t('symptomatic')}</span><b>{valid?numberOrDash(m):'—'}</b></div><div><span>{t('selectedBlock')}</span><b>{block||'—'}</b></div></div></Card>
  </div>
  {forecast && <ForecastPanels result={forecast} blocks={blocks} selectedBlock={block}/ >}
  <Card><SectionHeading title={t('inspectionHistory')} aside={<span className="tg-muted-caption">{history.data?.count ?? '—'} {t('records')}</span>}/>{history.loading?<LoadingState/>:history.error?<ErrorState error={history.error} onRetry={history.reload}/>:history.data?.records?.length?<div className="tg-table-wrap"><table className="tg-table"><thead><tr><th>{t('date')}</th><th>{t('estateBlocks')}</th><th>{t('disease')}</th><th>{t('inspected')}</th><th>{t('symptomatic')}</th><th>{t('observedIncidence')}</th></tr></thead><tbody>{history.data.records.map((r,i)=><tr key={r.observation_id||i}><td>{String(r.created_at_utc||r.forecast_origin_date||'—').slice(0,10)}</td><td><b>{r.block_id}</b></td><td>{diseaseName(r.disease_name)}</td><td>{numberOrDash(r.inspected_bushes)}</td><td>{numberOrDash(r.symptomatic_bushes)}</td><td>{percent(r.incidence_percent)}</td></tr>)}</tbody></table></div>:<EmptyState text={t('noHistory')}/>}</Card></div>
}
