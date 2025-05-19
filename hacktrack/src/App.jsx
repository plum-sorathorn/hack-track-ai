import React, { useState, useEffect, useMemo, useRef } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, ArcLayer, ScatterplotLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM, WebMercatorViewport } from '@deck.gl/core';
import { countriesGeoJson } from './data/countries';
import { geoCentroid, geoDistance } from 'd3-geo';
import { TransitionGroup, CSSTransition } from 'react-transition-group';
import './App.css';

/* View Initialization */
const WORLD_BOUNDS = [[200, -55], [-160, 85]];
function getViewState() {
  const { innerWidth: w, innerHeight: h } = window;
  const { longitude, latitude, zoom } = new WebMercatorViewport({ width: w, height: h })
    .fitBounds(WORLD_BOUNDS, { padding: 30 });
  return { longitude, latitude, zoom, pitch: 40, bearing: 0 };
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

const MAX_LOGS = 8

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

/* Main Component */
export default function App() {
  const centroids = useCountryCentroids();
  const [arcs, setArcs] = useState([]);
  const [logs, setLogs] = useState([]);
  const logRefs = useRef(new Map());

  useEffect(() => {
    if (!centroids.length) return;

    const fetchLiveLogs = async () => {
      try {
        const res = await fetch('http://localhost:8000/logs');
        const text = await res.text();
        if (!text) return;

        const data = JSON.parse(text);
        if (!data.logs) return;

        data.logs.forEach(([event, arc, summary]) => {
          const t0 = Date.now();

          if (arc && arc.src && arc.dst) {
            setArcs(prev => [...prev, { src: arc.src, dst: arc.dst, t0 }]);
          }

          if (arc && JSON.stringify(arc.src) === JSON.stringify([0, 0]) && arc.dst) {
            setArcs(prev => [...prev, { src: arc.dst, dst: arc.dst, t0 }]);
          }

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
        });
      } catch (err) {
        console.error("Failed to fetch logs:", err);
      }
    };

    const intervalId = setInterval(fetchLiveLogs, 10000);
    fetchLiveLogs(); // Run immediately on mount

    return () => clearInterval(intervalId); // Cleanup on unmount
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
      return [153, 225, 255, alpha];
    },
    getTargetColor: d => {
      const age = time - d.t0;
      const alpha = arcAlphaAtAge(age);
      return [70, 104, 117, alpha * 0.1];
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
    radiusMinPixels: 4,
    radiusMaxPixels: 4,
    getFillColor: d => [54, 111, 133, d.alpha],
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
