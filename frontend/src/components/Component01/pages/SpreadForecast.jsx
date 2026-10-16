import { useState } from 'react'
import { ChartNoAxesCombined, RefreshCcw } from '../ui/icons.jsx'
import { useLanguage } from '../locales/i18n.jsx'
import { get } from '../services/api.js'
import { useRemote } from '../hooks/useRemote.js'
import { Card, ErrorState, LoadingState, SectionHeading, SelectField, StatusToast } from '../ui/Widgets.jsx'
import ForecastPanels from '../ui/ForecastPanels.jsx'

export default function SpreadForecast({blocks,diseases,forecast,setForecast,focusBlock,setFocusBlock,focusDisease,setFocusDisease,navigate}) {
  const {t,diseaseName}=useLanguage()
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const selectedBlock=focusBlock||forecast?.selected_block_id||blocks[0]||''
  const selectedDisease=focusDisease||forecast?.disease_name||diseases[0]||''
  const loadLatest=async()=>{setBusy(true);setError('');try{const data=await get('/api/forecast/assisted/latest');setForecast(data);setFocusBlock(data.selected_block_id);setFocusDisease(data.disease_name)}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <div className="tg-stack"><Card><SectionHeading title={t('forecastDetails')} aside={<button className="tg-btn tg-secondary" disabled={busy} onClick={loadLatest}><RefreshCcw size={16}/>{t('savedForecast')}</button>}/><div className="tg-controls"><SelectField label={t('selectBlock')} value={selectedBlock} onChange={setFocusBlock} options={blocks}/><SelectField label={t('selectDisease')} value={selectedDisease} onChange={setFocusDisease} options={diseases.map(d=>({value:d,label:diseaseName(d)}))}/></div><div className="tg-inline-actions"><button className="tg-btn tg-primary" onClick={()=>navigate('observations')}><ChartNoAxesCombined size={16}/>{t('editInput')}</button></div><StatusToast message={error} error/></Card><ForecastPanels result={forecast?.disease_name===selectedDisease?forecast:null} blocks={blocks} selectedBlock={selectedBlock}/></div>
}
