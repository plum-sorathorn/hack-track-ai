import React, { useState, useEffect, useMemo, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, ArcLayer, ScatterplotLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM, WebMercatorViewport } from '@deck.gl/core';
import { countriesGeoJson } from './data/countries';
import { geoCentroid, geoDistance } from 'd3-geo';
import { TransitionGroup, CSSTransition } from 'react-transition-group';
import './App.css';

/* View Initialization */

const INITIAL_VIEW_STATE = {
  longitude: 25,
  latitude: 25,
  zoom: 0.9,
  pitch: 40,
  bearing: 0,
  minZoom: 5,
  maxZoom: 10
};

function getViewState() {
  return INITIAL_VIEW_STATE;
}
function arcHeight(src, dst) {
  const km = geoDistance(src, dst);
  return Math.max(0, km * 0.25);
}

const useCountryCentroids = () =>
  useMemo(
    () =>
      countriesGeoJson.features.map(f => ({
        name: f.properties?.NAME || '',
        coord: geoCentroid(f)
      })),
    []
  );

// log and fetch timings
const MAX_LOGS = 4
const INTERVAL_FETCH = 20000;
const INTERVAL_DRAIN = 1500;

/* Animation Timing */
const INITIAL_FLARE_FADE_IN_DURATION = 400;
const ARC_FADE_IN_DURATION = 800;
const ELEMENT_FADE_OUT_DURATION = 400;
const ARC_START_DELAY_AFTER_INITIAL_FLARE = 100;

const flare1_fadeInStartTime = 0;
const flare1_fadeInEndTime = flare1_fadeInStartTime + INITIAL_FLARE_FADE_IN_DURATION;
const arc_fadeInStartTime = flare1_fadeInStartTime + ARC_START_DELAY_AFTER_INITIAL_FLARE;
const arc_fadeInEndTime = arc_fadeInStartTime + ARC_FADE_IN_DURATION;
const flare2_fadeInStartTime = arc_fadeInEndTime - INITIAL_FLARE_FADE_IN_DURATION;
const flare2_fadeInEndTime = arc_fadeInEndTime;

const lastElementFullyAppearedTime = Math.max(
  flare1_fadeInEndTime,
  arc_fadeInEndTime,
  flare2_fadeInEndTime
);
const HOLD_DURATION_AFTER_ALL_APPEAR = 3500;
const fadeOutPhaseGlobalStartTime = lastElementFullyAppearedTime + HOLD_DURATION_AFTER_ALL_APPEAR;
const flare1_fadeOutStartTime = fadeOutPhaseGlobalStartTime;
const arc_fadeOutStartTime = fadeOutPhaseGlobalStartTime + (arc_fadeInStartTime - flare1_fadeInStartTime);
const flare2_fadeOutStartTime = fadeOutPhaseGlobalStartTime + (flare2_fadeInStartTime - flare1_fadeInStartTime);
const flare2_fadeOutEndTime = flare2_fadeOutStartTime + ELEMENT_FADE_OUT_DURATION;
const TOTAL_LIFECYCLE_DURATION = flare2_fadeOutEndTime;

const easeInOutQuad = t => (t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t);

const getAlphaForLifecycle = (age, fadeInStartTime, fadeInDuration, fadeOutStartTime, fadeOutDuration) => {
  if (age < fadeInStartTime) return 0;
  if (age >= fadeOutStartTime + fadeOutDuration) return 0;
  if (age < fadeInStartTime + fadeInDuration) {
    const progress = (age - fadeInStartTime) / fadeInDuration;
    return Math.round(255 * easeInOutQuad(progress));
  }
  if (age < fadeOutStartTime) return 255;
  const progress = (age - fadeOutStartTime) / fadeOutDuration;
  return Math.round(255 * (1 - easeInOutQuad(progress)));
};

const arcAlphaAtAge = age =>
  getAlphaForLifecycle(age, arc_fadeInStartTime, ARC_FADE_IN_DURATION, arc_fadeOutStartTime, ELEMENT_FADE_OUT_DURATION);

const flareAlphaAtAge = (age, type) => {
  if (type === 'start') {
    return getAlphaForLifecycle(age, flare1_fadeInStartTime, INITIAL_FLARE_FADE_IN_DURATION, flare1_fadeOutStartTime, ELEMENT_FADE_OUT_DURATION);
  }
  return getAlphaForLifecycle(age, flare2_fadeInStartTime, INITIAL_FLARE_FADE_IN_DURATION, flare2_fadeOutStartTime, ELEMENT_FADE_OUT_DURATION);
};

// arc simulation for now:
const generateRandomArcs = (centroids, count = 1) => {
  const now = Date.now();
  const result = [];
  for (let i = 0; i < count; i++) {
    const srcCentroid = centroids[Math.floor(Math.random() * centroids.length)];
    // 1 in 4 chance of a self-attack for demo purposes
    const isSelfAttack = Math.random() < 0.25;
    const dstCentroid = isSelfAttack ? srcCentroid : centroids[Math.floor(Math.random() * centroids.length)];

    result.push({
      src: srcCentroid.coord,
      dst: dstCentroid.coord,
      t0: now
    });
  }
  return result;
};

/* Main Component */
export default function App() {
  const [logs, setLogs] = useState([]);
  const [arcs, setArcs] = useState([]);
  const centroids = useCountryCentroids();
  const logQueue = useRef([]);
  const logRefs = useRef(new Map());

  // // Fetch logs periodically and add to queue
  // useEffect(() => {

  //   const fetchLiveLogs = async () => {
  //     try {
  //       const res = await fetch('http://localhost:8000/logs');
  //       console.log("Fetching Logs")
  //       const text = await res.text();
  //       if (!text) return;
  //       const data = JSON.parse(text);
  //       if (!data.logs) return;

  //       logQueue.current.push(...data.logs);
  //     } catch (err) {
  //       console.error("Failed to fetch logs:", err);
  //     }
  //   };

  //   const fetchInterval = setInterval(fetchLiveLogs, INTERVAL_FETCH);
  //   fetchLiveLogs(); // run once immediately

  //   return () => clearInterval(fetchInterval);
  // }, [centroids]);

  // placeholder for fetch logs function
  useEffect(() => {
    const generateRandomArcsInterval = setInterval(() => {
      const newArcs = generateRandomArcs(centroids, 1); // Generate 1 random arc
      setArcs(prev => [...prev, ...newArcs]);

      // Optionally, generate a random log entry for each arc
      const newLog = {
        id: `${Date.now()}-${Math.random()}`,
        text: `Simulated attack from ${newArcs[0].src} to ${newArcs[0].dst}`,
        meta: {
          source: 'Simulated',
          attack: 'Simulated Attack',
          timestamp: Date.now(),
        },
      };
      setLogs(prev => [newLog, ...prev].slice(0, MAX_LOGS));
    }, 1000);

    return () => clearInterval(generateRandomArcsInterval);
  }, [centroids]);

  // Drain queue and add entries one by one
  useEffect(() => {
    const drainInterval = setInterval(() => {
      if (logQueue.current.length === 0) return;

      const [event, arc, summary] = logQueue.current.shift();
      const t0 = Date.now();

      // Add arc
      if (arc && JSON.stringify(arc.src) === JSON.stringify([0, 0]) && arc.dst) {
        setArcs(prev => [...prev, { src: arc.dst, dst: arc.dst, t0 }]);
      } else if (arc && arc.src && arc.dst) {
        setArcs(prev => [...prev, { src: arc.src, dst: arc.dst, t0 }]);
      } 

      // Add log
      setLogs(prev => {
        const newLog = {
          id: `${t0}-${Math.random()}`,
          text: summary,
          meta: {
            source: event.source,
            attack: event.abuse_attack || event.otx_name,
            timestamp: event.timestamp
          }
        };
        return [newLog, ...prev].slice(0, MAX_LOGS);
      });
    }, INTERVAL_DRAIN);

    return () => clearInterval(drainInterval);
  }, []);


  /* Animation clock */
  const [time, setTime] = useState(Date.now());
  useEffect(() => {
    let raf;
    const tick = () => {
      setTime(Date.now());
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  /* Prune expired arcs */
  useEffect(() => {
    const cutoff = time - TOTAL_LIFECYCLE_DURATION;
    if (arcs.some(a => a.t0 < cutoff)) {
      setArcs(prev => prev.filter(a => a.t0 >= cutoff));
    }
  }, [time, arcs]);

  /* Country Layer — bright outlines on dark map */
  const countryLayer = new GeoJsonLayer({
    id: 'countries',
    data: countriesGeoJson,
    wrapLongitude: true,
    coordinateSystem: COORDINATE_SYSTEM.LNGLAT,
    pickable: true,
    autoHighlight: true,
    highlightColor: [230, 230, 230, 180], // light gray-white highlight
    getFillColor: [0, 0, 0, 0], // transparent
    getLineColor: [200, 200, 200, 220], // subtle white-gray outline
    lineWidthMinPixels: 0.8,
    stroked: true,
    filled: true,
    opacity: 0.9
  });

  /* Arc Layer — white fading arcs */
  const arcLayer = new ArcLayer({
    id: 'attack-arcs',
    data: arcs,
    getSourcePosition: d => d.src,
    getTargetPosition: d => d.dst,
    getHeight: d => arcHeight(d.src, d.dst),
    getWidth: 3,
    getSourceColor: d => {
      const age = time - d.t0;
      const alpha = arcAlphaAtAge(age);
      return [255, 255, 255, alpha];
    },
    getTargetColor: d => {
      const age = time - d.t0;
      const alpha = arcAlphaAtAge(age);
      return [180, 180, 180, alpha * 0.3];
    },
    updateTriggers: { getSourceColor: time, getTargetColor: time }
  });

  /* Flare Layer – white endpoint glows */
  const flareLayer = new ScatterplotLayer({
    id: 'endpoint-flares',
    data: arcs.flatMap(d => {
      const age = time - d.t0;
      const flares = [];
      const hasRealSrc = d.src && (d.src[0] !== 0 || d.src[1] !== 0);
      const hasRealDst = d.dst && (d.dst[0] !== 0 || d.dst[1] !== 0);
      const isSelfAttack = hasRealSrc && hasRealDst && 
        Math.abs(d.src[0] - d.dst[0]) < 0.01 && 
        Math.abs(d.src[1] - d.dst[1]) < 0.01;

      if (hasRealSrc && !isSelfAttack) {
        const startAlpha = flareAlphaAtAge(age, 'start');
        if (startAlpha > 0) {
          // Animate scale during fade-in
          let animScale = 1;
          if (age < flare1_fadeInEndTime) {
            const fadeProgress = Math.min(1, (age - flare1_fadeInStartTime) / INITIAL_FLARE_FADE_IN_DURATION);
            animScale = 0.3 + (easeInOutQuad(fadeProgress) * 0.7); // Grow from 0.3 to 1
          }
          flares.push({ position: d.src, alpha: startAlpha, type: 'start', scale: animScale, age });
        }
      }

      if (hasRealDst) {
        const endAlpha = flareAlphaAtAge(age, 'end');
        if (endAlpha > 0) {
          if (isSelfAttack) {
            const pulseSpeed = 0.003;
            const pulsePhase = (age * pulseSpeed) % (Math.PI * 2);
            const pulseScale = 2.5 + Math.sin(pulsePhase) * 1.2;
            flares.push({ 
              position: d.dst, 
              alpha: endAlpha, 
              type: 'self-attack', 
              scale: pulseScale,
              age 
            });
          } else {
            let baseScale = hasRealSrc ? 1 : 4;
            // Animate scale during fade-in for end flare
            if (age < flare2_fadeInEndTime) {
              const fadeProgress = Math.min(1, (age - flare2_fadeInStartTime) / INITIAL_FLARE_FADE_IN_DURATION);
              const growFactor = 0.3 + (easeInOutQuad(fadeProgress) * 0.7);
              baseScale *= growFactor;
            }
            flares.push({ position: d.dst, alpha: endAlpha, type: 'end', scale: baseScale, age });
          }
        }
      }

      if (!hasRealSrc && !hasRealDst) {
        const ambientAlpha = flareAlphaAtAge(age, 'end');
        if (ambientAlpha > 0) {
          let ambientScale = 6;
          // Animate ambient flare growth
          if (age < flare2_fadeInEndTime) {
            const fadeProgress = Math.min(1, (age - flare2_fadeInStartTime) / INITIAL_FLARE_FADE_IN_DURATION);
            ambientScale *= (0.5 + easeInOutQuad(fadeProgress) * 0.5);
          }
          flares.push({
            position: [0, 20],
            alpha: ambientAlpha * 0.4,
            type: 'ambient',
            scale: ambientScale,
            age
          });
        }
      }

      return flares;
    }),
    getPosition: d => d.position,
    radiusUnits: 'pixels',
    getRadius: d => {
      // Base radius in pixels for each type
      const baseRadius = d.type === 'self-attack' ? 2 : 
                        d.type === 'ambient' ? 6 : 
                        d.type === 'end' ? 5 : 5;
      return baseRadius * d.scale;
    },
    getFillColor: d => {
      if (d.type === 'self-attack') {
        return [240, 245, 255, d.alpha * 0.7];
      }
      if (d.type === 'ambient') return [255, 255, 255, d.alpha * 0.6];
      return [220, 220, 220, d.alpha * 0.4];
    },
    pickable: false,
    updateTriggers: { data: time, getFillColor: time, getRadius: time }
  });

  return (
    <div className="app-container">
      <div className="map-container">
        <h1 className="site-title">HackTrackAI</h1>
        <DeckGL
          viewState={getViewState()}
          controller
          layers={[countryLayer, arcLayer, flareLayer]}
          glOptions={{ alpha: true }}
          style={{
            filter: 'drop-shadow(1px 1px 10px rgba(0,174,255,1))',
            width: '100%',
            height: '100%'
          }}
        />
      </div>
      <div className="logs-container">
        <h2 className="logs-title">Event Logs</h2>
        <TransitionGroup component={null}>
          {logs.map(log => {
            let ref = logRefs.current.get(log.id);
            if (!ref) {
              ref = React.createRef();
              logRefs.current.set(log.id, ref);
            }
            return (
              <CSSTransition
                key={log.id}
                nodeRef={ref}
                timeout={300}
                classNames="log"
                onExited={() => logRefs.current.delete(log.id)}
              >
                <div ref={ref} className="log-entry">
                  <div>{log.text}</div>
                  <div style={{ fontSize: '0.7em', color: 'var(--text-dim)', marginTop: '0.2em' }}>
                    {log.meta?.source} • {log.meta?.attack} • {new Date(log.meta?.timestamp).toLocaleString()}
                  </div>
                </div>
              </CSSTransition>
            );
          })}
        </TransitionGroup>
      </div>
    </div>
  );
}