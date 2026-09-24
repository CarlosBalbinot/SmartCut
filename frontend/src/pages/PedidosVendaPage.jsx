import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { MoreHorizontal } from "lucide-react";
import { getTabelasPreco } from "../api/tabelasPreco";
import {
  getPedidosVenda, createPedidoVenda, getPedidoVenda, updateStatusPedidoVenda,
  getProximoNumeroPedidoVenda, getPdfPedidoVenda,
} from "../api/pedidos";
import { getVendedores } from "../api/vendedores";
import { listar as listarCondicoesPagamento } from "../api/condicoesPagamento";
import { listar as listarTes } from "../api/tes";
import ClienteInput from "../components/ClienteInput/ClienteInput";
import { useAuth } from "../auth/useAuth";
import styles from "./PedidosVendaPage.module.css";

const TAMANHOS_BASE = ["P", "M", "G", "GG"];
const TAMANHOS_PLUS = ["P", "M", "G", "GG", "G1", "G2", "G3"];
const TAM_KEY = { P: "qtd_p", M: "qtd_m", G: "qtd_g", GG: "qtd_gg", G1: "qtd_g1", G2: "qtd_g2", G3: "qtd_g3" };

async function downloadBlob(promiseFn, filename) {
  const blob = await promiseFn();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

const STATUS_LABELS = {
  Aberto:    "Aberto",
  Fechado:   "Fechado",
  Cancelado: "Cancelado",
};

const STATUS_CLS = {
  Aberto:    "stAberto",
  Fechado:   "stFechado",
  Cancelado: "stCancelado",
};

const STATUS_FILTRO_OPCOES = [
  { value: "",          label: "Todos" },
  { value: "Aberto",    label: "Aberto" },
  { value: "Fechado",   label: "Fechado" },
  { value: "Cancelado", label: "Cancelado" },
];

const CONDICOES_LABEL = { avista: "À Vista", aprazo: "A Prazo" };
const TIPO_LABEL = { intervalo: "Intervalo de Dias", fixo: "Dias Específicos" };

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const hojeISO = () => new Date().toISOString().split("T")[0];

// Nome longo (> limite) vira só o primeiro nome: "JOSE ROQUE GERHARDT" → "JOSE".
// O nome completo fica no title da célula.
const nomeCurto = (nome, limite = 16) => {
  if (!nome) return "";
  const n = nome.trim();
  return n.length > limite ? n.split(/\s+/)[0] : n;
};

const dataBR = (iso) => (iso ? new Date(iso).toLocaleDateString("pt-BR") : "");

// cliente: { id, codigo, razao_social, cnpj, cidade, uf } do ClienteInput —
// o backend copia o resto do cadastro para o pedido (cliente_*).
const MODAL_VAZIO = {
  numero: "", data_emissao: hojeISO(), prazo_entrega_dias: "30",
  condicoes: "avista", condicao_pagamento_id: "", vendedor_id: "", tabela_preco_id: "",
  cliente: null, tes_id: "", indicador_presenca: "1",
};

// Mesmas opções da aba Dados do detalhe do pedido.
const INDICADOR_PRESENCA_OPCOES = [
  { value: "0", label: "0 – Não se aplica" },
  { value: "1", label: "1 – Operação presencial" },
  { value: "2", label: "2 – Operação não presencial, pela Internet" },
  { value: "3", label: "3 – Operação não presencial, Teleatendimento" },
  { value: "4", label: "4 – NFC-e em operação com entrega a domicílio" },
  { value: "5", label: "5 – Operação presencial, fora do estabelecimento" },
  { value: "9", label: "9 – Operação não presencial, outros" },
];

export default function PedidosVendaPage() {
  const { hasPermission } = useAuth();
  const [pedidos, setPedidos]                     = useState([]);
  const [vendedores, setVendedores]               = useState([]);
  const [tabelas, setTabelas]                     = useState([]);
  const [condicoesPagamento, setCondicoesPagamento] = useState([]);
  const [tesList, setTesList]                     = useState([]);
  const [modal, setModal]                         = useState(null);
  const [saving, setSaving]                       = useState(false);
  const [erro, setErro]                           = useState(null);
  const [menuAberto, setMenuAberto]               = useState(null);
  const [menuPos, setMenuPos]                     = useState({ top: 0, left: 0 });
  const [modalView, setModalView]                 = useState(null);
  const [cancelandoPedido, setCancelandoPedido]   = useState(null);
  const [cancelando, setCancelando]               = useState(false);
  const [erroCancelar, setErroCancelar]           = useState(null);
  const [busca, setBusca]                         = useState("");
  const [statusFiltro, setStatusFiltro]           = useState("");
  const [modalCondicao, setModalCondicao]         = useState(false);
  const [buscaCondicao, setBuscaCondicao]         = useState("");
  const navigate                                  = useNavigate();
  const overlayMouseDownNode                      = useRef(null);
  const condicaoOverlayMouseDownNode              = useRef(null);

  // Lista sempre buscada do backend ao montar a tela (inclusive ao voltar do
  // detalhe) — sem cache entre navegações. Nomes de vendedor/tabela/condição
  // já vêm resolvidos na resposta.
  const carregarPedidos = () =>
    getPedidosVenda("venda").then((p) => setPedidos(p || [])).catch(() => {});

  useEffect(() => { carregarPedidos(); }, []);

  // Listas só do modal Novo Pedido (selects) — separadas da lista de pedidos
  // para que uma falha aqui não deixe a tabela vazia.
  useEffect(() => {
    Promise.all([
      getVendedores(),
      getTabelasPreco(),
      listarCondicoesPagamento({ situacao: "Ativa" }).catch(() => []),
      listarTes().catch(() => []),
    ]).then(([v, t, c, tes]) => {
      setVendedores((v || []).filter((x) => x.ativo !== false));
      // Campo do backend é "ativa" (TabelaPrecoOut).
      setTabelas((t || []).filter((x) => x.ativa));
      setCondicoesPagamento(c || []);
      setTesList((tes || []).filter((x) => x.tipo === "Saída" && x.situacao === "Ativo"));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!menuAberto) return;
    const close = () => setMenuAberto(null);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [menuAberto]);

  const abrirModal = async () => {
    const numero = await getProximoNumeroPedidoVenda("venda").catch(() => "");
    setModal({ ...MODAL_VAZIO, data_emissao: hojeISO(), numero: String(numero).padStart(6, "0") });
    setErro(null);
  };

  const fecharModal = () => { setModal(null); setErro(null); setModalCondicao(false); };

  const set = (key) => (e) => setModal((m) => ({ ...m, [key]: e.target.value }));

  const condicaoPagamentoSel = modal?.condicao_pagamento_id
    ? condicoesPagamento.find((c) => String(c.id) === String(modal.condicao_pagamento_id))
    : null;

  const abrirBuscaCondicao = () => {
    setBuscaCondicao("");
    setModalCondicao(true);
  };

  const fecharBuscaCondicao = () => setModalCondicao(false);

  const selecionarCondicao = (condicao) => {
    setModal((m) => ({ ...m, condicao_pagamento_id: condicao.id }));
    setModalCondicao(false);
  };

  const limparCondicao = (e) => {
    e.stopPropagation();
    setModal((m) => ({ ...m, condicao_pagamento_id: "" }));
  };

  const condicoesFiltradas = condicoesPagamento.filter((c) => {
    if (!buscaCondicao.trim()) return true;
    const q = buscaCondicao.trim().toLowerCase();
    return `${c.codigo || ""} ${c.descricao || ""}`.toLowerCase().includes(q);
  });

  // ── Menu de ações da linha (···) ──────────────────────────────────────────────
  const handleImprimirResumo = async (p) => {
    try {
      await downloadBlob(() => getPdfPedidoVenda(p.id), `pedido-${p.numero}.pdf`);
    } catch (e) {
      alert(e.message || "Erro ao gerar PDF.");
    }
  };

  // ── Modal de visualização (somente leitura) ───────────────────────────────────
  const abrirVisualizacao = async (p) => {
    setModalView({ numero: p.numero, loading: true });
    try {
      const full = await getPedidoVenda(p.id);
      // Nomes resolvidos vêm só na listagem — reaproveita os da linha.
      setModalView({
        ...full,
        vendedor_nome: p.vendedor_nome,
        tabela_preco_nome: p.tabela_preco_nome,
        condicao_pagamento_descricao: p.condicao_pagamento_descricao,
      });
    } catch {
      setModalView(null);
    }
  };

  const fecharVisualizacao = () => setModalView(null);

  // ── Cancelar pedido (soft-delete: muda status para Cancelado, não remove) ────
  const fecharCancelar = () => { setCancelandoPedido(null); setErroCancelar(null); };

  const handleConfirmarCancelamento = async () => {
    if (!cancelandoPedido) return;
    setCancelando(true);
    setErroCancelar(null);
    try {
      const atualizado = await updateStatusPedidoVenda(cancelandoPedido.id, "Cancelado");
      // Mescla: a resposta do status não traz os nomes resolvidos da listagem.
      setPedidos((ps) => ps.map((p) => (p.id === atualizado.id ? { ...p, ...atualizado } : p)));
      setCancelandoPedido(null);
    } catch (e) {
      setErroCancelar(e.message || "Erro ao cancelar pedido.");
    }
    setCancelando(false);
  };

  const pedidosFiltrados = pedidos.filter((p) => {
    if (statusFiltro && p.status !== statusFiltro) return false;
    if (busca.trim()) {
      const q = busca.trim().toLowerCase();
      const alvo = `${p.numero || ""} ${p.cliente_razao_social || ""} ${p.vendedor_nome || ""}`.toLowerCase();
      if (!alvo.includes(q)) return false;
    }
    return true;
  });

  const handleSalvar = async () => {
    if (!modal.cliente?.id) { setErro("Selecione um cliente do cadastro."); return; }
    if (modal.data_emissao < hojeISO()) { setErro("Data de emissão não pode ser anterior à data atual."); return; }
    setSaving(true); setErro(null);
    try {
      const criado = await createPedidoVenda({
        numero:               modal.numero,
        tipo:                 "venda",
        data_emissao:         modal.data_emissao,
        prazo_entrega_dias:   Number(modal.prazo_entrega_dias) || 0,
        condicoes:            modal.condicoes,
        condicao_pagamento_id: modal.condicao_pagamento_id ? Number(modal.condicao_pagamento_id) : null,
        vendedor_id:          modal.vendedor_id     || null,
        tabela_preco_id:      modal.tabela_preco_id || null,
        tes_id:               modal.tes_id ? Number(modal.tes_id) : null,
        indicador_presenca:   modal.indicador_presenca,
        // Só o vínculo: dados do cliente vêm do cadastro no backend.
        cliente_id:           modal.cliente.id,
      });
      navigate(`/vendas/pedidos/${criado.id}`);
    } catch (e) {
      setErro(e.message);
      setSaving(false);
    }
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Pedidos de Venda</h1>
        {hasPermission("pedidos_criar", "ver") && (
          <button className={styles.btnNovo} onClick={abrirModal}>+ Novo Pedido</button>
        )}
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <input
            className={styles.busca}
            placeholder="Buscar por cliente, número ou vendedor…"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </div>
        <select
          className={styles.statusFiltro}
          value={statusFiltro}
          onChange={(e) => setStatusFiltro(e.target.value)}
        >
          {STATUS_FILTRO_OPCOES.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      <div className={`sc-card ${styles.tableCard}`}>
        <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Nº</th>
              <th>Data</th>
              <th>Cliente</th>
              <th>Vendedor</th>
              <th>Tabela Preço</th>
              <th>Condição</th>
              <th>Total</th>
              <th>Comissão</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pedidosFiltrados.map((p) => (
              <tr key={p.id} onDoubleClick={() => abrirVisualizacao(p)}>
                <td title={p.numero}><code className={styles.num}>{p.numero}</code></td>
                <td title={dataBR(p.data_emissao)}>{dataBR(p.data_emissao) || "—"}</td>
                <td title={p.cliente_razao_social || ""}>{p.cliente_razao_social || "—"}</td>
                <td title={p.vendedor_nome || ""}>{nomeCurto(p.vendedor_nome) || "—"}</td>
                <td title={p.tabela_preco_nome || ""}>{p.tabela_preco_nome || "—"}</td>
                <td title={p.condicao_pagamento_descricao || ""}>{p.condicao_pagamento_descricao || "—"}</td>
                <td title={moeda(p.total)}>{moeda(p.total)}</td>
                <td title={moeda(p.comissao_valor)}>{moeda(p.comissao_valor)}</td>
                <td>
                  <span className={`${styles.badge} ${styles[STATUS_CLS[p.status] || "stAberto"]}`}>
                    {STATUS_LABELS[p.status] || p.status || "—"}
                  </span>
                </td>
                <td onDoubleClick={(e) => e.stopPropagation()}>
                  <div className={styles.menuWrap}>
                    <button
                      className={styles.btnMenu}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (menuAberto !== p.id) {
                          const rect = e.currentTarget.getBoundingClientRect();
                          setMenuPos({ top: rect.bottom + 4, left: rect.right - 160 });
                        }
                        setMenuAberto(menuAberto === p.id ? null : p.id);
                      }}
                      title="Mais ações"
                    >
                      <MoreHorizontal size={16} />
                    </button>
                    {menuAberto === p.id && (
                      <div className={styles.dropdown} style={{ top: menuPos.top, left: menuPos.left }} onClick={(e) => e.stopPropagation()}>
                        {hasPermission("pedidos_editar", "ver") && (
                          <button
                            className={styles.dropItem}
                            onClick={() => { setMenuAberto(null); navigate(`/vendas/pedidos/${p.id}`); }}
                          >
                            Editar
                          </button>
                        )}
                        <button
                          className={styles.dropItem}
                          onClick={() => { setMenuAberto(null); handleImprimirResumo(p); }}
                        >
                          Imprimir Resumo
                        </button>
                        {hasPermission("pedidos_excluir", "ver") && p.status === "Aberto" && (
                          <button
                            className={`${styles.dropItem} ${styles.dropItemDanger}`}
                            onClick={() => { setMenuAberto(null); setCancelandoPedido(p); }}
                          >
                            Cancelar Pedido
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {pedidosFiltrados.length === 0 && (
              <tr>
                <td colSpan={10} className={styles.empty}>
                  {pedidos.length === 0 ? "Nenhum pedido de venda cadastrado." : "Nenhum pedido encontrado para o filtro atual."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
      </div>

      {/* ══ MODAL — Visualização (somente leitura) ══ */}
      {modalView && (
        <div className={styles.overlay} onClick={fecharVisualizacao}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Pedido Nº {modalView.numero}</h2>
              <button className={styles.btnClose} onClick={fecharVisualizacao}>×</button>
            </div>

            {modalView.loading ? (
              <div className={styles.modalScroll}>
                <p className={styles.empty}>Carregando…</p>
              </div>
            ) : (
              <>
                <div className={styles.modalScroll}>
                  <p className={styles.secLabel}>Dados do pedido</p>
                  <div className={styles.viewGrid}>
                    <span><strong>Cliente:</strong> {modalView.cliente_razao_social || "—"}</span>
                    <span>
                      <strong>Data:</strong>{" "}
                      {modalView.data_emissao ? new Date(modalView.data_emissao).toLocaleDateString("pt-BR") : "—"}
                    </span>
                    <span><strong>Vendedor:</strong> {modalView.vendedor_nome || "—"}</span>
                    <span>
                      <strong>Tabela de Preço:</strong> {modalView.tabela_preco_nome || "—"}
                      {modalView.condicoes && ` (${CONDICOES_LABEL[modalView.condicoes] || modalView.condicoes})`}
                    </span>
                    <span><strong>Condição:</strong> {modalView.condicao_pagamento_descricao || "—"}</span>
                  </div>

                  <p className={styles.secLabel} style={{ marginTop: "1.25rem" }}>Itens</p>
                  {(() => {
                    const itensView = modalView.itens || [];
                    if (itensView.length === 0) {
                      return <p className={styles.empty}>Nenhum item.</p>;
                    }
                    const temPlusView = itensView.some(
                      (i) => (i.qtd_g1 || 0) + (i.qtd_g2 || 0) + (i.qtd_g3 || 0) > 0
                    );
                    const tamColsView = temPlusView ? TAMANHOS_PLUS : TAMANHOS_BASE;
                    const gruposOrdemView = [];
                    const grupoMapView = {};
                    itensView.forEach((item) => {
                      if (!grupoMapView[item.grupo_id]) {
                        grupoMapView[item.grupo_id] = [];
                        gruposOrdemView.push(item.grupo_id);
                      }
                      grupoMapView[item.grupo_id].push(item);
                    });
                    const th = { textAlign: "left", padding: "0.5rem 0.6rem", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--sc-text-secondary)", borderBottom: "1px solid var(--sc-border)" };
                    const td = { padding: "0.5rem 0.6rem", color: "var(--sc-text-primary)" };
                    return (
                      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                        <thead>
                          <tr>
                            <th style={th}>REF</th>
                            <th style={th}>Nome</th>
                            <th style={th}>Cor</th>
                            {tamColsView.map((t) => (
                              <th key={t} style={{ ...th, textAlign: "center" }}>{t}</th>
                            ))}
                            <th style={{ ...th, textAlign: "right" }}>P. Unit.</th>
                            <th style={{ ...th, textAlign: "right" }}>Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {gruposOrdemView.map((gid) => {
                            const grupo_itens = grupoMapView[gid];
                            return grupo_itens.map((item, idx) => (
                              <tr key={item.id} style={{ borderBottom: "1px solid var(--sc-border)" }}>
                                {idx === 0 && (
                                  <>
                                    <td rowSpan={grupo_itens.length} style={td}>
                                      <code>{item.grupo_codigo || "—"}</code>
                                    </td>
                                    <td rowSpan={grupo_itens.length} style={td}>{item.grupo_nome || "—"}</td>
                                  </>
                                )}
                                <td style={td}>{item.cor || "—"}</td>
                                {tamColsView.map((t) => (
                                  <td key={t} style={{ ...td, textAlign: "center" }}>
                                    {(item[TAM_KEY[t]] || 0) > 0 ? item[TAM_KEY[t]] : ""}
                                  </td>
                                ))}
                                <td style={{ ...td, textAlign: "right" }}>{moeda(item.preco_unitario)}</td>
                                <td style={{ ...td, textAlign: "right" }}>{moeda(item.preco_total)}</td>
                              </tr>
                            ));
                          })}
                        </tbody>
                      </table>
                    );
                  })()}

                  <div className={styles.viewFooter}>
                    <div className={styles.totaisLinha}>
                      <span>Comissão</span>
                      <span>{moeda(modalView.comissao_valor)}</span>
                    </div>
                    <div className={`${styles.totaisLinha} ${styles.totaisTotal}`}>
                      <span>Total Geral</span>
                      <strong>{moeda(modalView.total_pedido)}</strong>
                    </div>
                    <div className={styles.totaisLinha}>
                      <span>Status</span>
                      <span className={`${styles.badge} ${styles[STATUS_CLS[modalView.status] || "stAberto"]}`}>
                        {STATUS_LABELS[modalView.status] || modalView.status || "—"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className={styles.modalActions}>
                  <button className={styles.btnSecondary} onClick={fecharVisualizacao}>Fechar</button>
                  <button className={styles.btnPrimary} onClick={() => handleImprimirResumo(modalView)}>
                    Imprimir PDF
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ══ MODAL — Confirmar cancelamento ══ */}
      {cancelandoPedido && (
        <div className={styles.overlay} onClick={() => !cancelando && fecharCancelar()}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle} style={{ marginBottom: "0.75rem" }}>
              Cancelar Pedido
            </h2>
            <p className={styles.confirmText}>
              Tem certeza que deseja cancelar o Pedido Nº <strong>{cancelandoPedido.numero}</strong>{" "}
              de <strong>{cancelandoPedido.cliente_razao_social || "—"}</strong>? Esta ação não pode
              ser desfeita.
            </p>
            {erroCancelar && <p className={styles.erro}>{erroCancelar}</p>}
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharCancelar} disabled={cancelando}>
                Voltar
              </button>
              <button className={styles.btnDanger} onClick={handleConfirmarCancelamento} disabled={cancelando}>
                {cancelando ? "Cancelando…" : "Cancelar Pedido"}
              </button>
            </div>
          </div>
        </div>
      )}

      {modal && (
        <div
          className={styles.overlay}
          onMouseDown={(e) => { overlayMouseDownNode.current = e.target; }}
          onClick={(e) => {
            if (e.target === e.currentTarget && overlayMouseDownNode.current === e.currentTarget) {
              fecharModal();
            }
          }}
        >
          <div className={`${styles.modal} ${styles.modalNovoPedido}`} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>
                Novo Pedido de Venda
                {modal.numero && <span className={styles.modalTitleNumero}>Nº {modal.numero}</span>}
              </h2>
              <button className={styles.btnClose} onClick={fecharModal}>×</button>
            </div>

            <div className={styles.modalScroll}>
              {/* Mesma ordem da aba Dados do detalhe do pedido. */}
              <div className={styles.gridPedido}>
                <div className={`${styles.field} ${styles.colSpan3}`}>
                  <span>Cliente *</span>
                  <ClienteInput
                    cliente={modal.cliente}
                    onChange={(c) => { setErro(null); setModal((m) => ({ ...m, cliente: c })); }}
                  />
                </div>

                <label className={`${styles.field} ${styles.colSpan2}`}>
                  <span>Condição de Pagamento</span>
                  <div className={styles.condicaoField} onClick={abrirBuscaCondicao}>
                    <span className={`${styles.condicaoFieldText} ${!condicaoPagamentoSel ? styles.condicaoFieldPlaceholder : ""}`}>
                      {condicaoPagamentoSel ? condicaoPagamentoSel.descricao : "Selecionar condição..."}
                    </span>
                    {condicaoPagamentoSel && (
                      <button type="button" className={styles.condicaoFieldClear} onClick={limparCondicao} title="Limpar seleção">
                        ×
                      </button>
                    )}
                    <svg className={styles.condicaoFieldIcon} width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="11" cy="11" r="7" />
                      <line x1="21" y1="21" x2="16.3" y2="16.3" />
                    </svg>
                  </div>
                </label>
                <label className={styles.field}>
                  <span>Prazo de entrega (dias)</span>
                  <input type="number" min="0" className={styles.input}
                    value={modal.prazo_entrega_dias} onChange={set("prazo_entrega_dias")} />
                </label>

                <label className={styles.field}>
                  <span>Vendedor</span>
                  <select
                    className={styles.input}
                    value={modal.vendedor_id}
                    onChange={(e) => {
                      const vid = e.target.value;
                      setModal((m) => ({ ...m, vendedor_id: vid }));
                    }}
                  >
                    <option value="">Sem vendedor</option>
                    {vendedores.map((v) => <option key={v.id} value={v.id}>{v.nome}</option>)}
                  </select>
                </label>
                <label className={styles.field}>
                  <span>Tabela de preço</span>
                  <select className={styles.input} value={modal.tabela_preco_id} onChange={set("tabela_preco_id")}>
                    <option value="">— Selecionar —</option>
                    {tabelas.map((t) => (
                      <option key={t.id} value={t.id}>{t.nome}</option>
                    ))}
                  </select>
                </label>
                <label className={styles.field}>
                  <span>Preço da tabela</span>
                  <select className={styles.input} value={modal.condicoes} onChange={set("condicoes")}>
                    <option value="avista">À Vista</option>
                    <option value="aprazo">A Prazo</option>
                  </select>
                </label>

                <label className={styles.field}>
                  <span>TES padrão</span>
                  <select className={styles.input} value={modal.tes_id} onChange={set("tes_id")}>
                    <option value="">Nenhum</option>
                    {tesList.map((t) => (
                      <option key={t.id} value={t.id}>{t.codigo} — {t.descricao}</option>
                    ))}
                  </select>
                </label>
                <label className={styles.field}>
                  <span>Indicador de presença</span>
                  <select className={styles.input} value={modal.indicador_presenca} onChange={set("indicador_presenca")}>
                    {INDICADOR_PRESENCA_OPCOES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </label>
                {/* Data de emissão ocupa a 3ª coluna livre da última linha. */}
                <label className={styles.field}>
                  <span>Data de emissão</span>
                  <input type="date" className={styles.input} value={modal.data_emissao}
                    min={hojeISO()} onChange={set("data_emissao")} />
                </label>
              </div>
            </div>

            {erro && <p className={styles.erro}>{erro}</p>}

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharModal}>Cancelar</button>
              <button
                className={styles.btnPrimary}
                onClick={handleSalvar}
                disabled={saving || !modal.cliente?.id}
                title={modal.cliente?.id ? "" : "Selecione um cliente do cadastro"}
              >
                {saving ? "Criando…" : "Criar Pedido"}
              </button>
            </div>
          </div>
        </div>
      )}

      {modalCondicao && (
        <div
          className={styles.overlay}
          onMouseDown={(e) => { condicaoOverlayMouseDownNode.current = e.target; }}
          onClick={(e) => {
            if (e.target === e.currentTarget && condicaoOverlayMouseDownNode.current === e.currentTarget) {
              fecharBuscaCondicao();
            }
          }}
        >
          <div className={styles.modalCondicao} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Selecionar Condição de Pagamento</h2>
              <button className={styles.btnClose} onClick={fecharBuscaCondicao}>×</button>
            </div>

            <div className={styles.modalScroll}>
              <input
                className={styles.input}
                style={{ width: "100%", marginBottom: "1rem" }}
                placeholder="Buscar por descrição..."
                value={buscaCondicao}
                onChange={(e) => setBuscaCondicao(e.target.value)}
                autoFocus
              />

              <div className={styles.condicaoLista}>
                {condicoesFiltradas.length === 0 ? (
                  <p className={styles.empty}>Nenhuma condição encontrada.</p>
                ) : condicoesFiltradas.map((c) => {
                  const selecionada = String(modal?.condicao_pagamento_id) === String(c.id);
                  return (
                    <div
                      key={c.id}
                      className={`${styles.condicaoItem} ${selecionada ? styles.condicaoItemSelecionada : ""}`}
                      onClick={() => selecionarCondicao(c)}
                    >
                      <div className={styles.condicaoItemDescricao}>{c.descricao}</div>
                      <div className={styles.condicaoItemDetalhe}>
                        {c.codigo} · {TIPO_LABEL[c.tipo] || c.tipo} · {c.condicao}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharBuscaCondicao}>Cancelar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
