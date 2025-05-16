import React, { useState, useEffect, useMemo, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, ArcLayer, ScatterplotLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM, WebMercatorViewport } from '@deck.gl/core';
import { countriesGeoJson } from './data/countries';
import { geoCentroid, geoDistance } from 'd3-geo';
import { TransitionGroup, CSSTransition } from 'react-transition-group';
import './App.css';

/* View Initialization */
const WORLD_BOUNDS = [[-20, -60], [190, 85]];
function getViewState() {
  const { innerWidth: w, innerHeight: h } = window;
  const { longitude, latitude, zoom } = new WebMercatorViewport({ width: w, height: h })
    .fitBounds(WORLD_BOUNDS, { padding: 20 });
  return { longitude, latitude, zoom, pitch: 40, bearing: 0 };
}

function arcHeight(src, dst) {
  const km = geoDistance(src, dst);
  return Math.max(0, km * 0.2);
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

/* Simulation */
const EVENT_INTERVAL = 1000; // ms between simulated cyber‑events
const ATTACK_TYPES = ['DDoS', 'Phishing', 'Malware', 'Brute-force', 'SQL injection'];
const MAX_LOGS = 8

function generateSimulatedEvent(centroids) {
  const attacker = centroids[Math.floor(Math.random() * centroids.length)];
  let victim = attacker;
  while (victim === attacker) {
    victim = centroids[Math.floor(Math.random() * centroids.length)];
  }
  const type = ATTACK_TYPES[Math.floor(Math.random() * ATTACK_TYPES.length)];
  const timestamp = Date.now();
  return {
    id: `${timestamp}-${Math.random()}`,
    attacker,
    victim,
    type,
    timestamp,
    summary: `A ${type} attack from ${attacker.name} to ${victim.name}`
  };
}

/* Animation Timing */
const INITIAL_FLARE_FADE_IN_DURATION = 300;
const ARC_FADE_IN_DURATION = 700;
const ELEMENT_FADE_OUT_DURATION = 500;
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
const HOLD_DURATION_AFTER_ALL_APPEAR = 3000;
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

/* Main Component */
export default function App() {
  const centroids = useCountryCentroids();
  const [arcs, setArcs] = useState([]);
  const [logs, setLogs] = useState([]); // {id, text}
  const logRefs = useRef(new Map());    // Map<id, React.RefObject<HTMLDivElement>>

  /* Simulate incoming cyber‑events */
  useEffect(() => {
    if (!centroids.length) return;
    const id = setInterval(() => {
      const ev = generateSimulatedEvent(centroids);
      setArcs(prev => [...prev, { src: ev.attacker.coord, dst: ev.victim.coord, t0: Date.now() }]);
      setLogs(prev => {
        const updated = [{ id: ev.id, text: ev.summary }, ...prev];
        return updated.slice(0, MAX_LOGS);
      });
    }, EVENT_INTERVAL);
    return () => clearInterval(id);
  }, [centroids]);

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

  /* Layers */
  const countryLayer = new GeoJsonLayer({
    id: 'countries',
    data: countriesGeoJson,
    wrapLongitude: true,
    coordinateSystem: COORDINATE_SYSTEM.LNGLAT,
    pickable: true,
    autoHighlight: true,
    highlightColor: [0, 180, 255, 160],
    getFillColor: [0, 0, 0, 0],
    getLineColor: [255, 255, 255, 200],
    lineWidthMinPixels: 0.8,
    stroked: true,
    filled: true,
    opacity: 0.9
  });

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
      return [0, 180, 255, alpha];
    },
    getTargetColor: d => {
      const age = time - d.t0;
      const alpha = arcAlphaAtAge(age);
      return [0, 150, 255, alpha * 0.1];
    },
    updateTriggers: { getSourceColor: time, getTargetColor: time }
  });

  const flareLayer = new ScatterplotLayer({
    id: 'endpoint-flares',
    data: arcs.flatMap(d => {
      const age = time - d.t0;
      const flares = [];
      const startAlpha = flareAlphaAtAge(age, 'start');
      if (startAlpha > 0) flares.push({ position: d.src, alpha: startAlpha, type: 'start' });
      const endAlpha = flareAlphaAtAge(age, 'end');
      if (endAlpha > 0) flares.push({ position: d.dst, alpha: endAlpha, type: 'end' });
      return flares;
    }),
    getPosition: d => d.position,
    radiusMinPixels: 5,
    radiusMaxPixels: 8,
    getFillColor: d => [35, 92, 207, d.alpha],
    pickable: false,
    updateTriggers: { data: time }
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
                  {log.text}
                </div>
              </CSSTransition>
            );
          })}
        </TransitionGroup>
      </div>
    </div>
  );
}
