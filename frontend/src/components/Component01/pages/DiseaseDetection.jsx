import { useEffect, useState } from 'react'
import { Camera, CircleCheck, ArrowRight, UploadCloud, Sparkles } from '../ui/icons.jsx'
import { useLanguage } from '../locales/i18n.jsx'
import { Card, SectionHeading, StatusToast, percent } from '../ui/Widgets.jsx'
import { assetUrl, uploadImage } from '../services/api.js'

export default function DiseaseDetection({navigate, latestImage, setLatestImage, setFocusDisease}) {
  const {t,diseaseName}=useLanguage()
  const [file,setFile]=useState(null)
  const [preview,setPreview]=useState('')
  const [busy,setBusy]=useState(false)
  const [err,setErr]=useState('')
  useEffect(()=>{
    if(!file){return undefined}
    const objectUrl=URL.createObjectURL(file);setPreview(objectUrl)
    return ()=>{URL.revokeObjectURL(objectUrl);setPreview('')}
  },[file])
  const analyze=async()=>{
    if(!file)return
    setBusy(true);setErr('')
    try {const result=await uploadImage(file);setLatestImage(result);setFocusDisease(result.predicted_class)} catch(e){setErr(e.message)} finally {setBusy(false)}
  }
  const onChoose=(f)=>{if (!f) return; if (f.size >8*1024*1024) {setErr(t('imageFormats'));return} if(!['image/png','image/jpeg','image/webp'].includes(f.type)){setErr(t('imageFormats'));return} setErr('');setLatestImage(null);setFile(f)}
  return <div className="tg-stack">
    <div className="tg-two-cols tg-balanced">
      <Card><SectionHeading title={t('chooseImage')}/><label className={`tg-upload-zone ${preview?'has-image':''}`}><input type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>onChoose(e.target.files?.[0])}/>{preview?<img src={preview} alt={t('uploadedImage')}/>:<><span className="tg-upload-icon"><UploadCloud size={30}/></span><strong>{t('chooseImage')}</strong><small>{t('imageFormats')}</small></>}</label><div className="tg-inline-actions"><button className="tg-btn tg-primary" disabled={!file||busy} onClick={analyze}><Sparkles size={17}/> {busy?t('analyzing'):t('analyze')}</button>{file&&<span className="tg-filename">{file.name}</span>}</div><StatusToast message={err} error/></Card>
      <Card><SectionHeading title={t('result')}/>{!latestImage?<div className="tg-empty-feature"><Camera size={45}/><p>{t('uploadFirst')}</p></div>:<><div className="tg-prediction-box"><div className="tg-prediction-check"><CircleCheck size={23}/></div><div><small>{t('prediction')}</small><h2>{diseaseName(latestImage.predicted_class)}</h2></div></div><div className="tg-large-score"><span>{t('modelScore')}</span><strong>{percent(Number(latestImage.uncalibrated_softmax_score)*100,2)}</strong></div><div className="tg-score-list"><h3>{t('topPredictions')}</h3>{(latestImage.top_k||[]).map((row,i)=><div key={row.class_name}><span>{diseaseName(row.class_name)}</span><div className="tg-progress-track"><i style={{width:`${Math.max(0,Math.min(100,Number(row.softmax_score)*100))}%`}}/></div><b>{percent(Number(row.softmax_score)*100,2)}</b></div>)}</div><small className="tg-fine-note">{t('scoreNote')}</small><button className="tg-btn tg-primary tg-full" onClick={()=>navigate('recommendations')}>{t('openRecommendations')} <ArrowRight size={17}/></button></>}</Card>
    </div>
    {latestImage && <Card><SectionHeading title={t('overlay')} /><div className="tg-explain-grid"><figure><div className="tg-figure-bg"><img src={assetUrl(latestImage.heatmap_url)} alt={t('heatmap')}/></div><figcaption>{t('heatmap')}</figcaption></figure><figure><div className="tg-figure-bg"><img src={assetUrl(latestImage.overlay_url)} alt={t('overlay')}/></div><figcaption>{t('overlay')}</figcaption></figure></div></Card>}
  </div>
}
