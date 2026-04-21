const { nativeImage } = require('electron');

function generateDIcon(size = 64) {
  const buffer = Buffer.alloc(size * size * 4);

  const cornerRadius = size * 0.22;
  const halfW = size / 2;
  const halfH = size / 2;

  const barLeft = size * 0.30;
  const barRight = size * 0.44;
  const top = size * 0.22;
  const bottom = size * 0.78;
  const arcCx = barRight;
  const arcCy = (top + bottom) / 2;
  const arcOuterRx = size * 0.40;
  const arcOuterRy = (bottom - top) / 2;
  const stroke = barRight - barLeft;
  const arcInnerRx = Math.max(1, arcOuterRx - stroke);
  const arcInnerRy = Math.max(1, arcOuterRy - stroke);

  const bg = { r: 6, g: 6, b: 10 };
  const fg = { r: 255, g: 255, b: 255 };
  const rimAlpha = 0.22;

  function isInBg(x, y) {
    const dx = Math.abs(x - halfW) - (halfW - cornerRadius);
    const dy = Math.abs(y - halfH) - (halfH - cornerRadius);
    const cornerDist = Math.hypot(Math.max(dx, 0), Math.max(dy, 0));
    const boxDist = Math.min(Math.max(dx, dy), 0);
    return (cornerDist + boxDist - cornerRadius) <= 0;
  }

  function isInRim(x, y) {
    if (!isInBg(x, y)) return false;
    const dx = Math.abs(x - halfW) - (halfW - cornerRadius);
    const dy = Math.abs(y - halfH) - (halfH - cornerRadius);
    const cornerDist = Math.hypot(Math.max(dx, 0), Math.max(dy, 0));
    const boxDist = Math.min(Math.max(dx, dy), 0);
    const sdf = cornerDist + boxDist - cornerRadius;
    return sdf > -1.1;
  }

  function isInD(x, y) {
    if (x >= barLeft && x <= barRight && y >= top && y <= bottom) return true;
    if (x > barRight) {
      const dx = x - arcCx;
      const dy = y - arcCy;
      const outer = (dx * dx) / (arcOuterRx * arcOuterRx) + (dy * dy) / (arcOuterRy * arcOuterRy);
      const inner = (dx * dx) / (arcInnerRx * arcInnerRx) + (dy * dy) / (arcInnerRy * arcInnerRy);
      return outer <= 1 && inner >= 1;
    }
    return false;
  }

  const samples = size <= 32 ? 5 : 4;
  const total = samples * samples;

  for (let py = 0; py < size; py++) {
    for (let px = 0; px < size; px++) {
      let letterHits = 0;
      let bgHits = 0;
      let rimHits = 0;
      for (let sy = 0; sy < samples; sy++) {
        for (let sx = 0; sx < samples; sx++) {
          const fx = px + (sx + 0.5) / samples;
          const fy = py + (sy + 0.5) / samples;
          if (isInBg(fx, fy)) bgHits++;
          if (isInD(fx, fy)) letterHits++;
          if (isInRim(fx, fy)) rimHits++;
        }
      }
      const letterAlpha = letterHits / total;
      const bgAlpha = bgHits / total;
      const rimBlend = (rimHits / total) * rimAlpha;

      let r = bg.r * (1 - letterAlpha) + fg.r * letterAlpha;
      let g = bg.g * (1 - letterAlpha) + fg.g * letterAlpha;
      let b = bg.b * (1 - letterAlpha) + fg.b * letterAlpha;

      r = r * (1 - rimBlend) + 255 * rimBlend;
      g = g * (1 - rimBlend) + 255 * rimBlend;
      b = b * (1 - rimBlend) + 255 * rimBlend;

      const idx = (py * size + px) * 4;
      buffer[idx + 0] = Math.round(b);
      buffer[idx + 1] = Math.round(g);
      buffer[idx + 2] = Math.round(r);
      buffer[idx + 3] = Math.round(bgAlpha * 255);
    }
  }

  return nativeImage.createFromBitmap(buffer, { width: size, height: size });
}

function generateWindowsIconSet() {
  const base = generateDIcon(256);
  return base;
}

module.exports = { generateDIcon, generateWindowsIconSet };
