import { feature } from 'topojson-client';
import world110m from 'world-atlas/countries-110m.json';

const allCountries = feature(world110m, world110m.objects.countries);

// ISO-3166 numeric codes (change to alpha-2/3 or names if you prefer)
const BLACKLIST = [10]

export const countriesGeoJson = {
  type: 'FeatureCollection',
  features: allCountries.features.filter(
    f => !BLACKLIST.includes(+f.id)    // ← keep everything *not* on the list
  )
};