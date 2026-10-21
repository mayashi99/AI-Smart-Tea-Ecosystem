import { useState } from 'react'
import { ClipboardCheck, HeartHandshake, Leaf, ShieldCheck, ShieldAlert, Stethoscope, CalendarCheck } from '../ui/icons.jsx'
import { useLanguage } from '../locales/i18n.jsx'
import { post } from '../services/api.js'
import { useRemote } from '../hooks/useRemote.js'
import { Card, ErrorState, Field, SectionHeading, SectionList, SelectField, StatusToast, percent } from '../ui/Widgets.jsx'
export default function Recommendations({latestImage,blocks,focusBlock,focusDisease}) {
  const {t,diseaseName}=useLanguage()
  const classes=useRemote('/api/image/advisory/classes')
  const [choice,setChoice]=useState('')
  const [severity,setSeverity]=useState('')
  const [assess,setAssess]=useState('not_assessed')
  const [chosenBlock,setChosenBlock]=useState('')
  const [inspected,setInspected]=useState('')
  const [symptomatic,setSymptomatic]=useState('')
  const [notes,setNotes]=useState('')
  const [plan,setPlan]=useState(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const disease=choice||latestImage?.predicted_class||focusDisease?.toLowerCase()||classes.data?.classes?.[0]||''
  const block=chosenBlock||focusBlock||''
  const validCounts=(inspected===''&&symptomatic==='') || (Number.isInteger(Number(inspected)) && inspected!=='' && Number(inspected)>=1 && Number.isInteger(Number(symptomatic))&&symptomatic!==''&&Number(symptomatic)>=0&&Number(symptomatic)<=Number(inspected))
  const eligible=disease && (!severity || assess!=='not_assessed') && (disease!=='healthy'||!severity) && validCounts
  const createPlan=async()=>{if(!eligible)return;setBusy(true);setError('');try{const body={disease_name:disease,field_assessment:assess};if(severity)body.severity_level=severity;if(block)body.block_id=block;if(inspected!=='')body.inspected_bushes=Number(inspected);if(symptomatic!=='')body.symptomatic_bushes=Number(symptomatic);if(notes.trim())body.observation_notes=notes.trim();const result=await post('/api/image/advisory/advanced',body);setPlan(result)}catch(e){setError(e.message)}finally{setBusy(false)}}
  return <div className="tg-stack"><div className="tg-two-cols tg-form-result"><Card><SectionHeading title={t('assessment')}/>{classes.error && <ErrorState error={classes.error} onRetry={classes.reload}/>}<div className="tg-form-grid"><SelectField label={t('selectDisease')} value={disease} onChange={v=>{setChoice(v);setPlan(null);setSeverity('')}} options={(classes.data?.classes||[]).map(d=>({value:d,label:diseaseName(d)}))}/><SelectField label={t('selectBlock')} value={block} onChange={setChosenBlock} options={blocks} placeholder={t('chooseBlock')}/><SelectField label={t('assessment')} value={assess} onChange={v=>{setAssess(v);if(v==='not_assessed')setSeverity('')}} options={[{value:'not_assessed',label:t('notAssessed')},{value:'officer_observation',label:t('assessment')}]}/><SelectField label={t('severity')} value={severity} onChange={v=>{setSeverity(v);setAssess('officer_observation');setPlan(null)}} options={[{value:'low',label:t('low')},{value:'moderate',label:t('moderate')},{value:'high',label:t('high')}]} placeholder={t('chooseLevel')} disabled={disease==='healthy'}/><Field label={t('inspected')}><input type="number" min="1" step="1" value={inspected} onChange={e=>setInspected(e.target.value)} /></Field><Field label={t('symptomatic')}><input type="number" min="0" step="1" value={symptomatic} onChange={e=>setSymptomatic(e.target.value)}/></Field></div><Field label={t('notes')}><textarea rows={3} maxLength={500} value={notes} onChange={e=>setNotes(e.target.value)} placeholder={t('notesPlaceholder')}/></Field><p className="tg-fine-note">{t('assessmentNote')}</p><button className="tg-btn tg-primary tg-full" disabled={!eligible||busy||!classes.data} onClick={createPlan}><ClipboardCheck size={17}/>{busy?t('saving'):t('createPlan')}</button><StatusToast message={error} error/></Card>
      <Card><SectionHeading title={t('actionPlan')}/>{!plan?<div className="tg-empty-feature"><HeartHandshake size={48}/><p>{t('createPlan')}</p></div>:<><div className="tg-plan-header"><div className="tg-context-icon"><Leaf size={20}/></div><div><span>{t('disease')}</span><h2>{diseaseName(plan.disease_name)}</h2></div></div><div className="tg-inspection-metrics"><div><span>{t('selectedBlock')}</span><b>{plan.field_context?.block_id||'—'}</b></div><div><span>{t('severity')}</span><b>{plan.severity_assessment?.level?t(plan.severity_assessment.level):t('notAssessed')}</b></div><div><span>{t('observedIncidence')}</span><b>{percent(plan.field_context?.observed_incidence_percent)}</b></div></div><div className="tg-review-note"><ShieldCheck size={20}/><p>{t('reviewNote')}</p></div></>}</Card>
    </div>
    {plan && <Card><SectionHeading title={t('actionPlan')} sub={plan.title}/><div className="tg-plans"><SectionList title={t('immediateChecks')} items={plan.field_confirmation_steps} icon={Stethoscope}/><SectionList title={t('managementActions')} items={plan.management_actions} icon={ClipboardCheck}/><SectionList title={t('nonChemical')} items={plan.non_chemical_actions} icon={Leaf}/><SectionList title={t('watchFor')} items={plan.follow_up_plan?.watch_for} icon={CalendarCheck}/><SectionList title={t('followUp')} items={plan.follow_up_plan?.actions} icon={CalendarCheck}/><div className="tg-plan-section"><h3><ShieldAlert size={18}/>{t('chemicalSafety')}</h3><p className="tg-paragraph">{plan.chemical_control?.approval_note}</p><SectionList title={t('professionalReview')} items={plan.chemical_control?.decision_requirements}/><div className="tg-inline-links">{(plan.official_reference_urls||[]).map((url,i)=><a href={url} key={url} target="_blank" rel="noopener noreferrer">{t('sourceLabel')} {i+1} ↗</a>)}</div></div></div></Card>}
  </div>
}
