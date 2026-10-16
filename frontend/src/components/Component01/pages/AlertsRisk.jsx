import { useState } from 'react'
import { ShieldAlert } from '../ui/icons.jsx'
import { useLanguage } from '../locales/i18n.jsx'
import { useRemote } from '../hooks/useRemote.js'
import { Card, EmptyState, ErrorState, LoadingState, SectionHeading, SelectField, percent } from '../ui/Widgets.jsx'

const severityColor = (raw) => raw === 'DEMO_HIGH'?'high':raw === 'DEMO_WATCH'?'mid':'low'
export default function AlertsRisk({blocks,diseases,focusBlock,setFocusBlock,focusDisease,setFocusDisease}) {
  const {t,diseaseName}=useLanguage()
  const [day,setDay]=useState(1)
  const block=focusBlock||blocks[0]||''
  const disease=focusDisease||diseases[0]||''
  const summary=useRemote('/api/alerts/historical/overview')
  const chosen=useRemote(block&&disease?`/api/alerts/historical/blocks/${block}?disease=${encodeURIComponent(disease)}`:null)
  const daily=useRemote(block&&disease?`/api/alerts/historical/blocks/${block}/days/${day}?disease=${encodeURIComponent(disease)}`:null)
  return <div className="tg-stack"><Card><SectionHeading title={t('alertBreakdown')}/><div className="tg-controls"><SelectField label={t('selectBlock')} value={block} onChange={setFocusBlock} options={blocks}/><SelectField label={t('selectDisease')} value={disease} onChange={setFocusDisease} options={diseases.map(d=>({value:d,label:diseaseName(d)}))}/></div><div className="tg-block-grid">{(summary.data?.block_summaries||[]).map(r=><button key={r.block_id} onClick={()=>setFocusBlock(r.block_id)} className={`tg-block tg-b-${severityColor(r.overall_demo_level)} ${block===r.block_id?'selected':''}`}><b>{r.block_id}</b><small>{r.overall_demo_level==='DEMO_HIGH'?t('urgent'):r.overall_demo_level==='DEMO_WATCH'?t('watch'):t('normal')}</small></button>)}</div>{summary.loading?<LoadingState/>:summary.error?<ErrorState error={summary.error} onRetry={summary.reload}/>:!summary.data?.block_summaries?.length?<EmptyState/>:null}</Card>
    <div className="tg-two-cols tg-balanced"><Card><SectionHeading title={`${t('alertBreakdown')} · ${block}`}/>{chosen.loading?<LoadingState/>:chosen.error?<ErrorState error={chosen.error} onRetry={chosen.reload}/>:chosen.data?.block_disease_alerts?.length?<div className="tg-alert-tiles">{chosen.data.block_disease_alerts.map(row=><div key={row.disease_name} className="tg-alert-tile"><div className={`tg-alert-icon ${severityColor(row.seven_day_overall_demo_level)}`}><ShieldAlert size={20}/></div><div><b>{diseaseName(row.disease_name)}</b><small>{t('urgent')}: {row.seven_day_overall_demo_level==='DEMO_HIGH'?t('high'):row.seven_day_overall_demo_level==='DEMO_WATCH'?t('watch'):t('normal')}</small><span>{t('predictedIncidence')}: {percent(row.peak_predicted_incidence_pct)}</span></div></div>)}</div>:<EmptyState/>}</Card>
      <Card><SectionHeading title={t('dailyReview')} sub={`${block} · ${diseaseName(disease)}`}/><div className="tg-days">{Array.from({length:7},(_,i)=><button key={i} className={day===i+1?'active':''} onClick={()=>setDay(i+1)}>{t('day')} {i+1}</button>)}</div>{daily.loading?<LoadingState/>:daily.error?<ErrorState error={daily.error} onRetry={daily.reload}/>:daily.data?<div className="tg-day-metrics"><div><span>{t('date')}</span><b>{daily.data.forecast_target_date||'—'}</b></div><div><span>{t('predictedIncidence')}</span><b>{percent(daily.data.incidence_percent_prediction)}</b></div><div><span>{t('activity')}</span><b>{Number(daily.data.activity_predicted_class)===1?'●':'—'}</b></div><div><span>{t('newOnset')}</span><b>{Number(daily.data.new_onset_predicted_class)===1?'●':'—'}</b></div></div>:<EmptyState/>}</Card></div>
  </div>
}
