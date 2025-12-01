/**
 * Geographic utilities for AuraTracking Frontend
 */

/**
 * Calculate distance between two points using Haversine formula
 * @returns Distance in meters
 */
export function haversineDistance(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371000; // Earth's radius in meters
  
  const phi1 = (lat1 * Math.PI) / 180;
  const phi2 = (lat2 * Math.PI) / 180;
  const deltaPhi = ((lat2 - lat1) * Math.PI) / 180;
  const deltaLambda = ((lon2 - lon1) * Math.PI) / 180;
  
  const a =
    Math.sin(deltaPhi / 2) * Math.sin(deltaPhi / 2) +
    Math.cos(phi1) * Math.cos(phi2) *
    Math.sin(deltaLambda / 2) * Math.sin(deltaLambda / 2);
  
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  
  return R * c;
}

/**
 * Calculate bearing between two points
 * @returns Bearing in degrees (0-360)
 */
export function calculateBearing(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const phi1 = (lat1 * Math.PI) / 180;
  const phi2 = (lat2 * Math.PI) / 180;
  const deltaLambda = ((lon2 - lon1) * Math.PI) / 180;
  
  const y = Math.sin(deltaLambda) * Math.cos(phi2);
  const x =
    Math.cos(phi1) * Math.sin(phi2) -
    Math.sin(phi1) * Math.cos(phi2) * Math.cos(deltaLambda);
  
  const theta = Math.atan2(y, x);
  return ((theta * 180) / Math.PI + 360) % 360;
}

/**
 * Get cardinal direction from bearing
 */
export function getCardinalDirection(bearing: number): string {
  const directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return directions[Math.round(bearing / 45) % 8];
}

/**
 * Calculate bounding box for a set of coordinates
 */
export function calculateBounds(
  coordinates: Array<{ lat: number; lon: number }>
): { minLat: number; maxLat: number; minLon: number; maxLon: number } | null {
  if (coordinates.length === 0) return null;
  
  let minLat = coordinates[0].lat;
  let maxLat = coordinates[0].lat;
  let minLon = coordinates[0].lon;
  let maxLon = coordinates[0].lon;
  
  for (const coord of coordinates) {
    minLat = Math.min(minLat, coord.lat);
    maxLat = Math.max(maxLat, coord.lat);
    minLon = Math.min(minLon, coord.lon);
    maxLon = Math.max(maxLon, coord.lon);
  }
  
  return { minLat, maxLat, minLon, maxLon };
}

/**
 * Check if a point is within a bounding box
 */
export function isPointInBounds(
  lat: number,
  lon: number,
  bounds: { minLat: number; maxLat: number; minLon: number; maxLon: number }
): boolean {
  return (
    lat >= bounds.minLat &&
    lat <= bounds.maxLat &&
    lon >= bounds.minLon &&
    lon <= bounds.maxLon
  );
}

/**
 * Calculate center point of coordinates
 */
export function calculateCenter(
  coordinates: Array<{ lat: number; lon: number }>
): { lat: number; lon: number } | null {
  if (coordinates.length === 0) return null;
  
  let sumLat = 0;
  let sumLon = 0;
  
  for (const coord of coordinates) {
    sumLat += coord.lat;
    sumLon += coord.lon;
  }
  
  return {
    lat: sumLat / coordinates.length,
    lon: sumLon / coordinates.length,
  };
}

/**
 * Linear interpolation between two values
 */
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Linear interpolation for angles (handles 360° wraparound)
 */
export function lerpAngle(a: number, b: number, t: number): number {
  let diff = b - a;
  
  // Handle wraparound
  if (diff > 180) diff -= 360;
  if (diff < -180) diff += 360;
  
  return ((a + diff * t) + 360) % 360;
}

/**
 * Interpolate between two GPS positions
 */
export function interpolatePosition(
  pos1: { lat: number; lon: number; bearing?: number },
  pos2: { lat: number; lon: number; bearing?: number },
  t: number
): { lat: number; lon: number; bearing: number } {
  return {
    lat: lerp(pos1.lat, pos2.lat, t),
    lon: lerp(pos1.lon, pos2.lon, t),
    bearing: lerpAngle(pos1.bearing || 0, pos2.bearing || 0, t),
  };
}

/**
 * Convert meters to approximate degrees latitude
 * (1 degree latitude ≈ 111,320 meters)
 */
export function metersToDegreesLat(meters: number): number {
  return meters / 111320;
}

/**
 * Convert meters to approximate degrees longitude
 * (depends on latitude)
 */
export function metersToDegreesLon(meters: number, latitude: number): number {
  const latRad = (latitude * Math.PI) / 180;
  return meters / (111320 * Math.cos(latRad));
}

/**
 * Get grid cell key for heatmap aggregation
 */
export function getGridCellKey(
  lat: number,
  lon: number,
  resolution: number // in degrees
): string {
  const cellLat = Math.floor(lat / resolution);
  const cellLon = Math.floor(lon / resolution);
  return `${cellLat}:${cellLon}`;
}

/**
 * Supported coordinate datums
 */
export type Datum = 'WGS84' | 'SIRGAS2000';

/**
 * Convert coordinates from SIRGAS2000 to WGS84
 * SIRGAS2000 is the official Brazilian geodetic system, with small differences from WGS84
 *
 * @param lat - Latitude in SIRGAS2000
 * @param lon - Longitude in SIRGAS2000
 * @returns Coordinates in WGS84
 */
export function sirgas2000ToWgs84(lat: number, lon: number): { lat: number; lon: number } {
  // Approximate transformation for Brazil region
  // These values are based on the average differences between SIRGAS2000 and WGS84
  // For precise applications, use a proper geodetic transformation library

  // SIRGAS2000 to WGS84 transformation parameters for Brazil
  // These are approximate values and may vary by region
  const deltaLat = -0.0000001; // ~1cm difference in latitude
  const deltaLon = 0.0000002;  // ~2cm difference in longitude

  // Apply transformation
  const wgs84Lat = lat + deltaLat;
  const wgs84Lon = lon + deltaLon;

  return { lat: wgs84Lat, lon: wgs84Lon };
}

/**
 * Convert coordinates from WGS84 to SIRGAS2000
 *
 * @param lat - Latitude in WGS84
 * @param lon - Longitude in WGS84
 * @returns Coordinates in SIRGAS2000
 */
export function wgs84ToSirgas2000(lat: number, lon: number): { lat: number; lon: number } {
  // Inverse transformation
  const deltaLat = 0.0000001;
  const deltaLon = -0.0000002;

  const sirgasLat = lat + deltaLat;
  const sirgasLon = lon + deltaLon;

  return { lat: sirgasLat, lon: sirgasLon };
}

/**
 * Convert coordinates between different datums
 *
 * @param lat - Latitude in source datum
 * @param lon - Longitude in source datum
 * @param fromDatum - Source datum
 * @param toDatum - Target datum
 * @returns Coordinates in target datum
 */
export function convertDatum(
  lat: number,
  lon: number,
  fromDatum: Datum,
  toDatum: Datum
): { lat: number; lon: number } {
  if (fromDatum === toDatum) {
    return { lat, lon };
  }

  if (fromDatum === 'SIRGAS2000' && toDatum === 'WGS84') {
    return sirgas2000ToWgs84(lat, lon);
  }

  if (fromDatum === 'WGS84' && toDatum === 'SIRGAS2000') {
    return wgs84ToSirgas2000(lat, lon);
  }

  throw new Error(`Unsupported datum conversion: ${fromDatum} to ${toDatum}`);
}

/**
 * Apply coordinate offset to correct map base alignment issues
 * Useful for correcting known offsets in map tile providers
 *
 * @param lat - Latitude
 * @param lon - Longitude
 * @param offsetLat - Offset in degrees latitude (positive = north)
 * @param offsetLon - Offset in degrees longitude (positive = east)
 * @returns Adjusted coordinates
 */
export function applyCoordinateOffset(
  lat: number,
  lon: number,
  offsetLat: number,
  offsetLon: number
): { lat: number; lon: number } {
  return {
    lat: lat + offsetLat,
    lon: lon + offsetLon,
  };
}

/**
 * Get recommended offset for Brazil Tocantins region (23S)
 * Based on known offsets for different map providers
 *
 * @param mapProvider - Map provider name
 * @returns Offset in degrees {lat, lon}
 */
export function getRecommendedOffset(mapProvider: string): { lat: number; lon: number } {
  // Offsets are in degrees
  // For Tocantins region (around -11.5° lat, -47° lon)
  // 1 degree ≈ 111km, so small offsets are in meters
  
  switch (mapProvider.toLowerCase()) {
    case 'google':
    case 'googlemaps':
    case 'google-satellite':
      // Google Maps satellite tiles may have slight offset in Brazil
      // Typical offset: ~5-10 meters south, ~5-10 meters west
      return { lat: -0.00005, lon: -0.00005 }; // ~5.5m south, ~5.5m west
    
    case 'esri':
    case 'esri-world-imagery':
    case 'esri-satellite':
    case 'arcgis':
      // Esri World Imagery may have a slight offset in some regions
      // Based on user feedback for Tocantins: ~165m south, ~140m east offset needed
      // This suggests the tiles might be slightly offset
      // Default to 0, but allow manual adjustment
      return { lat: 0, lon: 0 };
    
    case 'osm':
    case 'openstreetmap':
      // OpenStreetMap is generally accurate
      return { lat: 0, lon: 0 };
    
    default:
      return { lat: 0, lon: 0 };
  }
}

