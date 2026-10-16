import { useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { MapPinned, TrendingUp, Activity } from './icons.jsx'
import { useLanguage } from '../locales/i18n.jsx'
import { Card, EmptyState, KpiCard, SectionHeading, percent } from './Widgets.jsx'

const colorFor = (value) => {
  const n = Number(value)
  if (!Number.isFinite(n)) return 'neutral'
  if (n >= 15) return 'high'
  if (n >= 5) return 'mid'
  return 'low'
}
const getDay = (r) => Number(r.horizon_day)

export default function ForecastPanels({result, blocks, selectedBlock: initialBlock}) {
  const {t} = useLanguage()
  const [selectedDay,setSelectedDay] = useState(1)
  const [inspectedBlock,setInspectedBlock] = useState('')
  const pickedBlock = inspectedBlock || initialBlock || result?.selected_block_id || ''
  const records = result?.all_block_forecast_for_selected_disease || []
  const dayRecords = useMemo(()=>records.filter(r=>getDay(r)===selectedDay),[records,selectedDay])
  const byBlock = useMemo(()=>dayRecords.reduce((acc,r)=>{acc[r.block_id]=r;return acc},{}),[dayRecords])
  const series = useMemo(()=>records.filter(r=>r.block_id===pickedBlock).sort((a,b)=>getDay(a)-getDay(b)).map(r=>({ day:getDay(r), value:Number(r.incidence_percent_prediction), date:r.forecast_target_date })),[records,pickedBlock])
  const current = byBlock[pickedBlock]
  if (!result) return <Card><EmptyState text={t('noForecast')}/></Card>
  const mapBlocks = (blocks?.length?blocks: [...new Set(records.map(r=>r.block_id))]).slice().sort()
  return <div className="tg-forecast-panels">
    <div className="tg-three-cols"><KpiCard label={t('selectedBlock')} value={pickedBlock||'—'} icon={MapPinned}/><KpiCard label={t('predictedIncidence')} value={percent(current?.incidence_percent_prediction)} icon={TrendingUp}/><KpiCard label={t('analysisPeriod')} value={result.forecast_origin_date||'—'} icon={Activity}/></div>
    {result?.forecast_method==='HISTORICAL_SEASONAL_CONTEXT_PLUS_TODAY_FIELD_OBSERVATION' && <Card><div className="tg-muted-caption"><strong>{t('forecastInterval')}:</strong> {result.forecast_target_start} → {result.forecast_target_end}</div><p className="tg-muted-caption">{t('seasonalBasisNote')}</p></Card>}
    <div className="tg-two-cols tg-map-layout">
      <Card><SectionHeading title={t('riskMap')} sub={`${t('day')} ${selectedDay} · ${result.disease_name}`}/><div className="tg-days">{Array.from({length:7},(_,i)=><button key={i} className={selectedDay===i+1?'active':''} onClick={()=>setSelectedDay(i+1)}>{t('day')} {i+1}</button>)}</div>
        <div className="tg-block-grid">{mapBlocks.map(block=>{const row=byBlock[block];return <button key={block} type="button" onClick={()=>setInspectedBlock(block)} className={`tg-block tg-b-${colorFor(row?.incidence_percent_prediction)} ${pickedBlock===block?'selected':''}`}><b>{block}</b><small>{percent(row?.incidence_percent_prediction)}</small></button>})}</div>
        <div className="tg-legend"><span><i className="tg-dot low"/> &lt;5%</span><span><i className="tg-dot mid"/> 5–15%</span><span><i className="tg-dot high"/> ≥15%</span></div>
      </Card>
      <Card><SectionHeading title={t('selectedBlockTrend')} sub={`${pickedBlock} · ${result.disease_name}`}/><div className="tg-chart-height"><ResponsiveContainer width="100%" height="100%"><AreaChart data={series} margin={{left:-16,right:12,top:12,bottom:0}}><defs><linearGradient id="tg-gradient" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#387961" stopOpacity={0.25}/><stop offset="100%" stopColor="#387961" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 4" stroke="#e4e9e4" vertical={false}/><XAxis dataKey="day" tickLine={false} axisLine={false} tick={{fill:'#7d8d80',fontSize:12}}/><YAxis domain={[0,100]} tickLine={false} axisLine={false} tick={{fill:'#7d8d80',fontSize:12}} tickFormatter={v=>`${v}%`}/><Tooltip formatter={(v)=>[percent(v),t('predictedIncidence')]} labelFormatter={d=>`${t('day')} ${d}`}/><Area type="monotone" dataKey="value" stroke="#247a56" strokeWidth={3} fill="url(#tg-gradient)"/></AreaChart></ResponsiveContainer></div>
        <div className="tg-selected-stats"><div><span>{t('activity')}</span><strong>{current?.activity_predicted_class === undefined?'—':Number(current.activity_predicted_class)===1?'Yes':'No'}</strong></div><div><span>{t('newOnset')}</span><strong>{current?.new_onset_predicted_class === undefined?'—':Number(current.new_onset_predicted_class)===1?'Yes':'No'}</strong></div><div><span>{t('date')}</span><strong>{current?.forecast_target_date||'—'}</strong></div></div>
      </Card>
    </div>
    <Card><SectionHeading title={t('compareBlocks')} sub={`${t('day')} ${selectedDay}`}/><div className="tg-table-wrap"><table className="tg-table"><thead><tr><th>{t('estateBlocks')}</th><th>{t('predictedIncidence')}</th><th>{t('activity')}</th><th>{t('newOnset')}</th></tr></thead><tbody>{dayRecords.slice().sort((a,b)=>Number(b.incidence_percent_prediction)-Number(a.incidence_percent_prediction)).map(row=><tr key={row.block_id} onClick={()=>setInspectedBlock(row.block_id)} className="tg-tr-action"><td><b>{row.block_id}</b></td><td>{percent(row.incidence_percent_prediction)}</td><td>{row.activity_predicted_class===undefined?'—':Number(row.activity_predicted_class)===1?'●':'—'}</td><td>{row.new_onset_predicted_class===undefined?'—':Number(row.new_onset_predicted_class)===1?'●':'—'}</td></tr>)}</tbody></table></div></Card>
  </div>
}
