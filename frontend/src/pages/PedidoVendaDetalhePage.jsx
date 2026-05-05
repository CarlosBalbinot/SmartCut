import { useState, useEffect, useRef } from "react";
import ReactDOM from "react-dom";
import { useParams, useNavigate } from "react-router-dom";
import {
  pedidosVendaApi, vendedoresApi, tabelasPrecoApi, gruposApi,
  modelosApi, coresApi,
} from "../services/api";
import styles from "./PedidoVendaDetalhePage.module.css";

const TAMANHOS_BASE = ["P", "M", "G", "GG"];
const TAMANHOS_PLUS = ["P", "M", "G", "GG", "G1", "G2", "G3"];
const TAM_KEY = { P: "qtd_p", M: "qtd_m", G: "qtd_g", GG: "qtd_gg", G1: "qtd_g1", G2: "qtd_g2", G3: "qtd_g3" };
const QTD_KEYS = ["qtd_p", "qtd_m", "qtd_g", "qtd_gg", "qtd_g1", "qtd_g2", "qtd_g3"];

const CONDICOES_LABEL = { avista: "À Vista", aprazo: "A Prazo" };

const STATUS_OPTIONS = [
  { value: "rascunho",   label: "Rascunho"    },
  { value: "confirmado", label: "Confirmado"  },
  { value: "producao",   label: "Em produção" },
  { value: "entregue",   label: "Entregue"    },
  { value: "cancelado",  label: "Cancelado"   },
];

const STATUS_CLS = {
  rascunho:   "stRascunho",
  confirmado: "stConfirmado",
  producao:   "stProducao",
  entregue:   "stEntregue",
  cancelado:  "stCancelado",
};

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const dataLocal = (iso) =>
  iso ? new Date(iso).toLocaleDateString("pt-BR") : "—";

async function downloadBlob(promiseFn, filename) {
  const blob = await promiseFn();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

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

const ITEM_VAZIO = {
  searchQuery: "", searchResults: [], selectedGrupo: null,
  modelo_id: "", cor_id: "", lote_id: "",
  cores: [], lotes: [],
  cor: "", qtd_p: "", qtd_m: "", qtd_g: "", qtd_gg: "",
  qtd_g1: "", qtd_g2: "", qtd_g3: "",
  precoUnit: "", loadingPreco: false,
  precoAutoFilled: false, precoSemTabela: false,
};

export default function PedidoVendaDetalhePage() {
  const { id }   = useParams();
  const navigate = useNavigate();

  const [pedido, setPedido]             = useState(null);
  const [vendedores, setVendedores]     = useState([]);
  const [tabelas, setTabelas]           = useState([]);
  const [modelos, setModelos]           = useState([]);
  const [loading, setLoading]           = useState(true);
  const [editModal, setEditModal]       = useState(null);
  const [itemModal, setItemModal]       = useState(null);
  const [deletarConfirm, setDeletarConfirm] = useState(false);
  const [saving, setSaving]             = useState(false);
  const [erroEdit, setErroEdit]         = useState(null);
  const [erroItem, setErroItem]         = useState(null);
  const searchTimer                     = useRef(null);
  const searchInputRef                  = useRef(null);
  const [acPos, setAcPos]               = useState({ top: 0, left: 0, width: 200 });

  const carregar = async () => {
    setLoading(true);
    try { setPedido(await pedidosVendaApi.get(id)); }
    catch { setPedido(null); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    carregar();
    Promise.all([vendedoresApi.list(), tabelasPrecoApi.list()])
      .then(([v, t]) => {
        setVendedores((v || []).filter((x) => x.ativo !== false));
        setTabelas((t || []).filter((x) => x.ativo));
      }).catch(() => {});
  }, [id]);

  // ── Status ──────────────────────────────────────────────────────────────────
  const handleStatusChange = async (novoStatus) => {
    try {
      await pedidosVendaApi.update(id, { status: novoStatus });
      setPedido((p) => p ? { ...p, status: novoStatus } : p);
    } catch {}
  };

  // ── Edit modal ───────────────────────────────────────────────────────────────
  const abrirEditModal = () => {
    if (!pedido) return;
    setEditModal({
      numero:               pedido.numero               || "",
      data_emissao:         pedido.data_emissao         || "",
      prazo_entrega_dias:   String(pedido.prazo_entrega_dias ?? ""),
      condicoes:            pedido.condicoes            || "avista",
      vendedor_id:          pedido.vendedor_id          || "",
      tabela_preco_id:      pedido.tabela_preco_id      || "",
      cliente_razao_social: pedido.cliente_razao_social || "",
      cliente_cnpj:         pedido.cliente_cnpj         || "",
      cliente_ie:           pedido.cliente_ie           || "",
      cliente_endereco:     pedido.cliente_endereco     || "",
      cliente_cidade:       pedido.cliente_cidade       || "",
      cliente_cep:          pedido.cliente_cep          || "",
      cliente_telefone:     pedido.cliente_telefone     || "",
      cliente_email:        pedido.cliente_email        || "",
      representante:        pedido.representante        || "",
    });
    setErroEdit(null);
  };

  const setEdit = (key) => (e) => setEditModal((m) => ({ ...m, [key]: e.target.value }));

  const handleSalvarEdit = async () => {
    if (!editModal.cliente_razao_social.trim()) { setErroEdit("Razão social é obrigatória."); return; }
    setSaving(true); setErroEdit(null);
    try {
      const updated = await pedidosVendaApi.update(id, {
        numero:               editModal.numero,
        data_emissao:         editModal.data_emissao,
        prazo_entrega_dias:   Number(editModal.prazo_entrega_dias) || 0,
        condicoes:            editModal.condicoes,
        vendedor_id:          editModal.vendedor_id     || null,
        tabela_preco_id:      editModal.tabela_preco_id || null,
        cliente_razao_social: editModal.cliente_razao_social.trim(),
        cliente_cnpj:         editModal.cliente_cnpj,
        cliente_ie:           editModal.cliente_ie,
        cliente_endereco:     editModal.cliente_endereco,
        cliente_cidade:       editModal.cliente_cidade,
        cliente_cep:          editModal.cliente_cep,
        cliente_telefone:     editModal.cliente_telefone,
        cliente_email:        editModal.cliente_email,
        representante:        editModal.representante,
      });
      setPedido(updated);
      setEditModal(null);
    } catch (e) {
      setErroEdit(e.message);
    } finally {
      setSaving(false);
    }
  };

  const tabelaEditSel = editModal?.tabela_preco_id
    ? tabelas.find((t) => t.id === editModal.tabela_preco_id)
    : null;

  // ── Item modal ────────────────────────────────────────────────────────────────
  const abrirItemModal = async () => {
    setItemModal({ ...ITEM_VAZIO }); setErroItem(null);
    try { const ms = await modelosApi.listar(); setModelos(ms || []); } catch {}
  };

  const handleSearchChange = (query) => {
    setItemModal((m) => ({ ...m, searchQuery: query, selectedGrupo: null, searchResults: [] }));
    if (searchInputRef.current) {
      const rect = searchInputRef.current.getBoundingClientRect();
      setAcPos({ top: rect.bottom + 2, left: rect.left, width: rect.width });
    }
    clearTimeout(searchTimer.current);
    if (query.trim().length < 2) return;
    searchTimer.current = setTimeout(async () => {
      try {
        const results = await gruposApi.buscar(query);
        setItemModal((m) => ({ ...m, searchResults: (results || []).slice(0, 10) }));
      } catch {}
    }, 300);
  };

  const selecionarGrupo = async (grupo) => {
    setItemModal((m) => ({
      ...m,
      searchQuery:     `${grupo.codigo ? grupo.codigo + " — " : ""}${grupo.nome}`,
      searchResults:   [],
      selectedGrupo:   grupo,
      qtd_p: "", qtd_m: "", qtd_g: "", qtd_gg: "",
      qtd_g1: "", qtd_g2: "", qtd_g3: "",
      precoUnit:       "",
      loadingPreco:    !!pedido?.tabela_preco_id,
      precoAutoFilled: false,
      precoSemTabela:  false,
    }));

    if (!pedido?.tabela_preco_id) return;

    try {
      const itensTabela = await tabelasPrecoApi.listItens(pedido.tabela_preco_id);
      const precoItem   = (itensTabela || []).find((it) => it.grupo_id === grupo.id);
      if (precoItem) {
        const val = pedido.condicoes === "avista" ? precoItem.preco_avista : precoItem.preco_aprazo;
        setItemModal((m) => ({ ...m, precoUnit: String(val ?? ""), loadingPreco: false, precoAutoFilled: true }));
        return;
      }
    } catch {}
    setItemModal((m) => ({ ...m, loadingPreco: false, precoSemTabela: true }));
  };

  const handleModeloChange = async (modelo_id) => {
    setItemModal((m) => ({ ...m, modelo_id, cor_id: "", lote_id: "", cor: "", cores: [], lotes: [] }));
    if (!modelo_id) return;
    try {
      const cores = await modelosApi.listarCores(modelo_id);
      setItemModal((m) => ({ ...m, cores: cores || [] }));
    } catch {}
  };

  const handleCorChange = async (cor_id) => {
    setItemModal((m) => ({ ...m, cor_id, lote_id: "", cor: "", lotes: [] }));
    if (!cor_id) return;
    try {
      const lotes = await coresApi.listarLotes(cor_id);
      const lotesAtivos = (lotes || []).filter(
        (l) => !l.status || l.status === "aberto" || l.status === "intacto"
      );
      setItemModal((m) => ({ ...m, lotes: lotesAtivos }));
    } catch {}
  };

  const handleLoteChange = (lote_id) => {
    const corSel = itemModal.cores.find((c) => String(c.id) === String(itemModal.cor_id));
    setItemModal((m) => ({ ...m, lote_id, cor: corSel?.nome || "" }));
  };

  const loteLabelFn = (l) => {
    const cod = l.codigo || l.nome || String(l.id).slice(0, 8);
    const qtd = l.quantidade_disponivel ?? l.qtd_disponivel ?? l.metros ?? null;
    return qtd != null ? `${cod} — ${qtd}kg disp.` : cod;
  };

  const totalItem = (() => {
    if (!itemModal) return 0;
    const qtd = QTD_KEYS.reduce((s, k) => s + (parseInt(itemModal[k]) || 0), 0);
    return qtd * (parseFloat(itemModal.precoUnit) || 0);
  })();

  const handleSalvarItem = async () => {
    if (!itemModal.selectedGrupo) { setErroItem("Selecione uma referência."); return; }
    const qtdTotal = QTD_KEYS.reduce((s, k) => s + (parseInt(itemModal[k]) || 0), 0);
    if (qtdTotal === 0) { setErroItem("Informe ao menos uma quantidade."); return; }
    setSaving(true); setErroItem(null);
    try {
      await pedidosVendaApi.addItem(id, {
        grupo_id:       itemModal.selectedGrupo.id,
        cor:            itemModal.cor,
        lote_id:        itemModal.lote_id || null,
        qtd_p:          parseInt(itemModal.qtd_p)  || 0,
        qtd_m:          parseInt(itemModal.qtd_m)  || 0,
        qtd_g:          parseInt(itemModal.qtd_g)  || 0,
        qtd_gg:         parseInt(itemModal.qtd_gg) || 0,
        qtd_g1:         parseInt(itemModal.qtd_g1) || 0,
        qtd_g2:         parseInt(itemModal.qtd_g2) || 0,
        qtd_g3:         parseInt(itemModal.qtd_g3) || 0,
        preco_unitario: parseFloat(itemModal.precoUnit) || 0,
      });
      await carregar();
      setItemModal(null);
    } catch (e) {
      setErroItem(e.message);
    } finally {
      setSaving(false);
    }
  };

  const removerItem = async (itemId) => {
    try { await pedidosVendaApi.removeItem(id, itemId); await carregar(); } catch {}
  };

  // ── Delete ─────────────────────────────────────────────────────────────────
  const handleDeletar = async () => {
    try { await pedidosVendaApi.remove(id); navigate("/pedidos-venda"); } catch {}
  };

  // ── Table grouping ──────────────────────────────────────────────────────────
  const itens       = pedido?.itens || [];
  const temPlus     = itens.some((i) => (i.qtd_g1 || 0) + (i.qtd_g2 || 0) + (i.qtd_g3 || 0) > 0);
  const tamCols     = temPlus ? TAMANHOS_PLUS : TAMANHOS_BASE;
  const gruposOrdem = [];
  const grupoMap    = {};
  itens.forEach((item) => {
    if (!grupoMap[item.grupo_id]) { grupoMap[item.grupo_id] = []; gruposOrdem.push(item.grupo_id); }
    grupoMap[item.grupo_id].push(item);
  });

  const tabelaAtual    = tabelas.find((t) => t.id === pedido?.tabela_preco_id);
  const comissaoPctStr = tabelaAtual
    ? `${((tabelaAtual.comissao_pct || 0) * 100).toFixed(1)}%`
    : null;

  const isPlus  = itemModal?.selectedGrupo?.tem_plus;
  const tamForm = isPlus ? TAMANHOS_PLUS : TAMANHOS_BASE;

  // ── Render ──────────────────────────────────────────────────────────────────
  if (loading) return <div className={styles.page}><p className={styles.stateMsg}>Carregando…</p></div>;
  if (!pedido) return (
    <div className={styles.page}>
      <button className={styles.btnBack} onClick={() => navigate("/pedidos-venda")}>← Pedidos de Venda</button>
      <p className={styles.stateMsg}>Pedido não encontrado.</p>
    </div>
  );

  return (
    <div className={styles.page}>
      <button className={styles.btnBack} onClick={() => navigate("/pedidos-venda")}>
        ← Pedidos de Venda
      </button>

      {/* ── Cabeçalho ── */}
      <div className={styles.headRow}>
        <div className={styles.headLeft}>
          <div className={styles.headTitulo}>
            <h1 className={styles.title}>Pedido {pedido.numero}</h1>
            <select
              className={`${styles.statusSelect} ${styles[STATUS_CLS[pedido.status] || "stRascunho"]}`}
              value={pedido.status || "rascunho"}
              onChange={(e) => handleStatusChange(e.target.value)}
            >
              {STATUS_OPTIONS.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div className={styles.headMeta}>
            <span><strong>Cliente:</strong> {pedido.cliente_razao_social || "—"}</span>
            <span><strong>Data:</strong> {dataLocal(pedido.data_emissao)}</span>
            <span><strong>Prazo:</strong> {pedido.prazo_entrega_dias ?? "—"} dias</span>
            <span><strong>Vendedor:</strong> {pedido.vendedor_nome || "—"}</span>
            <span><strong>Tabela:</strong> {pedido.tabela_nome || "—"}</span>
            <span><strong>Condição:</strong> {CONDICOES_LABEL[pedido.condicoes] || pedido.condicoes || "—"}</span>
          </div>
        </div>
        <button className={styles.btnSecondary} onClick={abrirEditModal}>Editar dados</button>
      </div>

      {/* ── Itens ── */}
      <div className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>Itens do pedido</h2>
          <button className={styles.btnPrimary} onClick={abrirItemModal}>+ Adicionar item</button>
        </div>

        <div className={styles.card}>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>REF</th>
                  <th>Nome</th>
                  <th>Cor</th>
                  {tamCols.map((t) => <th key={t} className={styles.thQty}>{t}</th>)}
                  <th className={styles.thPreco}>P. Unit.</th>
                  <th className={styles.thPreco}>Total</th>
                  <th style={{ width: 36 }}></th>
                </tr>
              </thead>
              <tbody>
                {gruposOrdem.map((gid) => {
                  const grupo_itens = grupoMap[gid];
                  return grupo_itens.map((item, idx) => (
                    <tr key={item.id} className={idx === 0 ? styles.trFirst : styles.trCont}>
                      {idx === 0 && (
                        <>
                          <td rowSpan={grupo_itens.length} className={styles.tdRef}>
                            <code>{item.grupo_codigo || "—"}</code>
                          </td>
                          <td rowSpan={grupo_itens.length} className={styles.tdNome}>
                            {item.grupo_nome || "—"}
                          </td>
                        </>
                      )}
                      <td>{item.cor || "—"}</td>
                      {tamCols.map((t) => (
                        <td key={t} className={styles.tdQty}>
                          {(item[TAM_KEY[t]] || 0) > 0 ? item[TAM_KEY[t]] : ""}
                        </td>
                      ))}
                      <td className={styles.tdPreco}>{moeda(item.preco_unitario)}</td>
                      <td className={styles.tdTotal}>{moeda(item.preco_total)}</td>
                      <td>
                        <button
                          className={styles.btnExcluir}
                          onClick={() => removerItem(item.id)}
                          title="Remover"
                        >×</button>
                      </td>
                    </tr>
                  ));
                })}
                {itens.length === 0 && (
                  <tr>
                    <td colSpan={4 + tamCols.length} className={styles.empty}>
                      Nenhum item adicionado.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {itens.length > 0 && (
            <div className={styles.totais}>
              {comissaoPctStr && (
                <div className={styles.totaisLinha}>
                  <span>Comissão ({comissaoPctStr})</span>
                  <span>{moeda(pedido.comissao_valor)}</span>
                </div>
              )}
              <div className={`${styles.totaisLinha} ${styles.totaisTotal}`}>
                <span>Total</span>
                <strong>{moeda(pedido.total_pedido)}</strong>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Ações ── */}
      <div className={styles.acoesSection}>
        <div className={styles.acoes}>
          <button
            className={styles.btnDownload}
            onClick={() => downloadBlob(() => pedidosVendaApi.pdfPedido(id), `pedido-${pedido.numero}.pdf`)}
          >
            ↓ Formulário de Pedido PDF
          </button>
          <button
            className={styles.btnDownload}
            onClick={() => downloadBlob(() => pedidosVendaApi.pdfCorte(id), `corte-${pedido.numero}.pdf`)}
          >
            ↓ Formulário de Corte PDF
          </button>
          <button
            className={styles.btnSecondary}
            onClick={async () => {
              try {
                await pedidosVendaApi.gerarEncaixe(id);
                alert("Encaixe iniciado! Em breve disponível na seção de encaixes.");
              } catch (e) {
                alert(e.message);
              }
            }}
          >
            Gerar Encaixe
          </button>
          <button className={styles.btnDanger} onClick={() => setDeletarConfirm(true)}>
            Excluir Pedido
          </button>
        </div>
        <p className={styles.notaInfo}>
          Após confirmar o pedido, use "Gerar Encaixe" para criar o encaixe otimizado das peças.
        </p>
      </div>

      {/* ══ MODAL — Editar dados ══ */}
      {editModal && (
        <div className={styles.overlay} onClick={() => { setEditModal(null); setErroEdit(null); }}>
          <div className={styles.modalLg} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Editar Pedido</h2>
              <button className={styles.btnClose}
                onClick={() => { setEditModal(null); setErroEdit(null); }}>×</button>
            </div>
            <div className={styles.modalScroll}>
              <p className={styles.secLabel}>Pedido</p>
              <div className={styles.grid2}>
                <label className={styles.field}>
                  <span>Nº Pedido</span>
                  <input className={styles.input} value={editModal.numero} onChange={setEdit("numero")} />
                </label>
                <label className={styles.field}>
                  <span>Data de emissão</span>
                  <input type="date" className={styles.input} value={editModal.data_emissao}
                    onChange={setEdit("data_emissao")} />
                </label>
                <label className={styles.field}>
                  <span>Prazo entrega (dias)</span>
                  <input type="number" min="0" className={styles.input}
                    value={editModal.prazo_entrega_dias} onChange={setEdit("prazo_entrega_dias")} />
                </label>
                <label className={styles.field}>
                  <span>Condição</span>
                  <select className={styles.input} value={editModal.condicoes} onChange={setEdit("condicoes")}>
                    <option value="avista">À Vista</option>
                    <option value="aprazo">A Prazo</option>
                  </select>
                </label>
                <label className={styles.field}>
                  <span>Vendedor</span>
                  <select className={styles.input} value={editModal.vendedor_id} onChange={setEdit("vendedor_id")}>
                    <option value="">— Nenhum —</option>
                    {vendedores.map((v) => <option key={v.id} value={v.id}>{v.nome}</option>)}
                  </select>
                </label>
                <label className={styles.field}>
                  <span>Tabela de preço</span>
                  <select className={styles.input} value={editModal.tabela_preco_id}
                    onChange={setEdit("tabela_preco_id")}>
                    <option value="">— Nenhuma —</option>
                    {tabelas.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.nome} — {((t.comissao_pct || 0) * 100).toFixed(0)}%
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {tabelaEditSel && (
                <div className={styles.aviso}>
                  Comissão: <strong>{((tabelaEditSel.comissao_pct || 0) * 100).toFixed(1)}%</strong>{" "}
                  sobre preço {editModal.condicoes === "avista" ? "à vista" : "a prazo"}
                </div>
              )}
              <p className={styles.secLabel} style={{ marginTop: "1.25rem" }}>Cliente</p>
              <div className={styles.grid2}>
                {CAMPOS_CLIENTE.map(({ k, l }) => (
                  <label key={k} className={styles.field}>
                    <span>{l}</span>
                    <input className={styles.input} value={editModal[k]} onChange={setEdit(k)} />
                  </label>
                ))}
                <label className={styles.field}>
                  <span>Representante</span>
                  <select className={styles.input} value={editModal.representante} onChange={setEdit("representante")}>
                    <option value="">— Nenhum —</option>
                    {vendedores.map((v) => <option key={v.id} value={v.nome}>{v.nome}</option>)}
                  </select>
                </label>
              </div>
            </div>
            {erroEdit && <p className={styles.erro}>{erroEdit}</p>}
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary}
                onClick={() => { setEditModal(null); setErroEdit(null); }}>Cancelar</button>
              <button className={styles.btnPrimary} onClick={handleSalvarEdit} disabled={saving}>
                {saving ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Adicionar item ══ */}
      {itemModal && (
        <div className={styles.overlay} onClick={() => { setItemModal(null); setErroItem(null); }}>
          <div className={styles.modalMd} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Adicionar item</h2>
              <button className={styles.btnClose}
                onClick={() => { setItemModal(null); setErroItem(null); }}>×</button>
            </div>

            <div className={styles.modalBody}>
              <div className={styles.searchWrap}>
                <label className={styles.field}>
                  <span>Referência — código ou nome</span>
                  <input
                    ref={searchInputRef}
                    className={styles.input}
                    placeholder="Digite para buscar…"
                    value={itemModal.searchQuery}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    onBlur={() => setTimeout(() => setItemModal((m) => m ? { ...m, searchResults: [] } : m), 200)}
                    autoComplete="off"
                  />
                </label>
                {itemModal.searchResults.length > 0 && ReactDOM.createPortal(
                  <ul className={styles.autocomplete} style={{ top: acPos.top, left: acPos.left, width: acPos.width }}>
                    {itemModal.searchResults.map((g) => (
                      <li key={g.id} className={styles.acItem} onClick={() => selecionarGrupo(g)}>
                        <code className={styles.acCod}>{g.codigo || "?"}</code>
                        <span className={styles.acNome}>{g.nome}</span>
                        {g.tem_plus && <span className={styles.acPlus}>Plus</span>}
                      </li>
                    ))}
                  </ul>,
                  document.body
                )}
              </div>

              {itemModal.selectedGrupo && (
                <>
                  <div className={styles.grupoInfo}>
                    <span className={styles.grupoNome}>{itemModal.selectedGrupo.nome}</span>
                    <code className={styles.grupoCod}>{itemModal.selectedGrupo.codigo}</code>
                    {itemModal.selectedGrupo.tem_plus && (
                      <span className={styles.badgePlus}>Plus</span>
                    )}
                  </div>

                  <div className={styles.tecidoSection}>
                    <label className={styles.field}>
                      <span>Modelo de Tecido</span>
                      <select className={styles.input} value={itemModal.modelo_id}
                        onChange={(e) => handleModeloChange(e.target.value)}>
                        <option value="">— Selecionar modelo —</option>
                        {modelos.map((mo) => <option key={mo.id} value={mo.id}>{mo.nome}</option>)}
                      </select>
                    </label>
                    {itemModal.modelo_id && (
                      <label className={styles.field}>
                        <span>Cor</span>
                        <select className={styles.input} value={itemModal.cor_id}
                          onChange={(e) => handleCorChange(e.target.value)}>
                          <option value="">— Selecionar cor —</option>
                          {itemModal.cores.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
                        </select>
                      </label>
                    )}
                    {itemModal.cor_id && (
                      <label className={styles.field}>
                        <span>Lote</span>
                        <select className={styles.input} value={itemModal.lote_id}
                          onChange={(e) => handleLoteChange(e.target.value)}>
                          <option value="">— Selecionar lote —</option>
                          {itemModal.lotes.map((l) => (
                            <option key={l.id} value={l.id}>{loteLabelFn(l)}</option>
                          ))}
                        </select>
                      </label>
                    )}
                    {itemModal.cor && (
                      <p className={styles.corExtraida}>
                        Cor selecionada: <strong>{itemModal.cor}</strong>
                      </p>
                    )}
                  </div>

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

                  <label className={styles.field}>
                    <span>Preço unitário (R$)</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={itemModal.precoUnit}
                      disabled={itemModal.loadingPreco}
                      onChange={(e) => setItemModal((m) => ({ ...m, precoUnit: e.target.value }))}
                    />
                    {pedido.tabela_nome && (
                      <small className={`${styles.precoHint}${itemModal.precoSemTabela ? " " + styles.precoHintWarn : ""}`}>
                        {itemModal.loadingPreco
                          ? "Buscando preço…"
                          : itemModal.precoSemTabela
                          ? "Produto sem preço nesta tabela"
                          : `Tabela ${pedido.tabela_nome} — ${CONDICOES_LABEL[pedido.condicoes] || pedido.condicoes}${itemModal.precoAutoFilled ? " — valor automático" : ""}`}
                      </small>
                    )}
                  </label>

                  <div className={styles.itemTotal}>
                    Total do item: <strong>{moeda(totalItem)}</strong>
                  </div>
                </>
              )}

              {erroItem && <p className={styles.erro}>{erroItem}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary}
                onClick={() => { setItemModal(null); setErroItem(null); }}>Cancelar</button>
              <button
                className={styles.btnPrimary}
                onClick={handleSalvarItem}
                disabled={saving || !itemModal.selectedGrupo}
              >
                {saving ? "Adicionando…" : "Adicionar item"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Confirmar exclusão ══ */}
      {deletarConfirm && (
        <div className={styles.overlay} onClick={() => setDeletarConfirm(false)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle} style={{ marginBottom: "0.75rem" }}>
              Excluir pedido?
            </h2>
            <p className={styles.confirmText}>
              Esta ação é irreversível. O pedido <strong>{pedido.numero}</strong> e todos os
              seus itens serão excluídos permanentemente.
            </p>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setDeletarConfirm(false)}>
                Cancelar
              </button>
              <button className={styles.btnDanger} onClick={handleDeletar}>Excluir</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
