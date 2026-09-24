import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getPedidoVenda } from "../api/pedidos";
import { getEncaixes, getPdfEncaixe } from "../api/encaixes";
import VisualizadorEncaixe from "../components/VisualizadorEncaixe/VisualizadorEncaixe";
import styles from "./EncaixePage.module.css";

// Paleta de cores para os moldes no canvas
const PALETTE = [
  "#3b82f6",
  "#ef4444",
  "#10b981",
  "#f59e0b",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#f97316",
  "#6366f1",
  "#84cc16",
  "#06b6d4",
  "#a855f7",
  "#f43f5e",
  "#22c55e",
  "#eab308",
];

function buildColorMap(placements) {
  const map = {};
  let idx = 0;
  for (const pl of placements) {
    if (!map[pl.id]) {
      map[pl.id] = PALETTE[idx % PALETTE.length];
      idx++;
    }
  }
  return map;
}

function agregarPecas(placements) {
  const map = {};
  for (const pl of placements) {
    const key = pl.id;
    if (!map[key]) {
      map[key] = {
        id: pl.id,
        peca: pl.peca ?? null,
        tamanho: pl.tamanho ?? null,
        grupo_nome: pl.grupo_nome ?? null,
        count: 0,
      };
    }
    map[key].count++;
  }
  return Object.values(map).sort((a, b) => {
    const ga = a.grupo_nome ?? "";
    const gb = b.grupo_nome ?? "";
    if (ga !== gb) return ga.localeCompare(gb);
    return (a.tamanho ?? "").localeCompare(b.tamanho ?? "");
  });
}

// ── Cor semântica do aproveitamento — reaproveitada no card de métrica e
// na borda do tooltip de justificativa. ────────────────────────────────────
function corAproveitamento(v) {
  if (v == null) return "var(--sc-text-primary)";
  if (v >= 80) return "var(--sc-success-text)";
  if (v >= 65) return "var(--color-primary)";
  return "var(--sc-danger-text)";
}

// ── Explicação automática (compacta) do % de aproveitamento, exibida só no
// tooltip ao passar o mouse no card — usa dados que já vêm no mapa_json,
// sem precisar de nada novo do backend. ────────────────────────────────────
function gerarJustificativa({ aproveitamento, partsCount, placementsCount }) {
  const naoPosicionadas =
    partsCount != null && placementsCount != null ? partsCount - placementsCount : 0;

  if (aproveitamento < 65) {
    const bullets = ["Peças com formas irregulares deixam espaços vazios."];
    if (naoPosicionadas > 0) {
      bullets.push(
        naoPosicionadas === 1
          ? "1 peça não posicionada (tecido muito estreito?)."
          : `${naoPosicionadas} peças não posicionadas (tecido muito estreito?).`
      );
    }
    bullets.push("Adicione mais peças para preencher vazios.");
    return { titulo: "Aproveitamento abaixo do ideal.", bullets };
  }

  if (aproveitamento < 80) {
    return {
      titulo: "Aproveitamento razoável.",
      bullets: ["Adicione peças de outros tamanhos para preencher os espaços."],
    };
  }

  return { titulo: "Ótimo aproveitamento!", bullets: [] };
}

export default function EncaixePage() {
  // :id é o pedido_id — buscamos todos os encaixes desse pedido
  const { id } = useParams();
  const navigate = useNavigate();

  const [pedido, setPedido] = useState(null);
  const [encaixes, setEncaixes] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [gerandoPdf, setGerandoPdf] = useState(false);
  const [enfestoAtivo, setEnfestoAtivo] = useState(0);
  const [pecaSelecionada, setPecaSelecionada] = useState(null);
  const [listaAberta, setListaAberta] = useState(true);
  const [showJustificativa, setShowJustificativa] = useState(false);

  useEffect(() => {
    Promise.all([getPedidoVenda(id), getEncaixes(id)])
      .then(([ped, encs]) => {
        setPedido(ped);
        setEncaixes(encs.filter((e) => e.status !== "deletado"));
      })
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false));
  }, [id]);

  function trocarEnfesto(idx) {
    setEnfestoAtivo(idx);
    setPecaSelecionada(null);
  }

  async function baixarPdf() {
    setGerandoPdf(true);
    try {
      const blob = await getPdfEncaixe(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const num = pedido?.numero?.replace(/\//g, "-") ?? id.slice(0, 8);
      a.download = `encaixe-${num}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (ex) {
      setErro(ex.message);
    } finally {
      setGerandoPdf(false);
    }
  }

  if (carregando) {
    return <div className={styles.loading}>Carregando encaixes…</div>;
  }

  if (erro) {
    return (
      <div className={styles.pagina}>
        <button type="button" className={styles.btnVoltar} onClick={() => navigate(-1)}>
          Voltar
        </button>
        <p className={styles.erroMsg}>{erro}</p>
      </div>
    );
  }

  if (encaixes.length === 0) {
    return (
      <div className={styles.pagina}>
        <button type="button" className={styles.btnVoltar} onClick={() => navigate(-1)}>
          Voltar
        </button>
        <p className={styles.vazio}>Nenhum encaixe gerado para este pedido.</p>
      </div>
    );
  }

  const enc = encaixes[enfestoAtivo] ?? encaixes[0];
  const mapa = enc.mapa_json ?? {};
  const placements = mapa.placements ?? [];
  const colorMap = buildColorMap(placements);
  const pecasAgregadas = agregarPecas(placements);
  const temVisualizador =
    mapa.largura_cm && mapa.comprimento_cm && placements.some((p) => p.polygon);

  const aproveitamento = enc.desperdicio_pct != null ? 100 - enc.desperdicio_pct : null;
  const corAprov = corAproveitamento(aproveitamento);
  const justificativa =
    aproveitamento != null
      ? gerarJustificativa({
          aproveitamento,
          partsCount: mapa.parts_count,
          placementsCount: placements.length,
          larguraCm: mapa.largura_cm,
        })
      : null;

  return (
    <div className={styles.pagina}>
      {/* ── Cabeçalho ── */}
      <div className={styles.topBar}>
        <button type="button" className={styles.btnVoltar} onClick={() => navigate(-1)}>
          Voltar
        </button>
        <div className={styles.topBarCenter}>
          <h1 className={styles.titulo}>
            Encaixe
            {pedido?.numero ? ` — Pedido ${pedido.numero}` : ""}
          </h1>
          {pedido?.cliente_razao_social && (
            <p className={styles.subtitulo}>{pedido.cliente_razao_social}</p>
          )}
        </div>
      </div>

      {/* ── Tabs por enfesto (só quando há mais de um) ── */}
      {encaixes.length > 1 && (
        <div className={styles.tabsBar}>
          {encaixes.map((e, idx) => (
            <button
              type="button"
              key={e.id}
              className={`${styles.tab} ${idx === enfestoAtivo ? styles.tabAtiva : ""}`}
              onClick={() => trocarEnfesto(idx)}
            >
              {e.mapa_json?.tecido_nome ?? "Tecido"} (enfesto {idx + 1})
            </button>
          ))}
        </div>
      )}

      {/* ── Layout principal: painel + visualizador ── */}
      <div className={styles.layout}>
        {/* ── Painel esquerdo ── */}
        <aside className={styles.painel}>
          <div className={styles.painelHeader}>
            <p className={styles.painelCliente}>
              {pedido?.cliente_razao_social || `Pedido ${pedido?.numero ?? ""}`}
            </p>
            <div className={styles.painelBadges}>
              <span className={styles.badgeTecido}>{mapa.tecido_nome ?? "Tecido"}</span>
              <span className={styles.enfestoNum}>
                Enfesto {enfestoAtivo + 1} de {encaixes.length}
              </span>
            </div>
          </div>

          {/* Métricas 2×2 */}
          <div className={styles.metricsGrid}>
            <div
              className={`${styles.metricCard} ${styles.cardAproveitamento}`}
              onMouseEnter={() => setShowJustificativa(true)}
              onMouseLeave={() => setShowJustificativa(false)}
            >
              <span className={styles.metricLabel}>Aproveitamento</span>
              <span className={styles.metricValor} style={{ color: corAprov }}>
                {aproveitamento != null ? `${aproveitamento.toFixed(1)}%` : "—"}
              </span>

              {showJustificativa && justificativa && (
                <div className={styles.tooltipJustificativa}>
                  <p className={styles.tooltipTitulo}>{justificativa.titulo}</p>
                  {justificativa.bullets.length > 0 && (
                    <ul className={styles.tooltipLista}>
                      {justificativa.bullets.map((b, i) => (
                        <li key={i}>{b}</li>
                      ))}
                    </ul>
                  )}
                  <p className={styles.tooltipRodape}>
                    Posicionadas: {placements.length}/{mapa.parts_count ?? placements.length}
                  </p>
                </div>
              )}
            </div>
            <div className={styles.metricCard}>
              <span className={styles.metricLabel}>Comprimento</span>
              <span className={styles.metricValor}>
                {enc.comp_metros != null ? `${Number(enc.comp_metros).toFixed(2)} m` : "—"}
              </span>
            </div>
            <div className={styles.metricCard}>
              <span className={styles.metricLabel}>Peso estimado</span>
              <span className={styles.metricValor}>
                {enc.peso_kg != null ? `${Number(enc.peso_kg).toFixed(3)} kg` : "—"}
              </span>
            </div>
            <div className={styles.metricCard}>
              <span className={styles.metricLabel}>Custo total</span>
              <span className={styles.metricValor}>
                {enc.custo_total != null
                  ? `R$ ${Number(enc.custo_total).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
                  : "—"}
              </span>
            </div>
          </div>

          {/* Lista de peças */}
          <div className={styles.pecasSection}>
            <button
              type="button"
              className={styles.pecasSectionHeader}
              onClick={() => setListaAberta((v) => !v)}
            >
              <span>Peças no enfesto</span>
              <span
                className={`${styles.pecasChevron} ${listaAberta ? styles.pecasChevronAberto : ""}`}
              >
                ›
              </span>
            </button>
            {listaAberta && (
              <div className={styles.pecasScroll}>
                {pecasAgregadas.length === 0 ? (
                  <p className={styles.semDados}>Dados não disponíveis.</p>
                ) : (
                  pecasAgregadas.map((p) => (
                    <button
                      type="button"
                      key={p.id}
                      className={`${styles.pecaItem} ${pecaSelecionada === p.id ? styles.pecaItemAtivo : ""}`}
                      onClick={() => setPecaSelecionada((atual) => (atual === p.id ? null : p.id))}
                    >
                      <span
                        className={styles.pecaCor}
                        style={{ backgroundColor: colorMap[p.id] ?? "#94a3b8" }}
                      />
                      <span className={styles.pecaLabel}>
                        {p.grupo_nome
                          ? `${p.grupo_nome}${p.peca ? ` — ${p.peca}` : ""}`
                          : (p.peca ?? "Molde")}
                      </span>
                      {p.tamanho && <span className={styles.pecaTamanho}>{p.tamanho}</span>}
                      <span className={styles.pecaQtd}>×{p.count}</span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* PDF */}
          <button
            type="button"
            className={styles.btnPdfPainel}
            onClick={baixarPdf}
            disabled={gerandoPdf}
          >
            {gerandoPdf ? "Gerando PDF…" : "↓ Baixar PDF de Corte"}
          </button>
        </aside>

        {/* ── Área direita: visualizador ── */}
        <div className={styles.areaDireita}>
          {temVisualizador ? (
            <VisualizadorEncaixe
              largura_cm={mapa.largura_cm}
              comprimento_cm={mapa.comprimento_cm}
              placements={placements}
              colorMap={colorMap}
              pecaSelecionada={pecaSelecionada}
            />
          ) : (
            <div className={styles.semVisualizador}>
              <p>Desenho do encaixe não disponível para este enfesto.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
