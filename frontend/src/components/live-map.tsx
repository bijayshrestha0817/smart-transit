"use client";

/**
 * Provider-agnostic live map. Today it renders Leaflet + OpenStreetMap, but every
 * caller talks only to this `<LiveMap>` surface — swapping in Google/Mapbox at P3
 * touches just `live-map-impl.tsx`, not the pages.
 *
 * The Leaflet implementation is dynamically imported with `ssr: false` because
 * react-leaflet touches `window` at module load; it must never run during SSR.
 */

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";

/** A live vehicle marker. */
export interface MapMarker {
  id: string | number;
  lat: number;
  lng: number;
  /** Degrees clockwise from north; rotates the marker if provided. */
  heading?: number | null;
  /** Popup label, e.g. the bus plate + route. */
  label?: string;
  /** Marker fill color (defaults to brand blue). */
  color?: string;
}

/** A static stop marker (small dot). */
export interface MapStop {
  id: string | number;
  lat: number;
  lng: number;
  name?: string;
}

export interface LiveMapProps {
  /** Moving vehicles. */
  markers: MapMarker[];
  /** Ordered route stops, drawn as small dots. */
  stops?: MapStop[];
  /** Optional route polyline as `[lat, lng]` pairs. */
  polyline?: [number, number][];
  /** Initial center; defaults to the first marker/stop, then Kathmandu. */
  center?: [number, number];
  zoom?: number;
  /** Wrapper classes; defaults to a 420px-tall rounded panel. */
  className?: string;
}

export const LiveMap = dynamic(() => import("./live-map-impl").then((m) => m.LiveMapImpl), {
  ssr: false,
  loading: () => <Skeleton className="h-[420px] w-full rounded-lg" />,
});
