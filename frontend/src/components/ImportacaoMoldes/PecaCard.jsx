import styles from "./PecaCard.module.css";

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

// ── SVG da silhueta com seta de sentido do fio ───────────────────────

function PecaSVG({ geometria, sentido_fio, rotacao_base = 0 }) {
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
  const sw = Math.max(w, h) * 0.012;

  const pontosStr = pontos.map((p) => `${p[0] - minX + pad},${p[1] - minY + pad}`).join(" ");

  const cx = vw / 2;
  const cy = vh / 2;
  const arrowLen = Math.min(vw, vh) * 0.35;
  const arrowSw = sw * 1.8;

  const arrow = buildArrow(sentido_fio, cx, cy, arrowLen, arrowSw);

  return (
    <svg viewBox={`0 0 ${vw} ${vh}`} className={styles.svg}>
      <polygon points={pontosStr} fill="var(--sc-100)" stroke="var(--sc-700)" strokeWidth={sw} />
      {arrow && (
        <g stroke="var(--sc-900)" fill="var(--sc-900)" strokeWidth={arrowSw} strokeLinecap="round">
          {arrow}
        </g>
      )}
    </svg>
  );
}

function buildArrow(sentido, cx, cy, len, sw) {
  const half = len / 2;
  const head = sw * 3;
  if (sentido === "vertical") {
    return (
      <>
        <line x1={cx} y1={cy - half} x2={cx} y2={cy + half} />
        <polygon points={arrowHead(cx, cy - half, 0, head)} />
        <polygon points={arrowHead(cx, cy + half, Math.PI, head)} />
      </>
    );
  }
  if (sentido === "horizontal") {
    return (
      <>
        <line x1={cx - half} y1={cy} x2={cx + half} y2={cy} />
        <polygon points={arrowHead(cx - half, cy, Math.PI / 2, head)} />
        <polygon points={arrowHead(cx + half, cy, -Math.PI / 2, head)} />
      </>
    );
  }
  if (sentido === "45graus") {
    const d = half * Math.SQRT1_2;
    return (
      <>
        <line x1={cx - d} y1={cy + d} x2={cx + d} y2={cy - d} />
        <polygon points={arrowHead(cx - d, cy + d, (3 * Math.PI) / 4, head)} />
        <polygon points={arrowHead(cx + d, cy - d, -Math.PI / 4, head)} />
      </>
    );
  }
  return null;
}

function arrowHead(x, y, angle, size) {
  const pts = [
    [0, -size],
    [-size * 0.55, size * 0.5],
    [size * 0.55, size * 0.5],
  ];
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  return pts.map(([px, py]) => `${x + px * cos - py * sin},${y + px * sin + py * cos}`).join(" ");
}

// ── Controles de rotação ─────────────────────────────────────────────

const ROTACOES = [
  { delta: -90, label: "−90°" },
  { delta: -45, label: "−45°" },
  { delta: +45, label: "+45°" },
  { delta: +90, label: "+90°" },
];

function BotoesRotacao({ rotacaoAtual, onChange }) {
  function aplicar(delta) {
    onChange((((rotacaoAtual + delta) % 360) + 360) % 360);
  }
  const deg = rotacaoAtual ?? 0;
  const indicador = deg === 0 ? "Rotação: 0°" : `Rotação: ${deg > 0 ? "+" : ""}${deg}°`;

  return (
    <div className={styles.rotacaoWrap}>
      <div className={styles.rotacaoBtns}>
        {ROTACOES.map(({ delta, label }) => (
          <button
            key={delta}
            type="button"
            className={styles.btnRotacao}
            onClick={() => aplicar(delta)}
          >
            {label}
          </button>
        ))}
        <button
          type="button"
          className={styles.btnReset}
          onClick={() => onChange(0)}
          title="Resetar rotação para 0°"
        >
          ↺
        </button>
      </div>
      <span className={styles.rotacaoIndicador}>{indicador}</span>
    </div>
  );
}

// ── Botões de sentido do fio ─────────────────────────────────────────

const SENTIDOS = [
  { valor: "vertical", label: "↕", titulo: "Vertical" },
  { valor: "horizontal", label: "↔", titulo: "Horizontal" },
  { valor: "45graus", label: "↗", titulo: "45°" },
];

function BotoesSentido({ valor, onChange }) {
  return (
    <div className={styles.btnGroup}>
      {SENTIDOS.map((s) => (
        <button
          key={s.valor}
          type="button"
          title={s.titulo}
          className={`${styles.btnSentido} ${valor === s.valor ? styles.btnSentidoAtivo : ""}`}
          onClick={() => onChange(s.valor)}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}

// ── Botões de tipo de corte ──────────────────────────────────────────

const TIPOS_CORTE = [
  { valor: "simples", label: "Simples" },
  { valor: "par", label: "Par ↔" },
  { valor: "par_sem_espelho", label: "Par s/↔" },
];

function BotoesTipoCorte({ valor, onChange }) {
  return (
    <div className={styles.btnGroupCorte}>
      {TIPOS_CORTE.map((t) => (
        <button
          key={t.valor}
          type="button"
          className={`${styles.btnCorte} ${valor === t.valor ? styles.btnCorteAtivo : ""}`}
          onClick={() => onChange(t.valor)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ── Card principal ───────────────────────────────────────────────────

export default function PecaCard({ peca, index, onChange, tituloExtra }) {
  const rotacao_base = peca.rotacao_base ?? 0;

  return (
    <div className={styles.card}>
      {/* Preview SVG rotacionado */}
      <div className={styles.preview}>
        <PecaSVG
          geometria={peca.geometria_json}
          sentido_fio={peca.sentido_fio}
          rotacao_base={rotacao_base}
        />
      </div>

      {/* Tamanho + área */}
      <div className={styles.infoBar}>
        {tituloExtra && <span className={styles.tamanhoTag}>{tituloExtra}</span>}
        <span className={styles.area}>
          {peca.area_cm2 != null ? `${Number(peca.area_cm2).toFixed(1)} cm²` : ""}
        </span>
      </div>

      <div className={styles.campos}>
        {/* Nome */}
        <div className={styles.campo}>
          <label className={styles.label}>Nome *</label>
          <input
            className={styles.input}
            name="nome"
            value={peca.nome}
            onChange={(e) => onChange(index, "nome", e.target.value)}
            required
          />
        </div>

        {/* Orientar peça */}
        <div className={styles.campo}>
          <label className={styles.label}>
            Orientar peça
            <span className={styles.labelDica}> — gire até ficar como ficaria sobre o tecido</span>
          </label>
          <BotoesRotacao
            rotacaoAtual={rotacao_base}
            onChange={(v) => onChange(index, "rotacao_base", v)}
          />
        </div>

        {/* Sentido do fio */}
        <div className={styles.campo}>
          <label className={styles.label}>Sentido do fio</label>
          <BotoesSentido
            valor={peca.sentido_fio}
            onChange={(v) => onChange(index, "sentido_fio", v)}
          />
        </div>

        {/* Tipo de corte */}
        <div className={styles.campo}>
          <label className={styles.label}>Tipo de corte</label>
          <BotoesTipoCorte
            valor={peca.tipo_corte}
            onChange={(v) => onChange(index, "tipo_corte", v)}
          />
        </div>
      </div>
    </div>
  );
}
