// App.jsx
import React, { useState, useEffect } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, ArcLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM } from '@deck.gl/core';
import { WebMercatorViewport } from '@deck.gl/core';
import { countriesGeoJson } from './data/countries';
import './App.css'

const WORLD_BOUNDS = [[-180, -60], [180, 85]];

function getViewState() {
  const { innerWidth: width, innerHeight: height } = window;
  const { longitude, latitude, zoom } =
        new WebMercatorViewport({ width, height })
          .fitBounds(WORLD_BOUNDS, { padding: 20 });
  return { longitude, latitude, zoom, pitch: 30, bearing: 0 };
}

export default function App() {
  const [arcs, setArcs] = useState([]);
  const [hoveredCountry, setHoveredCountry] = useState(null);
  const [viewState] = useState(getViewState());

  /* handing of event arcs */
  useEffect(() => {
    fetch('/events')
      .then(r => r.json())
      .then(events => {
        setArcs(
          events.map(e => ({
            source: [e.abuse_geo.longitude, e.abuse_geo.latitude],
            target: countryCentroids[e.destCountry] || [0, 0]
          }))
        );
      })
      .catch(console.error);
  }, []);

  // Stub for hover handler
  const handleCountryHover = info => {
    setHoveredCountry(info.object);
    console.log('hovered country:', info.object);
  };

  /* define layer for the countries for interactive map */
  const countryLayer = new GeoJsonLayer({
    id: 'countries',
    data: countriesGeoJson,
    wrapLongitude: true,
    coordinateSystem: COORDINATE_SYSTEM.LNGLAT,
    stroked: true,
    filled: true,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 0, 100],
    onHover: handleCountryHover,
    getFillColor: feature => {
      return [70, 70, 70];
    },
    updateTriggers: {
      getFillColor: hoveredCountry
    },
    getLineColor: [0, 0, 0, 255],
    lineWidthMinPixels: 0.5,
  });

  /* layer for the arcs */
  const arcLayer = new ArcLayer({
    id: 'attack-arcs',
    data: arcs,
    getSourcePosition: d => d.source,
    getTargetPosition: d => d.target,
    getSourceColor: [255, 180, 0],
    getTargetColor: [255, 180, 0],
    strokeWidth: 3,
    greatCircle: true
  });

  return (
    <div className="map-container">
      <DeckGL
        style={{
          width: '100%',
          height: '100%',
        }}
        viewState={viewState}
        controller={false}
        interactiveLayerIds={['countries']}
        layers={[countryLayer, arcLayer]}
        glOptions={{ alpha: true }}
    />
    </div>
  );
}
