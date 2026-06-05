/**
 * Offline GPS buffer backed by IndexedDB.
 *
 * When the WebSocket is down (or a send fails), the driver portal enqueues points
 * here; on reconnect it flushes them IN ORDER via `POST /driver/trips/{id}/gps/batch/`
 * (the points carry their original client timestamps for accurate replay). Points are
 * only deleted once the backend accepts the batch (202), so a failed flush loses
 * nothing. Keyed by an auto-increment id, so cursor iteration = insertion order.
 *
 * All functions no-op when IndexedDB is unavailable (SSR / unsupported browser).
 */

import { type DBSchema, type IDBPDatabase, openDB } from "idb";

import { gpsBatch, type GpsBatchPoint } from "@/lib/api/trips";

interface QueueRow {
  id?: number;
  tripId: number;
  point: GpsBatchPoint;
}

interface GpsQueueDB extends DBSchema {
  points: {
    key: number;
    value: QueueRow;
    indexes: { "by-trip": number };
  };
}

const DB_NAME = "smart-transit";
const STORE = "points";
const VERSION = 1;
const MAX_BATCH = 1_000;

let dbPromise: Promise<IDBPDatabase<GpsQueueDB>> | null = null;

function getDb(): Promise<IDBPDatabase<GpsQueueDB>> | null {
  if (typeof indexedDB === "undefined") return null;
  if (!dbPromise) {
    dbPromise = openDB<GpsQueueDB>(DB_NAME, VERSION, {
      upgrade(db) {
        const store = db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
        store.createIndex("by-trip", "tripId");
      },
    });
  }
  return dbPromise;
}

/** Buffer one point for later flush. */
export async function enqueueGps(tripId: number, point: GpsBatchPoint): Promise<void> {
  const db = getDb();
  if (!db) return;
  await (await db).add(STORE, { tripId, point });
}

/** How many points are still buffered for this trip. */
export async function pendingCount(tripId: number): Promise<number> {
  const db = getDb();
  if (!db) return 0;
  return (await db).countFromIndex(STORE, "by-trip", tripId);
}

/**
 * Flush all buffered points for `tripId` in insertion order, in batches of ≤1000.
 * Deletes each batch only after the backend accepts it; rethrows on failure with the
 * unsent points still queued. Returns the number of points successfully flushed.
 */
export async function flushGps(tripId: number): Promise<number> {
  const db = getDb();
  if (!db) return 0;
  const conn = await db;

  // Collect this trip's rows in key (insertion) order.
  const rows: Required<QueueRow>[] = [];
  let cursor = await conn.transaction(STORE).store.openCursor();
  while (cursor) {
    const value = cursor.value;
    if (value.tripId === tripId && typeof value.id === "number") {
      rows.push(value as Required<QueueRow>);
    }
    cursor = await cursor.continue();
  }
  if (rows.length === 0) return 0;

  let flushed = 0;
  for (let i = 0; i < rows.length; i += MAX_BATCH) {
    const slice = rows.slice(i, i + MAX_BATCH);
    // Throws on non-2xx — remaining slices stay queued for the next attempt.
    await gpsBatch(
      tripId,
      slice.map((r) => r.point),
    );
    const tx = conn.transaction(STORE, "readwrite");
    await Promise.all(slice.map((r) => tx.store.delete(r.id)));
    await tx.done;
    flushed += slice.length;
  }
  return flushed;
}
