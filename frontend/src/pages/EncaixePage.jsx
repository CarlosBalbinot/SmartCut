import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { encaixesApi, pedidosApi } from "../services/api";
import VisualizadorEncaixe from "../components/VisualizadorEncaixe/VisualizadorEncaixe";
import styles from "./EncaixePage.module.css";

// Paleta de cores para os moldes no canvas
const PALETTE = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
  "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16",
  "#06b6d4", "#a855f7", "#f43f5e", "#22c55e", "#eab308",
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

export default function EncaixePage() {
  // :id é o pedido_id — buscamos todos os encaixes desse pedido
  const { id } = useParams();
  const navigate = useNavigate();

  const [pedido, setPedido] = useState(null);
  const [encaixes, setEncaixes] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [gerandoPdf, setGerandoPdf] = useState(false);

  useEffect(() => {
    Promise.all([pedidosApi.obter(id), encaixesApi.listar(id)])
      .then(([ped, encs]) => {
        setPedido(ped);
        setEncaixes(encs.filter((e) => e.status !== "deletado"));
      })
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false));
  }, [id]);

  async function baixarPdf() {
    setGerandoPdf(true);
    try {
      const blob = await encaixesApi.pdf(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const num = pedido?.num_pedido?.replace(/\//g, "-") ?? id.slice(0, 8);
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
        <button className={styles.voltar} onClick={() => navigate(`/pedidos/${id}`)}>
          ← Pedido
        </button>
        <p className={styles.erroMsg}>{erro}</p>
      </div>
    );
  }

  if (encaixes.length === 0) {
    return (
      <div className={styles.pagina}>
        <button className={styles.voltar} onClick={() => navigate(`/pedidos/${id}`)}>
          ← Pedido
        </button>
        <p className={styles.vazio}>Nenhum encaixe gerado para este pedido.</p>
      </div>
    );
  }

  // ── Totais ───────────────────────────────────────────────────────────
  const totalMetros = encaixes.reduce((s, e) => s + (e.comp_metros ?? 0), 0);
  const totalPeso = encaixes.reduce((s, e) => s + (e.peso_kg ?? 0), 0);
  const totalCusto = encaixes.reduce((s, e) => s + (e.custo_total ?? 0), 0);
  const aproveitamento =
    encaixes.reduce((s, e) => s + (100 - (e.desperdicio_pct ?? 0)), 0) /
    encaixes.length;

  return (
    <div className={styles.pagina}>
      {/* ── Cabeçalho ── */}
      <div className={styles.topBar}>
        <button
          className={styles.voltar}
          onClick={() => navigate(`/pedidos/${id}`)}
        >
          ← Pedido
        </button>
        <div className={styles.topBarCenter}>
          <h1 className={styles.titulo}>
            Encaixe
            {pedido?.num_pedido ? ` — Pedido ${pedido.num_pedido}` : ""}
          </h1>
          {pedido?.cliente && (
            <p className={styles.subtitulo}>{pedido.cliente}</p>
          )}
        </div>
        <button
          className={styles.btnPdf}
          onClick={baixarPdf}
          disabled={gerandoPdf}
        >
          {gerandoPdf ? "Gerando PDF…" : "↓ Baixar Relatório PDF"}
        </button>
      </div>

      {/* ── Cards de resumo ── */}
      <div className={styles.cards}>
        <div className={styles.card}>
          <span className={styles.cardLabel}>Enfestos</span>
          <span className={styles.cardValor}>{encaixes.length}</span>
        </div>
        <div className={styles.card}>
          <span className={styles.cardLabel}>Metros totais</span>
          <span className={styles.cardValor}>{totalMetros.toFixed(2)} m</span>
        </div>
        <div className={styles.card}>
          <span className={styles.cardLabel}>Peso total</span>
          <span className={styles.cardValor}>{totalPeso.toFixed(3)} kg</span>
        </div>
        <div className={`${styles.card} ${styles.cardDestaque}`}>
          <span className={styles.cardLabel}>Custo total</span>
          <span className={styles.cardValor}>
            R${" "}
            {totalCusto.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
          </span>
        </div>
        <div className={`${styles.card} ${aproveitamento >= 75 ? styles.cardBom : styles.cardAlerta}`}>
          <span className={styles.cardLabel}>Aproveitamento</span>
          <span className={styles.cardValor}>{aproveitamento.toFixed(1)}%</span>
        </div>
      </div>

      {/* ── Um card por enfesto ── */}
      {encaixes.map((enc, idx) => {
        const mapa = enc.mapa_json ?? {};
        const placements = mapa.placements ?? [];
        const colorMap = buildColorMap(placements);
        const pecasAgregadas = agregarPecas(placements);
        const temVisualizador =
          mapa.largura_cm && mapa.comprimento_cm && placements.some((p) => p.polygon);

        return (
          <section key={enc.id} className={styles.enfesto}>
            {/* Header do enfesto */}
            <div className={styles.enfestoHeader}>
              <div className={styles.enfestoTopo}>
                <span className={styles.badgeTecido}>
                  {mapa.tecido_nome ?? "Tecido"}
                </span>
                <span className={styles.enfestoNum}>Enfesto {idx + 1}</span>
              </div>
              <p className={styles.enfestoInstrucoes}>
                {enc.num_camadas} camada{enc.num_camadas !== 1 ? "s" : ""}
                {" · "}
                {enc.comp_metros != null
                  ? `${Number(enc.comp_metros).toFixed(2)} m`
                  : "— m"}
                {" · "}
                {enc.peso_kg != null
                  ? `${Number(enc.peso_kg).toFixed(3)} kg`
                  : "— kg"}
                {" · "}
                {enc.custo_total != null
                  ? `R$ ${Number(enc.custo_total).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
                  : "—"}
                {enc.desperdicio_pct != null && (
                  <>
                    {" · "}
                    <span
                      className={
                        enc.desperdicio_pct <= 25
                          ? styles.desperdicioBom
                          : styles.desperdicioAlerta
                      }
                    >
                      {Number(enc.desperdicio_pct).toFixed(1)}% desperdício
                    </span>
                  </>
                )}
              </p>
            </div>

            {/* Corpo: lista de peças + visualizador */}
            <div className={styles.enfestoBody}>
              {/* Lista de peças */}
              <div className={styles.pecasList}>
                <h3 className={styles.pecasTitle}>Peças no enfesto</h3>
                {pecasAgregadas.length === 0 ? (
                  <p className={styles.semDados}>Dados não disponíveis.</p>
                ) : (
                  pecasAgregadas.map((p) => (
                    <div key={p.id} className={styles.pecaItem}>
                      <span
                        className={styles.pecaCor}
                        style={{ backgroundColor: colorMap[p.id] ?? "#94a3b8" }}
                      />
                      <span className={styles.pecaLabel}>
                        {p.grupo_nome
                          ? `${p.grupo_nome}${p.peca ? ` — ${p.peca}` : ""}`
                          : (p.peca ?? "Molde")}
                      </span>
                      {p.tamanho && (
                        <span className={styles.pecaTamanho}>{p.tamanho}</span>
                      )}
                      <span className={styles.pecaQtd}>×{p.count}</span>
                    </div>
                  ))
                )}
              </div>

              {/* Visualizador Konva */}
              {temVisualizador && (
                <div className={styles.visualizadorWrap}>
                  <VisualizadorEncaixe
                    largura_cm={mapa.largura_cm}
                    comprimento_cm={mapa.comprimento_cm}
                    placements={placements}
                    colorMap={colorMap}
                  />
                </div>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
