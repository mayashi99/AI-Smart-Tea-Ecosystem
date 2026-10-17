import { useState, useEffect, useRef } from 'react'

// Base backend API URL (can be customized via VITE_API_URL environment variable)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [loading, setLoading] = useState(false)
  const [purityLoading, setPurityLoading] = useState(false)
  const [error, setError] = useState(null)
  const [invalidImageError, setInvalidImageError] = useState(null)
  const [prediction, setPrediction] = useState(null)
  const [purityResult, setPurityResult] = useState(null)
  const [backendStatus, setBackendStatus] = useState('checking') // 'online' | 'offline' | 'checking'
  const [modelInfo, setModelInfo] = useState(null)
  const [dragActive, setDragActive] = useState(false)

  const fileInputRef = useRef(null)

  // Check Component 03 backend health on mount
  useEffect(() => {
    checkBackendHealth()
  }, [])

  // Clean up ObjectURL when component unmounts or previewUrl changes
  useEffect(() => {
    return () => {
      if (previewUrl && previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  const checkBackendHealth = async () => {
    setBackendStatus('checking')
    try {
      const res = await fetch(`${API_BASE_URL}/api/component3/info`)
      if (res.ok) {
        const data = await res.json()
        setBackendStatus('online')
        setModelInfo(data)
      } else {
        setBackendStatus('offline')
      }
    } catch {
      setBackendStatus('offline')
    }
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

    // 3. Create preview URL for the exact uploaded image
    if (previewUrl && previewUrl.startsWith('blob:')) {
      URL.revokeObjectURL(previewUrl)
    }

    const objectUrl = URL.createObjectURL(file)
    setSelectedFile(file)
    setPreviewUrl(objectUrl)
    setPrediction(null)
    setPurityResult(null)
    setInvalidImageError(null)
  }

  // File input change handler
  const onFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0])
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
    setPrediction(null)

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
          // Keep default error text
        }
        throw new Error(errorDetail)
      }

      const result = await response.json()
      if (result.success) {
        setPrediction(result)
        setBackendStatus('online')
      } else {
        throw new Error(result.error || 'Failed to obtain tea grade prediction.')
      }
    } catch (err) {
      console.error('Component 03 prediction error:', err)
      setPrediction(null)
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
        setBackendStatus('offline')
      } else {
        setError(msg)
      }
    } finally {
      setLoading(false)
    }
  }

  // Trigger experimental purity analysis via Component 03 backend endpoint
  const handleAnalyzePurity = async () => {
    if (!selectedFile) {
      setError('Please select or upload a tea leaf image first.')
      return
    }

    setPurityLoading(true)
    setError(null)
    setInvalidImageError(null)
    setPurityResult(null)

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
        } catch {
          // Keep default error text
        }
        throw new Error(errorDetail)
      }

      const result = await response.json()
      if (result.success) {
        setPurityResult(result)
        setBackendStatus('online')
      } else {
        throw new Error(result.error || 'Failed to execute purity analysis.')
      }
    } catch (err) {
      console.error('Component 03 purity analysis error:', err)
      setPurityResult(null)
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
        setBackendStatus('offline')
      } else {
        setError(msg)
      }
    } finally {
      setPurityLoading(false)
    }
  }

  // Run both Grade Prediction and Purity Analysis sequentially
  const handleRunAllAnalysis = async () => {
    await handlePredict()
    await handleAnalyzePurity()
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
    setError(null)
    setInvalidImageError(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="tea-app-container">
      {/* App Header */}
      <header className="app-header">
        <div className="header-top">
          <div className="header-brand">
            <div className="brand-icon" aria-hidden="true">🍃</div>
            <div>
              <h1 className="header-title">AI Smart Tea Ecosystem</h1>
              <p className="header-subtitle">
                Component 03: AI-Powered Tea Grade, Purity, Mixed Composition &amp; Defect Analysis
              </p>
            </div>
          </div>

          {/* Backend Connection Indicator */}
          <div className="backend-status-pill" title={`API Base: ${API_BASE_URL}/api/component3`}>
            <span
              className={`status-dot ${
                backendStatus === 'online' ? 'online' : backendStatus === 'offline' ? 'offline' : ''
              }`}
            />
            <span>
              {backendStatus === 'online'
                ? 'Component 03 Online'
                : backendStatus === 'offline'
                ? 'Backend Offline'
                : 'Connecting...'}
            </span>
          </div>
        </div>
      </header>

      {/* Scope Transparency Banner */}
      <div className="model-architecture-banner">
        <span className="architecture-tag">Component 03 Scope</span>
        <div>
          <strong>Active Capabilities:</strong> Trained <strong>YOLO11 Classification Model</strong> for whole-sample tea grade categorization, alongside an <strong>Experimental Computer Vision Purity Module</strong>.
          <em> Notice: No particle bounding boxes, heatmaps, or Grad-CAM++ are implemented. Validated commercial purity percentages require future ground-truth purity datasets.</em>
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
                {/* Uploaded invalid image with warning badge */}
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

                {/* Explanation and Guidance */}
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
              <span>📷</span> Upload Tea Grade Image
            </h2>
            {selectedFile && (
              <button type="button" className="btn-secondary" onClick={handleReset}>
                Reset
              </button>
            )}
          </div>

          <div className="card-body">
            {!previewUrl ? (
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
                <h3 className="upload-title">Drag &amp; drop tea leaf image here</h3>
                <p className="upload-subtitle">Supports JPG, PNG, WEBP, or BMP (up to 15MB)</p>
                <div className="upload-btn-styled">
                  <span>Browse Image</span>
                </div>
              </div>
            ) : (
              <div>
                {/* Uploaded File Selected Bar */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.75rem 1rem',
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    marginBottom: '1.25rem',
                    flexWrap: 'wrap',
                    gap: '0.75rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <span style={{ fontSize: '1.25rem' }}>📄</span>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{selectedFile.name}</div>
                      <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                        {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={loading || purityLoading}
                    >
                      Change Image
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
                      disabled={loading || purityLoading}
                    >
                      {loading ? 'Classifying Grade...' : 'Classify Tea Grade'}
                    </button>
                    <button
                      type="button"
                      className="btn-purity"
                      onClick={handleAnalyzePurity}
                      disabled={loading || purityLoading}
                    >
                      {purityLoading ? 'Analyzing Purity...' : 'Analyze Purity (Experimental)'}
                    </button>
                    <button
                      type="button"
                      className="btn-primary"
                      style={{ background: '#047857' }}
                      onClick={handleRunAllAnalysis}
                      disabled={loading || purityLoading}
                    >
                      Run Full Analysis
                    </button>
                  </div>
                </div>

                {/* Loading Indicator */}
                {(loading || purityLoading) && (
                  <div className="loading-indicator">
                    <div className="spinner" />
                    <div className="loading-text">
                      {loading && purityLoading
                        ? 'Running Grade Classification & Purity Analysis...'
                        : loading
                        ? 'Analyzing tea-leaf sample with YOLO11 model...'
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
            RESULTS CARD (Preserves responsive layout: Beside on desktop, Above on mobile)
            ===================================================================== */}
        {(prediction || purityResult) && (
          <section className="card results-card" aria-labelledby="results-heading">
            <div className="card-header">
              <h2 id="results-heading">
                <span>🎯</span> Component 03: Analysis Results
              </h2>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                {prediction && (
                  <span
                    style={{
                      background: '#dcfce7',
                      color: '#15803d',
                      padding: '0.25rem 0.65rem',
                      borderRadius: '9999px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                    }}
                  >
                    Model: YOLO11-cls
                  </span>
                )}
                {purityResult && (
                  <span className="badge-experimental">
                    Purity: Experimental CV
                  </span>
                )}
              </div>
            </div>

            <div className="card-body">
              {/* Responsive Container: Row on desktop (beside), Column on mobile (above) */}
              <div className="results-flex-container">
                {/* 1. Uploaded Image Card (BESIDE on desktop, ABOVE on mobile) */}
                <div className="result-image-pane">
                  <div className="image-preview-card">
                    <div className="image-preview-header">
                      <span>Uploaded Sample</span>
                      <span className="image-badge">Exact Input Image</span>
                    </div>

                    <div className="uploaded-image-wrapper">
                      <img
                        src={previewUrl}
                        alt="Uploaded tea leaf sample"
                        className="uploaded-image-preview"
                      />
                    </div>

                    <div className="image-meta-footer">
                      <span>File: {selectedFile?.name || 'leaf_sample.jpg'}</span>
                      <span>{(selectedFile?.size / (1024 * 1024)).toFixed(2)} MB</span>
                    </div>
                  </div>
                </div>

                {/* 2. Details Pane: Grade Prediction & Purity Results */}
                <div className="result-details-pane">
                  {/* --- GRADE PREDICTION RESULTS --- */}
                  {prediction && (
                    <>
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

                        {/* Actual Confidence Score Returned by Model */}
                        <div className="confidence-metric-row">
                          <span className="confidence-label">Model Confidence</span>
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
                            <span className="section-caption">Confidence Distribution</span>
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
                    </>
                  )}

                  {/* --- PURITY ANALYSIS RESULTS (PHASE 2 & 3) --- */}
                  {purityResult && (
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

                      {/* Dataset Gap & Next Steps Roadmap */}
                      <div style={{ padding: '0.85rem 1rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0', fontSize: '0.8rem' }}>
                        <div style={{ fontWeight: 700, color: '#334155', marginBottom: '0.35rem' }}>
                          Next Steps for Certified Commercial Purity:
                        </div>
                        <ul style={{ paddingLeft: '1.25rem', color: '#64748b' }}>
                          {purityResult.next_steps_for_certification?.map((step, idx) => (
                            <li key={idx} style={{ marginBottom: '0.2rem' }}>{step}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}

                  {/* If Purity is not yet run, provide a direct prompt */}
                  {prediction && !purityResult && (
                    <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#f0fdf4', borderRadius: '8px', border: '1px dashed #86efac', textAlign: 'center' }}>
                      <p style={{ fontSize: '0.85rem', color: '#166534', marginBottom: '0.65rem' }}>
                        Want to evaluate particle color consistency and chromatic anomalies for this sample?
                      </p>
                      <button
                        type="button"
                        className="btn-purity"
                        onClick={handleAnalyzePurity}
                        disabled={purityLoading}
                      >
                        {purityLoading ? 'Analyzing Purity...' : 'Run Purity Analysis (Experimental)'}
                      </button>
                    </div>
                  )}

                  {/* Component 03 Modules Roadmap Status */}
                  <div style={{ marginTop: '1.75rem', padding: '1rem', background: '#f8fafc', borderRadius: '10px', border: '1px solid #e2e8f0' }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#334155', marginBottom: '0.65rem' }}>
                      Component 03 Analytical Modules Status
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', fontSize: '0.78rem' }}>
                      <div style={{ padding: '0.5rem 0.65rem', background: '#ffffff', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                        <span style={{ color: '#059669', fontWeight: 600 }}>● Tea Grade Classification:</span> <strong>Active (YOLO11)</strong>
                      </div>
                      <div style={{ padding: '0.5rem 0.65rem', background: '#ffffff', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                        <span style={{ color: '#d97706', fontWeight: 600 }}>◐ Purity Analysis:</span> <strong>Experimental CV Baseline</strong>
                      </div>
                      <div style={{ padding: '0.5rem 0.65rem', background: '#ffffff', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                        <span style={{ color: '#64748b', fontWeight: 600 }}>○ Mixed Composition:</span> <em>Not Implemented</em>
                      </div>
                      <div style={{ padding: '0.5rem 0.65rem', background: '#ffffff', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                        <span style={{ color: '#64748b', fontWeight: 600 }}>○ Defect Analysis:</span> <em>Not Implemented</em>
                      </div>
                    </div>
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
                          prediction?.top5 ? `Top 5: ${prediction.top5.map((t) => `${t.grade} (${t.confidence_percentage}%)`).join(', ')}` : null,
                          purityResult ? `Purity Status: Experimental Baseline (Validated Rating Not Available)` : null,
                          purityResult?.experimental_metrics ? `Color Uniformity: ${purityResult.experimental_metrics.color_uniformity_index}/100, Anomaly Ratio: ${purityResult.experimental_metrics.chromatic_anomaly_percentage}%` : null,
                        ].filter(Boolean)
                        navigator.clipboard?.writeText(reportParts.join('\n'))
                        alert('Analysis report copied to clipboard!')
                      }}
                    >
                      <span>📋</span> Copy Report
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}
      </main>

      {/* App Footer */}
      <footer className="app-footer">
        <p>AI-Powered Smart Tea Ecosystem &bull; Component 03: Tea Grade, Purity, Mixed Composition &amp; Defect Analysis</p>
        <span className="footer-model-badge">
          Model: Ultralytics YOLO11 Classification &bull; Whole-Image Analysis (No Particle Bounding Boxes or Heatmaps)
        </span>
      </footer>
    </div>
  )
}

export default App
