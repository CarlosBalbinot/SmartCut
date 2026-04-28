#!/usr/bin/env node
/**
 * nest_worker.js — Textile nesting engine (skyline bottom-left packer)
 *
 * Reads a JSON job from stdin and writes a JSON result to stdout.
 *
 * Input schema:
 *   {
 *     bin: { width: number, height: number },   // cm; height = max length budget
 *     parts: [
 *       {
 *         id:        string,
 *         polygon:   [[x, y], ...],             // exterior ring in cm, any winding
 *         quantity:  number,
 *         rotations: [0, 90, 180, 270]          // allowed rotation angles in degrees
 *       }
 *     ]
 *   }
 *
 * Output schema:
 *   {
 *     placements: [{ id, x, y, rotation }],  // x/y = bottom-left corner, cm
 *     efficiency: number,                    // 0–1  (piece area / used bin area)
 *     width_used: number                     // cm of fabric length consumed
 *   }
 *
 * Coordinate system:
 *   x = across the fabric width  (0 … bin.width, fixed)
 *   y = along the fabric length  (0 … ∞, the dimension we minimise)
 *
 * Algorithm: Skyline Bottom-Left with per-piece rotation selection.
 *   For each piece (pieces sorted by bounding-box area, largest first) we try
 *   every allowed rotation, pick the rotation+position that results in the
 *   lowest "top" (y + height) after placement, and update the skyline.
 */

'use strict';

// ── Geometry helpers ─────────────────────────────────────────────────────────

/** Returns axis-aligned bounding box of a polygon. */
function bbox(poly) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const [x, y] of poly) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  return { minX, minY, w: maxX - minX, h: maxY - minY };
}

/** Shoelace area (absolute value). */
function polyArea(poly) {
  let a = 0;
  for (let i = 0; i < poly.length; i++) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2;
}

/** Rotate polygon by `deg` degrees around the origin. */
function rotatePoly(poly, deg) {
  if (deg === 0) return poly;
  const rad = (deg * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  return poly.map(([x, y]) => [x * cos - y * sin, x * sin + y * cos]);
}

/**
 * Returns bounding-box {w, h} of the polygon after rotation,
 * with the polygon translated so its bottom-left corner is at (0, 0).
 */
function rotatedBBox(poly, deg) {
  const rotated = rotatePoly(poly, deg);
  const b = bbox(rotated);
  return { w: b.w, h: b.h };
}

// ── Skyline data structure ────────────────────────────────────────────────────
//
// The skyline is an array of non-overlapping horizontal segments, sorted by x:
//   [{ x, w, y }, ...]
// where y is the current "top" (filled height) of that strip.

function skylineMaxY(segments, left, right) {
  let maxY = 0;
  for (const s of segments) {
    const sRight = s.x + s.w;
    if (s.x < right && sRight > left) maxY = Math.max(maxY, s.y);
  }
  return maxY;
}

/**
 * Finds the placement position (x, y) for a piece of size (pw × ph) that
 * minimises the resulting top (y + ph) across all candidate x positions.
 * Returns null if the piece is wider than the bin.
 */
function findBest(segments, binWidth, pw, ph) {
  if (pw > binWidth) return null;

  let bestTop = Infinity;
  let bestX = 0;

  for (const seg of segments) {
    // Candidate: start piece at seg.x
    const startX = seg.x;
    if (startX + pw > binWidth) continue;

    const y = skylineMaxY(segments, startX, startX + pw);
    const top = y + ph;

    if (top < bestTop || (top === bestTop && startX < bestX)) {
      bestTop = top;
      bestX = startX;
    }
  }

  if (bestTop === Infinity) return null;
  return { x: bestX, y: bestTop - ph };
}

/**
 * Updates the skyline after placing a piece at (px, py) with size (pw × ph).
 */
function updateSkyline(segments, px, py, pw, ph) {
  const right = px + pw;
  const top = py + ph;
  const next = [];

  for (const s of segments) {
    const sRight = s.x + s.w;
    if (sRight <= px || s.x >= right) {
      // No overlap — keep as-is
      next.push(s);
    } else {
      // Overlaps — keep parts outside the piece's x range
      if (s.x < px) next.push({ x: s.x, w: px - s.x, y: s.y });
      if (sRight > right) next.push({ x: right, w: sRight - right, y: s.y });
    }
  }

  // New segment at the piece's top
  next.push({ x: px, w: pw, y: top });

  // Sort and merge adjacent segments with equal y
  next.sort((a, b) => a.x - b.x);
  const merged = [];
  for (const s of next) {
    if (
      merged.length &&
      merged[merged.length - 1].y === s.y &&
      merged[merged.length - 1].x + merged[merged.length - 1].w === s.x
    ) {
      merged[merged.length - 1].w += s.w;
    } else {
      merged.push({ ...s });
    }
  }
  return merged;
}

// ── Main nesting logic ────────────────────────────────────────────────────────

function nest(bin, parts) {
  const { width } = bin;

  // Expand parts by quantity, annotating with bounding-box area for sorting
  const items = [];
  for (const part of parts) {
    const area = polyArea(part.polygon);
    const rots = (part.rotations && part.rotations.length) ? part.rotations : [0];
    for (let i = 0; i < part.quantity; i++) {
      items.push({ id: part.id, polygon: part.polygon, rots, area });
    }
  }

  // Sort largest-area pieces first (improves packing density)
  items.sort((a, b) => b.area - a.area);

  // Initialise skyline: one full-width segment at y = 0
  let skyline = [{ x: 0, w: width, y: 0 }];
  const placements = [];
  let totalPartArea = 0;

  for (const item of items) {
    totalPartArea += item.area;

    let best = null; // { x, y, rotation, top }

    for (const rot of item.rots) {
      const { w: pw, h: ph } = rotatedBBox(item.polygon, rot);
      const pos = findBest(skyline, width, pw, ph);
      if (!pos) continue;

      const top = pos.y + ph;
      if (
        !best ||
        top < best.top ||
        (top === best.top && pos.x < best.x)
      ) {
        best = { x: pos.x, y: pos.y, rotation: rot, top, pw, ph };
      }
    }

    if (!best) {
      // Piece could not be placed within bin.width — skip (shouldn't happen)
      continue;
    }

    skyline = updateSkyline(skyline, best.x, best.y, best.pw, best.ph);
    placements.push({ id: item.id, x: best.x, y: best.y, rotation: best.rotation });
  }

  const widthUsed = Math.max(...skyline.map(s => s.y), 0);
  const binArea = width * widthUsed;
  const efficiency = binArea > 0 ? Math.min(totalPartArea / binArea, 1) : 0;

  return {
    placements,
    efficiency: Math.round(efficiency * 10000) / 10000,
    width_used: Math.round(widthUsed * 1000) / 1000,
  };
}

// ── Entry point ───────────────────────────────────────────────────────────────

const chunks = [];
process.stdin.on('data', (d) => chunks.push(d));
process.stdin.on('end', () => {
  try {
    const input = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if (!input.bin || !Array.isArray(input.parts)) {
      throw new Error('Input must have {bin, parts}');
    }
    const result = nest(input.bin, input.parts);
    process.stdout.write(JSON.stringify(result));
  } catch (err) {
    process.stderr.write((err.stack || err.message) + '\n');
    process.exit(1);
  }
});
