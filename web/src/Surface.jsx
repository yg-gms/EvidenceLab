import React, { useEffect, useRef } from 'react';

// Decorative wireframe surface in the workspace cover; independent of the dataset.
export default function Surface() {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    function draw() {
      const { width: w, height: h } = canvas.getBoundingClientRect();
      const scale = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = w * scale;
      canvas.height = h * scale;
      const ctx = canvas.getContext('2d');
      ctx.scale((scale * w) / 510, (scale * h) / 220);
      function project(i, j) {
        const u = i / 54,
          v = j / 35;
        const z =
          86 * Math.exp(-((u - 0.49) ** 2 / 0.037 + (v - 0.59) ** 2 / 0.12)) +
          49 * Math.exp(-((u - 0.9) ** 2 / 0.028 + (v - 0.33) ** 2 / 0.18)) +
          19 * Math.sin(8 * u + 2 * v) * Math.cos(3 * v);
        return [-15 + u * 405 + v * 140, 143 + v * 95 - u * 60 - z];
      }
      for (let j = 0; j <= 35; j++) {
        ctx.beginPath();
        for (let i = 0; i <= 54; i++) {
          const p = project(i, j);
          i ? ctx.lineTo(...p) : ctx.moveTo(...p);
        }
        ctx.strokeStyle = 'rgba(105,237,201,' + (0.26 + (0.35 * j) / 35) + ')';
        ctx.lineWidth = 0.78;
        ctx.stroke();
      }
      for (let i = 0; i <= 54; i++) {
        ctx.beginPath();
        for (let j = 0; j <= 35; j++) {
          const p = project(i, j);
          j ? ctx.lineTo(...p) : ctx.moveTo(...p);
        }
        ctx.strokeStyle = 'rgba(103,218,195,.38)';
        ctx.lineWidth = 0.65;
        ctx.stroke();
      }
      for (let i = 3; i < 54; i += 6)
        for (let j = 3; j < 35; j += 6) {
          const [x, y] = project(i, j);
          ctx.fillStyle = '#8fe9c9';
          ctx.fillRect(x - 1, y - 1, 1.9, 1.9);
        }
    }
    const observer = new ResizeObserver(draw);
    observer.observe(canvas);
    draw();
    return () => observer.disconnect();
  }, []);
  return <canvas className="surface" ref={ref} aria-hidden="true" />;
}
