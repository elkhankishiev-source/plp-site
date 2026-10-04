/* Линейные «рисованные» иконки для офферов Property Library.
   Каждая иконка рисуется в своей рамке 40×40 и ставится через place(svg, name, x, y, size, rot).
   Штрих проводится дважды с лёгким смещением — так линия выглядит нарисованной пером. */
(function () {
  let seed = 3;
  const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
  let INK = '#17180F';
  const jit = (d, a) => d.replace(/-?\d+(\.\d+)?/g, (n) => (+n + (rnd() - .5) * a).toFixed(2));
  const stroke = (d, w = 1.25, c = INK) =>
    `<path d="${jit(d, .35)}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>` +
    `<path d="${jit(d, .6)}" fill="none" stroke="${c}" stroke-width="${w * .45}" stroke-linecap="round" stroke-linejoin="round" opacity=".55"/>`;
  const fill = (d, c) => `<path d="${d}" fill="${c}" stroke="none"/>`;
  const hatch = (x1, y1, x2, y2, n, w = .5) => { let s = ''; for (let i = 0; i < n; i++) { const t = i / (n - 1); s += `M${x1 + (x2 - x1) * t} ${y1} l-2 ${y2 - y1} `; } return stroke(s, w); };
  /* овал многоугольником: дуги SVG дрожание ломает (флаги дуги — тоже числа) */
  const ell = (cx, cy, rx, ry) => { let d = ''; for (let i = 0; i <= 26; i++) { const t = i / 26 * Math.PI * 2; d += (i ? ' L' : 'M') + (cx + rx * Math.cos(t)).toFixed(2) + ' ' + (cy + ry * Math.sin(t)).toFixed(2); } return d + ' Z'; };

  const I = {
    coins: (acc) => {
      let s = '';
      for (let i = 0; i < 5; i++) { const y = 32 - i * 4.2; s += fill(ell(20, y, 11, 3.6), i === 4 ? acc : '#FFFFFF') + stroke(ell(20, y, 11, 3.6)) + stroke(`M9 ${y} l0 4.2 M31 ${y} l0 4.2`, .9); }
      s += stroke('M18 13 q2 -2 4 0 q-1 1.8 -3 2 q-2 .2 -1 2 q2 1.6 4 0', .8);
      s += fill(ell(33, 34, 6, 2.2), '#FFFFFF') + stroke(ell(33, 34, 6, 2.2)) + stroke('M27 34 l0 3 M39 34 l0 3', .8);
      return s;
    },
    key: (acc) => fill(ell(11, 20, 7.5, 7.5), acc) + stroke(ell(11, 20, 7.5, 7.5)) + stroke(ell(11, 20, 2.6, 2.6), .9) +
      stroke('M18.5 20 L37 20 M31 20 l0 5 M35 20 l0 4 M24 20 l0 3'),
    calc: (acc) => fill('M9 4 h22 v32 h-22 z', '#FFFFFF') + stroke('M9 4 h22 v32 h-22 z') + fill('M12 7 h16 v7 h-16 z', acc) + stroke('M12 7 h16 v7 h-16 z', .9) +
      stroke('M13 18 h3 v3 h-3 z M19 18 h3 v3 h-3 z M25 18 h3 v3 h-3 z M13 24 h3 v3 h-3 z M19 24 h3 v3 h-3 z M25 24 h3 v8 h-3 z M13 30 h3 v3 h-3 z M19 30 h3 v3 h-3 z', .8) +
      stroke('M20 10.5 h6', .8),
    chart: (acc) => stroke('M5 36 L37 36 M5 36 L5 4', 1.1) +
      [[9, 26], [16, 21], [23, 16], [30, 9]].map(([x, y], i) => fill(`M${x} ${y} h5 v${36 - y} h-5 z`, i === 3 ? acc : '#FFFFFF') + stroke(`M${x} ${y} h5 v${36 - y} h-5 z`, .9) + hatch(x + 1.5, y + 2, x + 4.5, 35, 3, .35)).join('') +
      stroke('M7 24 Q 15 22 20 15 T 34 5', 1.2) + stroke('M29 4.5 L34.5 4.5 L33.5 10', 1.2),
    piggy: (acc) => fill(ell(19, 22, 14, 10), acc) + stroke(ell(19, 22, 14, 10)) + stroke('M31 19 q6 -1 5 5 q-1 3 -5 2', 1) + stroke(ell(34, 22, 1.4, 1.1), .7) +
      stroke('M10 14 l-2 -6 l7 4 M11 31 l0 5 h4 l0 -4 M24 31 l0 5 h4 l0 -5 M5 21 q-4 -2 -2 -5', 1) + stroke('M16 12 h8', 1.4) + stroke(ell(26, 18, .9, .9), 1),
    contract: (acc) => fill('M8 4 h18 l6 6 v26 h-24 z', '#FFFFFF') + stroke('M8 4 h18 l6 6 v26 h-24 z M26 4 v6 h6') +
      stroke('M12 13 h12 M12 17 h16 M12 21 h14 M12 25 h9', .7) + stroke('M13 31 q3 -4 5 0 t 5 -1 q2 -2 4 1', .9, '#2F4FA3') +
      fill('M30 20 l6 -6 l3 3 l-6 6 z', acc) + stroke('M30 20 l6 -6 l3 3 l-6 6 z M30 20 l-1.5 4.5 l4.5 -1.5', .9),
    calendar: (acc) => fill('M6 8 h28 v28 h-28 z', '#FFFFFF') + fill('M6 8 h28 v7 h-28 z', acc) + stroke('M6 8 h28 v28 h-28 z M6 15 h28 M12 5 v6 M28 5 v6') +
      stroke('M11 20 h3 M18 20 h3 M25 20 h3 M11 25 h3 M18 25 h3 M11 30 h3 M18 30 h3', .9) + stroke(ell(26.5, 28.5, 3.8, 3.4), 1.1, '#B4533A'),
    palm: (acc) => stroke('M21 38 q-3 -12 1 -24', 1.3) + hatch(19, 20, 22, 36, 5, .35) +
      stroke('M22 14 q-8 -6 -16 -1 M22 14 q-5 -9 -13 -9 M22 14 q2 -9 10 -10 M22 14 q9 -4 15 3 M22 14 q6 1 9 9', 1.1) +
      fill(ell(21, 15.5, 2.2, 2), acc) + stroke('M4 38 q17 -3 34 0', 1),
    sun: (acc) => fill(ell(20, 20, 8, 8), acc) + stroke(ell(20, 20, 8, 8)) +
      stroke('M20 4 v5 M20 31 v5 M4 20 h5 M31 20 h5 M9 9 l3.5 3.5 M27.5 27.5 l3.5 3.5 M31 9 l-3.5 3.5 M12.5 27.5 l-3.5 3.5', 1),
    plane: (acc) => fill('M4 24 L36 10 L28 34 L20 26 Z', '#FFFFFF') + stroke('M4 24 L36 10 L28 34 L20 26 Z M36 10 L20 26 L19 34 L24 30') + fill('M20 26 L19 34 L24 30 Z', acc) +
      stroke('M2 34 q4 2 7 -1 M5 39 q5 1 9 -3', .7),
    arrow: (acc) => stroke('M4 34 Q 10 18 20 22 T 34 6', 1.6) + stroke('M27 5 L35 5 L34 13', 1.6),
    spark: (acc) => stroke('M20 6 v10 M20 24 v10 M6 20 h10 M24 20 h10 M11 11 l4 4 M29 29 l-4 -4 M29 11 l-4 4 M11 29 l4 -4', 1),
    percent: (acc) => fill(ell(12, 12, 5, 5), acc) + stroke(ell(12, 12, 5, 5)) + stroke(ell(28, 28, 5, 5)) + stroke('M30 6 L10 34', 1.6),
    house: (acc) => fill('M8 20 L20 9 L32 20 V35 H8 Z', '#FFFFFF') + stroke('M5 22 L20 8 L35 22 M8 20 V35 H32 V20') + fill('M17 25 h6 v10 h-6 z', acc) + stroke('M17 25 h6 v10 h-6 z', .9) +
      stroke('M11 23 h4 v4 h-4 z M25 23 h4 v4 h-4 z', .8) + hatch(9, 30, 16, 34, 3, .35),
    wave: (acc) => stroke('M2 16 q5 -5 9 0 t 9 0 t 9 0 t 9 0 M2 24 q5 -5 9 0 t 9 0 t 9 0 t 9 0', 1.1, '#3E6C7A') + stroke('M6 32 q5 -4 9 0 t 9 0 t 9 0', .8, '#3E6C7A'),
    shield: (acc) => fill('M20 4 L33 9 V20 Q33 31 20 37 Q7 31 7 20 V9 Z', acc) + stroke('M20 4 L33 9 V20 Q33 31 20 37 Q7 31 7 20 V9 Z') + stroke('M13 20 l5 5 l9 -10', 1.6),
    tag: (acc) => fill('M6 12 h22 l8 8 l-8 8 h-22 z', acc) + stroke('M6 12 h22 l8 8 l-8 8 h-22 z') + stroke(ell(27, 20, 1.6, 1.6), .9) + stroke('M28.6 20 q6 -8 9 -14', .8),
    ruler: (acc) => fill('M4 26 L26 4 L36 14 L14 36 Z', acc) + stroke('M4 26 L26 4 L36 14 L14 36 Z') + stroke('M9 21 l3 3 M13 17 l2 2 M17 13 l3 3 M21 9 l2 2', .8),
  };
  window.doodle = function (svg, name, x, y, size = 16, rot = 0, acc = '#F4DD6E', ink = '#17180F') {
    const k = size / 40; INK = ink;
    svg.insertAdjacentHTML('beforeend', `<g transform="translate(${x} ${y}) rotate(${rot}) scale(${k}) translate(-20 -20)">${I[name](acc)}</g>`);
    INK = '#17180F';
  };
})();
