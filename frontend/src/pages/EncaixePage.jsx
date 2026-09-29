import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getEncaixe, getEncaixes, getPdfEncaixe } from "../api/encaixes";
import { imprimirRelatorio, RELATORIO_FORMULARIO_CORTE } from "../api/relatorios";
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

// Índice da paleta por peça (a cor em si é a mesma do PALETTE). O swatch do
// painel usa classes (pecaCor0..13) e o Visualizador recebe o hex do PALETTE —
// assim nenhum estilo inline na página.
function buildColorIdx(placements) {
  const map = {};
  let idx = 0;
  for (const pl of placements) {
    if (!(pl.id in map)) {
      map[pl.id] = idx % PALETTE.length;
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

// ── Nível semântico do aproveitamento — vira data-nivel no card de métrica
// (a cor fica no CSS, ver .metricValor[data-nivel]). ──────────────────────
function nivelAproveitamento(v) {
  if (v == null) return "neutro";
  if (v >= 80) return "bom";
  if (v >= 65) return "medio";
  return "ruim";
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

const fmtEnc = (n) => (n != null ? `ENC-${String(n).padStart(3, "0")}` : "ENC-—");

// Tecido do encaixe: nome gravado no mapa ou modelo/cor do lote.
const nomeTecido = (enc) =>
  enc.tecido_nome || [enc.lote?.modelo, enc.lote?.cor_tecido].filter(Boolean).join(" — ") || null;

export default function EncaixePage() {
  // :id é o id do ENCAIXE. Links antigos traziam o id do pedido — sem
  // encaixe com esse id, tenta como pedido e redireciona para o primeiro
  // encaixe dele.
  const { id } = useParams();
  const navigate = useNavigate();

  const [enc, setEnc] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [gerandoPdf, setGerandoPdf] = useState(false);
  const [imprimindo, setImprimindo] = useState(false);
  const [pecaSelecionada, setPecaSelecionada] = useState(null);
  const [listaAberta, setListaAberta] = useState(true);
  const [showJustificativa, setShowJustificativa] = useState(false);

  useEffect(() => {
    let ativo = true;
    setCarregando(true);
    setErro(null);
    setPecaSelecionada(null);
    getEncaixe(id)
      .then((e) => ativo && setEnc(e))
      .catch(async (ex) => {
        const doPedido = await getEncaixes(id).catch(() => []);
        const primeiro = [...doPedido].sort((a, b) => (a.numero_enc ?? 0) - (b.numero_enc ?? 0))[0];
        if (!ativo) return;
        if (primeiro) navigate(`/producao/encaixes/${primeiro.id}`, { replace: true });
        else setErro(ex.message);
      })
      .finally(() => ativo && setCarregando(false));
    return () => {
      ativo = false;
    };
  }, [id]);

  const pedido = enc?.pedido;
  const oc = enc?.ordem_corte;
  const nav = enc?.navegacao;

  // Encaixe de OC abre o formulário de corte (relPro001) no card do
  // visualizador, sobre a OC. Encaixe sem OC (Encaixe Rápido/antigos) segue
  // no PDF legado, gerado por pedido.
  async function imprimirFormularioCorte() {
    if (!oc) return;
    setImprimindo(true);
    try {
      await imprimirRelatorio(RELATORIO_FORMULARIO_CORTE, oc.id);
    } catch (ex) {
      setErro(ex.message);
    } finally {
      setImprimindo(false);
    }
  }

  // Rota legada: baixa o PDF de corte de UM pedido com todos os seus
  // encaixes (sem OC). Não abre visualizador — é download direto.
  async function baixarPdf() {
    if (!pedido) return;
    setGerandoPdf(true);
    try {
      const blob = await getPdfEncaixe(pedido.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const num = pedido.numero?.replace(/\//g, "-") ?? id.slice(0, 8);
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

  if (!enc) {
    return (
      <div className={styles.pagina}>
        <button type="button" className={styles.btnVoltar} onClick={() => navigate(-1)}>
          Voltar
        </button>
        <p className={styles.vazio}>Encaixe não encontrado.</p>
      </div>
    );
  }

  const ehRapido = pedido?.tipo === "encaixe_rapido";
  const tecidoLote = [nomeTecido(enc), enc.lote ? `lote ${enc.lote.codigo_lote}` : null]
    .filter(Boolean)
    .join(" · ");
  const mapa = enc.mapa_json ?? {};
  const placements = mapa.placements ?? [];
  const colorIdx = buildColorIdx(placements);
  const colorMap = Object.fromEntries(
    Object.entries(colorIdx).map(([id, idx]) => [id, PALETTE[idx]])
  );
  const pecasAgregadas = agregarPecas(placements);
  const temVisualizador =
    mapa.largura_cm && mapa.comprimento_cm && placements.some((p) => p.polygon);

  const aproveitamento = enc.desperdicio_pct != null ? 100 - enc.desperdicio_pct : null;
  const nivelAprov = nivelAproveitamento(aproveitamento);
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
      {/* ── Cabeçalho: ENC, OC e pedido (links); navegação na mesma OC ── */}
      <div className={styles.topBar}>
        <button type="button" className={styles.btnVoltar} onClick={() => navigate(-1)}>
          Voltar
        </button>
        <div className={styles.topBarCenter}>
          <h1 className={styles.titulo}>
            {fmtEnc(enc.numero_enc)}
            {enc.parte ? ` · parte ${enc.parte}` : ""}
          </h1>
          <p className={styles.subtitulo}>
            {oc && (
              <>
                <Link to={`/producao/ordens-corte/${oc.id}`} className={styles.linkApoio}>
                  {oc.numero_fmt}
                </Link>
                {pedido && !ehRapido ? " · " : ""}
              </>
            )}
            {pedido && !ehRapido && (
              <>
                <Link
                  to={`/vendas/pedidos/${pedido.id}?modo=visualizar`}
                  className={styles.linkApoio}
                >
                  Pedido {pedido.numero}
                </Link>
                {pedido.cliente ? ` · ${pedido.cliente}` : ""}
              </>
            )}
            {(ehRapido || !pedido) && (enc.descricao || (ehRapido ? "Encaixe Rápido" : ""))}
          </p>
        </div>
        {nav && nav.total > 1 && (
          <div className={styles.painelBadges}>
            <button
              type="button"
              className={`${styles.btnVoltar} ${nav.anterior_id ? "" : styles.navDesabilitado}`}
              disabled={!nav.anterior_id}
              onClick={() => navigate(`/producao/encaixes/${nav.anterior_id}`)}
              title="Encaixe anterior"
            >
              ‹ Anterior
            </button>
            <span className={styles.enfestoNum}>
              {nav.posicao} de {nav.total}
            </span>
            <button
              type="button"
              className={`${styles.btnVoltar} ${nav.proximo_id ? "" : styles.navDesabilitado}`}
              disabled={!nav.proximo_id}
              onClick={() => navigate(`/producao/encaixes/${nav.proximo_id}`)}
              title="Próximo encaixe"
            >
              Próximo ›
            </button>
          </div>
        )}
      </div>

      {/* ── Layout principal: painel + visualizador ── */}
      <div className={styles.layout}>
        {/* ── Painel esquerdo ── */}
        <aside className={styles.painel}>
          <div className={styles.painelHeader}>
            <p className={styles.painelCliente}>{tecidoLote || "Tecido"}</p>
            <div className={styles.painelBadges}>
              <span className={styles.badgeTecido}>
                {enc.num_camadas} camada{enc.num_camadas !== 1 ? "s" : ""}
              </span>
              {enc.enfesto != null && (
                <span className={styles.enfestoNum}>Enfesto {enc.enfesto}</span>
              )}
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
              <span className={styles.metricValor} data-nivel={nivelAprov}>
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
              <span className={styles.metricLabel} title="Comprimento de uma camada (risco)">
                Comprimento do risco
              </span>
              <span className={styles.metricValor}>
                {enc.comp_metros != null ? `${Number(enc.comp_metros).toFixed(2)} m` : "—"}
              </span>
            </div>
            <div className={styles.metricCard}>
              <span className={styles.metricLabel}>Peso total</span>
              <span
                className={styles.metricValor}
                title={
                  enc.peso_kg != null
                    ? `${Number(enc.peso_kg).toFixed(3)} kg por camada × ${enc.num_camadas}`
                    : ""
                }
              >
                {enc.peso_total_kg != null ? `${Number(enc.peso_total_kg).toFixed(3)} kg` : "—"}
              </span>
            </div>
            <div className={styles.metricCard}>
              <span className={styles.metricLabel}>Custo total</span>
              <span className={styles.metricValor}>
                {enc.custo_total_camadas != null
                  ? `R$ ${Number(enc.custo_total_camadas).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
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
                        className={`${styles.pecaCor} ${styles[`pecaCor${colorIdx[p.id] ?? 0}`]}`}
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

          {/* Formulário de corte da OC (relPro001) ou, sem OC, o PDF legado por pedido. */}
          {oc ? (
            <button
              type="button"
              className={styles.btnPdfPainel}
              onClick={imprimirFormularioCorte}
              disabled={imprimindo}
            >
              {imprimindo ? "Abrindo…" : "Formulário de corte"}
            </button>
          ) : (
            pedido && (
              <button
                type="button"
                className={styles.btnPdfPainel}
                onClick={baixarPdf}
                disabled={gerandoPdf}
              >
                {gerandoPdf ? "Gerando PDF…" : "↓ Baixar PDF de Corte"}
              </button>
            )
          )}
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
