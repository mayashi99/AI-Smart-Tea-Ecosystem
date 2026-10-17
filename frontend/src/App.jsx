
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'

import Home from './Home/Home'
import HarvestQuality from './components/component2/HarvestQuality/HarvestQuality'
import PlantDensity from './components/component2/PlantDensity/PlantDensity'
import PlantHealth from './components/component2/PlantHelth/PlantHealth'
import HarvestReadiness from './components/component2/HarvestReadiness/HarvestReadiness'
import YieldPrediction from './components/component2/yield prediction/YieldPrediction'
import IntelligentHarvestPlanning from './components/component2/IntelligentHarvestPlanning/IntelligentHarvestPlanning'
import YieldTrends from './components/component2/yield trend/YieldTrends'
import Navbar from './components/Navbar'

function NormalizePath() {
  const location = useLocation()

  const normalizedPath = location.pathname.replace(/^\/{2,}/, '/')

  if (normalizedPath !== location.pathname) {
    return (
      <Navigate
        replace
        to={`${normalizedPath}${location.search}${location.hash}`}
      />
    )
  }

  return null
}

function App() {
  return (
    <BrowserRouter>
      <NormalizePath />

      <Navbar />

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/yield-trends" element={<YieldTrends />} />
        <Route path="/harvest-quality" element={<HarvestQuality />} />

        <Route
          path="/plant-density"
          element={<PlantDensity />}
        />

        <Route
          path="/plantation-health"
          element={<PlantHealth />}
        />

        <Route
          path="/harvest-readiness"
          element={<HarvestReadiness />}
        />
        <Route
          path="/yield-prediction"
          element={<YieldPrediction />}
        />
        <Route
          path="/intelligent-harvest-planning"
          element={<IntelligentHarvestPlanning />}
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
