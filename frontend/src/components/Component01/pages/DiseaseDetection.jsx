import { useEffect, useRef, useState } from 'react'
import { Camera, CircleCheck, ArrowRight, UploadCloud, Sparkles } from '../ui/icons.jsx'
import { useLanguage } from '../locales/i18n.jsx'
import { Card, SectionHeading, StatusToast, percent } from '../ui/Widgets.jsx'
import { assetUrl, uploadImage } from '../services/api.js'

export default function DiseaseDetection({navigate, latestImage, setLatestImage}) {
  const {t,diseaseName}=useLanguage()
  const [file,setFile]=useState(null)
  const [preview,setPreview]=useState('')
  const [busy,setBusy]=useState(false)
  const [err,setErr]=useState('')
  const [unsuitable,setUnsuitable]=useState(false)
  const requestId=useRef(0)
  const controller=useRef(null)
  useEffect(()=>()=>{requestId.current+=1;controller.current?.abort()},[])
  useEffect(()=>()=>{if(preview)URL.revokeObjectURL(preview)},[preview])
  const analyze=async()=>{
    if(!file)return
    const id=++requestId.current
    controller.current?.abort()
    controller.current=new AbortController()
    setBusy(true);setErr('');setUnsuitable(false);setLatestImage(null)
    try {
      const result=await uploadImage(file,{signal:controller.current.signal})
      if(id!==requestId.current)return
      if(['rejected','uncertain'].includes(result?.analysis_status)){setUnsuitable(result.analysis_status==='rejected'?'invalidTeaImage':'imageSuitabilityError');return}
      if(!result?.predicted_class)throw new Error(t('imageSuitabilityError'))
      setLatestImage(result)
    } catch(e){if(id===requestId.current)setErr(e.message)} finally {if(id===requestId.current)setBusy(false)}
  }
  const onChoose=(f)=>{if (!f) return; requestId.current+=1;controller.current?.abort();setBusy(false);setLatestImage(null);setFile(null);setPreview('');setUnsuitable(false); if (f.size >8*1024*1024) {setErr(t('imageFormats'));return} if(!['image/png','image/jpeg','image/webp'].includes(f.type)){setErr(t('imageFormats'));return} setErr('');setFile(f);setPreview(URL.createObjectURL(f))}
  return <div className="tg-stack">
    <div className="tg-two-cols tg-balanced">
      <Card><SectionHeading title={t('chooseImage')}/><label className={`tg-upload-zone ${preview?'has-image':''}`}><input type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>onChoose(e.target.files?.[0])}/>{preview?<img src={preview} alt={t('uploadedImage')}/>:<><span className="tg-upload-icon"><UploadCloud size={30}/></span><strong>{t('chooseImage')}</strong><small>{t('imageFormats')}</small></>}</label><div className="tg-inline-actions"><button className="tg-btn tg-primary" disabled={!file||busy} onClick={analyze}><Sparkles size={17}/> {busy?t('analyzing'):t('analyze')}</button>{file&&<span className="tg-filename">{file.name}</span>}</div><StatusToast message={unsuitable?t(unsuitable):err} error/></Card>
      <Card><SectionHeading title={t('result')}/>{!latestImage?<div className="tg-empty-feature"><Camera size={45}/><p>{t('uploadFirst')}</p></div>:<><div className="tg-prediction-box"><div className="tg-prediction-check"><CircleCheck size={23}/></div><div><small>{t('prediction')}</small><h2>{diseaseName(latestImage.predicted_class)}</h2></div></div><div className="tg-large-score"><span>{t('modelScore')}</span><strong>{percent(Number(latestImage.uncalibrated_softmax_score)*100,2)}</strong></div><div className="tg-score-list"><h3>{t('topPredictions')}</h3>{(latestImage.top_k||[]).map((row)=><div key={row.class_name}><span>{diseaseName(row.class_name)}</span><div className="tg-progress-track"><i style={{width:`${Math.max(0,Math.min(100,Number(row.softmax_score)*100))}%`}}/></div><b>{percent(Number(row.softmax_score)*100,2)}</b></div>)}</div><small className="tg-fine-note">{t('scoreNote')}</small><button className="tg-btn tg-primary tg-full" onClick={()=>navigate('recommendations')}>{t('openRecommendations')} <ArrowRight size={17}/></button></>}</Card>
    </div>
    {latestImage && <Card><SectionHeading title={t('overlay')} /><div className="tg-explain-grid"><figure><div className="tg-figure-bg"><img src={assetUrl(latestImage.heatmap_url)} alt={t('heatmap')}/></div><figcaption>{t('heatmap')}</figcaption></figure><figure><div className="tg-figure-bg"><img src={assetUrl(latestImage.overlay_url)} alt={t('overlay')}/></div><figcaption>{t('overlay')}</figcaption></figure></div></Card>}
  </div>
}
