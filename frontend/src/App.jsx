import React, { useState, useEffect, useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, ArcLayer, ScatterplotLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM, WebMercatorViewport } from '@deck.gl/core';
import { countriesGeoJson } from './data/countries';
import { geoCentroid, geoInterpolate, geoDistance } from 'd3-geo';
import './App.css';

/* helpers */
const WORLD_BOUNDS = [[-20, -60], [190, 85]];
function getViewState() {
  const {innerWidth: w, innerHeight: h} = window;
  const {longitude, latitude, zoom} =
    new WebMercatorViewport({width: w, height: h}).fitBounds(WORLD_BOUNDS, {padding: 20});
  return {longitude, latitude, zoom, pitch: 40, bearing: 0};
}

function arcHeight(src, dst) {
  const km = geoDistance(src, dst);
  return Math.max(0, km * 0.2);
}

// precalculate all country centroids once
const useCountryCentroids = () =>
  useMemo(
    () =>
      countriesGeoJson.features.map(f => ({
        name: f.properties?.NAME || '',
        coord: geoCentroid(f),
      })),
    [],
  );

/* timing constants */
const ARC_INTERVAL = 700;     // ms
const TRAVEL_TIME  = 500;     // ms - Duration for fade-in
const VISIBLE_TIME = 10_500;  // ms - Total lifespan of an arc before it's purged
const FADE_OUT_DURATION = 500; // ms - Duration for fade-out
const FADE_OUT_START_AGE = VISIBLE_TIME - FADE_OUT_DURATION;

const alphaAtAge = age => {
  age = Math.max(0, age);
  if (age <= TRAVEL_TIME) {
    if (TRAVEL_TIME === 0) return 255;
    return (age / TRAVEL_TIME) * 255;
  }

  else if (age <= FADE_OUT_START_AGE) {
    return 255;
  }

  else if (age <= VISIBLE_TIME) {
    if (FADE_OUT_DURATION <= 0) {
      return 0
    }
    const timeRemainingInLifespan = VISIBLE_TIME - age;
    const alpha = (timeRemainingInLifespan / FADE_OUT_DURATION) * 255;
    return Math.max(0, Math.min(255, alpha));
  }
  else {
    return 0;
  }
};

/* MAIN APP FUNCTION*/
export default function App() {
  const centroids = useCountryCentroids();
  const [arcs, setArcs] = useState([])
  const [logs, setLogs] = useState([]);

  /* demo generator – add one arc every 3s */
  useEffect(() => {
    const id = setInterval(() => {
      // pick two different random countries
      const src = centroids[Math.floor(Math.random() * centroids.length)].coord;
      let dst = src;
      while (dst === src) {
        dst = centroids[Math.floor(Math.random() * centroids.length)].coord;
      }
      setArcs(prev => {
        const next = [...prev, {src, dst, t0: Date.now()}];
        return next.slice(-5);
      });
    }, ARC_INTERVAL);
    fetch('/events')
      .then(r => r.json())
      .then(events =>
        setArcs(
          events.map(e => ({
            source: [e.abuse_geo?.longitude || 0, e.abuse_geo?.latitude || 0],
            target: [0, 0], // TODO: real dest coords
          }))
        )
      )
      .catch(console.error);

    fetch('/logs')
      .then(r => r.json?.() ?? [])
      .then(setLogs)
      .catch(() =>
        setLogs([
          'The threat log is warming up...',
          'No recent attacks yet. Stay vigilant.',
        ])
      );
    return () => clearInterval(id);
  }, [centroids]);

  /* animation clock */
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

  /* purge old arcs */
  useEffect(() => {
    const cutoff = time - VISIBLE_TIME;
    if (arcs.length && arcs[0].t0 < cutoff) {
      setArcs(prevArcs => prevArcs.filter(a => a.t0 >= cutoff));
    }
  }, [time, arcs]);


  /* deck.gl layers */
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
    opacity: 0.9,
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
      const alphaValue = alphaAtAge(age);
      return [0, 180, 255, alphaValue * 1];
    },
    getTargetColor: d => {
      const age = time - d.t0
      const alphaValue = alphaAtAge(age);
      return [0, 150, 255, alphaValue * 0.1];
    },
    updateTriggers: {
      getSourceColor: time,
      getTargetColor: time
    }
  });

  /* small flares on the endpoints */
  const flareLayer = new ScatterplotLayer({
    id: 'endpoint-flares',
    data: arcs.filter(d => (time - d.t0) < VISIBLE_TIME).flatMap(d => [d.src, d.dst]),
    getPosition: p => p,
    radiusMinPixels: 8,
    radiusMaxPixels: 10,
    getFillColor: [0, 180, 255, 240],
    pickable: false,
    updateTriggers: {
      getSourceColor: time,
      getTargetColor: time
    }
  });

  return (
    <div className="app-container">
      {/* MAP */}
      <div className="map-container">
        <h1 className="site-title">HackTrackAI</h1>
        <DeckGL
          viewState={getViewState()}
          controller
          layers={[countryLayer, arcLayer, flareLayer]}
          glOptions={{alpha: true}}
          style={{
            filter: 'drop-shadow(1px 1px 15px rgba(0,174,255,1))', 
            width: '100%', 
            height: '100%'
          }}
        />
      </div>

      {/* LOG PANEL */}
      <div className="logs-container">
        <h2 className="logs-title">Event Logs</h2>
        {logs.map((entry, i) => (
          <div key={i} className="log-entry">
            {entry}
          </div>
        ))}
      </div>
    </div>
  );
}
