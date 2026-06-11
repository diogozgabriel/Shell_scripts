// Gera build/icon.png (512x512) sem dependências externas.
const zlib = require('zlib');
const fs = require('fs');
const path = require('path');

const S = 512;
const px = Buffer.alloc(S * S * 4);

function put(x, y, r, g, b, a = 255) {
  if (x < 0 || y < 0 || x >= S || y >= S) return;
  const i = (y * S + x) * 4;
  // alpha-blend simples sobre o que já existe
  const na = a / 255, oa = px[i + 3] / 255;
  const outA = na + oa * (1 - na);
  if (outA === 0) return;
  px[i]     = Math.round((r * na + px[i]     * oa * (1 - na)) / outA);
  px[i + 1] = Math.round((g * na + px[i + 1] * oa * (1 - na)) / outA);
  px[i + 2] = Math.round((b * na + px[i + 2] * oa * (1 - na)) / outA);
  px[i + 3] = Math.round(outA * 255);
}

const inRounded = (x, y, x0, y0, x1, y1, rad) => {
  if (x < x0 || x > x1 || y < y0 || y > y1) return false;
  const cx = Math.max(x0 + rad, Math.min(x, x1 - rad));
  const cy = Math.max(y0 + rad, Math.min(y, y1 - rad));
  return (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad ||
         (x >= x0 + rad && x <= x1 - rad) || (y >= y0 + rad && y <= y1 - rad)
         ? ((x >= x0 + rad && x <= x1 - rad) || (y >= y0 + rad && y <= y1 - rad) ||
            (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad)
         : false;
};

// Fundo: quadrado arredondado com gradiente azul-roxo
for (let y = 0; y < S; y++) {
  for (let x = 0; x < S; x++) {
    if (inRounded(x, y, 16, 16, S - 16, S - 16, 110)) {
      const t = (x + y) / (2 * S);
      put(x, y, Math.round(210 - 40 * t), Math.round(40 + 30 * t), Math.round(90 + 60 * t));
    }
  }
}

// Balão de chat branco
for (let y = 0; y < S; y++) {
  for (let x = 0; x < S; x++) {
    if (inRounded(x, y, 96, 130, S - 96, 330, 60)) put(x, y, 245, 246, 255);
  }
}
// rabinho do balão (triângulo)
for (let y = 330; y < 410; y++) {
  const w = Math.max(0, 70 - (y - 330));
  for (let x = 150; x < 150 + w; x++) put(x, y, 245, 246, 255);
}
// três pontos
for (const cx of [180, 256, 332]) {
  for (let y = -26; y <= 26; y++) {
    for (let x = -26; x <= 26; x++) {
      if (x * x + y * y <= 26 * 26) put(cx + x, 230 + y, 190, 50, 100);
    }
  }
}

// Monta o PNG
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type), data]);
  const crcTable = [];
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    crcTable[n] = c >>> 0;
  }
  let crc = 0xffffffff;
  for (const byte of body) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  const crcBuf = Buffer.alloc(4);
  crcBuf.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
  return Buffer.concat([len, body, crcBuf]);
}

const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(S, 0);
ihdr.writeUInt32BE(S, 4);
ihdr[8] = 8;  // bit depth
ihdr[9] = 6;  // RGBA

const raw = Buffer.alloc(S * (S * 4 + 1));
for (let y = 0; y < S; y++) {
  raw[y * (S * 4 + 1)] = 0; // filtro none
  px.copy(raw, y * (S * 4 + 1) + 1, y * S * 4, (y + 1) * S * 4);
}

const png = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk('IHDR', ihdr),
  chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
  chunk('IEND', Buffer.alloc(0)),
]);

fs.writeFileSync(path.join(__dirname, 'icon.png'), png);
console.log('icon.png gerado:', png.length, 'bytes');
