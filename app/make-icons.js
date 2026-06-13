/* One-off icon generator for the PWA. No deps — hand-rolls a PNG via zlib.
   Draws a light-blue tile with a white medical cross, kept inside the
   maskable safe zone so the same art works for "any" and "maskable". */
const zlib = require("zlib");
const fs = require("fs");

function crc32(buf) {
  let c = ~0;
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i];
    for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xEDB88320 & -(c & 1));
  }
  return (~c) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length, 0);
  const t = Buffer.from(type, "ascii");
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(Buffer.concat([t, data])), 0);
  return Buffer.concat([len, t, data, crc]);
}
function png(size, draw) {
  const px = Buffer.alloc(size * size * 4);
  const set = (x, y, r, g, b, a) => {
    const i = (y * size + x) * 4;
    px[i] = r; px[i + 1] = g; px[i + 2] = b; px[i + 3] = a;
  };
  draw(set, size);
  // add filter byte (0) per row
  const raw = Buffer.alloc(size * (size * 4 + 1));
  for (let y = 0; y < size; y++) {
    raw[y * (size * 4 + 1)] = 0;
    px.copy(raw, y * (size * 4 + 1) + 1, y * size * 4, (y + 1) * size * 4);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; ihdr[9] = 6; // 8-bit, RGBA
  const idat = zlib.deflateSync(raw, { level: 9 });
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]),
    chunk("IHDR", ihdr), chunk("IDAT", idat), chunk("IEND", Buffer.alloc(0)),
  ]);
}

function draw(set, S) {
  // background gradient-ish light blue
  for (let y = 0; y < S; y++) {
    for (let x = 0; x < S; x++) {
      const tg = y / S;
      const r = Math.round(43 + tg * 0);     // #2b8fd6 -> slightly darker bottom
      const g = Math.round(143 - tg * 20);
      const b = Math.round(214 - tg * 30);
      set(x, y, r, g, b, 255);
    }
  }
  // white medical cross within safe zone (center 46%)
  const cx = S / 2, cy = S / 2;
  const arm = S * 0.23;   // half-length of cross arm
  const th = S * 0.085;   // half-thickness
  for (let y = 0; y < S; y++) {
    for (let x = 0; x < S; x++) {
      const dx = Math.abs(x - cx), dy = Math.abs(y - cy);
      const inV = dx <= th && dy <= arm;
      const inH = dy <= th && dx <= arm;
      if (inV || inH) set(x, y, 255, 255, 255, 255);
    }
  }
}

[192, 512].forEach((s) => {
  fs.writeFileSync(__dirname + `/icon-${s}.png`, png(s, draw));
  console.log("wrote icon-" + s + ".png");
});
