/**
 * ParteCard — representa uma "parte" do molde (Frente, Costa, Manga…)
 * com todos os tamanhos exibidos em miniatura lado a lado.
 * Controles compartilhados: nome, rotacao_base, sentido_fio, tipo_corte.
 */
import styles from "./ParteCard.module.css";

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

function MiniSVG({ geometria, rotacao_base = 0 }) {
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

  const pontosStr = pontos
    .map((p) => `${p[0] - minX + pad},${p[1] - minY + pad}`)
    .join(" ");

  return (
    <svg viewBox={`0 0 ${vw} ${vh}`} className={styles.miniSvg}>
      <polygon
        points={pontosStr}
        fill="var(--sc-100)"
        stroke="var(--sc-700)"
        strokeWidth={sw}
      />
    </svg>
  );
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
    onChange(((rotacaoAtual + delta) % 360 + 360) % 360);
  }
  const deg = rotacaoAtual ?? 0;
  const indicador =
    deg === 0 ? "Rotação: 0°" : `Rotação: ${deg > 0 ? "+" : ""}${deg}°`;

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
  { valor: "vertical",   label: "↕", titulo: "Vertical"   },
  { valor: "horizontal", label: "↔", titulo: "Horizontal" },
  { valor: "45graus",    label: "↗", titulo: "45°"        },
];

function BotoesSentido({ valor, onChange }) {
  return (
    <div className={styles.btnGroup}>
      {SENTIDOS.map((s) => (
        <button
          key={s.valor}
          type="button"
          title={s.titulo}
          className={`${styles.btnSentido} ${valor === s.valor ? styles.btnAtivo : ""}`}
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
  { valor: "simples",         label: "Simples" },
  { valor: "par",             label: "Par ↔"   },
  { valor: "par_sem_espelho", label: "Par s/↔" },
];

function BotoesTipoCorte({ valor, onChange }) {
  return (
    <div className={styles.btnGroupCorte}>
      {TIPOS_CORTE.map((t) => (
        <button
          key={t.valor}
          type="button"
          className={`${styles.btnCorte} ${valor === t.valor ? styles.btnAtivo : ""}`}
          onClick={() => onChange(t.valor)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

// ── Componente principal ─────────────────────────────────────────────

export default function ParteCard({ parte, index, onChange }) {
  function set(campo, valor) {
    onChange(index, campo, valor);
  }

  const rotacaoBase = parte.rotacao_base ?? 0;

  return (
    <div className={styles.card}>
      {/* Cabeçalho: número da parte + nome editável */}
      <div className={styles.header}>
        <span className={styles.parteNum}>Parte {index + 1}</span>
        <input
          className={styles.nomeInput}
          value={parte.nome}
          onChange={(e) => set("nome", e.target.value)}
          placeholder="Frente, Costa, Manga..."
        />
      </div>

      {/* Miniaturas dos tamanhos — rotacionadas em tempo real */}
      <div className={styles.tamanhos}>
        {parte.pecas.map((p) => (
          <div key={p.tamanho} className={styles.tamanhoItem}>
            <div className={styles.miniPreview}>
              <MiniSVG geometria={p.geometria_json} rotacao_base={rotacaoBase} />
            </div>
            <span className={styles.tamanhoLabel}>{p.tamanho}</span>
            <span className={styles.areaLabel}>
              {Number(p.area_cm2).toFixed(0)} cm²
            </span>
          </div>
        ))}
      </div>

      {/* Controles compartilhados */}
      <div className={styles.controles}>
        <div className={styles.controleItem}>
          <label className={styles.label}>
            Orientar peça
            <span className={styles.labelDica}> — gire até ficar como no tecido</span>
          </label>
          <BotoesRotacao
            rotacaoAtual={rotacaoBase}
            onChange={(v) => set("rotacao_base", v)}
          />
        </div>
        <div className={styles.controleItem}>
          <label className={styles.label}>Sentido do fio</label>
          <BotoesSentido
            valor={parte.sentido_fio}
            onChange={(v) => set("sentido_fio", v)}
          />
        </div>
        <div className={styles.controleItem}>
          <label className={styles.label}>Tipo de corte</label>
          <BotoesTipoCorte
            valor={parte.tipo_corte}
            onChange={(v) => set("tipo_corte", v)}
          />
        </div>
      </div>
    </div>
  );
}
