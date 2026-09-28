// The 42 Universal Cartographics regions, from the same raster the app uses
// to name a journal position (Ben Peddell's EliteDangerousRegionMap, MIT).
// Each of its 2048 rows runs south to north from z0, as `length, region`
// runs across x from x0; one cell is about 49 ly. The atlas draws borders
// straight from it, so they are exact, and it answers "which region is
// this?" for any point without asking Python.

// How bright each region's stars read in the backdrop, from what Universal
// Cartographics named it: the arms and streams carry the galaxy's light, the
// gaps and voids between them are dark. Everything else sits between.
const BRIGHT = /\b(arm|spur|stream|conflux|straits|centre)\b/i;
const DARK = /\b(gap|void|abyss|rift|vault|veils|tenebrae|acheron)\b/i;
const GLOW_SIZE = 512;

export function regionTone(name) {
  if (BRIGHT.test(name)) return 1;
  if (DARK.test(name)) return .28;
  return .62;
}

export function decodeRegions(payload) {
  const size = Number(payload.size) || 2048;
  const ids = new Uint8Array(size * size);
  (payload.rows || []).forEach((row, z) => {
    let x = 0;
    for (let index = 0; index + 1 < row.length; index += 2) {
      const length = row[index];
      ids.fill(row[index + 1], z * size + x, Math.min(size * (z + 1), z * size + x + length));
      x += length;
    }
  });
  const names = ["", ...(payload.names || [])];
  const x0 = Number(payload.x0), z0 = Number(payload.z0), scale = Number(payload.scale);
  const extent = size * scale;
  const idAt = (x, z) => {
    const px = Math.floor((x - x0) / scale), pz = Math.floor((z - z0) / scale);
    return px < 0 || pz < 0 || px >= size || pz >= size ? 0 : ids[pz * size + px];
  };
  return {
    ids, size, x0, z0, scale, extent, names, idAt,
    labels: payload.labels || [],
    centre: payload.centre || [25.2, -20.9, 25900],
    glow: glowMap(ids, size, names),
  };
}

// The backdrop's structure: each region's tone, averaged down to 512 cells
// and blurred across about 1,600 ly, so the arms read as soft bands of light
// rather than region-shaped blocks.
function glowMap(ids, size, names) {
  const tones = names.map((name, id) => (id ? regionTone(name) : 0));
  const step = size / GLOW_SIZE;
  let field = new Float32Array(GLOW_SIZE * GLOW_SIZE);
  for (let z = 0; z < GLOW_SIZE; z += 1) {
    for (let x = 0; x < GLOW_SIZE; x += 1) {
      let sum = 0;
      for (let dz = 0; dz < step; dz += 1) {
        const row = (z * step + dz) * size + x * step;
        for (let dx = 0; dx < step; dx += 1) sum += tones[ids[row + dx]];
      }
      field[z * GLOW_SIZE + x] = sum / (step * step);
    }
  }
  for (let pass = 0; pass < 3; pass += 1) field = blur(field, GLOW_SIZE, 6);
  const out = new Uint8Array(GLOW_SIZE * GLOW_SIZE);
  for (let index = 0; index < out.length; index += 1) out[index] = Math.round(Math.min(1, field[index]) * 255);
  return {data: out, size: GLOW_SIZE};
}

// Separable box blur; three passes come close to a Gaussian.
function blur(source, size, radius) {
  const across = new Float32Array(source.length), out = new Float32Array(source.length);
  const width = radius * 2 + 1;
  for (let z = 0; z < size; z += 1) {
    let sum = 0;
    for (let x = -radius; x <= radius; x += 1) sum += source[z * size + Math.min(size - 1, Math.max(0, x))];
    for (let x = 0; x < size; x += 1) {
      across[z * size + x] = sum / width;
      sum += source[z * size + Math.min(size - 1, x + radius + 1)] - source[z * size + Math.max(0, x - radius)];
    }
  }
  for (let x = 0; x < size; x += 1) {
    let sum = 0;
    for (let z = -radius; z <= radius; z += 1) sum += across[Math.min(size - 1, Math.max(0, z)) * size + x];
    for (let z = 0; z < size; z += 1) {
      out[z * size + x] = sum / width;
      sum += across[Math.min(size - 1, z + radius + 1) * size + x] - across[Math.max(0, z - radius) * size + x];
    }
  }
  return out;
}

// Where the commander has been, region by region: distinct systems, and the
// first and last time the journal put them there.
export function regionVisits(regions, route) {
  const visits = new Map();
  const seen = new Set();
  for (const row of route) {
    const id = regions.idAt(row.pos[0], row.pos[2]);
    if (!id) continue;
    const entry = visits.get(id) || {id, systems: 0, first: row.timestamp || "", last: row.timestamp || ""};
    const key = `${id}|${String(row.system || "").toLowerCase()}`;
    if (!seen.has(key)) {
      seen.add(key);
      entry.systems += 1;
    }
    if (row.timestamp && (!entry.first || row.timestamp < entry.first)) entry.first = row.timestamp;
    if (row.timestamp && row.timestamp > entry.last) entry.last = row.timestamp;
    visits.set(id, entry);
  }
  return visits;
}
