import { useState } from 'react'
import './PlantDensity.css'

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

const ZONE_FACTORS = {
  'Low Country': 1,
  'Mid Country': 0.95,
  'Up Country': 0.87,
}

const ROW_SPACING_METERS = 1.2
const PLANT_SPACING_METERS = 0.75

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
                className={`${fieldClass} plant-density-select`}
              >
                <option value="">Unit</option>
                <option value="Acre">Acre</option>
                <option value="Hectare">Hectare</option>
              </select>
            </div>
          </div>

          <div className="grid gap-2">
            <label className="text-sm font-bold text-lime-950" htmlFor="row-spacing">
              Row Spacing
            </label>
            <input
              aria-readonly="true"
              className={`${fieldClass} cursor-not-allowed bg-stone-100 font-bold`}
              id="row-spacing"
              readOnly
              type="text"
              value={`${ROW_SPACING_METERS} m`}
            />
          </div>

          <div className="grid gap-2">
            <label className="text-sm font-bold text-lime-950" htmlFor="plant-spacing">
              Plant Spacing
            </label>
            <input
              aria-readonly="true"
              className={`${fieldClass} cursor-not-allowed bg-stone-100 font-bold`}
              id="plant-spacing"
              readOnly
              type="text"
              value={`${PLANT_SPACING_METERS} m`}
            />
          </div>

          <div className="grid gap-2">
            <label className="text-sm font-bold text-lime-950" htmlFor="plantation-zone">
              Plantation Zone
            </label>
            <select
              id="plantation-zone"
              value={plantationZone}
              onChange={(event) => setPlantationZone(event.target.value)}
              className={`${fieldClass} plant-density-select`}
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
              className={`${fieldClass} plant-density-select`}
            >
              <option value="">Select terrain</option>
              <option value="Flat">Flat</option>
              <option value="Gentle Slope">Gentle Slope</option>
              <option value="Steep Slope">Steep Slope</option>
              <option value="Rocky/Uneven">Rocky/Uneven</option>
            </select>
          </div>

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
