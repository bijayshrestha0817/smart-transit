"use client";

/**
 * `navigator.geolocation.watchPosition` wrapper with permission + error state.
 *
 * Returns the latest fix and re-invokes `onPosition` on every update. `speed` and
 * `heading` come straight from the device and may be null (stationary / no compass).
 * The watch is torn down on unmount or when `enabled` flips false.
 */

import { useEffect, useRef, useState } from "react";

export interface GeoPosition {
  lat: number;
  lng: number;
  /** Metres per second, or null when unavailable. */
  speed: number | null;
  /** Degrees clockwise from true north, or null. */
  heading: number | null;
  /** Accuracy radius in metres. */
  accuracy: number;
  /** Epoch ms of the fix. */
  timestamp: number;
}

export type GeoPermissionState = "prompt" | "granted" | "denied" | "unsupported";

interface UseGeolocationOptions {
  enabled?: boolean;
  onPosition?: (position: GeoPosition) => void;
}

export interface UseGeolocationResult {
  position: GeoPosition | null;
  error: string | null;
  permission: GeoPermissionState;
}

export function useGeolocation({
  enabled = true,
  onPosition,
}: UseGeolocationOptions = {}): UseGeolocationResult {
  const [position, setPosition] = useState<GeoPosition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [permission, setPermission] = useState<GeoPermissionState>("prompt");

  const onPositionRef = useRef(onPosition);
  useEffect(() => {
    onPositionRef.current = onPosition;
  });

  useEffect(() => {
    if (!enabled) return;

    if (typeof navigator === "undefined" || !navigator.geolocation) {
      // Terminal one-shot state for an unsupported environment — not a cascading update.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPermission("unsupported");
      return;
    }

    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        setPermission("granted");
        setError(null);
        const next: GeoPosition = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          speed: pos.coords.speed,
          heading: pos.coords.heading,
          accuracy: pos.coords.accuracy,
          timestamp: pos.timestamp,
        };
        setPosition(next);
        onPositionRef.current?.(next);
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          setPermission("denied");
          setError("Location permission denied. Enable it to broadcast your position.");
        } else {
          setError(err.message || "Couldn't read your location.");
        }
      },
      { enableHighAccuracy: true, maximumAge: 2_000, timeout: 15_000 },
    );

    return () => navigator.geolocation.clearWatch(watchId);
  }, [enabled]);

  return { position, error, permission };
}
