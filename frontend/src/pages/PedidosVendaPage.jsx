import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { MoreHorizontal } from "lucide-react";
import { tabelasPrecoApi } from "../services/api";
import {
  getPedidosVenda, createPedidoVenda, getPedidoVenda, updateStatusPedidoVenda,
  getProximoNumeroPedidoVenda, getPdfPedidoVenda,
} from "../api/pedidos";
import { getVendedores } from "../api/vendedores";
import { getClientes, getClienteByCnpj } from "../api/clientes";
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

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const hojeISO = () => new Date().toISOString().split("T")[0];

const MODAL_VAZIO = {
  numero: "", data_emissao: hojeISO(), prazo_entrega_dias: "30",
  condicoes: "avista", vendedor_id: "", tabela_preco_id: "",
  cliente_razao_social: "", cliente_cnpj: "", cliente_ie: "",
  cliente_endereco: "", cliente_cidade: "", cliente_cep: "",
  cliente_telefone: "", cliente_email: "", representante: "",
};

const CAMPOS_CLIENTE = [
  { k: "cliente_razao_social", l: "Razão Social *"    },
  { k: "cliente_cnpj",         l: "CNPJ"              },
  { k: "cliente_ie",           l: "Inscrição Estadual" },
  { k: "cliente_endereco",     l: "Endereço"           },
  { k: "cliente_cidade",       l: "Cidade"             },
  { k: "cliente_cep",          l: "CEP"                },
  { k: "cliente_telefone",     l: "Telefone"           },
  { k: "cliente_email",        l: "E-mail"             },
];

export default function PedidosVendaPage() {
  const { hasPermission } = useAuth();
  const [pedidos, setPedidos]                     = useState([]);
  const [vendedores, setVendedores]               = useState([]);
  const [tabelas, setTabelas]                     = useState([]);
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
  const [clienteBusca, setClienteBusca]           = useState(null);
  const [modalCliente, setModalCliente]           = useState(false);
  const [buscaCliente, setBuscaCliente]           = useState("");
  const [resultadosCliente, setResultadosCliente] = useState([]);
  const [carregandoClientes, setCarregandoClientes] = useState(false);
  const navigate                                  = useNavigate();
  const overlayMouseDownNode                      = useRef(null);
  const buscaOverlayMouseDownNode                 = useRef(null);

  useEffect(() => {
    Promise.all([
      getPedidosVenda("venda"),
      getVendedores(),
      tabelasPrecoApi.list(),
    ]).then(([p, v, t]) => {
      setPedidos(p || []);
      setVendedores((v || []).filter((x) => x.ativo !== false));
      setTabelas((t || []).filter((x) => x.ativo));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!menuAberto) return;
    const close = () => setMenuAberto(null);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [menuAberto]);

  useEffect(() => {
    if (!modalCliente) return;
    setCarregandoClientes(true);
    const t = setTimeout(() => {
      getClientes(buscaCliente)
        .then((lista) => setResultadosCliente(lista || []))
        .catch(() => setResultadosCliente([]))
        .finally(() => setCarregandoClientes(false));
    }, 300);
    return () => clearTimeout(t);
  }, [modalCliente, buscaCliente]);

  const abrirModal = async () => {
    const numero = await getProximoNumeroPedidoVenda("venda").catch(() => "");
    setModal({ ...MODAL_VAZIO, data_emissao: hojeISO(), numero: String(numero).padStart(6, "0") });
    setErro(null);
    setClienteBusca(null);
    setModalCliente(false);
  };

  const fecharModal = () => { setModal(null); setErro(null); setClienteBusca(null); setModalCliente(false); };

  const set = (key) => (e) => setModal((m) => ({ ...m, [key]: e.target.value }));

  const abrirBuscaCliente = () => {
    setBuscaCliente("");
    setResultadosCliente([]);
    setModalCliente(true);
  };

  const fecharBuscaCliente = () => setModalCliente(false);

  const selecionarCliente = (cliente) => {
    setModal((m) => ({
      ...m,
      cliente_razao_social: cliente.razao_social || "",
      cliente_cnpj:         cliente.cnpj || cliente.cpf || "",
      cliente_ie:           cliente.ie || "",
      cliente_endereco:     cliente.endereco || "",
      cliente_cidade:       cliente.cidade || "",
      cliente_cep:          cliente.cep || "",
      cliente_telefone:     cliente.telefone || "",
      cliente_email:        cliente.email || "",
    }));
    setClienteBusca("selecionado");
    setModalCliente(false);
  };

  const buscarClientePorCnpj = async () => {
    const digits = (modal.cliente_cnpj || "").replace(/\D/g, "");
    if (digits.length !== 11 && digits.length !== 14) return;

    setClienteBusca("buscando");
    try {
      const cliente = await getClienteByCnpj(digits);
      if (cliente) {
        setModal((m) => ({
          ...m,
          cliente_razao_social: cliente.razao_social || m.cliente_razao_social,
          cliente_ie:           cliente.ie            || m.cliente_ie,
          cliente_endereco:     cliente.endereco       || m.cliente_endereco,
          cliente_cidade:       cliente.cidade         || m.cliente_cidade,
          cliente_cep:          cliente.cep            || m.cliente_cep,
          cliente_telefone:     cliente.telefone       || m.cliente_telefone,
          cliente_email:        cliente.email          || m.cliente_email,
        }));
        setClienteBusca("encontrado");
      } else {
        setClienteBusca("nao_cadastrado");
      }
    } catch {
      setClienteBusca(null);
    }
  };

  const tabelaSel = modal?.tabela_preco_id
    ? tabelas.find((t) => t.id === modal.tabela_preco_id)
    : null;

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
      setModalView(full);
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
      setPedidos((ps) => ps.map((p) => (p.id === atualizado.id ? atualizado : p)));
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
      const alvo = `${p.numero || ""} ${p.cliente_razao_social || ""}`.toLowerCase();
      if (!alvo.includes(q)) return false;
    }
    return true;
  });

  const handleSalvar = async () => {
    if (!modal.cliente_razao_social.trim()) { setErro("Razão social é obrigatória."); return; }
    setSaving(true); setErro(null);
    try {
      const criado = await createPedidoVenda({
        numero:               modal.numero,
        tipo:                 "venda",
        data_emissao:         modal.data_emissao,
        prazo_entrega_dias:   Number(modal.prazo_entrega_dias) || 0,
        condicoes:            modal.condicoes,
        vendedor_id:          modal.vendedor_id     || null,
        tabela_preco_id:      modal.tabela_preco_id || null,
        cliente_razao_social: modal.cliente_razao_social.trim(),
        cliente_cnpj:         modal.cliente_cnpj,
        cliente_ie:           modal.cliente_ie,
        cliente_endereco:     modal.cliente_endereco,
        cliente_cidade:       modal.cliente_cidade,
        cliente_cep:          modal.cliente_cep,
        cliente_telefone:     modal.cliente_telefone,
        cliente_email:        modal.cliente_email,
        representante:        modal.representante,
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
            placeholder="Buscar por cliente ou número…"
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
                <td><code className={styles.num}>{p.numero}</code></td>
                <td>{p.data_emissao ? new Date(p.data_emissao).toLocaleDateString("pt-BR") : "—"}</td>
                <td>{p.cliente_razao_social || "—"}</td>
                <td>{p.vendedor_nome  || "—"}</td>
                <td>{p.tabela_nome    || "—"}</td>
                <td>{CONDICOES_LABEL[p.condicoes] || p.condicoes || "—"}</td>
                <td>{moeda(p.total_pedido)}</td>
                <td>{moeda(p.comissao_valor)}</td>
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
                    <span><strong>Tabela de Preço:</strong> {modalView.tabela_nome || "—"}</span>
                    <span>
                      <strong>Condição:</strong>{" "}
                      {CONDICOES_LABEL[modalView.condicoes] || modalView.condicoes || "—"}
                    </span>
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
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Novo Pedido de Venda</h2>
              <button className={styles.btnClose} onClick={fecharModal}>×</button>
            </div>

            <div className={styles.modalScroll}>
              <p className={styles.secLabel}>Pedido</p>
              <div className={styles.grid2}>
                <label className={styles.field}>
                  <span>Nº Pedido</span>
                  <input className={styles.input} value={modal.numero} onChange={set("numero")} />
                </label>
                <label className={styles.field}>
                  <span>Data de emissão</span>
                  <input type="date" className={styles.input} value={modal.data_emissao}
                    onChange={set("data_emissao")} />
                </label>
                <label className={styles.field}>
                  <span>Prazo de entrega (dias)</span>
                  <input type="number" min="0" className={styles.input}
                    value={modal.prazo_entrega_dias} onChange={set("prazo_entrega_dias")} />
                </label>
                <label className={styles.field}>
                  <span>Condição de pagamento</span>
                  <select className={styles.input} value={modal.condicoes} onChange={set("condicoes")}>
                    <option value="avista">À Vista</option>
                    <option value="aprazo">A Prazo</option>
                  </select>
                </label>
                <label className={styles.field}>
                  <span>Vendedor</span>
                  <select
                    className={styles.input}
                    value={modal.vendedor_id}
                    onChange={(e) => {
                      const vid  = e.target.value;
                      const vend = vendedores.find((v) => String(v.id) === String(vid));
                      setModal((m) => ({ ...m, vendedor_id: vid, representante: vend?.nome || "" }));
                    }}
                  >
                    <option value="">— Nenhum —</option>
                    {vendedores.map((v) => <option key={v.id} value={v.id}>{v.nome}</option>)}
                  </select>
                </label>
                <label className={styles.field}>
                  <span>Tabela de preço</span>
                  <select className={styles.input} value={modal.tabela_preco_id} onChange={set("tabela_preco_id")}>
                    <option value="">— Selecionar —</option>
                    {tabelas.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.nome} ({((t.comissao_pct || 0) * 100).toFixed(0)}% comissão)
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {tabelaSel && (
                <div className={styles.aviso}>
                  Comissão: <strong>{((tabelaSel.comissao_pct || 0) * 100).toFixed(1)}%</strong> sobre preço{" "}
                  {modal.condicoes === "avista" ? "à vista" : "a prazo"}
                </div>
              )}

              <p className={styles.secLabel} style={{ marginTop: "1.5rem" }}>Cliente</p>
              <div className={styles.grid2}>
                {CAMPOS_CLIENTE.map(({ k, l }) =>
                  k === "cliente_cnpj" ? (
                    <label key={k} className={styles.field}>
                      <span>{l}</span>
                      <div style={{ display: "flex", gap: "0.4rem" }}>
                        <input
                          className={styles.input}
                          style={{ flex: 1 }}
                          value={modal.cliente_cnpj}
                          onChange={(e) => { set("cliente_cnpj")(e); setClienteBusca(null); }}
                          onBlur={buscarClientePorCnpj}
                        />
                        <button
                          type="button"
                          className={styles.btnSecondary}
                          style={{ padding: "0 0.6rem", flexShrink: 0 }}
                          onClick={abrirBuscaCliente}
                          title="Buscar cliente cadastrado"
                        >
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="11" cy="11" r="7" />
                            <line x1="21" y1="21" x2="16.3" y2="16.3" />
                          </svg>
                        </button>
                      </div>
                      {(clienteBusca === "encontrado" || clienteBusca === "selecionado") && (
                        <span style={{ fontSize: "0.78rem", color: "var(--sc-success-text)", marginTop: "0.15rem" }}>
                          {clienteBusca === "selecionado" ? "Cliente selecionado" : "Cliente encontrado e preenchido"}
                        </span>
                      )}
                      {clienteBusca === "nao_cadastrado" && (
                        <span style={{ fontSize: "0.78rem", color: "var(--sc-text-muted)", marginTop: "0.15rem" }}>
                          Cliente não cadastrado — preencha manualmente
                        </span>
                      )}
                    </label>
                  ) : (
                    <label key={k} className={styles.field}>
                      <span>{l}</span>
                      <input className={styles.input} value={modal[k]} onChange={set(k)} />
                    </label>
                  )
                )}
              </div>
            </div>

            {erro && <p className={styles.erro}>{erro}</p>}

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharModal}>Cancelar</button>
              <button className={styles.btnPrimary} onClick={handleSalvar} disabled={saving}>
                {saving ? "Criando…" : "Criar Pedido →"}
              </button>
            </div>
          </div>
        </div>
      )}

      {modalCliente && (
        <div
          className={styles.overlay}
          onMouseDown={(e) => { buscaOverlayMouseDownNode.current = e.target; }}
          onClick={(e) => {
            if (e.target === e.currentTarget && buscaOverlayMouseDownNode.current === e.currentTarget) {
              fecharBuscaCliente();
            }
          }}
        >
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Selecionar Cliente</h2>
              <button className={styles.btnClose} onClick={fecharBuscaCliente}>×</button>
            </div>

            <div className={styles.modalScroll}>
              <input
                className={styles.input}
                style={{ width: "100%", marginBottom: "1rem" }}
                placeholder="Buscar por nome ou CNPJ..."
                value={buscaCliente}
                onChange={(e) => setBuscaCliente(e.target.value)}
                autoFocus
              />

              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "0.5rem 0.6rem", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--sc-text-secondary)", borderBottom: "1px solid var(--sc-border)" }}>Razão Social</th>
                    <th style={{ textAlign: "left", padding: "0.5rem 0.6rem", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--sc-text-secondary)", borderBottom: "1px solid var(--sc-border)" }}>CNPJ</th>
                    <th style={{ textAlign: "left", padding: "0.5rem 0.6rem", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--sc-text-secondary)", borderBottom: "1px solid var(--sc-border)" }}>Cidade</th>
                    <th style={{ textAlign: "left", padding: "0.5rem 0.6rem", fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--sc-text-secondary)", borderBottom: "1px solid var(--sc-border)" }}>Telefone</th>
                    <th style={{ borderBottom: "1px solid var(--sc-border)" }}></th>
                  </tr>
                </thead>
                <tbody>
                  {carregandoClientes ? (
                    <tr><td colSpan={5} className={styles.empty}>Buscando…</td></tr>
                  ) : resultadosCliente.length === 0 ? (
                    <tr>
                      <td colSpan={5} className={styles.empty}>
                        Nenhum cliente encontrado.{" "}
                        <a
                          href="/cadastros/clientes"
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: "var(--sc-action)" }}
                        >
                          Cadastrar novo cliente
                        </a>
                      </td>
                    </tr>
                  ) : resultadosCliente.map((c) => (
                    <tr key={c.id} style={{ borderBottom: "1px solid var(--sc-border)" }}>
                      <td style={{ padding: "0.55rem 0.6rem", color: "var(--sc-text-primary)" }}>{c.razao_social}</td>
                      <td style={{ padding: "0.55rem 0.6rem", color: "var(--sc-text-primary)" }}>{c.cnpj || c.cpf || "—"}</td>
                      <td style={{ padding: "0.55rem 0.6rem", color: "var(--sc-text-primary)" }}>{c.cidade || "—"}</td>
                      <td style={{ padding: "0.55rem 0.6rem", color: "var(--sc-text-primary)" }}>{c.telefone || "—"}</td>
                      <td style={{ padding: "0.55rem 0.6rem", textAlign: "right" }}>
                        <button className={styles.btnLink} onClick={() => selecionarCliente(c)}>Selecionar</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharBuscaCliente}>Cancelar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
