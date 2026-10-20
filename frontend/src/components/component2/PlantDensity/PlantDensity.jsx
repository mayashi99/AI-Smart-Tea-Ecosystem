import { useState } from 'react'
const AREA_CONVERSIONS = {
  Acre: 4046.86,
  Hectare: 10000,
}

const TERRAIN_FACTORS = {
  Flat: 1,
  'Gentle Slope': 0.92,
  'Steep Slope': 0.8,
  'Rocky/Uneven': 0.75,
}

const TERRAIN_PREVIEWS = {
  Flat: {
    title: 'Level planting beds',
    ground: 'M0 119 L0 76 C48 70 78 80 119 75 C158 69 203 78 240 72 L240 120 Z',
    rows: ['M12 84 C68 78 116 87 228 80', 'M8 96 C72 90 144 101 235 93', 'M5 108 C75 103 156 113 240 105'],
    dots: [[42, 82], [83, 83], [125, 82], [168, 81], [205, 80], [28, 95], [70, 95], [112, 96], [153, 95], [197, 94], [47, 107], [91, 108], [136, 108], [180, 107], [220, 106]],
  },
  'Gentle Slope': {
    title: 'Gentle contour slope',
    ground: 'M0 119 L0 90 C48 85 80 72 116 60 C159 46 196 38 240 22 L240 120 Z',
    rows: ['M5 91 C55 88 91 74 128 62 C166 49 199 42 236 28', 'M4 102 C57 99 94 85 132 73 C169 60 202 52 238 39', 'M1 113 C61 110 102 96 138 84 C174 72 207 63 240 51'],
    dots: [[36, 88], [79, 78], [119, 65], [161, 51], [202, 39], [27, 100], [70, 91], [110, 78], [152, 64], [194, 51], [49, 109], [92, 98], [133, 85], [174, 71], [217, 58]],
  },
  'Steep Slope': {
    title: 'Steep terraced slope',
    ground: 'M0 119 L0 104 L38 96 L38 84 L78 76 L78 64 L119 55 L119 43 L160 35 L160 23 L202 14 L202 5 L240 0 L240 120 Z',
    rows: ['M1 104 L39 96 L39 90', 'M39 84 L79 76 L79 70', 'M79 64 L120 55 L120 49', 'M120 43 L161 35 L161 29', 'M161 23 L203 14 L203 8'],
    dots: [[19, 100], [54, 80], [95, 60], [137, 39], [179, 19], [31, 103], [66, 83], [107, 63], [149, 43], [191, 23]],
  },
  'Rocky/Uneven': {
    title: 'Uneven planting pockets',
    ground: 'M0 119 L0 93 C25 79 43 95 63 76 C82 58 103 82 121 67 C140 51 163 78 183 62 C204 45 217 57 240 42 L240 120 Z',
    rows: ['M8 103 C39 89 47 99 68 82 C86 67 105 87 122 73 C143 57 159 82 180 67 C200 53 217 64 235 51'],
    dots: [[22, 96], [59, 81], [101, 77], [144, 68], [188, 63], [220, 55]],
    rocks: [[77, 98, 8], [119, 92, 6], [170, 91, 9], [37, 108, 6], [211, 85, 7]],
  },
}

const ZONE_FACTORS = {
  'Low Country': 1,
  'Mid Country': 0.95,
  'Up Country': 0.87,
}

const ROW_SPACING_METERS = 1.2
const PLANT_SPACING_METERS = 0.75

function TerrainPreview({ terrainType }) {
  const preview = TERRAIN_PREVIEWS[terrainType]

  if (!preview) return null

  return (
    <aside className="overflow-hidden rounded-2xl border border-lime-900/10 bg-gradient-to-br from-lime-50 to-emerald-50 p-4 sm:col-span-2" aria-live="polite">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-green-800">Land structure preview</p>
          <h2 className="mt-1 text-lg font-black text-lime-950">{preview.title}</h2>
        </div>
        <span className="rounded-full bg-green-900 px-3 py-1 text-xs font-bold text-white">{terrainType}</span>
      </div>
      <div>
        <svg viewBox="0 0 240 120" className="w-full rounded-xl bg-sky-100 shadow-inner" role="img" aria-label={`${terrainType} land structure with tea planting rows`}>
          <path d="M0 0 H240 V72 C186 55 132 77 72 60 C41 51 19 58 0 66 Z" fill="#dff3f8" />
          <path d={preview.ground} fill="#8eb85b" />
          {preview.rows.map((row) => <path key={row} d={row} fill="none" stroke="#456c34" strokeWidth="2" strokeLinecap="round" />)}
          {preview.dots.map(([x, y], index) => <g key={`${x}-${y}-${index}`}><circle cx={x} cy={y} r="4.5" fill="#1f6a43" /><circle cx={x - 1.2} cy={y - 1.5} r="1.7" fill="#9bd76d" /></g>)}
          {preview.rocks?.map(([x, y, r]) => <circle key={`${x}-${y}`} cx={x} cy={y} r={r} fill="#7b7466" />)}
        </svg>
      </div>
    </aside>
  )
}

function PlantDensity() {
  const [landArea, setLandArea] = useState('')
  const [areaUnit, setAreaUnit] = useState('')
  const [plantationZone, setPlantationZone] = useState('')
  const [terrainType, setTerrainType] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState(null)

  const fieldClass =
    'h-12 w-full rounded-xl border border-lime-900/20 bg-stone-50 px-4 text-sm text-lime-950 outline-none transition focus:border-green-700 focus:ring-4 focus:ring-green-700/15'

  const formatNumber = (value) =>
    new Intl.NumberFormat('en-US', {
      maximumFractionDigits: 0,
    }).format(value)

  const validateInputs = () => {
    const numericFields = [
      { label: 'Total Land Area', value: landArea },
    ]

    const emptyNumber = numericFields.find(({ value }) => value === '')
    if (emptyNumber) {
      return `${emptyNumber.label} is required.`
    }

    const invalidNumber = numericFields.find(({ value }) => {
      const parsedValue = Number(value)
      return !Number.isFinite(parsedValue) || parsedValue <= 0
    })
    if (invalidNumber) {
      return `${invalidNumber.label} must be greater than zero.`
    }

    if (!areaUnit) {
      return 'Please select a land area unit.'
    }

    if (!plantationZone) {
      return 'Please select a plantation zone.'
    }

    if (!terrainType) {
      return 'Please select a terrain type.'
    }

    return ''
  }

  const handleSubmit = (event) => {
    event.preventDefault()

    const validationMessage = validateInputs()
    if (validationMessage) {
      setError(validationMessage)
      setResult(null)
      return
    }

    setError('')
    setIsLoading(true)

    window.setTimeout(() => {
      const landAreaSqm = Number(landArea) * AREA_CONVERSIONS[areaUnit]
      const spacingArea = ROW_SPACING_METERS * PLANT_SPACING_METERS
      const basePlantCount = landAreaSqm / spacingArea
      const terrainFactor = TERRAIN_FACTORS[terrainType]
      const zoneFactor = ZONE_FACTORS[plantationZone]
      const optimizedBushCount = Math.round(
        basePlantCount * terrainFactor * zoneFactor,
      )

      setResult({
        basePlantCount: Math.round(basePlantCount),
        terrainFactor,
        zoneFactor,
        optimizedBushCount,
      })
      setIsLoading(false)
    }, 350)
  }

  return (
    <main className="min-h-screen bg-stone-100 bg-[linear-gradient(135deg,rgba(43,93,45,0.10),rgba(139,105,62,0.16))] px-4 py-8 text-lime-950 sm:px-6 lg:px-8">
      <section className="mx-auto grid w-full max-w-4xl gap-6">
        <form
          className="grid gap-4 rounded-3xl border border-lime-900/10 bg-stone-50/95 p-5 shadow-2xl shadow-lime-950/10 sm:grid-cols-2 sm:p-7"
          onSubmit={handleSubmit}
        >
          <div className="grid gap-2 sm:col-span-2">
            <label className="text-sm font-bold text-lime-950" htmlFor="land-area">
              Total Land Area
            </label>
            <div className="grid gap-3 sm:grid-cols-[1fr_150px]">
              <input
                id="land-area"
                min="0"
                placeholder="0"
                step="0.01"
                type="number"
                value={landArea}
                onChange={(event) => setLandArea(event.target.value)}
                className={fieldClass}
              />
              <select
                aria-label="Land area unit"
                value={areaUnit}
                onChange={(event) => setAreaUnit(event.target.value)}
                className={`${fieldClass} appearance-none [background-image:linear-gradient(45deg,_transparent_50%,_#4d7c0f_50%),_linear-gradient(135deg,_#4d7c0f_50%,_transparent_50%)] [background-position:calc(100%_-_20px)_20px,_calc(100%_-_14px)_20px] [background-repeat:no-repeat] [background-size:6px_6px,_6px_6px] pr-[2.5rem]`}
              >
                <option value="">Unit</option>
                <option value="Acre">Acre</option>
                <option value="Hectare">Hectare</option>
              </select>
            </div>
          </div>

          <div className="grid gap-2">
            <label className="text-sm font-bold text-lime-950" htmlFor="plantation-zone">
              Plantation Zone
            </label>
            <select
              id="plantation-zone"
              value={plantationZone}
              onChange={(event) => setPlantationZone(event.target.value)}
              className={`${fieldClass} appearance-none [background-image:linear-gradient(45deg,_transparent_50%,_#4d7c0f_50%),_linear-gradient(135deg,_#4d7c0f_50%,_transparent_50%)] [background-position:calc(100%_-_20px)_20px,_calc(100%_-_14px)_20px] [background-repeat:no-repeat] [background-size:6px_6px,_6px_6px] pr-[2.5rem]`}
            >
              <option value="">Select zone</option>
              <option value="Low Country">Low Country</option>
              <option value="Mid Country">Mid Country</option>
              <option value="Up Country">Up Country</option>
            </select>
          </div>

          <div className="grid gap-2">
            <label className="text-sm font-bold text-lime-950" htmlFor="terrain-type">
              Terrain Type
            </label>
            <select
              id="terrain-type"
              value={terrainType}
              onChange={(event) => setTerrainType(event.target.value)}
              className={`${fieldClass} appearance-none [background-image:linear-gradient(45deg,_transparent_50%,_#4d7c0f_50%),_linear-gradient(135deg,_#4d7c0f_50%,_transparent_50%)] [background-position:calc(100%_-_20px)_20px,_calc(100%_-_14px)_20px] [background-repeat:no-repeat] [background-size:6px_6px,_6px_6px] pr-[2.5rem]`}
            >
              <option value="">Select terrain</option>
              <option value="Flat">Flat</option>
              <option value="Gentle Slope">Gentle Slope</option>
              <option value="Steep Slope">Steep Slope</option>
              <option value="Rocky/Uneven">Rocky/Uneven</option>
            </select>
          </div>

          <TerrainPreview terrainType={terrainType} />

          {error && (
            <p className="rounded-xl border-l-4 border-orange-700 bg-orange-50 px-4 py-3 text-sm font-bold text-orange-900 sm:col-span-2">
              {error}
            </p>
          )}

          <button
            className="h-12 rounded-xl bg-gradient-to-r from-green-900 to-lime-700 text-sm font-extrabold text-stone-50 shadow-lg shadow-green-950/20 transition hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-wait disabled:opacity-70 sm:col-span-2"
            disabled={isLoading}
            type="submit"
          >
            {isLoading ? 'Calculating...' : 'Calculate Recommendation'}
          </button>
        </form>

        {result && (
          <section
            className="grid gap-4 rounded-3xl border border-lime-900/10 bg-stone-50/95 p-5 shadow-2xl shadow-lime-950/10 sm:grid-cols-3 sm:p-7"
            aria-live="polite"
          >
            <div className="rounded-2xl bg-lime-100 p-4">
              <p className="mb-2 text-xs font-extrabold uppercase text-lime-950/60">
                Base Plant Count
              </p>
              <strong className="text-2xl font-black text-green-950">
                {formatNumber(result.basePlantCount)}
              </strong>
            </div>
            <div className="rounded-2xl bg-lime-100 p-4">
              <p className="mb-2 text-xs font-extrabold uppercase text-lime-950/60">
                Terrain Factor
              </p>
              <strong className="text-2xl font-black text-green-950">
                {result.terrainFactor.toFixed(2)}
              </strong>
            </div>
            <div className="rounded-2xl bg-lime-100 p-4">
              <p className="mb-2 text-xs font-extrabold uppercase text-lime-950/60">
                Zone Factor
              </p>
              <strong className="text-2xl font-black text-green-950">
                {result.zoneFactor.toFixed(2)}
              </strong>
            </div>
            <div className="rounded-2xl bg-gradient-to-r from-green-900 to-lime-700 p-5 text-stone-50 sm:col-span-3">
              <p className="mb-2 text-xs font-extrabold uppercase text-stone-50/75">
                Recommended Bush Count
              </p>
              <strong className="text-4xl font-black sm:text-5xl">
                {formatNumber(result.optimizedBushCount)}
              </strong>
            </div>
            <p className="leading-7 text-lime-950/70 sm:col-span-3">
              For a {terrainType.toLowerCase()} site in the{' '}
              {plantationZone.toLowerCase()}, plan for approximately{' '}
              {formatNumber(result.optimizedBushCount)} tea bushes while keeping
              the entered row and plant spacing.
            </p>
          </section>
        )}
      </section>
    </main>
  )
}

export default PlantDensity
