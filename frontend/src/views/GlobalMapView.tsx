import React, { useState, useEffect, useRef } from 'react';
import { 
  Globe, 
  Layers, 
  Plane, 
  Anchor, 
  Activity, 
  MapPin, 
  RefreshCw, 
  ExternalLink 
} from 'lucide-react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { EvidenceFinding } from '../types/osint';

interface GlobalMapViewProps {
  findings: EvidenceFinding[];
}

export const GlobalMapView: React.FC<GlobalMapViewProps> = ({ findings }) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);

  const [layerAircraft, setLayerAircraft] = useState(true);
  const [layerEarthquakes, setLayerEarthquakes] = useState(true);
  const [layerMaritime, setLayerMaritime] = useState(true);
  const [layerEvidence, setLayerEvidence] = useState(true);

  const [earthquakes, setEarthquakes] = useState<any[]>([]);
  const [aircrafts, setAircrafts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch public live situational data
  const fetchSituationalData = async () => {
    setIsLoading(true);
    try {
      // 1. USGS Earthquakes
      const eqRes = await fetch('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson');
      if (eqRes.ok) {
        const eqData = await eqRes.json();
        setEarthquakes(eqData.features || []);
      }

      // 2. OpenSky Aircraft (sample public box)
      const acRes = await fetch('https://opensky-network.org/api/states/all?lamin=20&lomin=-120&lamax=50&lomax=-70');
      if (acRes.ok) {
        const acData = await acRes.json();
        setAircrafts((acData.states || []).slice(0, 30));
      }
    } catch (err) {
      console.warn('Situational telemetry query warning:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSituationalData();
  }, []);

  // Initialize Leaflet map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: [25, 10],
      zoom: 3,
      zoomControl: true,
      attributionControl: false
    });

    // Dark-mode CartoDB tile layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      subdomains: 'abcd',
    }).addTo(map);

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Render Markers onto map
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Clear existing dynamic markers
    map.eachLayer((layer) => {
      if (layer instanceof L.CircleMarker || layer instanceof L.Marker) {
        map.removeLayer(layer);
      }
    });

    // 1. Render Investigation Evidence GPS
    if (layerEvidence) {
      findings.forEach((f) => {
        if (f.entity_type === 'geo_coordinate' && f.raw_payload?.latitude && f.raw_payload?.longitude) {
          const lat = Number(f.raw_payload.latitude);
          const lon = Number(f.raw_payload.longitude);
          if (!isNaN(lat) && !isNaN(lon)) {
            const marker = L.circleMarker([lat, lon], {
              radius: 9,
              fillColor: '#38BDF8',
              color: '#FFFFFF',
              weight: 2,
              fillOpacity: 0.9
            }).addTo(map);
            marker.bindPopup(`
              <div style="color: #080D16; font-family: sans-serif; font-size: 12px;">
                <strong style="color: #0284C7;">Verified Investigation Evidence</strong><br>
                <span>${f.entity_value}</span><br>
                <small>${f.source_name}</small>
              </div>
            `);
          }
        }
      });
    }

    // 2. Render USGS Earthquakes
    if (layerEarthquakes) {
      earthquakes.slice(0, 40).forEach((eq) => {
        const coords = eq.geometry?.coordinates;
        if (coords && coords.length >= 2) {
          const lon = coords[0];
          const lat = coords[1];
          const mag = eq.properties?.mag || 1;
          const marker = L.circleMarker([lat, lon], {
            radius: Math.max(4, mag * 2.5),
            fillColor: '#EF4444',
            color: '#B91C1C',
            weight: 1,
            fillOpacity: 0.7
          }).addTo(map);
          marker.bindPopup(`
            <div style="color: #080D16; font-family: sans-serif; font-size: 12px;">
              <strong style="color: #DC2626;">USGS Seismic Event (M${mag})</strong><br>
              <span>${eq.properties?.place}</span>
            </div>
          `);
        }
      });
    }

    // 3. Render OpenSky Aircraft
    if (layerAircraft) {
      aircrafts.forEach((ac) => {
        const lat = ac[6];
        const lon = ac[5];
        const callsign = (ac[1] || 'N/A').trim();
        const country = ac[2];
        if (lat && lon) {
          const marker = L.circleMarker([lat, lon], {
            radius: 5,
            fillColor: '#F59E0B',
            color: '#D97706',
            weight: 1,
            fillOpacity: 0.8
          }).addTo(map);
          marker.bindPopup(`
            <div style="color: #080D16; font-family: sans-serif; font-size: 12px;">
              <strong style="color: #D97706;">Live Aircraft ADS-B (${callsign})</strong><br>
              <span>Origin: ${country}</span>
            </div>
          `);
        }
      });
    }
  }, [findings, earthquakes, aircrafts, layerEvidence, layerEarthquakes, layerAircraft]);

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col overflow-hidden relative">
      {/* Top Floating Controls */}
      <div className="absolute top-6 left-6 z-[1000] flex items-center space-x-3 bg-[#121D2D]/90 backdrop-blur-md border border-[#26364B] rounded-xl p-2 shadow-2xl">
        <div className="flex items-center space-x-2 px-3 py-1 border-r border-[#26364B]">
          <Globe className="w-4 h-4 text-sky-400" />
          <span className="text-xs font-bold text-[#F8FAFC]">Global Geospatial Layers</span>
        </div>

        <button
          onClick={() => setLayerEvidence(!layerEvidence)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center space-x-1.5 cursor-pointer ${
            layerEvidence ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30' : 'text-[#64748B] hover:text-[#94A3B8]'
          }`}
        >
          <MapPin className="w-3.5 h-3.5" />
          <span>Investigation Evidence</span>
        </button>

        <button
          onClick={() => setLayerAircraft(!layerAircraft)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center space-x-1.5 cursor-pointer ${
            layerAircraft ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' : 'text-[#64748B] hover:text-[#94A3B8]'
          }`}
        >
          <Plane className="w-3.5 h-3.5" />
          <span>Aircraft (OpenSky)</span>
        </button>

        <button
          onClick={() => setLayerEarthquakes(!layerEarthquakes)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center space-x-1.5 cursor-pointer ${
            layerEarthquakes ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' : 'text-[#64748B] hover:text-[#94A3B8]'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>Seismic (USGS)</span>
        </button>

        <button
          onClick={fetchSituationalData}
          disabled={isLoading}
          className="p-1.5 rounded-lg hover:bg-[#1E293B] text-[#94A3B8] hover:text-[#F8FAFC] transition-all cursor-pointer"
          title="Refresh Public Feeds"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-sky-400' : ''}`} />
        </button>
      </div>

      {/* Map Container */}
      <div ref={mapContainerRef} className="flex-1 w-full h-full bg-[#080D16]" />
    </div>
  );
};
