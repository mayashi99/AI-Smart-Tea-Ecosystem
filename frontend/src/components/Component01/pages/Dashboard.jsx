import { useMemo, useState } from 'react'
import { ArrowRight, CloudRain, Leaf, Map, ShieldAlert, Wind } from '../ui/icons.jsx'
import { AreaChart, Area, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts'
import { useLanguage } from '../locales/i18n.jsx'
import { useRemote } from '../hooks/useRemote.js'
import { Card, SectionHeading, KpiCard, LoadingState, ErrorState, EmptyState, ActionLink, numberOrDash, percent } from '../ui/Widgets.jsx'

export default function Dashboard({navigate,blocks,diseases,setFocusBlock}) {
  const {t} = useLanguage()
  const overview=useRemote('/api/dashboard/historical/overview')
  const alerts=useRemote('/api/alerts/historical/overview')
  const climate=useRemote('/api/dashboard/historical/climate?limit=12')
  const [chosen,setChosen]=useState('')
  const selected = chosen || blocks[0]
  const block = useRemote(selected ? `/api/dashboard/historical/blocks/${selected}` : null)
  const currentMonth = climate.data?.monthly_records?.at(-1)
  const chartData = (climate.data?.monthly_records||[]).map(row=>({month:String(row.Year_Month||''),rain:Number(row.Rainfall_Total_Mm),temp:Number(row.Temperature_Mean_C)}))
  const flagged = alerts.data?.summary?.blocks_high_overall
  const levelMap=useMemo(()=>Object.fromEntries((alerts.data?.block_summaries||[]).map(row=>[row.block_id,row.overall_demo_level])),[alerts.data])
  const levelClass = (level) => level==='DEMO_HIGH'?'high':level==='DEMO_WATCH'?'mid':level==='DEMO_INFO'?'low':'neutral'
  return <div className="tg-stack">
    <div className="tg-hero"><div className="tg-hero-content"><span className="tg-hero-tag"><Leaf size={15}/> PLANTATION HEALTH</span><h2>{t('overviewTitle')}</h2><p>{t('overviewDesc')}</p><button className="tg-btn tg-white" onClick={()=>navigate('detection')}>{t('analyze')} <ArrowRight size={17}/></button></div><div className="tg-hero-art" aria-hidden="true"><span className="tg-leaf-art l1"/><span className="tg-leaf-art l2"/><span className="tg-leaf-art l3"/><span className="tg-leaf-art l4"/></div></div>
    <div className="tg-four-cols"><KpiCard label={t('estateBlocks')} value={blocks.length||'—'} icon={Map}/><KpiCard label={t('diseaseTypes')} value={diseases.length||'—'} icon={Leaf}/><KpiCard label={t('forecastDays')} value={overview.data?.metadata?.forecast_available_horizon_days?.length || '—'} icon={Wind}/><KpiCard label={t('alertBlocks')} value={flagged??'—'} icon={ShieldAlert}/></div>
    <div className="tg-two-cols tg-balanced"><Card><SectionHeading title={t('blocksOverview')} aside={<ActionLink onClick={()=>navigate('forecast')}>{t('viewForecast')}</ActionLink>}/>{alerts.loading && !alerts.data?<LoadingState/>:alerts.error?<ErrorState error={alerts.error} onRetry={alerts.reload}/>:<><div className="tg-block-grid">{blocks.map(b=><button key={b} className={`tg-block tg-b-${levelClass(levelMap[b])} ${selected===b?'selected':''}`} onClick={()=>{setChosen(b);setFocusBlock(b)}}><b>{b}</b><small>{levelMap[b]==='DEMO_HIGH'?t('urgent'):levelMap[b]==='DEMO_WATCH'?t('watch'):levelMap[b]==='DEMO_INFO'?t('normal'):'—'}</small></button>)}</div>{blocks.length===0 && <EmptyState/>}</>}</Card>
      <Card><SectionHeading title={t('recentClimate')} aside={<ActionLink onClick={()=>navigate('climate')}>{t('viewAll')}</ActionLink>}/>{climate.loading?<LoadingState/>:climate.error?<ErrorState error={climate.error} onRetry={climate.reload}/>:chartData.length?<><div className="tg-chart-height tg-overview-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData} margin={{top:8,left:-16,right:10,bottom:0}}><defs><linearGradient id="tg-rain-grad" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#2f8d78" stopOpacity={.23}/><stop offset="100%" stopColor="#2f8d78" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#e9eee8" vertical={false} strokeDasharray="3 3"/><XAxis dataKey="month" tickLine={false} axisLine={false} tick={{fill:'#7a8a80',fontSize:10}}/><YAxis tickLine={false} axisLine={false} tick={{fill:'#7a8a80',fontSize:11}}/><Tooltip/><Area dataKey="rain" type="monotone" stroke="#2f8d78" strokeWidth={2.5} fill="url(#tg-rain-grad)" name={t('rainfall')}/></AreaChart></ResponsiveContainer></div><div className="tg-muted-row"><span><CloudRain size={16}/> {t('rainfall')}</span><b>{numberOrDash(currentMonth?.Rainfall_Total_Mm,1)} mm</b><span>{String(currentMonth?.Year_Month||'')}</span></div></>:<EmptyState/>}</Card></div>
    <Card><SectionHeading title={`${t('selectedBlock')} · ${selected||'—'}`} aside={<ActionLink onClick={()=>navigate('alerts')}>{t('openAlerts')}</ActionLink>}/>{block.loading?<LoadingState/>:block.error?<ErrorState error={block.error} onRetry={block.reload}/>:<div className="tg-context-grid">{(block.data?.block_disease_context||[]).map((row,i)=><div className="tg-context-tile" key={`${row.disease_name}-${i}`}><div className="tg-context-icon"><Leaf size={17}/></div><b>{t(String(row.disease_name||'').toLowerCase())}</b><span>{t('observedIncidence')}</span><strong>{percent(row.sample_incidence_pct)}</strong></div>)}{!block.data?.block_disease_context?.length && <EmptyState/>}</div>}</Card>
  </div>
}
