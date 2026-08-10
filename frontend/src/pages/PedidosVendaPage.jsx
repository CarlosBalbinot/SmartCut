import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { pedidosVendaApi, vendedoresApi, tabelasPrecoApi, clientesApi } from "../services/api";
import styles from "./PedidosVendaPage.module.css";

const STATUS_LABELS = {
  rascunho:   "Rascunho",
  confirmado: "Confirmado",
  producao:   "Em produção",
  entregue:   "Entregue",
  cancelado:  "Cancelado",
};

const STATUS_CLS = {
  rascunho:   "stRascunho",
  confirmado: "stConfirmado",
  producao:   "stProducao",
  entregue:   "stEntregue",
  cancelado:  "stCancelado",
};

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
  const [pedidos, setPedidos]                     = useState([]);
  const [vendedores, setVendedores]               = useState([]);
  const [tabelas, setTabelas]                     = useState([]);
  const [modal, setModal]                         = useState(null);
  const [saving, setSaving]                       = useState(false);
  const [erro, setErro]                           = useState(null);
  const [menuAberto, setMenuAberto]               = useState(null);
  const [menuPos, setMenuPos]                     = useState({ top: 0, left: 0 });
  const [pedidoParaDeletar, setPedidoParaDeletar] = useState(null);
  const [editStatusModal, setEditStatusModal]     = useState(null);
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
      pedidosVendaApi.list("venda"),
      vendedoresApi.list(),
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
      clientesApi.listar(buscaCliente)
        .then((lista) => setResultadosCliente(lista || []))
        .catch(() => setResultadosCliente([]))
        .finally(() => setCarregandoClientes(false));
    }, 300);
    return () => clearTimeout(t);
  }, [modalCliente, buscaCliente]);

  const abrirModal = async () => {
    const numero = await pedidosVendaApi.proximoNumero("venda").catch(() => "");
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
      const cliente = await clientesApi.buscarCnpj(digits);
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

  const handleSalvarStatus = async () => {
    if (!editStatusModal) return;
    try {
      await pedidosVendaApi.update(editStatusModal.id, { status: editStatusModal.status });
      setPedidos((ps) =>
        ps.map((p) => p.id === editStatusModal.id ? { ...p, status: editStatusModal.status } : p)
      );
      setEditStatusModal(null);
    } catch {}
  };

  const handleDeletar = async () => {
    if (!pedidoParaDeletar) return;
    try {
      await pedidosVendaApi.remove(pedidoParaDeletar.id);
      setPedidos((ps) => ps.filter((p) => p.id !== pedidoParaDeletar.id));
      setPedidoParaDeletar(null);
    } catch {}
  };

  const handleSalvar = async () => {
    if (!modal.cliente_razao_social.trim()) { setErro("Razão social é obrigatória."); return; }
    setSaving(true); setErro(null);
    try {
      const criado = await pedidosVendaApi.create({
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
      navigate(`/pedidos-venda/${criado.id}`);
    } catch (e) {
      setErro(e.message);
      setSaving(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Pedidos de Venda</h1>
        <button className={styles.btnPrimary} onClick={abrirModal}>+ Novo Pedido</button>
      </div>

      <div className={styles.card}>
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
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {pedidos.map((p) => (
              <tr key={p.id}>
                <td><code className={styles.num}>{p.numero}</code></td>
                <td>{p.data_emissao ? new Date(p.data_emissao).toLocaleDateString("pt-BR") : "—"}</td>
                <td>{p.cliente_razao_social || "—"}</td>
                <td>{p.vendedor_nome  || "—"}</td>
                <td>{p.tabela_nome    || "—"}</td>
                <td>{CONDICOES_LABEL[p.condicoes] || p.condicoes || "—"}</td>
                <td>{moeda(p.total_pedido)}</td>
                <td>{moeda(p.comissao_valor)}</td>
                <td>
                  <span className={`${styles.badge} ${styles[STATUS_CLS[p.status] || "stRascunho"]}`}>
                    {STATUS_LABELS[p.status] || p.status || "—"}
                  </span>
                </td>
                <td>
                  <div className={styles.rowActions}>
                    <button
                      className={styles.btnAbrir}
                      onClick={() => navigate(`/pedidos-venda/${p.id}`)}
                    >
                      Abrir →
                    </button>
                    <div className={styles.menuWrap}>
                      <button
                        className={styles.btnMenu}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (menuAberto !== p.id) {
                            const rect = e.currentTarget.getBoundingClientRect();
                            setMenuPos({ top: rect.bottom + 4, left: rect.right - 158 });
                          }
                          setMenuAberto(menuAberto === p.id ? null : p.id);
                        }}
                      >
                        ···
                      </button>
                      {menuAberto === p.id && (
                        <div className={styles.dropdown} style={{ top: menuPos.top, left: menuPos.left }} onClick={(e) => e.stopPropagation()}>
                          <button
                            className={styles.dropItem}
                            onClick={() => navigate(`/pedidos-venda/${p.id}`)}
                          >
                            Abrir →
                          </button>
                          <button
                            className={styles.dropItem}
                            onClick={() => {
                              setMenuAberto(null);
                              setEditStatusModal({ id: p.id, numero: p.numero, status: p.status || "rascunho" });
                            }}
                          >
                            Editar status
                          </button>
                          <button
                            className={`${styles.dropItem} ${styles.dropItemDanger}`}
                            onClick={() => { setMenuAberto(null); setPedidoParaDeletar(p); }}
                          >
                            Excluir
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </td>
              </tr>
            ))}
            {pedidos.length === 0 && (
              <tr>
                <td colSpan={10} className={styles.empty}>Nenhum pedido de venda cadastrado.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {pedidoParaDeletar && (
        <div className={styles.overlay} onClick={() => setPedidoParaDeletar(null)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>Excluir pedido?</h2>
            <p className={styles.confirmText}>
              Esta ação é irreversível. O pedido{" "}
              <strong>{pedidoParaDeletar.numero}</strong> de{" "}
              <strong>{pedidoParaDeletar.cliente_razao_social || "—"}</strong> e todos
              os seus itens serão excluídos permanentemente.
            </p>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setPedidoParaDeletar(null)}>
                Cancelar
              </button>
              <button className={styles.btnDanger} onClick={handleDeletar}>
                Excluir
              </button>
            </div>
          </div>
        </div>
      )}

      {editStatusModal && (
        <div className={styles.overlay} onClick={() => setEditStatusModal(null)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>Editar status</h2>
            <p className={styles.confirmText}>
              Pedido <strong>{editStatusModal.numero}</strong>
            </p>
            <label className={styles.field} style={{ marginBottom: "1.5rem" }}>
              <span>Novo status</span>
              <select
                className={styles.input}
                value={editStatusModal.status}
                onChange={(e) => setEditStatusModal((m) => ({ ...m, status: e.target.value }))}
              >
                <option value="rascunho">Rascunho</option>
                <option value="confirmado">Confirmado</option>
                <option value="producao">Em produção</option>
                <option value="entregue">Entregue</option>
                <option value="cancelado">Cancelado</option>
              </select>
            </label>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setEditStatusModal(null)}>
                Cancelar
              </button>
              <button className={styles.btnPrimary} onClick={handleSalvarStatus}>
                Salvar
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
                          href="/clientes"
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
