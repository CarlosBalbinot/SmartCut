/**
 * ParteCard — representa uma "parte" do molde (Frente, Costa, Manga…)
 * com todos os tamanhos exibidos em miniatura, a seta de sentido do
 * fio arrastável e os controles de rotação/tipo de corte.
 */
import styles from "./ParteCard.module.css";
import MiniSVG from "./MiniSVG";
import SetaFioArrastavel from "../SetaFioArrastavel";

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

// ── Botões de tipo de corte ──────────────────────────────────────────

const TIPOS_CORTE = [
  { valor: "simples", label: "1 peça" },
  { valor: "par", label: "2 peças espelhadas" },
  { valor: "par_sem_espelho", label: "2 peças sem espelho" },
];

function BotoesTipoCorte({ valor, onChange }) {
  return (
    <>
      {!valor && (
        <button type="button" className={styles.btnCorteVazio} disabled>
          Selecione o tipo de corte
        </button>
      )}
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
    </>
  );
}

// ── Componente principal ─────────────────────────────────────────────

export default function ParteCard({ parte, index, onChange, onRemove }) {
  function set(campo, valor) {
    onChange(index, campo, valor);
  }

  const rotacaoBase = parte.rotacao_base ?? 0;

  // Peça representativa para a seta: o maior tamanho com geometria disponível
  const pecaRepresentativa = [...parte.pecas].reverse().find((p) => p.geometria_json) ?? null;

  return (
    <div className={styles.card}>
      {/* Cabeçalho: número da parte + nome editável */}
      <div className={styles.header}>
        <span className={styles.parteNum}>Parte {index + 1}</span>
        <input
          className={`${styles.nomeInput} sc-upper`}
          value={parte.nome}
          onChange={(e) => set("nome", e.target.value.toUpperCase())}
          placeholder="Frente, Costa, Manga..."
        />
        <button
          type="button"
          className={styles.btnRemover}
          onClick={() => onRemove(index)}
          title="Remover esta parte"
        >
          ×
        </button>
      </div>

      {/* Corpo: seta de sentido do fio (esquerda) + tamanhos e controles (direita) */}
      <div className={styles.corpo}>
        <div className={styles.colEsquerda}>
          <SetaFioArrastavel
            geometria_json={pecaRepresentativa?.geometria_json}
            sentidoFio={parte.sentido_fio}
            onChange={(categoria) => set("sentido_fio", categoria)}
            width={180}
            height={180}
            showLabel={false}
          />
        </div>

        <div className={styles.colDireita}>
          {/* Miniaturas dos tamanhos — rotacionadas em tempo real */}
          <div className={styles.tamanhos}>
            {parte.pecas.map((p) => (
              <div key={p.tamanho} className={styles.tamanhoItem}>
                <div className={styles.miniPreview}>
                  <MiniSVG geometria={p.geometria_json} rotacao_base={rotacaoBase} />
                </div>
                <span className={styles.tamanhoLabel}>{p.tamanho}</span>
                <span className={styles.areaLabel}>
                  {p.area_cm2 != null ? `${Number(p.area_cm2).toFixed(0)} cm²` : "faltando"}
                </span>
              </div>
            ))}
          </div>

          <div className={styles.controleItem}>
            <label className={styles.label}>
              Orientar peça
              <span className={styles.labelDica}> — gire até ficar como no tecido</span>
            </label>
            <BotoesRotacao rotacaoAtual={rotacaoBase} onChange={(v) => set("rotacao_base", v)} />
          </div>

          <div className={styles.controleItem}>
            <label className={styles.label}>
              Tipo de corte<span className={styles.obrigatorio}> *</span>
            </label>
            <BotoesTipoCorte valor={parte.tipo_corte} onChange={(v) => set("tipo_corte", v)} />
          </div>
        </div>
      </div>
    </div>
  );
}
