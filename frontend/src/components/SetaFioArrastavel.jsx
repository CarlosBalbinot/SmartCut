/**
 * SetaFioArrastavel — silhueta da peça com uma seta sobreposta que o
 * usuário arrasta (mouse nativo, sem lib) para definir o sentido do
 * fio. Reutilizado no modal de edição de molde e no ParteCard da
 * importação.
 */
import { useMemo, useRef, useState } from "react";
import MiniSVG from "./ImportacaoMoldes/MiniSVG";
import styles from "./SetaFioArrastavel.module.css";

export const CATEGORIA_LABEL = {
  vertical: "Vertical",
  horizontal: "Horizontal",
  "45graus": "45 graus",
};

export function anguloInicial(sentidoFio) {
  if (sentidoFio === "horizontal") return 0;
  if (sentidoFio === "45graus") return 45;
  return 90; // vertical, ou sem sentido definido
}

// Converte o ângulo (0-360, eixo x para a direita, y para baixo) em
// categoria de sentido do fio, em 8 setores de 45° cada.
export function anguloParaCategoria(deg) {
  const a = ((deg % 360) + 360) % 360;
  if (a < 22.5 || a >= 337.5) return "horizontal";
  if (a < 67.5) return "45graus";
  if (a < 112.5) return "vertical";
  if (a < 157.5) return "45graus";
  if (a < 202.5) return "horizontal";
  if (a < 247.5) return "45graus";
  if (a < 292.5) return "vertical";
  return "45graus";
}

// ── Overlay da seta ──────────────────────────────────────────────────

function SetaOverlay({ width, height, angulo }) {
  const cx = width / 2;
  const cy = height / 2;
  const len = Math.min(width, height) * 0.4;
  const rad = (angulo * Math.PI) / 180;
  const tipX = cx + Math.cos(rad) * len;
  const tipY = cy + Math.sin(rad) * len;
  const head = Math.min(width, height) * 0.045;
  const head1x = tipX - head * Math.cos(rad - Math.PI / 7);
  const head1y = tipY - head * Math.sin(rad - Math.PI / 7);
  const head2x = tipX - head * Math.cos(rad + Math.PI / 7);
  const head2y = tipY - head * Math.sin(rad + Math.PI / 7);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className={styles.setaSvg}>
      <line x1={cx} y1={cy} x2={tipX} y2={tipY} className={styles.setaLinha} />
      <polygon
        points={`${tipX},${tipY} ${head1x},${head1y} ${head2x},${head2y}`}
        className={styles.setaPonta}
      />
      <circle cx={cx} cy={cy} r={Math.min(width, height) * 0.018} className={styles.setaCentro} />
    </svg>
  );
}

// ── Componente principal ─────────────────────────────────────────────

export default function SetaFioArrastavel({
  geometria_json,
  sentidoFio,
  onChange,
  width = 200,
  height = 200,
  showLabel = true,
}) {
  const [angulo, setAngulo] = useState(() => anguloInicial(sentidoFio));
  const [arrastando, setArrastando] = useState(false);
  const canvasRef = useRef(null);

  const categoria = useMemo(() => anguloParaCategoria(angulo), [angulo]);

  function calcularAngulo(e) {
    const rect = canvasRef.current.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = e.clientX - cx;
    const dy = e.clientY - cy;
    const graus = (Math.atan2(dy, dx) * 180) / Math.PI;
    return (graus + 360) % 360;
  }

  function atualizar(novoAngulo) {
    setAngulo(novoAngulo);
    onChange?.(anguloParaCategoria(novoAngulo), novoAngulo);
  }

  function handleMouseDown(e) {
    setArrastando(true);
    atualizar(calcularAngulo(e));
  }

  function handleMouseMove(e) {
    if (!arrastando) return;
    atualizar(calcularAngulo(e));
  }

  function pararArrasto() {
    setArrastando(false);
  }

  return (
    <div className={styles.wrap}>
      {showLabel && <p className={styles.instrucao}>Arraste para definir o sentido do fio</p>}

      <div
        ref={canvasRef}
        className={styles.canvas}
        style={{ aspectRatio: `${width} / ${height}` }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={pararArrasto}
        onMouseLeave={pararArrasto}
      >
        <div className={styles.pecaWrap}>
          <MiniSVG geometria={geometria_json} />
        </div>
        <SetaOverlay width={width} height={height} angulo={angulo} />
      </div>

      <p className={styles.anguloLabel}>
        Ângulo: {Math.round(angulo)}° → {CATEGORIA_LABEL[categoria]}
      </p>
    </div>
  );
}
