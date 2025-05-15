import React, { useState, useEffect, useMemo } from 'react';
import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, ArcLayer, ScatterplotLayer } from '@deck.gl/layers';
import { COORDINATE_SYSTEM, WebMercatorViewport } from '@deck.gl/core';
import { countriesGeoJson } from './data/countries'; // Ensure this path is correct
import { geoCentroid, geoDistance } from 'd3-geo';
import './App.css';

const WORLD_BOUNDS = [[-20, -60], [190, 85]];
function getViewState() {
  const { innerWidth: w, innerHeight: h } = window;
  const { longitude, latitude, zoom } =
    new WebMercatorViewport({ width: w, height: h }).fitBounds(WORLD_BOUNDS, { padding: 20 });
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
        coord: geoCentroid(f),
      })),
    [],
  );

const ARC_INTERVAL = 700; // Interval for new arcs

// --- Animation Timing Constants ---
const INITIAL_FLARE_FADE_IN_DURATION = 300; // Time for a flare to fade in
const ARC_FADE_IN_DURATION = 700;         // Time for the arc to "travel" or fully appear
const ELEMENT_FADE_OUT_DURATION = 500;    // Common fade out duration for all elements

const ARC_START_DELAY_AFTER_INITIAL_FLARE = 100; // Arc visuals begin 100ms after initial flare starts fading in.

// --- Calculated Timings (relative to an event's t0, all in milliseconds) ---

// Initial Flare (Flare 1 at source)
const flare1_fadeInStartTime = 0;
const flare1_fadeInEndTime = flare1_fadeInStartTime + INITIAL_FLARE_FADE_IN_DURATION;

// Arc
const arc_fadeInStartTime = flare1_fadeInStartTime + ARC_START_DELAY_AFTER_INITIAL_FLARE;
const arc_fadeInEndTime = arc_fadeInStartTime + ARC_FADE_IN_DURATION;

// Destination Flare (Flare 2 at destination)
// This flare will start fading in before the arc completes and finish fading in exactly when the arc finishes.
const flare2_fadeInStartTime = arc_fadeInEndTime - INITIAL_FLARE_FADE_IN_DURATION;
const flare2_fadeInEndTime = arc_fadeInEndTime; // Flare 2 finishes appearing when arc finishes appearing

// Hold Duration: Time all elements remain fully visible after the last one (Arc and Dest Flare) has fully appeared.
const lastElementFullyAppearedTime = Math.max(flare1_fadeInEndTime, arc_fadeInEndTime, flare2_fadeInEndTime);
const HOLD_DURATION_AFTER_ALL_APPEAR = 3000; // Hold for 3 seconds (adjust as needed)

// Fade Out Start Times:
// Elements start fading out after the hold period, maintaining the original appearance order.
const fadeOutPhaseGlobalStartTime = lastElementFullyAppearedTime + HOLD_DURATION_AFTER_ALL_APPEAR;

// Individual fade out start times, offset from the global fade out start time
const flare1_fadeOutStartTime = fadeOutPhaseGlobalStartTime + (flare1_fadeInStartTime - flare1_fadeInStartTime); // Effectively fadeOutPhaseGlobalStartTime
const arc_fadeOutStartTime = fadeOutPhaseGlobalStartTime + (arc_fadeInStartTime - flare1_fadeInStartTime);
const flare2_fadeOutStartTime = fadeOutPhaseGlobalStartTime + (flare2_fadeInStartTime - flare1_fadeInStartTime);

// Total Lifecycle Duration (for cleaning up arcs from state)
// This is when the last element (Destination Flare, in this sequence) finishes fading out.
const flare2_fadeOutEndTime = flare2_fadeOutStartTime + ELEMENT_FADE_OUT_DURATION;
const TOTAL_LIFECYCLE_DURATION = flare2_fadeOutEndTime; // Max age of an arc visual

const easeInOutQuad = t => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;

// Helper function to calculate alpha based on lifecycle phases
const getAlphaForLifecycle = (age, fadeInStartTime, fadeInDuration, fadeOutStartTime, fadeOutDuration) => {
  // Before fade-in starts
  if (age < fadeInStartTime) {
    return 0;
  }
  // After fade-out ends
  if (age >= fadeOutStartTime + fadeOutDuration) {
    return 0;
  }

  // Fade In Phase
  if (age >= fadeInStartTime && age < fadeInStartTime + fadeInDuration) {
    const progress = (age - fadeInStartTime) / fadeInDuration;
    return Math.round(255 * easeInOutQuad(progress));
  }

  // Fully Visible Phase (between fade-in end and fade-out start)
  if (age >= fadeInStartTime + fadeInDuration && age < fadeOutStartTime) {
    return 255;
  }

  // Fade Out Phase
  if (age >= fadeOutStartTime && age < fadeOutStartTime + fadeOutDuration) { // Condition was age < fadeOutStartTime + fadeOutDuration
    const progress = (age - fadeOutStartTime) / fadeOutDuration;
    return Math.round(255 * (1 - easeInOutQuad(progress)));
  }
  
  return 0; // Default catch-all (should ideally be covered by above)
};


const arcAlphaAtAge = age => {
  return getAlphaForLifecycle(
    age,
    arc_fadeInStartTime,
    ARC_FADE_IN_DURATION,
    arc_fadeOutStartTime,
    ELEMENT_FADE_OUT_DURATION
  );
};

const flareAlphaAtAge = (age, type) => {
  if (type === 'start') { // Source flare
    return getAlphaForLifecycle(
      age,
      flare1_fadeInStartTime,
      INITIAL_FLARE_FADE_IN_DURATION,
      flare1_fadeOutStartTime,
      ELEMENT_FADE_OUT_DURATION
    );
  } else if (type === 'end') { // Destination flare
    return getAlphaForLifecycle(
      age,
      flare2_fadeInStartTime,
      INITIAL_FLARE_FADE_IN_DURATION, // Assuming dest flare has same fade-in duration as initial
      flare2_fadeOutStartTime,
      ELEMENT_FADE_OUT_DURATION
    );
  }
  return 0;
};

export default function App() {
  const centroids = useCountryCentroids();
  const [arcs, setArcs] = useState([]);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    const id = setInterval(() => {
      const src = centroids[Math.floor(Math.random() * centroids.length)].coord;
      let dst = src;
      while (dst === src) {
        dst = centroids[Math.floor(Math.random() * centroids.length)].coord;
      }
      setArcs(prev => {
        const next = [...prev, { src, dst, t0: Date.now() }];
        return next.slice(-10); // Keep up to 10 arcs, adjust as needed
      });
    }, ARC_INTERVAL);

    // Initial data fetching (example structure)
    fetch('/events') // Replace with your actual API endpoint
      .then(r => r.json())
      .then(events => {
        if (Array.isArray(events)) {
            setArcs(
                events.map(e => ({
                  src: [e.abuse_geo?.longitude || 0, e.abuse_geo?.latitude || 0],
                  dst: [0, 0], // Assuming a default destination or that your event data provides it
                  t0: Date.now() - Math.random() * 1000, // Stagger initial events slightly
                })).slice(-10) // Limit initial fetched arcs too
              );
        }
      }
      )
      .catch(console.error);

    fetch('/logs') // Replace with your actual API endpoint
      .then(r => r.json?.() ?? [])
      .then(setLogs)
      .catch(() =>
        setLogs([
          'The threat log is warming up...',
          'No recent attacks yet. Stay vigilant.',
        ])
      );

    return () => clearInterval(id);
  }, [centroids]); // Removed arcs from here to prevent potential re-fetch loops if not intended

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

  useEffect(() => {
    // Cleanup arcs that have completed their lifecycle
    const cutoff = time - TOTAL_LIFECYCLE_DURATION;
    if (arcs.some(a => a.t0 < cutoff)) { // Check if any arc is old enough to be removed
        setArcs(prevArcs => prevArcs.filter(a => a.t0 >= cutoff));
    }
  }, [time, arcs]); // arcs dependency is needed here to react to changes in the arcs array


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
      const alpha = arcAlphaAtAge(age);
      return [0, 180, 255, alpha];
    },
    getTargetColor: d => {
      const age = time - d.t0;
      const alpha = arcAlphaAtAge(age);
      return [0, 150, 255, alpha * 0.1]; 
    },
    updateTriggers: {
      getSourceColor: time,
      getTargetColor: time,
    },
  });

  const flareLayer = new ScatterplotLayer({
    id: 'endpoint-flares',
    data: arcs.flatMap(d => {
      const age = time - d.t0;
      const flares = [];

      const startFlareAlpha = flareAlphaAtAge(age, 'start');
      if (startFlareAlpha > 0) {
        flares.push({ position: d.src, alpha: startFlareAlpha, type: 'start' });
      }

      const endFlareAlpha = flareAlphaAtAge(age, 'end');
      if (endFlareAlpha > 0) {
        flares.push({ position: d.dst, alpha: endFlareAlpha, type: 'end' });
      }
      return flares;
    }),
    getPosition: d => d.position,
    radiusMinPixels: 5,
    radiusMaxPixels: 8,
    getFillColor: d => [35, 92, 207, d.alpha],
    pickable: false,
    updateTriggers: {
      data: time
    },
  });

  return (
    <div className="app-container">
      <div className="map-container">
        <h1 className="site-title">HackTrackAI</h1>
        <DeckGL
          viewState={getViewState()}
          controller
          layers={[countryLayer, arcLayer, flareLayer]}
          glOptions={{ alpha: true }} // Ensure GL context supports transparency
          style={{
            filter: 'drop-shadow(1px 1px 15px rgba(0,174,255,1))',
            width: '100%',
            height: '100%'
          }}
        />
      </div>
      <div className="logs-container">
        <h2 className="logs-title">Event Logs</h2>
        {logs.map((entry, i) => (
          <div key={i} className="log-entry">
            {typeof entry === 'object' ? JSON.stringify(entry) : entry}
          </div>
        ))}
      </div>
    </div>
  );
}