import React, { useState, useEffect } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, ArcLayer, ScatterplotLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM, WebMercatorViewport } from '@deck.gl/core';
import { countriesGeoJson } from './data/countries';
import './App.css';

/* INITIALIZATION OF VIEW */
const WORLD_BOUNDS = [[-20, -60], [190, 85]];
function getViewState() {
  const { innerWidth: width, innerHeight: height } = window;
  const { longitude, latitude, zoom } =
    new WebMercatorViewport({ width, height }).fitBounds(WORLD_BOUNDS, { padding: 20 });
  return { longitude, latitude, zoom, pitch: 40, bearing: 0 };
}

export default function App() {
  const [arcs, setArcs] = useState([]);
  const [logs, setLogs] = useState([]);

  /* fetch events & logs (unchanged) */
  useEffect(() => {
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
}, []);

/* map layers */
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
    greatCircle: true,
    getSourceColor: [0, 180, 255, 200],
    getTargetColor: [0, 180, 255, 20],
    strokeWidth: 3,
    parameters: {
      blendFunc: ['SRC_ALPHA', 'ONE'],
      blendEquation: 'ADD'
    },
});

const flareLayer = new ScatterplotLayer({
  id: 'endpoint-flares',
  data: arcs.flatMap(d => [d.source, d.target]),
  getPosition: p => p,
  radiusMinPixels: 2,
  radiusMaxPixels: 6,
  getFillColor: [0, 180, 255, 220],
  pickable: false
});

  return (
    <div className="app-container">
      {/* MAP */}
      <div className="map-container">
        <h1 className="site-title">HackTrackAI</h1>
       <div
          className="deck-wrapper"
          style={{
            filter: 'drop-shadow(1px 1px 15px rgb(0, 174, 255, 1))',
            width: '100%',
            height: '100%'
          }}
        >
          <DeckGL
            viewState={getViewState()}
            controller={true}
            layers={[countryLayer, arcLayer, flareLayer]}
            glOptions={{ alpha: true }}
            style={{ width: '100%', height: '100%' }}
          />
        </div>
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
