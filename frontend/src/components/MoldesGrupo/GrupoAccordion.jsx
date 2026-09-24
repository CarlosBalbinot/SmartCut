import { useState } from "react";
import MiniSVG from "../ImportacaoMoldes/MiniSVG";
import styles from "./GrupoAccordion.module.css";

const TIPO_LABEL = {
  simples: "Simples",
  par: "Par ↔",
  par_sem_espelho: "Par s/↔",
};

const SENTIDO_LABEL = {
  vertical: "↕",
  horizontal: "↔",
  "45graus": "↗",
};

export default function GrupoAccordion({ grupo, podeEditar, podeExcluir, onEditarMolde, onDeletarGrupo }) {
  const [aberto, setAberto] = useState(false);

  // Agrupa moldes por peca (parte)
  const porParte = agruparPorParte(grupo.moldes);
  const totalMoldes = grupo.moldes.length;

  return (
    <div className={styles.grupo}>
      {/* ── Cabeçalho do grupo ── */}
      <div className={styles.header} onClick={() => setAberto((v) => !v)}>
        <span className={`${styles.seta} ${aberto ? styles.setaAberta : ""}`}>›</span>
        <span className={styles.nomeGrupo}>
          {grupo.codigo ? `${grupo.codigo} — ${grupo.nome}` : grupo.nome}
        </span>
        <span className={styles.contagem}>
          {Object.keys(porParte).length} parte{Object.keys(porParte).length !== 1 ? "s" : ""}
          {" · "}
          {totalMoldes} molde{totalMoldes !== 1 ? "s" : ""}
        </span>
        {podeExcluir && (
          <button
            className={styles.btnDeletar}
            title="Excluir grupo"
            onClick={(e) => {
              e.stopPropagation();
              onDeletarGrupo(grupo.id, grupo.nome);
            }}
          >
            ✕
          </button>
        )}
      </div>

      {/* ── Conteúdo expandido ── */}
      {aberto && (
        <div className={styles.corpo}>
          {Object.entries(porParte).map(([parte, moldes]) => (
            <div key={parte} className={styles.parte}>
              <div className={styles.parteHeader}>
                <span className={styles.parteNome}>{parte || "—"}</span>
                <span className={styles.parteMeta}>
                  {SENTIDO_LABEL[moldes[0]?.sentido_fio] ?? ""}
                  {" · "}
                  {TIPO_LABEL[moldes[0]?.tipo_corte] ?? moldes[0]?.tipo_corte}
                </span>
              </div>
              <div className={styles.moldesGrid}>
                {moldes.map((m) => (
                  <div
                    key={m.id}
                    className={styles.moldeCard}
                    onClick={podeEditar ? () => onEditarMolde(m) : undefined}
                    title={podeEditar ? "Editar molde" : undefined}
                  >
                    <div className={styles.miniPreviewWrap}>
                      <MiniSVG geometria={m.geometria_json} />
                      <span className={styles.tamanhoBadge}>{m.tamanho ?? "—"}</span>
                    </div>
                    <span className={styles.moldeNome} title={m.nome}>{m.nome}</span>
                    <span className={styles.moldeArea}>
                      {m.area_cm2 != null ? `${Number(m.area_cm2).toFixed(1)} cm²` : "—"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function agruparPorParte(moldes) {
  const map = {};
  for (const m of moldes) {
    const parte = m.peca ?? "";
    if (!map[parte]) map[parte] = [];
    map[parte].push(m);
  }
  // Ordena tamanhos dentro de cada parte
  const ordem = ["PP", "P", "M", "G", "GG", "XGG"];
  for (const parte of Object.values(map)) {
    parte.sort((a, b) => {
      const ia = ordem.indexOf(a.tamanho ?? "");
      const ib = ordem.indexOf(b.tamanho ?? "");
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });
  }
  return map;
}
