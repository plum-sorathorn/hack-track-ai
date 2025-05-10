import { feature } from 'topojson-client';
import world110m from 'world-atlas/countries-110m.json';

export const countriesGeoJson = feature(
  world110m,
  world110m.objects.countries
);

export const countryCentroids = {
  US: [-98.5795, 39.8283],
  CN: [104.1954, 35.8617],
  RU: [105.3188, 61.5240],
  IN: [78.9629, 20.5937],
  DE: [10.4515, 51.1657],
};