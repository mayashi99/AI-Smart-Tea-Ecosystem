import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Home from './Home/Home'
import PlantDensity from './PlantDensity/PlantDensity'
import PlantHealth from './PlantHelth/PlantHealth'
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
        <Route path="/plant-density" element={<PlantDensity />} />
        <Route path="/plantation-health" element={<PlantHealth />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
