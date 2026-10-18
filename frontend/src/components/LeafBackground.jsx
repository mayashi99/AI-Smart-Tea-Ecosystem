import swirl from '../assets/leaves-wind.webp'
import leafA from '../assets/leaf-a.webp'
import leafB from '../assets/leaf-b.webp'
import leafC from '../assets/leaf-c.webp'
import leafD from '../assets/leaf-d.webp'

// Fixed values (not random) so the layout is stable between renders.
const flyers = [
  { src: leafB, top: 10, size: 30, duration: 17, delay: -2, spin: 540 },
  { src: leafC, top: 24, size: 22, duration: 13, delay: -9, spin: -420 },
  { src: leafD, top: 38, size: 26, duration: 19, delay: -14, spin: 360 },
  { src: leafA, top: 55, size: 44, duration: 23, delay: -5, spin: -300 },
  { src: leafC, top: 70, size: 20, duration: 15, delay: -11, spin: 480 },
  { src: leafB, top: 84, size: 26, duration: 21, delay: -17, spin: -540 },
  { src: leafD, top: 30, size: 18, duration: 12, delay: -6, spin: 600 },
  { src: leafA, top: 4, size: 34, duration: 25, delay: -20, spin: 320 },
  { src: leafB, top: 62, size: 22, duration: 16, delay: -1, spin: -360 },
  { src: leafD, top: 92, size: 24, duration: 18, delay: -8, spin: 420 },
]

export default function LeafBackground({ animated = true }) {
  return (
    <>
      {/* Behind the content: the full leaf swirl carried left-to-right by the wind. */}
      <div className={`leaf-bg ${animated ? '' : 'is-static'}`} aria-hidden="true">
        <span className="swirl-track"><img className="leaf-swirl" src={swirl} alt="" /></span>
        <span className="swirl-track is-second"><img className="leaf-swirl" src={swirl} alt="" /></span>
      </div>
      {/* In front of the content: single leaves blowing across the screen. */}
      {animated && (
        <div className="leaf-fg" aria-hidden="true">
          {flyers.map((leaf, index) => (
            <span
              key={index}
              className="flying-leaf"
              style={{ '--top': `${leaf.top}vh`, '--duration': `${leaf.duration}s`, '--delay': `${leaf.delay}s`, '--spin': `${leaf.spin}deg` }}
            >
              <img src={leaf.src} alt="" style={{ width: leaf.size }} />
            </span>
          ))}
        </div>
      )}
    </>
  )
}
