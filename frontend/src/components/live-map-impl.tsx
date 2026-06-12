"use client";

/**
 * Leaflet implementation behind `<LiveMap>` (loaded client-only via next/dynamic).
 *
 * Markers use `L.divIcon` (inline SVG) rather than Leaflet's default PNG icons — this
 * sidesteps the well-known broken-image-path problem under bundlers and lets us tint the
 * bus badge with its route color, point a small heading arrow, and enlarge the selected one.
 *
 * `FitView` frames the map to all points but keys on marker/stop IDENTITY (not their
 * coordinates), so live position ticks don't constantly recenter the view — it only
 * refits when buses enter/leave. `FlyToFocus` pans to a selected bus on demand.
 */

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useMemo } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";

import type { LiveMapProps } from "./live-map";

/** Kathmandu — a sane default before any coordinate is known. */
const DEFAULT_CENTER: [number, number] = [27.7172, 85.324];
const FOCUS_ZOOM = 16;

function busIcon(color = "#1e88e5", heading?: number | null, selected = false): L.DivIcon {
  const hasHeading = typeof heading === "number" && Number.isFinite(heading);
  const rotation = hasHeading ? heading : 0;
  const size = selected ? 38 : 28;
  const ring = selected
    ? `<circle cx="12" cy="12" r="11.5" fill="none" stroke="${color}" stroke-width="1.5" opacity="0.45"/>`
    : "";
  // Directional pointer on the badge rim — only drawn when we actually have a heading,
  // and rotated about the badge centre so the bus glyph itself stays upright/readable.
  const pointer = hasHeading
    ? `<g transform="rotate(${rotation} 12 12)"><path d="M12 0.4 L14.7 4.8 L9.3 4.8 Z" fill="${color}" stroke="white" stroke-width="0.9" stroke-linejoin="round"/></g>`
    : "";
  return L.divIcon({
    className: "live-bus-marker",
    html: `<div style="width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center;">
      <svg viewBox="0 0 24 24" width="${size}" height="${size}" style="filter:drop-shadow(0 1px 2px rgba(0,0,0,.45))">
        ${ring}
        ${pointer}
        <circle cx="12" cy="12" r="9.5" fill="${color}" stroke="white" stroke-width="1.5"/>
        <g transform="translate(5.4 5.4) scale(0.55)" fill="none" stroke="white" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
          <rect width="16" height="16" x="4" y="3" rx="2"/>
          <path d="M4 11h16"/>
          <path d="M10 6h4"/>
          <path d="M8 15h.01"/>
          <path d="M16 15h.01"/>
          <path d="M6 19v2"/>
          <path d="M18 21v-2"/>
        </g>
      </svg></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
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

/**
 * Frame the map to all plotted points, but only when the SET of points changes
 * (keyed on `fitKey` = marker/stop ids) — not on every coordinate tick, which would
 * fight live updates and any user-initiated fly-to.
 */
function FitView({ points, fitKey }: { points: [number, number][]; fitKey: string }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], Math.max(map.getZoom(), 14));
      return;
    }
    map.fitBounds(points as L.LatLngBoundsExpression, { padding: [40, 40], maxZoom: 16 });
    // Refit only when the point SET changes; `points` identity changes every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, fitKey]);
  return null;
}

/** Pan/zoom to a selected point whenever its `nonce` changes. */
function FlyToFocus({ focus }: { focus: LiveMapProps["focus"] }) {
  const map = useMap();
  const nonce = focus?.nonce;
  useEffect(() => {
    if (!focus) return;
    map.flyTo([focus.lat, focus.lng], Math.max(map.getZoom(), FOCUS_ZOOM), { duration: 0.6 });
    // Re-fly whenever the caller bumps `nonce` (even if coordinates repeat).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, nonce]);
  return null;
}

export function LiveMapImpl({
  markers,
  stops = [],
  polyline,
  center,
  zoom = 13,
  className,
  focus,
  selectedId,
}: LiveMapProps) {
  const points = useMemo<[number, number][]>(
    () => [
      ...markers.map((m) => [m.lat, m.lng] as [number, number]),
      ...stops.map((s) => [s.lat, s.lng] as [number, number]),
    ],
    [markers, stops],
  );

  // Identity of the plotted set — drives FitView without reacting to position ticks.
  const fitKey = useMemo(
    () => [...markers.map((m) => `m${m.id}`), ...stops.map((s) => `s${s.id}`)].sort().join("|"),
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
        <Marker
          key={`bus-${m.id}`}
          position={[m.lat, m.lng]}
          icon={busIcon(m.color, m.heading, m.id === selectedId)}
          zIndexOffset={m.id === selectedId ? 1000 : 0}
        >
          {m.label ? <Popup>{m.label}</Popup> : null}
        </Marker>
      ))}

      <FitView points={points} fitKey={fitKey} />
      <FlyToFocus focus={focus} />
    </MapContainer>
  );
}

export default LiveMapImpl;
