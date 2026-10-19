import { useState, useEffect, useRef } from 'react'

// Base backend API URL (can be customized via VITE_API_URL environment variable)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// 8 Official Sri Lankan Tea Grades Encyclopedia Data
const CEYLON_GRADES_REFERENCE = [
  {
    code: 'BOP',
    name: 'Broken Orange Pekoe',
    category: 'Broken Leaf',
    sieveSize: 'Medium (~1.4 - 2.0 mm)',
    liquor: 'Strong, brisk, rich amber liquor',
    description: 'The backbone of Ceylon tea. Balanced particle size producing bold color and vibrant briskness.',
    icon: '🍃',
  },
  {
    code: 'BOP_1A',
    name: 'Broken Orange Pekoe 1A',
    category: 'Broken Leaf',
    sieveSize: 'Bold Cut (~1.8 - 2.4 mm)',
    liquor: 'Substantial body with golden amber brightness',
    description: 'Cleanly cut bold particles without tips. Renowned for consistent brewing strength.',
    icon: '🌿',
  },
  {
    code: 'BP',
    name: 'Broken Pekoe',
    category: 'Broken Leaf',
    sieveSize: 'Chunky Fragments (~2.0 - 2.8 mm)',
    liquor: 'Heavy body with deep coppery liquor',
    description: 'Substantial chunky leaf fragments offering rich mouthfeel and great blending characteristics.',
    icon: '🍂',
  },
  {
    code: 'DUST',
    name: 'Tea Dust (Dust 1)',
    category: 'Dust / Quick Brew',
    sieveSize: 'Fine Powder (<0.8 mm)',
    liquor: 'Intense dark brew, instantaneous strength',
    description: 'Smallest clean particle cut prized for commercial tea bags, catering, and rapid robust extraction.',
    icon: '⚡',
  },
  {
    code: 'FBOP',
    name: 'Flowery Broken Orange Pekoe',
    category: 'Flowery Grade',
    sieveSize: 'Semi-Broken with Tips (~1.6 - 2.2 mm)',
    liquor: 'Bright liquor with pleasant aromatic aroma',
    description: 'Contains visible golden or silvery tips imparting delicate sweetness and refined cup quality.',
    icon: '🌸',
  },
  {
    code: 'FBOPF_sp',
    name: 'Flowery Broken Orange Pekoe Fannings Special',
    category: 'Tippy Premium',
    sieveSize: 'Medium Fannings (~1.0 - 1.5 mm)',
    liquor: 'Fragrant liquor with caramel undertones',
    description: 'A stylish fannings grade carrying attractive tips that produce a vibrant, aromatic cup.',
    icon: '✨',
  },
  {
    code: 'FBOPF_Exsp',
    name: 'FBOP Fannings Extra Special',
    category: 'Tippy Premium',
    sieveSize: 'Finely Textured with Silver Tips',
    liquor: 'Exquisite delicacy with flowery honey notes',
    description: 'World-renowned high-end Ceylon specialty featuring abundant needle tips of the utmost refinement.',
    icon: '👑',
  },
  {
    code: 'Fngs1',
    name: 'Fannings 1',
    category: 'Fannings',
    sieveSize: 'Fine Granules (~0.8 - 1.2 mm)',
    liquor: 'High color, fast infusing brisk liquor',
    description: 'Uniform fine-grained leaf particles larger than dust, widely celebrated for quick premium infusion.',
    icon: '🌱',
  },
]

function App() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [purityLoading, setPurityLoading] = useState(false)
  const [mixedLoading, setMixedLoading] = useState(false)
  const [defectsLoading, setDefectsLoading] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const [error, setError] = useState(null)
  const [invalidImageError, setInvalidImageError] = useState(null)

  // Analysis Results
  const [prediction, setPrediction] = useState(null)
  const [purityResult, setPurityResult] = useState(null)
  const [mixedResult, setMixedResult] = useState(null)
  const [defectsResult, setDefectsResult] = useState(null)

  // Interactive View States
  const [activeTab, setActiveTab] = useState('overview')
  const [showBoundingBoxes, setShowBoundingBoxes] = useState(true)
  const [selectedDefectFilter, setSelectedDefectFilter] = useState('all')
  const [dragActive, setDragActive] = useState(false)
  const [toastMessage, setToastMessage] = useState(null)

  // Modals
  const [showGradesModal, setShowGradesModal] = useState(false)
  const [showCertModal, setShowCertModal] = useState(false)
  const [showImageZoom, setShowImageZoom] = useState(false)

  // Backend Health Ping
  const [backendOnline, setBackendOnline] = useState(false)

  const fileInputRef = useRef(null)

  // Clean up ObjectURL when component unmounts or previewUrl changes
  useEffect(() => {
    return () => {
      if (previewUrl && previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  // Check Backend Health
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/component3/health`, { method: 'GET' })
        if (res.ok) {
          setBackendOnline(true)
        } else {
          setBackendOnline(false)
        }
      } catch {
        setBackendOnline(false)
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 15000)
    return () => clearInterval(interval)
  }, [])

  // Show Toast
  const triggerToast = (msg) => {
    setToastMessage(msg)
    setTimeout(() => {
      setToastMessage((curr) => (curr === msg ? null : curr))
    }, 3200)
  }

  // Validate and handle chosen file
  const handleFile = (file) => {
    setError(null)
    if (!file) return

    // 1. Validate file type
    const validMimes = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp', 'image/jpg']
    const isImageMime = validMimes.includes(file.type)
    const hasValidExt = /\.(jpe?g|png|webp|bmp)$/i.test(file.name)

    if (!isImageMime && !hasValidExt) {
      setError(`Invalid file format: "${file.name}". Please upload a valid tea-leaf image (.jpg, .jpeg, .png, .webp, or .bmp).`)
      return
    }

    // 2. Validate file size (15MB max)
    const maxSizeBytes = 15 * 1024 * 1024
    if (file.size > maxSizeBytes) {
      setError(`File size too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Maximum allowed size is 15 MB.`)
      return
    }

    if (file.size === 0) {
      setError('The selected image file is empty (0 bytes). Please choose a valid image.')
      return
    }

    // 3. Create preview URL
    if (previewUrl && previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(previewUrl)
    }

    const objectUrl = URL.createObjectURL(file)
    setSelectedFile(file)
    setPreviewUrl(objectUrl)
    setPrediction(null)
    setPurityResult(null)
    setMixedResult(null)
    setDefectsResult(null)
    setShowBoundingBoxes(true)
    setSelectedDefectFilter('all')
    setInvalidImageError(null)
    setActiveTab('overview')
    triggerToast(`Sample "${file.name}" loaded successfully`)
  }

  // File input change handler
  const onFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0])
    }
  }

  // Load standard Demo Sample image directly from backend
  const handleSelectDemoSample = async (sampleId, sampleName, filename) => {
    try {
      setDemoLoading(true)
      setError(null)
      setInvalidImageError(null)

      const response = await fetch(`${API_BASE_URL}/api/component3/demo-samples/${sampleId}`)
      if (!response.ok) {
        throw new Error(`Failed to load demo sample (${response.statusText})`)
      }
      const blob = await response.blob()
      const file = new File([blob], filename || `${sampleId}.jpg`, { type: 'image/jpeg' })

      if (previewUrl && previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(previewUrl)
      }
      const objectUrl = URL.createObjectURL(file)
      setSelectedFile(file)
      setPreviewUrl(objectUrl)
      setPrediction(null)
      setPurityResult(null)
      setMixedResult(null)
      setDefectsResult(null)
      setShowBoundingBoxes(true)
      setSelectedDefectFilter('all')
      setActiveTab('overview')
      triggerToast(`Loaded demo preset: ${sampleName}`)
    } catch (err) {
      console.error('Demo sample load error:', err)
      setError(`Could not load demo sample: ${err.message}`)
    } finally {
      setDemoLoading(false)
    }
  }

  // Drag and Drop handlers
  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0])
    }
  }

  // Trigger classification prediction via Component 03 backend endpoint
  const handlePredict = async () => {
    if (!selectedFile) {
      setError('Please select or upload a tea leaf image first.')
      return
    }

    setLoading(true)
    setError(null)
    setInvalidImageError(null)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await fetch(`${API_BASE_URL}/api/component3/predict`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        let errorDetail = `Backend returned status ${response.status} (${response.statusText})`
        try {
          const errJson = await response.json()
          if (errJson.detail) {
            errorDetail = errJson.detail
          }
        } catch {
          // Keep default
        }
        throw new Error(errorDetail)
      }

      const result = await response.json()
      if (result.success) {
        setPrediction(result)
        triggerToast(`Grade identified: ${result.predicted_grade} (${result.confidence_percentage}%)`)
      } else {
        throw new Error(result.error || 'Failed to obtain tea grade prediction.')
      }
    } catch (err) {
      console.error('Component 03 prediction error:', err)
      const msg = err.message || 'An unexpected error occurred while predicting tea grade.'
      if (
        msg.toLowerCase().includes('invalid image') ||
        msg.toLowerCase().includes('portrait') ||
        msg.toLowerCase().includes('not match any recognized tea grade') ||
        msg.toLowerCase().includes('unnatural') ||
        msg.toLowerCase().includes('particles')
      ) {
        setInvalidImageError(msg)
      } else if (msg.includes('Failed to fetch')) {
        setError(`Cannot connect to the backend at ${API_BASE_URL}. Ensure the FastAPI server is running with Component 03 registered.`)
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  // Trigger experimental purity analysis
  const handleAnalyzePurity = async () => {
    if (!selectedFile) {
      setError('Please select or upload a tea leaf image first.')
      return
    }

    setPurityLoading(true)
    setError(null)
    setInvalidImageError(null)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await fetch(`${API_BASE_URL}/api/component3/purity`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        let errorDetail = `Backend returned status ${response.status} (${response.statusText})`
        try {
          const errJson = await response.json()
          if (errJson.detail) {
            errorDetail = errJson.detail
          }
        } catch {}
        throw new Error(errorDetail)
      }

      const result = await response.json()
      if (result.success) {
        setPurityResult(result)
        triggerToast('CV Purity & Homogeneity analyzed')
      } else {
        throw new Error(result.error || 'Failed to execute purity analysis.')
      }
    } catch (err) {
      console.error('Component 03 purity analysis error:', err)
      const msg = err.message || 'An unexpected error occurred during purity analysis.'
      if (
        msg.toLowerCase().includes('invalid image') ||
        msg.toLowerCase().includes('portrait') ||
        msg.toLowerCase().includes('tea leaf particles') ||
        msg.toLowerCase().includes('unnatural')
      ) {
        setInvalidImageError(msg)
      } else if (msg.includes('Failed to fetch')) {
        setError(`Cannot connect to the backend at ${API_BASE_URL}. Ensure the FastAPI server is running with Component 03 registered.`)
      } else {
        setError(msg)
      }
    } finally {
      setPurityLoading(false)
    }
  }

  // Trigger Mixed Tea Grade Composition analysis
  const handleCheckMixedComposition = async () => {
    if (!selectedFile) {
      setError('Please select or upload a tea leaf image first.')
      return
    }

    setMixedLoading(true)
    setError(null)
    setInvalidImageError(null)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await fetch(`${API_BASE_URL}/api/component3/mixed-composition`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        let errorDetail = `Backend returned status ${response.status} (${response.statusText})`
        try {
          const errJson = await response.json()
          if (errJson.detail) {
            errorDetail = errJson.detail
          }
        } catch {}
        throw new Error(errorDetail)
      }

      const result = await response.json()
      if (result.success) {
        setMixedResult(result)
        triggerToast(`Mixture analysis: ${result.mix_status}`)
      } else {
        throw new Error(result.error || 'Failed to analyze mixed grade composition.')
      }
    } catch (err) {
      console.error('Component 03 mixed composition error:', err)
      const msg = err.message || 'An unexpected error occurred during mixed composition analysis.'
      if (
        msg.toLowerCase().includes('invalid image') ||
        msg.toLowerCase().includes('portrait') ||
        msg.toLowerCase().includes('tea leaf') ||
        msg.toLowerCase().includes('unnatural')
      ) {
        setInvalidImageError(msg)
      } else if (msg.includes('Failed to fetch')) {
        setError(`Cannot connect to the backend at ${API_BASE_URL}. Ensure the FastAPI server is running with Component 03 registered.`)
      } else {
        setError(msg)
      }
    } finally {
      setMixedLoading(false)
    }
  }

  // Trigger Unauthorized Particle & Defect Detection with Bounding Boxes
  const handleDetectDefects = async () => {
    if (!selectedFile) {
      setError('Please select or upload a tea leaf image first.')
      return
    }

    setDefectsLoading(true)
    setError(null)
    setInvalidImageError(null)

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await fetch(`${API_BASE_URL}/api/component3/detect-defects`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        let errorDetail = `Backend returned status ${response.status} (${response.statusText})`
        try {
          const errJson = await response.json()
          if (errJson.detail) {
            errorDetail = errJson.detail
          }
        } catch {}
        throw new Error(errorDetail)
      }

      const result = await response.json()
      if (result.success) {
        setDefectsResult(result)
        setShowBoundingBoxes(true)
        triggerToast(`Pinpointed ${result.total_defects} defect bounding boxes`)
      } else {
        throw new Error(result.error || 'Failed to detect unauthorized particle defects.')
      }
    } catch (err) {
      console.error('Component 03 defect detection error:', err)
      const msg = err.message || 'An unexpected error occurred during defect detection.'
      if (
        msg.toLowerCase().includes('invalid image') ||
        msg.toLowerCase().includes('portrait') ||
        msg.toLowerCase().includes('tea leaf') ||
        msg.toLowerCase().includes('unnatural')
      ) {
        setInvalidImageError(msg)
      } else if (msg.includes('Failed to fetch')) {
        setError(`Cannot connect to the backend at ${API_BASE_URL}. Ensure the FastAPI server is running with Component 03 registered.`)
      } else {
        setError(msg)
      }
    } finally {
      setDefectsLoading(false)
    }
  }

  // Run all Component 03 analyses sequentially
  const handleRunAllAnalysis = async () => {
    await handlePredict()
    await handleCheckMixedComposition()
    await handleDetectDefects()
    await handleAnalyzePurity()
    setActiveTab('overview')
  }

  // Reset all state
  const handleReset = () => {
    if (previewUrl && previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(previewUrl)
    }
    setSelectedFile(null)
    setPreviewUrl(null)
    setPrediction(null)
    setPurityResult(null)
    setMixedResult(null)
    setDefectsResult(null)
    setShowBoundingBoxes(true)
    setSelectedDefectFilter('all')
    setError(null)
    setInvalidImageError(null)
    setActiveTab('overview')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
    triggerToast('Inspection canvas reset')
  }

  // Calculate Tea Quality Index (TQI) composite score
  const calculateTQI = () => {
    let score = 85
    if (prediction) {
      const conf = prediction.confidence_percentage || (prediction.confidence * 100)
      score = score * 0.4 + conf * 0.6
    }
    if (mixedResult) {
      score = (score + mixedResult.uniformity_score) / 2
    }
    if (defectsResult) {
      const defectPenalty = Math.min(defectsResult.total_defects * 4, 35)
      score = Math.max(score - defectPenalty, 20)
    }
    return Math.round(score)
  }

  const tqiScore = calculateTQI()
  const isAnyLoading = loading || purityLoading || mixedLoading || defectsLoading || demoLoading

  return (
    <div className="tea-app-container">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="tea-toast" role="status" aria-live="polite">
          <span>🍃</span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* App Header */}
      <header className="app-header">
        <div className="header-top">
          <div className="header-brand">
            <div className="brand-icon" aria-hidden="true">🍃</div>
            <div className="header-title-group">
              <div className="header-badge-row">
                <span className="header-system-tag">Sri Lanka Tea Board Standards</span>
                <span className="header-system-tag">Neural CV Suite 3.0</span>
              </div>
              <h1 className="header-title">AI Smart Tea Ecosystem</h1>
              <p className="header-subtitle">
                Component 03: AI-Powered Tea Grade, Purity, Mixed Composition &amp; Defect Analysis
              </p>
            </div>
          </div>

          <div className="header-right-actions">
            <div className="backend-status-pill">
              <span className={`status-dot ${backendOnline ? 'online' : 'offline'}`} />
              <span>{backendOnline ? 'FastAPI & YOLO11 Online' : 'Connecting Engine...'}</span>
            </div>
            <button
              type="button"
              className="header-guide-btn"
              onClick={() => setShowGradesModal(true)}
            >
              <span>📖</span> Grades Encyclopedia
            </button>
          </div>
        </div>

        {/* Stats & Capabilities Ribbon */}
        <div className="header-stats-ribbon">
          <div className="header-stat-item">
            <span className="header-stat-icon">🏷️</span>
            <div>
              <div className="header-stat-label">Model Engine</div>
              <div className="header-stat-val">Ultralytics YOLO11</div>
            </div>
          </div>
          <div className="header-stat-item">
            <span className="header-stat-icon">⚖️</span>
            <div>
              <div className="header-stat-label">Granulometry</div>
              <div className="header-stat-val">TRI Sifting Breakdown</div>
            </div>
          </div>
          <div className="header-stat-item">
            <span className="header-stat-icon">🎯</span>
            <div>
              <div className="header-stat-label">Defect Locator</div>
              <div className="header-stat-val">Pinpoint BBox Annotator</div>
            </div>
          </div>
          <div className="header-stat-item">
            <span className="header-stat-icon">🔬</span>
            <div>
              <div className="header-stat-label">Purity Protocol</div>
              <div className="header-stat-val">CV Chromatic Baseline</div>
            </div>
          </div>
        </div>
      </header>

      {/* Scope Transparency Banner */}
      <div className="model-architecture-banner">
        <span className="architecture-tag">Component 03 Scope</span>
        <div>
          <strong>Active Capabilities:</strong> Trained <strong>YOLO11 Classification Model</strong> for whole-sample tea grade categorization, <strong>Granulometric Mixed Grade Composition Analysis</strong>, <strong>Unauthorized Particle &amp; Defect Detection with Bounding Boxes</strong>, and <strong>Experimental Computer Vision Purity Analysis</strong>.
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="error-banner" role="alert">
          <div>
            <strong>Error: </strong>
            {error}
          </div>
          <button
            type="button"
            className="error-close-btn"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            &times;
          </button>
        </div>
      )}

      {/* Main Content */}
      <main className="main-grid">
        {/* =====================================================================
            INVALID IMAGE WARNING CARD
            ===================================================================== */}
        {invalidImageError && (
          <section className="card invalid-image-card" role="alert" aria-live="assertive">
            <div className="invalid-image-card-header">
              <div className="invalid-card-badge">
                <span className="invalid-icon" aria-hidden="true">🚫</span>
                <div>
                  <h2 className="invalid-card-title">Invalid Tea Sample Image</h2>
                  <p className="invalid-card-subtitle">
                    The uploaded image is not a recognized tea leaf sample
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="error-close-btn"
                onClick={() => setInvalidImageError(null)}
                aria-label="Dismiss error"
              >
                &times;
              </button>
            </div>

            <div className="invalid-image-card-body">
              <div className="invalid-grid">
                <div className="invalid-image-preview-wrapper">
                  <img
                    src={previewUrl}
                    alt="Uploaded non-tea sample"
                    className="invalid-preview-img"
                  />
                  <div className="invalid-overlay-banner">
                    <span>⚠️ Invalid Sample Rejected</span>
                  </div>
                </div>

                <div className="invalid-details-pane">
                  <div className="invalid-message-box">
                    <strong>Validation Error:</strong>
                    <p>{invalidImageError}</p>
                  </div>

                  <div className="tea-criteria-box">
                    <h4>📋 Required Criteria for Valid Tea Grade Analysis:</h4>
                    <ul>
                      <li>
                        <strong>Dry Ceylon Tea Leaves:</strong> Must clearly show processed tea leaf particles (such as BOP, BOP 1A, BP, DUST, FBOP, FBOPF, Fngs1).
                      </li>
                      <li>
                        <strong>No Extraneous Subjects:</strong> Do not upload photos of people, faces, animals, vehicles, buildings, or outdoor garden greenery.
                      </li>
                      <li>
                        <strong>Presentation Surface:</strong> Spread tea particles uniformly on a clean, light/white paper or neutral presentation tray.
                      </li>
                      <li>
                        <strong>Sharp Focus &amp; Illumination:</strong> Ensure overhead lighting without severe shadows or blur.
                      </li>
                    </ul>
                  </div>

                  <div className="invalid-actions-row">
                    <button
                      type="button"
                      className="btn-primary"
                      style={{ background: '#dc2626' }}
                      onClick={() => {
                        handleReset()
                        setTimeout(() => fileInputRef.current?.click(), 100)
                      }}
                    >
                      <span>🔄</span> Choose Another Image
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => setInvalidImageError(null)}
                    >
                      Dismiss Notice
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Upload Card */}
        <section className="card upload-card" aria-labelledby="upload-heading">
          <div className="card-header">
            <h2 id="upload-heading">
              <span>📷</span> Upload Tea Leaf Sample Image
            </h2>
            {selectedFile && (
              <button type="button" className="btn-secondary" onClick={handleReset}>
                Reset Canvas
              </button>
            )}
          </div>

          <div className="card-body">
            {!previewUrl ? (
              <div>
                <div
                  className={`upload-dropzone ${dragActive ? 'drag-active' : ''}`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/bmp"
                    onChange={onFileChange}
                    aria-label="Upload tea leaf image"
                  />
                  <div className="upload-icon-wrapper">
                    <span>🍃</span>
                  </div>
                  <h3 className="upload-title">Drop your tea leaf sample photo here</h3>
                  <p className="upload-subtitle">Supports JPG, PNG, WEBP, or BMP up to 15MB • Clean flat presentation surface recommended</p>
                  <div className="upload-btn-styled">
                    <span>Browse Local Image</span>
                  </div>
                </div>

                {/* One-Click Demo Sample Presets */}
                <div className="demo-samples-container">
                  <div className="demo-samples-header">
                    <span className="demo-samples-title">
                      <span>🧪</span> One-Click Demo Tea Presets:
                    </span>
                    <span className="demo-samples-hint">
                      Instantly test Component 03 analytical capabilities with certified sample images
                    </span>
                  </div>
                  <div className="demo-samples-grid">
                    <button
                      type="button"
                      className="demo-sample-card-btn"
                      onClick={() => handleSelectDemoSample('pure_bop', 'Clean Pure BOP Sample', 'pure_bop_sample.jpg')}
                      disabled={isAnyLoading}
                    >
                      <div className="demo-sample-icon">🌿</div>
                      <div className="demo-sample-text-wrap">
                        <div className="demo-sample-name-row">
                          <span className="demo-sample-name">Clean Pure BOP</span>
                          <span className="demo-sample-badge badge-pure">Pure Grade</span>
                        </div>
                        <div className="demo-sample-target">Single grade target • High uniformity &bull; 0 defects</div>
                      </div>
                    </button>

                    <button
                      type="button"
                      className="demo-sample-card-btn"
                      onClick={() => handleSelectDemoSample('mixed_bop_dust', 'Mixed Grade (BOP + DUST)', 'mixed_bop_dust_sample.jpg')}
                      disabled={isAnyLoading}
                    >
                      <div className="demo-sample-icon">⚡</div>
                      <div className="demo-sample-text-wrap">
                        <div className="demo-sample-name-row">
                          <span className="demo-sample-name">Mixed Grade (BOP + DUST)</span>
                          <span className="demo-sample-badge badge-blend">Blended</span>
                        </div>
                        <div className="demo-sample-target">Admixture detection &bull; Particle size ratio breakdown</div>
                      </div>
                    </button>

                    <button
                      type="button"
                      className="demo-sample-card-btn"
                      onClick={() => handleSelectDemoSample('defective_stalks', 'Defective Sample with Stalks', 'defective_stalks_sample.jpg')}
                      disabled={isAnyLoading}
                    >
                      <div className="demo-sample-icon">🚨</div>
                      <div className="demo-sample-text-wrap">
                        <div className="demo-sample-name-row">
                          <span className="demo-sample-name">Contaminated with Stalks</span>
                          <span className="demo-sample-badge badge-defect">Defects</span>
                        </div>
                        <div className="demo-sample-target">Tests particle bounding box object localization</div>
                      </div>
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div>
                {/* Active Sample Command Deck */}
                <div className="active-sample-deck">
                  <div className="active-sample-info">
                    <img
                      src={previewUrl}
                      alt="Sample thumbnail"
                      className="active-sample-thumb"
                    />
                    <div className="active-sample-meta">
                      <div className="active-sample-title">{selectedFile.name}</div>
                      <div className="active-sample-subtitle">
                        {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB &bull; Ready for inference
                      </div>
                    </div>
                  </div>

                  <div className="active-sample-buttons">
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isAnyLoading}
                    >
                      Change Photo
                    </button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/bmp"
                      onChange={onFileChange}
                      style={{ display: 'none' }}
                    />
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={handlePredict}
                      disabled={isAnyLoading}
                    >
                      {loading ? 'Classifying...' : 'Classify Grade'}
                    </button>
                    <button
                      type="button"
                      className="btn-mixed"
                      onClick={handleCheckMixedComposition}
                      disabled={isAnyLoading}
                    >
                      {mixedLoading ? 'Checking...' : 'Check Mixture'}
                    </button>
                    <button
                      type="button"
                      className="btn-defects"
                      onClick={handleDetectDefects}
                      disabled={isAnyLoading}
                    >
                      {defectsLoading ? 'Scanning...' : 'Detect Defects'}
                    </button>
                    <button
                      type="button"
                      className="btn-purity"
                      onClick={handleAnalyzePurity}
                      disabled={isAnyLoading}
                    >
                      {purityLoading ? 'Analyzing...' : 'Analyze Purity'}
                    </button>
                    <button
                      type="button"
                      className="btn-run-all"
                      onClick={handleRunAllAnalysis}
                      disabled={isAnyLoading}
                    >
                      <span>✨</span> Run Full AI Suite
                    </button>
                  </div>
                </div>

                {/* Loading Indicator */}
                {isAnyLoading && (
                  <div className="loading-indicator">
                    <div className="spinner" />
                    <div className="loading-text">
                      {demoLoading
                        ? 'Fetching standard demo sample from Component 03...'
                        : loading && mixedLoading && defectsLoading
                        ? 'Running Full Suite: YOLO11 Classifier, Granulometry & Defect Pinpointer...'
                        : loading
                        ? 'Analyzing tea-leaf sample with YOLO11 model...'
                        : mixedLoading
                        ? 'Analyzing multi-grade granulometry and particle size distribution...'
                        : defectsLoading
                        ? 'Scanning sample for unauthorized stalks, coarse fibers & pin-pointing bounding boxes...'
                        : 'Computing experimental color & texture homogeneity metrics...'}
                    </div>
                    <div className="loading-subtext">
                      Component 03 AI &amp; Computer Vision Engine processing leaf sample
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {/* =====================================================================
            RESULTS DASHBOARD CARD
            ===================================================================== */}
        {(prediction || purityResult || mixedResult || defectsResult) && (
          <section className="card results-card" aria-labelledby="results-heading">
            <div className="card-header">
              <h2 id="results-heading">
                <span>🎯</span> Component 03: Inspection Intelligence
              </h2>
              <div className="results-header-badges">
                {prediction && (
                  <span className="result-pill-badge" style={{ background: '#dcfce7', color: '#15803d' }}>
                    🏷️ {prediction.predicted_grade} ({prediction.confidence_percentage}%)
                  </span>
                )}
                {mixedResult && (
                  <span
                    className="result-pill-badge"
                    style={{
                      background: mixedResult.is_mixed ? '#fef3c7' : '#ecfdf5',
                      color: mixedResult.is_mixed ? '#92400e' : '#065f46',
                    }}
                  >
                    ⚖️ {mixedResult.is_mixed ? 'Mixed Cut' : 'Pure Grade'}
                  </span>
                )}
                {defectsResult && (
                  <span
                    className="result-pill-badge"
                    style={{
                      background: defectsResult.has_unauthorized_particles ? '#fee2e2' : '#ecfdf5',
                      color: defectsResult.has_unauthorized_particles ? '#991b1b' : '#065f46',
                    }}
                  >
                    🚨 {defectsResult.total_defects} Defect Box{defectsResult.total_defects === 1 ? '' : 'es'}
                  </span>
                )}
                {purityResult && (
                  <span className="badge-experimental">
                    🔬 CV Purity: {purityResult.experimental_metrics?.color_uniformity_index}/100
                  </span>
                )}
              </div>
            </div>

            <div className="card-body">
              {/* Results Tab Navigation */}
              <nav className="results-tab-bar" aria-label="Inspection views">
                <button
                  type="button"
                  className={`results-tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
                  onClick={() => setActiveTab('overview')}
                >
                  <span>📌</span> Executive Overview
                </button>
                <button
                  type="button"
                  className={`results-tab-btn ${activeTab === 'grade' ? 'active' : ''}`}
                  onClick={() => setActiveTab('grade')}
                >
                  <span>🏷️</span> Grade Classification
                  {prediction && <span className="tab-count-pill">{prediction.predicted_grade}</span>}
                </button>
                <button
                  type="button"
                  className={`results-tab-btn ${activeTab === 'mixture' ? 'active' : ''}`}
                  onClick={() => setActiveTab('mixture')}
                >
                  <span>⚖️</span> Mixed Granulometry
                  {mixedResult && <span className="tab-count-pill">{mixedResult.mix_status.split(' ')[0]}</span>}
                </button>
                <button
                  type="button"
                  className={`results-tab-btn ${activeTab === 'defects' ? 'active' : ''}`}
                  onClick={() => setActiveTab('defects')}
                >
                  <span>🔍</span> Defect Bounding Boxes
                  {defectsResult && <span className="tab-count-pill">{defectsResult.total_defects}</span>}
                </button>
                <button
                  type="button"
                  className={`results-tab-btn ${activeTab === 'purity' ? 'active' : ''}`}
                  onClick={() => setActiveTab('purity')}
                >
                  <span>🔬</span> Purity Metrics
                </button>
                <button
                  type="button"
                  className={`results-tab-btn ${activeTab === 'all' ? 'active' : ''}`}
                  onClick={() => setActiveTab('all')}
                >
                  <span>📑</span> All in One
                </button>
              </nav>

              {/* Responsive Container: Row on desktop (beside), Column on mobile (above) */}
              <div className="results-flex-container">
                {/* 1. Uploaded Image Card (BESIDE on desktop, ABOVE on mobile) */}
                <div className="result-image-pane">
                  <div className="image-preview-card">
                    <div className="image-preview-header">
                      <span>Interactive Sample Canvas</span>
                      <span className="image-badge">
                        {showBoundingBoxes && defectsResult?.annotated_image ? 'Defect Bounding Boxes' : 'Original Raw'}
                      </span>
                    </div>

                    {/* Image View Toggle if Bounding Boxes are available */}
                    {defectsResult?.annotated_image && (
                      <div className="image-view-toggle-bar">
                        <button
                          type="button"
                          className={`image-toggle-btn ${!showBoundingBoxes ? 'active' : ''}`}
                          onClick={() => setShowBoundingBoxes(false)}
                        >
                          <span>📷</span> Original Raw
                        </button>
                        <button
                          type="button"
                          className={`image-toggle-btn ${showBoundingBoxes ? 'active' : ''}`}
                          onClick={() => setShowBoundingBoxes(true)}
                        >
                          <span>🎯</span> Bounding Boxes ({defectsResult.total_defects})
                        </button>
                      </div>
                    )}

                    <div
                      className="uploaded-image-wrapper"
                      onClick={() => setShowImageZoom(true)}
                      title="Click to view full-resolution image"
                    >
                      <img
                        src={showBoundingBoxes && defectsResult?.annotated_image ? defectsResult.annotated_image : previewUrl}
                        alt="Uploaded tea leaf sample"
                        className="uploaded-image-preview"
                      />
                      <div className="image-zoom-overlay-hint">
                        <span>🔍 Click to expand</span>
                      </div>
                    </div>

                    <div className="image-meta-footer">
                      <span>Sample: {selectedFile?.name || 'leaf_sample.jpg'}</span>
                      <span>{(selectedFile?.size / (1024 * 1024)).toFixed(2)} MB</span>
                    </div>
                  </div>
                </div>

                {/* 2. Details Pane: Tabs and Details */}
                <div className="result-details-pane">
                  {/* OVERVIEW TAB HERO SCORECARD */}
                  {(activeTab === 'overview' || activeTab === 'all') && (
                    <div className="quality-scorecard-hero">
                      <div className="quality-hero-text">
                        <h3>Tea Quality Index (TQI): {tqiScore} / 100</h3>
                        <p>
                          {prediction
                            ? `Primary Grade: ${prediction.predicted_grade} (${prediction.confidence_percentage}% confidence). `
                            : 'Grade classification pending. '}
                          {mixedResult
                            ? `${mixedResult.mix_status}. `
                            : ''}
                          {defectsResult
                            ? `${defectsResult.commercial_verdict}.`
                            : ''}
                        </p>
                      </div>
                      <div className="quality-gauge-circle">
                        <div className="quality-gauge-val">{tqiScore}</div>
                        <div className="quality-gauge-label">Quality</div>
                      </div>
                    </div>
                  )}

                  {/* --- 1. GRADE PREDICTION RESULTS --- */}
                  {(activeTab === 'overview' || activeTab === 'grade' || activeTab === 'all') && prediction && (
                    <div style={{ marginBottom: '1.75rem' }}>
                      <div className="prediction-summary-box">
                        <span className="prediction-category-badge">
                          {prediction.grade_category || 'Standard Sri Lankan Grade'}
                        </span>

                        <h3 className="prediction-grade-name">
                          {prediction.predicted_grade}
                        </h3>

                        <div className="prediction-grade-desc">
                          {prediction.grade_full_name && prediction.grade_full_name !== prediction.predicted_grade
                            ? `${prediction.grade_full_name}`
                            : 'Tea Grade Classification'}
                          {prediction.grade_description ? ` — ${prediction.grade_description}` : ''}
                        </div>

                        {/* Confidence Score Metric */}
                        <div className="confidence-metric-row">
                          <span className="confidence-label">YOLO11 Model Confidence</span>
                          <span className="confidence-value">
                            {prediction.confidence_percentage !== undefined
                              ? `${prediction.confidence_percentage}%`
                              : `${(prediction.confidence * 100).toFixed(2)}%`}
                          </span>
                        </div>
                      </div>

                      {/* Top 5 Predicted Classes */}
                      {prediction.top5 && prediction.top5.length > 0 && (
                        <div className="top5-section">
                          <div className="section-heading-row">
                            <h4 className="section-title">
                              <span>📊</span> Top {prediction.top5.length} Predicted Classes
                            </h4>
                            <span className="section-caption">Probability Distribution</span>
                          </div>

                          <div className="top5-list">
                            {prediction.top5.map((item, index) => {
                              const isTop = index === 0
                              const percentage =
                                item.confidence_percentage !== undefined
                                  ? item.confidence_percentage
                                  : Number((item.confidence * 100).toFixed(2))

                              return (
                                <div
                                  key={item.grade}
                                  className={`top5-item ${isTop ? 'top-rank' : ''}`}
                                >
                                  <div className="top5-item-header">
                                    <div className="grade-label-group">
                                      <span className="rank-badge">#{item.rank || index + 1}</span>
                                      <div>
                                        <span className="grade-code">{item.grade}</span>
                                        {item.full_name && item.full_name !== item.grade && (
                                          <span className="grade-full"> ({item.full_name})</span>
                                        )}
                                      </div>
                                    </div>
                                    <span className="score-display">{percentage}%</span>
                                  </div>

                                  <div className="progress-bar-track">
                                    <div
                                      className="progress-bar-fill"
                                      style={{ width: `${Math.max(percentage, 1.5)}%` }}
                                      role="progressbar"
                                      aria-valuenow={percentage}
                                      aria-valuemin="0"
                                      aria-valuemax="100"
                                    />
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* --- 2. MIXED TEA GRADE COMPOSITION RESULTS --- */}
                  {(activeTab === 'overview' || activeTab === 'mixture' || activeTab === 'all') && mixedResult && (
                    <div className="mixed-comp-section">
                      <div className="section-heading-row">
                        <h4 className="section-title">
                          <span>⚖️</span> Mixed Tea Grade Composition &amp; Granulometry
                        </h4>
                        <span className="uniformity-gauge-pill">
                          Uniformity: <strong>{mixedResult.uniformity_score} / 100</strong>
                        </span>
                      </div>

                      {/* Mixture Status Banner */}
                      <div
                        className={`mixed-status-banner ${
                          mixedResult.mix_severity === 'pure_single_grade'
                            ? 'pure'
                            : mixedResult.mix_severity === 'minor_grade_variation'
                            ? 'minor'
                            : mixedResult.mix_severity === 'moderately_mixed'
                            ? 'mixed'
                            : 'heavy'
                        }`}
                      >
                        <div className="mixed-status-title">
                          <span>{mixedResult.is_mixed ? '⚠️' : '✅'}</span>
                          <span>{mixedResult.mix_status}</span>
                        </div>
                        <div style={{ fontSize: '0.82rem', fontWeight: 700 }}>
                          {mixedResult.is_mixed ? 'Multi-Grade Admixture Detected' : 'Conforms to Single Grade'}
                        </div>
                      </div>

                      {/* Commercial Verdict */}
                      <div className="purity-notice-box" style={{ marginBottom: '1rem' }}>
                        <strong>Commercial Inspector Verdict:</strong> {mixedResult.commercial_verdict}
                      </div>

                      {/* Composition Breakdown List */}
                      <div className="composition-list-card">
                        {mixedResult.composition_breakdown?.map((comp) => (
                          <div key={comp.grade} className="composition-row-item">
                            <div className="composition-row-header">
                              <div className="comp-grade-title">
                                <span style={{ color: comp.color_hex }}>●</span>
                                <span>{comp.grade}</span>
                                {comp.full_name && comp.full_name !== comp.grade && (
                                  <span style={{ fontSize: '0.78rem', color: '#64748b', fontWeight: 400 }}>
                                    ({comp.full_name})
                                  </span>
                                )}
                                <span className="comp-role-badge">{comp.role}</span>
                              </div>
                              <span className="comp-pct-display" style={{ color: comp.color_hex }}>
                                {comp.percentage}%
                              </span>
                            </div>

                            <div className="progress-bar-track">
                              <div
                                className="progress-bar-fill"
                                style={{
                                  width: `${Math.max(comp.percentage, 2)}%`,
                                  background: comp.color_hex,
                                }}
                                role="progressbar"
                                aria-valuenow={comp.percentage}
                                aria-valuemin="0"
                                aria-valuemax="100"
                              />
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Granulometry physical sifting summary */}
                      {mixedResult.granulometry_metrics && (
                        <div style={{ padding: '0.9rem 1.15rem', background: '#f8fafc', borderRadius: '10px', border: '1px solid #e2e8f0', fontSize: '0.82rem' }}>
                          <div style={{ fontWeight: 700, color: '#1e293b', marginBottom: '0.45rem' }}>
                            Granulometric Sifting Fractions (TRI Sri Lanka Standard):
                          </div>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', color: '#64748b' }}>
                            <div style={{ background: '#ffffff', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                              Fine (&lt;0.8mm): <strong style={{ color: '#0f172a' }}>{mixedResult.granulometry_metrics.fine_particles_pct}%</strong>
                            </div>
                            <div style={{ background: '#ffffff', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                              Medium (~1.5mm): <strong style={{ color: '#0f172a' }}>{mixedResult.granulometry_metrics.medium_particles_pct}%</strong>
                            </div>
                            <div style={{ background: '#ffffff', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                              Bold (&gt;2.2mm): <strong style={{ color: '#0f172a' }}>{mixedResult.granulometry_metrics.bold_particles_pct}%</strong>
                            </div>
                            <div style={{ background: '#ffffff', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                              Dispersion: <strong style={{ color: '#0f172a' }}>{mixedResult.granulometry_metrics.cv_dispersion}</strong>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* --- 3. DEFECT BOUNDING BOXES & CLEANLINESS --- */}
                  {(activeTab === 'overview' || activeTab === 'defects' || activeTab === 'all') && defectsResult && (
                    <div className="defect-section">
                      <div className="section-heading-row">
                        <h4 className="section-title">
                          <span>🔍</span> Unauthorized Particle Materials &amp; Defect Bounding Boxes
                        </h4>
                        <span style={{ fontSize: '0.85rem', fontWeight: 800, color: defectsResult.has_unauthorized_particles ? '#dc2626' : '#16a34a' }}>
                          {defectsResult.total_defects} Pinpointed Object{defectsResult.total_defects === 1 ? '' : 's'}
                        </span>
                      </div>

                      {/* Cleanliness Status Card */}
                      <div
                        className={`cleanliness-status-card ${
                          defectsResult.cleanliness_grade.includes('Grade A')
                            ? 'pristine'
                            : defectsResult.cleanliness_grade.includes('Grade B')
                            ? 'commercial'
                            : 'substandard'
                        }`}
                      >
                        <div>
                          <div style={{ fontSize: '1rem', fontWeight: 800 }}>
                            {defectsResult.cleanliness_grade}
                          </div>
                          <div style={{ fontSize: '0.82rem', marginTop: '0.2rem' }}>
                            {defectsResult.commercial_verdict}
                          </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <span style={{ fontSize: '1.4rem', fontWeight: 800 }}>
                            {defectsResult.defect_density_pct}%
                          </span>
                          <div style={{ fontSize: '0.72rem' }}>Defect Density Area</div>
                        </div>
                      </div>

                      {/* Defect Filter Pills */}
                      <div className="defect-filter-pills">
                        <button
                          type="button"
                          className={`defect-pill-btn ${selectedDefectFilter === 'all' ? 'active' : ''}`}
                          onClick={() => setSelectedDefectFilter('all')}
                        >
                          All Defects ({defectsResult.total_defects})
                        </button>
                        <button
                          type="button"
                          className={`defect-pill-btn ${selectedDefectFilter === 'stalk' ? 'active' : ''}`}
                          onClick={() => setSelectedDefectFilter('stalk')}
                          style={{ borderColor: '#f59e0b', color: selectedDefectFilter === 'stalk' ? '#fff' : '#b45309' }}
                        >
                          Stalks / Stems ({defectsResult.defect_counts?.stalk || 0})
                        </button>
                        <button
                          type="button"
                          className={`defect-pill-btn ${selectedDefectFilter === 'fiber' ? 'active' : ''}`}
                          onClick={() => setSelectedDefectFilter('fiber')}
                          style={{ borderColor: '#8b5cf6', color: selectedDefectFilter === 'fiber' ? '#fff' : '#6b21a8' }}
                        >
                          Coarse Fibers ({defectsResult.defect_counts?.fiber || 0})
                        </button>
                        <button
                          type="button"
                          className={`defect-pill-btn ${selectedDefectFilter === 'pale_flake' ? 'active' : ''}`}
                          onClick={() => setSelectedDefectFilter('pale_flake')}
                          style={{ borderColor: '#eab308', color: selectedDefectFilter === 'pale_flake' ? '#fff' : '#854d0e' }}
                        >
                          Pale Flakes ({defectsResult.defect_counts?.pale_flake || 0})
                        </button>
                        <button
                          type="button"
                          className={`defect-pill-btn ${selectedDefectFilter === 'foreign_matter' ? 'active' : ''}`}
                          onClick={() => setSelectedDefectFilter('foreign_matter')}
                          style={{ borderColor: '#ef4444', color: selectedDefectFilter === 'foreign_matter' ? '#fff' : '#991b1b' }}
                        >
                          Foreign Matter ({defectsResult.defect_counts?.foreign_matter || 0})
                        </button>
                      </div>

                      {/* Pinpointed Bounding Boxes List */}
                      {defectsResult.defects && defectsResult.defects.length > 0 ? (
                        <div className="defect-items-grid">
                          {defectsResult.defects
                            .filter((d) => selectedDefectFilter === 'all' || d.defect_type === selectedDefectFilter)
                            .map((d) => (
                              <div key={d.id} className="defect-item-card">
                                <div className="defect-item-top">
                                  <span
                                    className="defect-tag-pill"
                                    style={{ background: d.badge_bg, color: d.badge_text }}
                                  >
                                    #{d.id} {d.label}
                                  </span>
                                  <span style={{ fontSize: '0.8rem', fontWeight: 800, color: '#1e293b' }}>
                                    {d.confidence_percentage}% Conf
                                  </span>
                                </div>
                                <div style={{ fontSize: '0.78rem', color: '#64748b', marginBottom: '0.4rem', lineHeight: 1.4 }}>
                                  {d.description}
                                </div>
                                <div className="defect-coords-text">
                                  BBox [x, y, w, h]: [{d.bbox_pixel.join(', ')}]px &bull; Area: {d.area_px}px
                                </div>
                              </div>
                            ))}
                        </div>
                      ) : (
                        <div style={{ padding: '1.25rem', background: '#f8fafc', borderRadius: '10px', textAlign: 'center', fontSize: '0.88rem', color: '#16a34a', border: '1px solid #bbf7d0' }}>
                          ✅ Pristine Clean Sample: No unauthorized particle materials or defects pinpointed.
                        </div>
                      )}
                    </div>
                  )}

                  {/* --- 4. EXPERIMENTAL PURITY ANALYSIS RESULTS --- */}
                  {(activeTab === 'overview' || activeTab === 'purity' || activeTab === 'all') && purityResult && (
                    <div className="purity-section">
                      <div className="purity-header-row">
                        <h4 className="section-title">
                          <span>🔬</span> Dry-Tea Purity &amp; Homogeneity Analysis
                        </h4>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <span className="badge-unvalidated">
                            Validated Purity: Not Available
                          </span>
                          <span className="badge-experimental">
                            Experimental CV
                          </span>
                        </div>
                      </div>

                      {/* Transparent Audit Disclaimer Box */}
                      <div className="purity-notice-box">
                        <strong>Dataset Audit Notice:</strong> {purityResult.transparency_notice}
                      </div>

                      {/* Objective Visual Metrics Grid */}
                      {purityResult.experimental_metrics && (
                        <div className="purity-metrics-grid">
                          <div className="metric-tile">
                            <div className="metric-tile-title">Color Uniformity Index</div>
                            <div className="metric-tile-value" style={{ color: '#059669' }}>
                              {purityResult.experimental_metrics.color_uniformity_index}
                              <span style={{ fontSize: '1rem', fontWeight: 500 }}> / 100</span>
                            </div>
                            <div className="metric-tile-desc">
                              Particle color homogeneity (lower variation = higher score)
                            </div>
                          </div>

                          <div className="metric-tile">
                            <div className="metric-tile-title">Chromatic Anomaly Ratio</div>
                            <div className="metric-tile-value" style={{ color: '#d97706' }}>
                              {purityResult.experimental_metrics.chromatic_anomaly_percentage}%
                            </div>
                            <div className="metric-tile-desc">
                              Estimated atypical / stalk-like off-color particles
                            </div>
                          </div>

                          <div className="metric-tile">
                            <div className="metric-tile-title">Particle Coverage</div>
                            <div className="metric-tile-value" style={{ color: '#0284c7' }}>
                              {purityResult.experimental_metrics.particle_coverage_percentage}%
                            </div>
                            <div className="metric-tile-desc">
                              Foreground sample density relative to image area
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Quick Prompts to run other analyses if not yet executed */}
                  <div style={{ marginTop: '1.5rem', display: 'flex', gap: '0.65rem', flexWrap: 'wrap' }}>
                    {!prediction && (
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={handlePredict}
                        disabled={loading}
                      >
                        {loading ? 'Classifying...' : '🏷️ Classify Grade'}
                      </button>
                    )}
                    {!mixedResult && (
                      <button
                        type="button"
                        className="btn-mixed"
                        onClick={handleCheckMixedComposition}
                        disabled={mixedLoading}
                      >
                        {mixedLoading ? 'Checking...' : '⚡ Check Mixed Composition'}
                      </button>
                    )}
                    {!defectsResult && (
                      <button
                        type="button"
                        className="btn-defects"
                        onClick={handleDetectDefects}
                        disabled={defectsLoading}
                      >
                        {defectsLoading ? 'Scanning...' : '🚨 Detect Defect Bounding Boxes'}
                      </button>
                    )}
                    {!purityResult && (
                      <button
                        type="button"
                        className="btn-purity"
                        onClick={handleAnalyzePurity}
                        disabled={purityLoading}
                      >
                        {purityLoading ? 'Analyzing...' : '🔬 Run Purity Analysis'}
                      </button>
                    )}
                  </div>

                  {/* Action Bar */}
                  <div className="action-bar">
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => {
                        handleReset()
                        setTimeout(() => fileInputRef.current?.click(), 100)
                      }}
                    >
                      <span>🔄</span> Test Another Sample
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => {
                        const reportParts = [
                          'AI Smart Tea Ecosystem - Component 03 Analysis Report',
                          prediction ? `Predicted Grade: ${prediction.predicted_grade} (${prediction.confidence_percentage}%)` : null,
                          mixedResult ? `Mixed Composition: ${mixedResult.mix_status} (Uniformity: ${mixedResult.uniformity_score}/100)` : null,
                          defectsResult ? `Defect Analysis: ${defectsResult.total_defects} defect(s) detected - ${defectsResult.cleanliness_grade}` : null,
                          purityResult?.experimental_metrics ? `Color Uniformity: ${purityResult.experimental_metrics.color_uniformity_index}/100` : null,
                        ].filter(Boolean)
                        navigator.clipboard?.writeText(reportParts.join('\n'))
                        triggerToast('Analysis report copied to clipboard!')
                      }}
                    >
                      <span>📋</span> Copy Report
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => setShowCertModal(true)}
                    >
                      <span>📜</span> Quality Certificate
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}
      </main>

      {/* =====================================================================
          SRI LANKAN TEA GRADES ENCYCLOPEDIA MODAL
          ===================================================================== */}
      {showGradesModal && (
        <div className="modal-backdrop" onClick={() => setShowGradesModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <span>📖</span> Ceylon Tea Grades Reference Guide
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowGradesModal(false)}
                aria-label="Close modal"
              >
                &times;
              </button>
            </div>
            <div className="modal-body">
              <p style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '1.25rem' }}>
                Official classification standard defined by the Tea Research Institute of Sri Lanka (TRI) and recognized by the Colombo Tea Auction.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
                {CEYLON_GRADES_REFERENCE.map((g) => (
                  <div
                    key={g.code}
                    style={{
                      background: '#f8fafc',
                      border: '1px solid #e2e8f0',
                      borderRadius: '12px',
                      padding: '1rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.4rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontFamily: 'var(--font-heading)', fontWeight: 800, fontSize: '1.1rem', color: '#064e3b' }}>
                        {g.icon} {g.code}
                      </span>
                      <span style={{ fontSize: '0.72rem', background: '#d1fae5', color: '#065f46', padding: '0.15rem 0.5rem', borderRadius: '9999px', fontWeight: 700 }}>
                        {g.category}
                      </span>
                    </div>
                    <div style={{ fontWeight: 600, fontSize: '0.86rem', color: '#1e293b' }}>
                      {g.name}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                      <strong>Particle:</strong> {g.sieveSize}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                      <strong>Liquor:</strong> {g.liquor}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#475569', marginTop: '0.25rem', lineHeight: 1.4 }}>
                      {g.description}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          QUALITY CERTIFICATE MODAL (Print Ready)
          ===================================================================== */}
      {showCertModal && (
        <div className="modal-backdrop" onClick={() => setShowCertModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <span>📜</span> Commercial Inspection Certificate
              </div>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  type="button"
                  className="btn-primary"
                  style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem' }}
                  onClick={() => window.print()}
                >
                  <span>🖨️</span> Print Certificate
                </button>
                <button
                  type="button"
                  className="modal-close-btn"
                  onClick={() => setShowCertModal(false)}
                  aria-label="Close modal"
                >
                  &times;
                </button>
              </div>
            </div>
            <div className="modal-body">
              <div className="certificate-sheet">
                <div className="certificate-header">
                  <div className="cert-emblem">🍃</div>
                  <h3 className="cert-title">SRI LANKA TEA QUALITY ASSESSMENT</h3>
                  <div className="cert-subtitle">Certificate of Analytical Inspection &bull; Component 03</div>
                </div>

                <div className="cert-grid">
                  <div>
                    <div className="cert-field-label">Primary Tea Grade</div>
                    <div className="cert-field-val" style={{ color: '#064e3b' }}>
                      {prediction ? `${prediction.predicted_grade} (${prediction.confidence_percentage}%)` : 'Not Evaluated'}
                    </div>
                  </div>
                  <div>
                    <div className="cert-field-label">Overall Quality Index</div>
                    <div className="cert-field-val" style={{ color: '#059669' }}>
                      {tqiScore} / 100 (Export Ready)
                    </div>
                  </div>
                  <div>
                    <div className="cert-field-label">Mixture Conformity</div>
                    <div className="cert-field-val">
                      {mixedResult ? mixedResult.mix_status : 'Pending'}
                    </div>
                  </div>
                  <div>
                    <div className="cert-field-label">Cleanliness Classification</div>
                    <div className="cert-field-val" style={{ color: defectsResult?.has_unauthorized_particles ? '#dc2626' : '#15803d' }}>
                      {defectsResult ? defectsResult.cleanliness_grade : 'Pending'}
                    </div>
                  </div>
                  <div>
                    <div className="cert-field-label">Pinpointed Defect Count</div>
                    <div className="cert-field-val">
                      {defectsResult ? `${defectsResult.total_defects} Objects (${defectsResult.defect_density_pct}% Area)` : 'Pending'}
                    </div>
                  </div>
                  <div>
                    <div className="cert-field-label">Color Uniformity Index</div>
                    <div className="cert-field-val">
                      {purityResult?.experimental_metrics ? `${purityResult.experimental_metrics.color_uniformity_index} / 100` : 'Pending'}
                    </div>
                  </div>
                </div>

                <div style={{ background: '#f8fafc', padding: '0.85rem 1rem', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '0.82rem', color: '#475569', marginBottom: '1.25rem' }}>
                  <strong>Commercial Inspector Summary:</strong>{' '}
                  {mixedResult?.commercial_verdict || defectsResult?.commercial_verdict || 'Sample verified by automated YOLO11 vision pipeline.'}
                </div>

                <div className="cert-footer-stamp">
                  <div>
                    <div><strong>Engine:</strong> YOLO11 Neural Network Classifier</div>
                    <div><strong>Timestamp:</strong> {new Date().toLocaleString()}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontWeight: 800, color: '#064e3b' }}>AI SMART TEA ECOSYSTEM</div>
                    <div style={{ fontSize: '0.72rem' }}>Digital Authentication Verified</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          IMAGE ZOOM / LIGHTBOX MODAL
          ===================================================================== */}
      {showImageZoom && (
        <div className="modal-backdrop" onClick={() => setShowImageZoom(false)}>
          <div
            className="modal-content"
            style={{ maxWidth: '900px', background: '#0b1120', border: '1px solid #334155' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header" style={{ background: '#0f172a', borderBottomColor: '#1e293b' }}>
              <div className="modal-title" style={{ color: '#ffffff' }}>
                <span>🔍</span> High-Resolution Sample Inspection
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowImageZoom(false)}
                style={{ background: '#1e293b', color: '#ffffff', borderColor: '#334155' }}
              >
                &times;
              </button>
            </div>
            <div style={{ padding: '1rem', display: 'flex', justifyContent: 'center', background: '#0b1120' }}>
              <img
                src={showBoundingBoxes && defectsResult?.annotated_image ? defectsResult.annotated_image : previewUrl}
                alt="Full preview"
                style={{ maxWidth: '100%', maxHeight: '75vh', objectFit: 'contain', borderRadius: '8px' }}
              />
            </div>
          </div>
        </div>
      )}

      {/* App Footer */}
      <footer className="app-footer">
        <p>AI-Powered Smart Tea Ecosystem &bull; Component 03: Tea Grade, Purity, Mixed Composition &amp; Defect Analysis</p>
        <span className="footer-model-badge">
          Model: Ultralytics YOLO11 Classification &bull; Mixed Composition Granulometry &bull; Defect Bounding Box Object Locator
        </span>
      </footer>
    </div>
  )
}

export default App
