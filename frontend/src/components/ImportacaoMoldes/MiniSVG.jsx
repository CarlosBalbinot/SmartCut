import styles from "./MiniSVG.module.css";

// ── Rotação de pontos em torno do centróide ───────────────────────────

function rotatePts(pontos, angleDeg) {
  if (!angleDeg) return pontos;
  const xs = pontos.map((p) => p[0]);
  const ys = pontos.map((p) => p[1]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const rad = (angleDeg * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  return pontos.map(([x, y]) => [
    cx + (x - cx) * cos - (y - cy) * sin,
    cy + (x - cx) * sin + (y - cy) * cos,
  ]);
}

// ── Mini silhueta SVG ────────────────────────────────────────────────

export default function MiniSVG({ geometria, rotacao_base = 0 }) {
  if (!geometria?.coordinates?.[0]) return null;
  const rawPontos = geometria.coordinates[0];
  if (rawPontos.length < 2) return null;

  const pontos = rotatePts(rawPontos, rotacao_base);

  const xs = pontos.map((p) => p[0]);
  const ys = pontos.map((p) => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const w = maxX - minX || 1;
  const h = maxY - minY || 1;
  const pad = Math.max(w, h) * 0.08;
  const vw = w + pad * 2;
  const vh = h + pad * 2;
  const sw = Math.max(w, h) * 0.014;

  const pontosStr = pontos.map((p) => `${p[0] - minX + pad},${p[1] - minY + pad}`).join(" ");

  return (
    <svg viewBox={`0 0 ${vw} ${vh}`} className={styles.miniSvg}>
      <polygon points={pontosStr} fill="var(--sc-100)" stroke="var(--sc-700)" strokeWidth={sw} />
    </svg>
  );
}
