"use client";

/**
 * Leaflet implementation behind `<LiveMap>` (loaded client-only via next/dynamic).
 *
 * Markers use `L.divIcon` (inline SVG) rather than Leaflet's default PNG icons — this
 * sidesteps the well-known broken-image-path problem under bundlers and lets us rotate
 * the bus marker by heading. The `FitView` child re-frames the map whenever the set of
 * plotted points changes.
 */

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useMemo } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";

import type { LiveMapProps } from "./live-map";

/** Kathmandu — a sane default before any coordinate is known. */
const DEFAULT_CENTER: [number, number] = [27.7172, 85.324];

function busIcon(color = "#1e88e5", heading?: number | null): L.DivIcon {
  const rotation = typeof heading === "number" && Number.isFinite(heading) ? heading : 0;
  return L.divIcon({
    className: "live-bus-marker",
    html: `<div style="transform:rotate(${rotation}deg);width:26px;height:26px;display:flex;align-items:center;justify-content:center;">
      <svg viewBox="0 0 24 24" width="26" height="26" style="filter:drop-shadow(0 1px 2px rgba(0,0,0,.4))">
        <path d="M12 2 L20 21 L12 16 L4 21 Z" fill="${color}" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
      </svg></div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

function stopIcon(): L.DivIcon {
  return L.divIcon({
    className: "live-stop-marker",
    html: `<div style="width:10px;height:10px;border-radius:9999px;background:#64748b;border:2px solid white;box-shadow:0 1px 2px rgba(0,0,0,.3)"></div>`,
    iconSize: [10, 10],
    iconAnchor: [5, 5],
  });
}

/** Re-frame the map to fit all plotted points whenever they change. */
function FitView({ points }: { points: [number, number][] }) {
  const map = useMap();
  const key = points.map((p) => p.join(",")).join("|");
  useEffect(() => {
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], Math.max(map.getZoom(), 14));
      return;
    }
    map.fitBounds(points as L.LatLngBoundsExpression, { padding: [40, 40], maxZoom: 16 });
    // `key` captures the point set; `points` identity changes every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key]);
  return null;
}

export function LiveMapImpl({
  markers,
  stops = [],
  polyline,
  center,
  zoom = 13,
  className,
}: LiveMapProps) {
  const points = useMemo<[number, number][]>(
    () => [
      ...markers.map((m) => [m.lat, m.lng] as [number, number]),
      ...stops.map((s) => [s.lat, s.lng] as [number, number]),
    ],
    [markers, stops],
  );

  const initialCenter = center ?? points[0] ?? DEFAULT_CENTER;

  return (
    <MapContainer
      center={initialCenter}
      zoom={zoom}
      scrollWheelZoom
      className={className ?? "h-[420px] w-full rounded-lg border"}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {polyline && polyline.length > 1 && (
        <Polyline positions={polyline} pathOptions={{ color: "#64748b", weight: 3, opacity: 0.7 }} />
      )}

      {stops.map((s) => (
        <Marker key={`stop-${s.id}`} position={[s.lat, s.lng]} icon={stopIcon()}>
          {s.name ? <Popup>{s.name}</Popup> : null}
        </Marker>
      ))}

      {markers.map((m) => (
        <Marker key={`bus-${m.id}`} position={[m.lat, m.lng]} icon={busIcon(m.color, m.heading)}>
          {m.label ? <Popup>{m.label}</Popup> : null}
        </Marker>
      ))}

      <FitView points={points} />
    </MapContainer>
  );
}

export default LiveMapImpl;
