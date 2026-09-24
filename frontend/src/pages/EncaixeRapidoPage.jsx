import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { getCoresDoModelo, getLotesDaCor, getModelos } from "../api/tecidos";
import { buscarGrupos } from "../api/moldes";
import { gerarEncaixeAutomatico, getPdfEncaixe } from "../api/encaixes";
import { getProximoNumeroPedidoVenda, createPedidoVenda, addItemPedidoVenda } from "../api/pedidos";
import styles from "./EncaixeRapidoPage.module.css";

const TAMANHOS_BASE = ["P", "M", "G", "GG"];
const TAMANHOS_PLUS = ["P", "M", "G", "GG", "G1", "G2", "G3"];
const TAM_KEY = {
  P: "qtd_p", M: "qtd_m", G: "qtd_g", GG: "qtd_gg",
  G1: "qtd_g1", G2: "qtd_g2", G3: "qtd_g3",
};
const QTD_KEYS = ["qtd_p", "qtd_m", "qtd_g", "qtd_gg", "qtd_g1", "qtd_g2", "qtd_g3"];

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const ITEM_VAZIO = {
  searchQuery: "", searchResults: [], selectedGrupo: null,
  tecido_id: "",
  qtd_p: "", qtd_m: "", qtd_g: "", qtd_gg: "",
  qtd_g1: "", qtd_g2: "", qtd_g3: "",
};

const TM_VAZIO = {
  tmModeloId: "", tmCores: [], tmCorId: "", tmLotes: [], tmLoteId: "", tmErr: null,
};

export default function EncaixeRapidoPage() {
  const navigate = useNavigate();

  const [nome, setNome]               = useState("");
  const [modelos, setModelos]         = useState([]);
  const [tecidos, setTecidos]         = useState([]);
  const [tecidoModal, setTecidoModal] = useState(null);
  const [pecas, setPecas]             = useState([]);

  const [itemModal, setItemModal]     = useState(null);
  const [gerando, setGerando]         = useState(false);
  const [resultado, setResultado]     = useState(null);
  const [avisos, setAvisos]           = useState([]);
  const [erroGeral, setErroGeral]     = useState(null);
  const [erroModal, setErroModal]     = useState(null);
  const searchTimer                   = useRef(null);

  useEffect(() => {
    getModelos().then((m) => setModelos(m || [])).catch(() => {});
  }, []);

  // ── Tecido modal handlers ──────────────────────────────────────────────────
  const abrirTecidoModal = () => setTecidoModal({ ...TM_VAZIO });

  const handleTmModelo = async (id) => {
    setTecidoModal((m) => ({ ...m, tmModeloId: id, tmCores: [], tmCorId: "", tmLotes: [], tmLoteId: "" }));
    if (!id) return;
    try {
      const cs = (await getCoresDoModelo(id)) || [];
      setTecidoModal((m) => ({ ...m, tmCores: cs }));
    } catch {}
  };

  const handleTmCor = async (id) => {
    setTecidoModal((m) => ({ ...m, tmCorId: id, tmLotes: [], tmLoteId: "" }));
    if (!id) return;
    try {
      const all = (await getLotesDaCor(id)) || [];
      setTecidoModal((m) => ({
        ...m,
        tmLotes: all.filter((l) => l.status !== "esgotado" && l.status !== "arquivado"),
      }));
    } catch {}
  };

  const handleConfirmarTecido = () => {
    const { tmModeloId, tmCorId, tmLoteId, tmCores, tmLotes } = tecidoModal;
    if (!tmModeloId || !tmCorId || !tmLoteId) {
      setTecidoModal((m) => ({ ...m, tmErr: "Selecione modelo, cor e lote." }));
      return;
    }
    const modelo = modelos.find((m) => m.id === tmModeloId);
    const cor    = tmCores.find((c) => c.id === tmCorId);
    const lote   = tmLotes.find((l) => l.id === tmLoteId);
    setTecidos((ts) => [...ts, {
      _id:            `tm-${Date.now()}-${Math.random()}`,
      modelo_id:      modelo.id,
      modelo_nome:    modelo.nome,
      cor_id:         cor.id,
      cor_nome:       cor.nome_cor,
      cor_largura_cm: cor.largura_util_cm,
      lote_id:        lote.id,
      lote_codigo:    lote.codigo_lote,
      lote_peso_kg:   lote.peso_disponivel_kg,
    }]);
    setTecidoModal(null);
  };

  const removerTecido = (_id) => setTecidos((ts) => ts.filter((t) => t._id !== _id));

  // ── Item modal handlers ────────────────────────────────────────────────────
  const abrirItemModal = () => { setItemModal({ ...ITEM_VAZIO }); setErroModal(null); };

  const handleSearchChange = (query) => {
    setItemModal((m) => ({ ...m, searchQuery: query, selectedGrupo: null, searchResults: [] }));
    clearTimeout(searchTimer.current);
    if (query.trim().length < 2) return;
    searchTimer.current = setTimeout(async () => {
      try {
        const results = await buscarGrupos(query);
        setItemModal((m) => ({ ...m, searchResults: (results || []).slice(0, 10) }));
      } catch {}
    }, 400);
  };

  const selecionarGrupo = (grupo) => {
    setItemModal((m) => ({
      ...m,
      searchQuery:   `${grupo.codigo ? grupo.codigo + " — " : ""}${grupo.nome}`,
      searchResults: [],
      selectedGrupo: grupo,
      qtd_p: "", qtd_m: "", qtd_g: "", qtd_gg: "",
      qtd_g1: "", qtd_g2: "", qtd_g3: "",
    }));
  };

  const handleConfirmarItem = () => {
    if (!itemModal.selectedGrupo)  { setErroModal("Selecione uma referência."); return; }
    if (!itemModal.tecido_id)      { setErroModal("Selecione o tecido desta peça."); return; }
    const qtdTotal = QTD_KEYS.reduce((s, k) => s + (parseInt(itemModal[k]) || 0), 0);
    if (qtdTotal === 0)            { setErroModal("Informe ao menos uma quantidade."); return; }

    const isPlus  = itemModal.selectedGrupo.tem_plus;
    const tamCols = isPlus ? TAMANHOS_PLUS : TAMANHOS_BASE;
    const qtds    = Object.fromEntries(
      tamCols.map((t) => [TAM_KEY[t], parseInt(itemModal[TAM_KEY[t]]) || 0])
    );

    const tecSel = tecidos.find((t) => t._id === itemModal.tecido_id);
    setPecas((ps) => [...ps, {
      _id:          `${Date.now()}-${Math.random()}`,
      grupo_id:     itemModal.selectedGrupo.id,
      grupo_nome:   itemModal.selectedGrupo.nome,
      grupo_codigo: itemModal.selectedGrupo.codigo,
      tem_plus:     isPlus,
      cor:          tecSel?.cor_nome ?? "",
      tecido_id:    itemModal.tecido_id,
      ...qtds,
    }]);
    setItemModal(null);
  };

  const removerPeca = (_id) => setPecas((ps) => ps.filter((p) => p._id !== _id));

  const pecaQtdEntries = (peca) => {
    const cols = peca.tem_plus ? TAMANHOS_PLUS : TAMANHOS_BASE;
    return cols
      .filter((t) => (peca[TAM_KEY[t]] || 0) > 0)
      .map((t) => ({ tam: t, qtd: peca[TAM_KEY[t]] }));
  };

  const corAproveitamento = (v) => {
    if (v == null) return undefined;
    if (v >= 85) return "var(--sc-success-text)";
    if (v >= 70) return "var(--color-primary)";
    return "var(--sc-danger-text)";
  };

  // ── Gerar encaixe ─────────────────────────────────────────────────────────
  const handleGerar = async () => {
    if (tecidos.length === 0)            { setErroGeral("Adicione ao menos um tecido."); return; }
    if (pecas.length === 0)              { setErroGeral("Adicione ao menos uma peça."); return; }
    if (pecas.some((p) => !p.tecido_id)) { setErroGeral("Todas as peças precisam ter um tecido."); return; }
    setGerando(true); setErroGeral(null); setResultado(null); setAvisos([]);

    try {
      await getProximoNumeroPedidoVenda("encaixe_rapido").catch(() => "001");
      const pedido = await createPedidoVenda({
        tipo:                  "encaixe_rapido",
        data_emissao:          new Date().toISOString().split("T")[0],
        prazo_entrega_dias:    0,
        condicoes:             "avista",
        observacoes_internas:  nome || null,
        cliente_razao_social:  nome || "Encaixe Rápido",
      });

      for (const peca of pecas) {
        const tecido = tecidos.find((t) => t._id === peca.tecido_id);
        await addItemPedidoVenda(pedido.id, {
          grupo_id:       peca.grupo_id,
          cor:            peca.cor,
          lote_id:        tecido?.lote_id ?? null,
          qtd_p:          peca.qtd_p  || 0,
          qtd_m:          peca.qtd_m  || 0,
          qtd_g:          peca.qtd_g  || 0,
          qtd_gg:         peca.qtd_gg || 0,
          qtd_g1:         peca.qtd_g1 || 0,
          qtd_g2:         peca.qtd_g2 || 0,
          qtd_g3:         peca.qtd_g3 || 0,
          preco_unitario: 0,
        });
      }

      // gerarAutomatico retorna {encaixes, avisos} — sem .catch: falhas
      // agora sobem para o catch abaixo, que já exibe erroGeral na tela em
      // vez de redirecionar silenciosamente.
      const resposta = await gerarEncaixeAutomatico(pedido.id);
      const encaixe = resposta?.encaixes?.[0] ?? null;

      if (encaixe?.id) {
        setResultado({
          encaixe_id:     encaixe.id,
          pedido_id:      pedido.id,
          aproveitamento: encaixe.desperdicio_pct != null ? 100 - encaixe.desperdicio_pct : null,
          metros:         encaixe.comp_metros != null ? encaixe.comp_metros.toFixed(2) : null,
          peso:           encaixe.peso_kg,
          custo:          encaixe.custo_total,
        });
        setAvisos(resposta?.avisos ?? []);
      } else {
        navigate("/producao/encaixes");
      }
    } catch (e) {
      setErroGeral(e.message || "Erro ao gerar encaixe.");
    } finally {
      setGerando(false);
    }
  };

  const isPlus  = itemModal?.selectedGrupo?.tem_plus;
  const tamForm = isPlus ? TAMANHOS_PLUS : TAMANHOS_BASE;
  const tmCor   = tecidoModal?.tmCores.find((c) => c.id === tecidoModal.tmCorId);

  return (
    <div className="sc-page">
      <div className="sc-page-header"><h1>Encaixe Rápido</h1></div>
      <div className={styles.cols}>
        {/* ── Coluna esquerda ── */}
        <div className={styles.colLeft}>

          <div className="sc-card">
            <p className={styles.sectionLabel}>Configuração do Encaixe</p>
            <label className={styles.field}>
              <span>Nome / identificação (opcional)</span>
              <input
                className={styles.input}
                placeholder="Ex: Legging / Pedido 001"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
              />
            </label>
          </div>

          {/* ── Card Tecidos ── */}
          <div className="sc-card">
            <p className={styles.sectionLabel}>Tecidos do Encaixe</p>

            {tecidos.length === 0 ? (
              <p className={styles.tecidosVazio}>Adicione ao menos um tecido</p>
            ) : (
              <ul className={styles.tecidosList}>
                {tecidos.map((t) => (
                  <li key={t._id} className={styles.tecidoCard}>
                    <div className={styles.tecidoInfo}>
                      <span className={styles.tecidoNome}>{t.modelo_nome} — {t.cor_nome}</span>
                      <span className={styles.tecidoMeta}>
                        Lote {t.lote_codigo} · {t.lote_peso_kg} kg disp. · {t.cor_largura_cm} cm largura
                      </span>
                    </div>
                    <button
                      className={styles.btnRemovePeca}
                      onClick={() => removerTecido(t._id)}
                      title="Remover tecido"
                    >×</button>
                  </li>
                ))}
              </ul>
            )}

            <button
              className={styles.btnAddPeca}
              onClick={abrirTecidoModal}
              style={{ marginTop: tecidos.length ? "0.75rem" : "0.5rem" }}
            >
              + Adicionar Tecido
            </button>
          </div>

          {/* ── Card Peças ── */}
          <div className="sc-card">
            <p className={styles.sectionLabel}>Peças a encaixar</p>

            {pecas.length > 0 && (
              <ul className={styles.pecasList}>
                {pecas.map((peca) => {
                  const tec = tecidos.find((t) => t._id === peca.tecido_id);
                  return (
                    <li key={peca._id} className={styles.pecaCard}>
                      <div className={styles.pecaInfo}>
                        <div>
                          <code className={styles.pecaCod}>{peca.grupo_codigo || "?"}</code>
                          {peca.grupo_nome}
                          {tec && (
                            <span className={styles.pecaTecido}>
                              {" | "}Tecido: {tec.modelo_nome} — {tec.cor_nome}
                            </span>
                          )}
                        </div>
                        <div className={styles.pecaQtds}>
                          {pecaQtdEntries(peca).map(({ tam, qtd }) => (
                            <span key={tam} className={styles.tamBadge}>{tam}×{qtd}</span>
                          ))}
                        </div>
                      </div>
                      <button
                        className={styles.btnRemovePeca}
                        onClick={() => removerPeca(peca._id)}
                        title="Remover peça"
                      >×</button>
                    </li>
                  );
                })}
              </ul>
            )}

            <button className={styles.btnAddPeca} onClick={abrirItemModal}>
              + Adicionar peça
            </button>
          </div>

          <button
            className={styles.btnGerar}
            onClick={handleGerar}
            disabled={gerando}
          >
            {gerando ? "Gerando encaixe…" : "Gerar Encaixe"}
          </button>
        </div>

        {/* ── Coluna direita ── */}
        <div className={styles.colRight}>
          {gerando ? (
            <div className={styles.emptyState}>
              <div className={styles.spinner} />
              <p className={styles.emptyText}>Gerando encaixe…</p>
            </div>
          ) : erroGeral ? (
            <div className={styles.errorState}>
              <p className={styles.errorText}>{erroGeral}</p>
              <button className={styles.btnPrimary} onClick={handleGerar}>
                Tentar novamente
              </button>
            </div>
          ) : !resultado ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>✂</div>
              <p className={styles.emptyText}>
                Configure as peças e clique em<br />
                <strong>Gerar Encaixe</strong>
              </p>
            </div>
          ) : resultado.aproveitamento != null && resultado.aproveitamento <= 0 ? (
            <div className={styles.warningState}>
              {avisos.length > 0 ? (
                avisos.map((aviso, i) => (
                  <p key={i} className={styles.warningText}>{aviso}</p>
                ))
              ) : (
                <p className={styles.warningText}>
                  Nenhuma peça foi posicionada no tecido. Verifique a largura
                  útil do tecido selecionado.
                </p>
              )}
              <button className={styles.btnPrimary} onClick={handleGerar}>
                Tentar novamente
              </button>
            </div>
          ) : (
            <div className={styles.resultCard}>
              <div className={styles.resultHeader}>
                <p className={styles.resultTitle}>Encaixe gerado com sucesso</p>
                <p className={styles.resultSub}>{nome || "Encaixe rápido"}</p>
              </div>

              <div className={styles.resultGrid}>
                <div className={styles.resultMetric}>
                  <span className={styles.resultMetricLabel}>Aproveitamento</span>
                  <span
                    className={styles.resultMetricValue}
                    style={{ color: corAproveitamento(resultado.aproveitamento) }}
                  >
                    {resultado.aproveitamento != null
                      ? `${Number(resultado.aproveitamento).toFixed(1)}%`
                      : "—"}
                  </span>
                </div>
                <div className={styles.resultMetric}>
                  <span className={styles.resultMetricLabel}>Comprimento</span>
                  <span className={styles.resultMetricValue}>
                    {resultado.metros != null ? `${resultado.metros} m` : "—"}
                  </span>
                </div>
                <div className={styles.resultMetric}>
                  <span className={styles.resultMetricLabel}>Peso estimado</span>
                  <span className={styles.resultMetricValue}>
                    {resultado.peso != null
                      ? `${Number(resultado.peso).toFixed(2)} kg`
                      : "—"}
                  </span>
                </div>
                <div className={styles.resultMetric}>
                  <span className={styles.resultMetricLabel}>Custo estimado</span>
                  <span className={styles.resultMetricValue}>
                    {resultado.custo != null ? moeda(resultado.custo) : "—"}
                  </span>
                </div>
              </div>

              <div className={styles.resultActions}>
                <button
                  className={styles.btnPrimary}
                  onClick={() => navigate(`/producao/encaixes/${resultado.pedido_id}`)}
                >
                  Ver encaixe completo →
                </button>
                <button
                  className={styles.btnDownload}
                  onClick={async () => {
                    try {
                      const blob = await getPdfEncaixe(resultado.pedido_id);
                      const url  = URL.createObjectURL(blob);
                      const a    = document.createElement("a");
                      a.href = url;
                      a.download = `corte-encaixe.pdf`;
                      document.body.appendChild(a);
                      a.click();
                      document.body.removeChild(a);
                      URL.revokeObjectURL(url);
                    } catch {}
                  }}
                >
                  ↓ Baixar PDF de Corte
                </button>
              </div>

              {avisos.length > 0 && (
                <div className={styles.avisoBanner}>
                  {avisos.map((aviso, i) => (
                    <p key={i}>{aviso}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ══ MODAL — Adicionar Tecido ══ */}
      {tecidoModal && (
        <div className={styles.overlay} onClick={() => setTecidoModal(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Adicionar Tecido</h2>
              <button className={styles.btnClose} onClick={() => setTecidoModal(null)}>×</button>
            </div>

            <div className={styles.modalBody}>
              <label className={styles.field}>
                <span>Modelo</span>
                <select
                  className={styles.input}
                  value={tecidoModal.tmModeloId}
                  onChange={(e) => handleTmModelo(e.target.value)}
                >
                  <option value="">— Selecionar modelo —</option>
                  {modelos.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.nome}{m.tipo ? ` (${m.tipo})` : ""}
                    </option>
                  ))}
                </select>
              </label>

              <label className={styles.field}>
                <span>Cor</span>
                <select
                  className={styles.input}
                  value={tecidoModal.tmCorId}
                  onChange={(e) => handleTmCor(e.target.value)}
                  disabled={!tecidoModal.tmModeloId || tecidoModal.tmCores.length === 0}
                >
                  <option value="">— Selecionar cor —</option>
                  {tecidoModal.tmCores.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome_cor} — {c.largura_util_cm} cm
                    </option>
                  ))}
                </select>
              </label>

              <label className={styles.field}>
                <span>Lote</span>
                <select
                  className={styles.input}
                  value={tecidoModal.tmLoteId}
                  onChange={(e) => setTecidoModal((m) => ({ ...m, tmLoteId: e.target.value }))}
                  disabled={!tecidoModal.tmCorId || tecidoModal.tmLotes.length === 0}
                >
                  <option value="">— Selecionar lote —</option>
                  {tecidoModal.tmLotes.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.codigo_lote} — {l.peso_disponivel_kg} kg · {tmCor?.largura_util_cm} cm
                    </option>
                  ))}
                </select>
              </label>

              {tecidoModal.tmErr && <p className={styles.erroModal}>{tecidoModal.tmErr}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setTecidoModal(null)}>
                Cancelar
              </button>
              <button
                className={styles.btnPrimary}
                onClick={handleConfirmarTecido}
                disabled={!tecidoModal.tmLoteId}
              >
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Adicionar peça ══ */}
      {itemModal && (
        <div className={styles.overlay} onClick={() => { setItemModal(null); setErroModal(null); }}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Adicionar peça</h2>
              <button className={styles.btnClose}
                onClick={() => { setItemModal(null); setErroModal(null); }}>×</button>
            </div>

            <div className={styles.modalBody}>
              <div className={styles.searchWrap}>
                <label className={styles.field}>
                  <span>Referência — código ou nome</span>
                  <input
                    className={styles.input}
                    placeholder="Digite para buscar…"
                    value={itemModal.searchQuery}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    autoComplete="off"
                    autoFocus
                  />
                </label>
                {itemModal.searchResults.length > 0 && (
                  <ul className={styles.autocomplete}>
                    {itemModal.searchResults.map((g) => (
                      <li key={g.id} className={styles.acItem} onClick={() => selecionarGrupo(g)}>
                        <code className={styles.acCod}>{g.codigo || "?"}</code>
                        <span className={styles.acNome}>{g.nome}</span>
                        {g.tem_plus && <span className={styles.acPlus}>Plus</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {itemModal.selectedGrupo && (
                <>
                  <label className={styles.field}>
                    <span>Tecido desta peça</span>
                    {tecidos.length === 0 ? (
                      <>
                        <select className={styles.input} disabled>
                          <option>Nenhum tecido disponível</option>
                        </select>
                        <span className={styles.tecidoAviso}>Adicione um tecido primeiro</span>
                      </>
                    ) : (
                      <select
                        className={styles.input}
                        value={itemModal.tecido_id}
                        onChange={(e) => setItemModal((m) => ({ ...m, tecido_id: e.target.value }))}
                      >
                        <option value="">— Selecionar tecido —</option>
                        {tecidos.map((t) => (
                          <option key={t._id} value={t._id}>
                            {t.modelo_nome} — {t.cor_nome} ({t.lote_codigo})
                          </option>
                        ))}
                      </select>
                    )}
                  </label>

                  <div className={styles.tamSection}>
                    <p className={styles.tamLabel}>Quantidades por tamanho</p>
                    <div className={styles.tamGrid}>
                      {tamForm.map((tam) => (
                        <label key={tam} className={styles.tamItem}>
                          <span>{tam}</span>
                          <input
                            type="number"
                            min="0"
                            className={styles.tamInput}
                            value={itemModal[TAM_KEY[tam]]}
                            onChange={(e) =>
                              setItemModal((m) => ({ ...m, [TAM_KEY[tam]]: e.target.value }))
                            }
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {erroModal && <p className={styles.erroModal}>{erroModal}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary}
                onClick={() => { setItemModal(null); setErroModal(null); }}>
                Cancelar
              </button>
              <button
                className={styles.btnPrimary}
                onClick={handleConfirmarItem}
                disabled={!itemModal.selectedGrupo}
              >
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
