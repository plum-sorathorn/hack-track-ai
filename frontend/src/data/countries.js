import { feature } from 'topojson-client';
import world110m from 'world-atlas/countries-110m.json';

export const countriesGeoJson = feature(
  world110m,
  world110m.objects.countries
);
