import { useState } from 'react'
import { CloudRain, Droplets, Thermometer, Leaf } from '../ui/icons.jsx'
import { AreaChart, Area, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useLanguage } from '../locales/i18n.jsx'
import { useRemote } from '../hooks/useRemote.js'
import { Card, EmptyState, ErrorState, KpiCard, LoadingState, SectionHeading, SelectField, numberOrDash, percent } from '../ui/Widgets.jsx'

export default function ClimateSeverity({blocks,diseases}) {
  const {t,diseaseName} = useLanguage()
  const climate=useRemote('/api/dashboard/historical/climate?limit=24')
  const [block,setBlock]=useState('')
  const [disease,setDisease]=useState('')
  const currentBlock=block||blocks[0]||''
  const currentDisease=disease||diseases[0]||''
  const details=useRemote(currentBlock&&currentDisease?`/api/dashboard/historical/blocks/${currentBlock}?disease=${encodeURIComponent(currentDisease)}`:null)
  const records=climate.data?.monthly_records||[]
  const last=records.at(-1)
  const graph=records.map(r=>({month:String(r.Year_Month||''), rainfall:Number(r.Rainfall_Total_Mm),temp:Number(r.Temperature_Mean_C),humidity:Number(r.Humidity_Mean_Pct)}))
  return <div className="tg-stack">
    <div className="tg-three-cols"><KpiCard label={t('temperature')} value={last?`${numberOrDash(last.Temperature_Mean_C,1)} °C`:'—'} icon={Thermometer}/><KpiCard label={t('rainfall')} value={last?`${numberOrDash(last.Rainfall_Total_Mm,1)} mm`:'—'} icon={CloudRain}/><KpiCard label={t('humidity')} value={last?`${numberOrDash(last.Humidity_Mean_Pct,1)}%`:'—'} icon={Droplets}/></div>
    <Card><SectionHeading title={t('climateChart')} sub={last?.Year_Month?`${t('month')}: ${last.Year_Month}`:undefined}/>{climate.loading?<LoadingState/>:climate.error?<ErrorState error={climate.error} onRetry={climate.reload}/>:graph.length?<div className="tg-chart-height tg-wide-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={graph} margin={{top:14,left:-14,right:12,bottom:0}}><CartesianGrid strokeDasharray="3 3" stroke="#e8eee8" vertical={false}/><XAxis dataKey="month" tick={{fontSize:11,fill:'#77867a'}} tickLine={false} axisLine={false}/><YAxis tick={{fontSize:11,fill:'#77867a'}} tickLine={false} axisLine={false}/><Tooltip/><Legend/><Area dataKey="rainfall" name={t('rainfall')} type="monotone" stroke="#2e8978" strokeWidth={2} fill="#2e8978" fillOpacity={0.07}/><Area dataKey="temp" name={t('temperature')} type="monotone" stroke="#e6a64e" strokeWidth={2} fill="none"/><Area dataKey="humidity" name={t('humidity')} type="monotone" stroke="#5c91bd" strokeWidth={2} fill="none"/></AreaChart></ResponsiveContainer></div>:<EmptyState/>}</Card>
    <Card><SectionHeading title={t('diseaseIncidence')}/><div className="tg-controls"><SelectField label={t('selectBlock')} value={currentBlock} onChange={setBlock} options={blocks}/><SelectField label={t('selectDisease')} value={currentDisease} onChange={setDisease} options={diseases.map(d=>({value:d,label:diseaseName(d)}))}/></div>{details.loading?<LoadingState/>:details.error?<ErrorState error={details.error} onRetry={details.reload}/>:<div className="tg-context-grid">{(details.data?.block_disease_context||[]).map((r,i)=><div className="tg-context-tile" key={i}><div className="tg-context-icon"><Leaf size={18}/></div><b>{diseaseName(r.disease_name)}</b><span>{t('observedIncidence')}</span><strong>{percent(r.sample_incidence_pct)}</strong><small>{t('analysisPeriod')}: {r.forecast_origin_date||details.data?.forecast_origin_date||'—'}</small></div>)}{!details.data?.block_disease_context?.length && <EmptyState/>}</div>}<p className="tg-fine-note">{t('incidenceNote')}</p></Card>
  </div>
}
