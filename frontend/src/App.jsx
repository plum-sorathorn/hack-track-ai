import React, { useState, useEffect } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, ArcLayer } from '@deck.gl/layers';
import {COORDINATE_SYSTEM} from '@deck.gl/core';
import { countriesGeoJson, countryCentroids } from './data/countries';

const INITIAL_VIEW_STATE = {
  longitude: 0,
  latitude: 0,
  zoom: 0.75,
  pitch: 0,
  bearing: 0
};

export default function App() {
  const [arcs, setArcs] = useState([]);

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

  const countryLayer = new GeoJsonLayer({
    id: 'countries',
    data: countriesGeoJson,
    wrapLongitude: true,
    coordinateSystem: COORDINATE_SYSTEM.LNGLAT,
    stroked:   true,
    filled:    true,
    getFillColor: [70, 70, 70],
    getLineColor: [200, 200, 200],
    getLineWidth: 1,
    pickable: true,
  });

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
    <DeckGL
      initialViewState={INITIAL_VIEW_STATE}
      controller={false}
      layers={[countryLayer, arcLayer]}
      style={{
        width: '100%',
        height: '100vh',
        backgroundColor: 'transparent'
      }}
      glOptions={{ alpha: true }}
    />
  );
}
