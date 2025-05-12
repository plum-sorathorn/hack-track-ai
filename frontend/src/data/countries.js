import { feature } from 'topojson-client';
import world110m from 'world-atlas/countries-110m.json';

const allCountries = feature(world110m, world110m.objects.countries);

const BLACKLIST = [10]

export const countriesGeoJson = {
  type: 'FeatureCollection',
  features: allCountries.features.filter(
    f => !BLACKLIST.includes(+f.id)
  )
};