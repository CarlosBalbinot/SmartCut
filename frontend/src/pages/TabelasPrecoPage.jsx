import { useState, useEffect } from "react";
import { getGrupos } from "../api/moldes";
import {
  addItemTabelaPreco,
  createTabelaPreco,
  deleteTabelaPreco,
  getItensTabelaPreco,
  getTabelasPreco,
  removeItemTabelaPreco,
  updateTabelaPreco,
} from "../api/tabelasPreco";
import { useAuth } from "../auth/useAuth";
import PrecosProdutoTabela from "../components/PrecosProdutoTabela/PrecosProdutoTabela";
import styles from "./TabelasPrecoPage.module.css";

const MODULO = "configuracoes_editar";

const fmtR = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(parseFloat(v) || 0);

// Erro no padrão do sistema: campo levemente vermelho + mensagem só no
// tooltip (title). Inline porque o CSS module desta página não tem a classe.
const ERRO_CAMPO = { background: "var(--sc-danger-bg)", borderColor: "var(--sc-danger-text)" };
const ERRO_BOTAO = { boxShadow: "0 0 0 2px var(--sc-danger-text)" };
const UPPER = { textTransform: "uppercase" };

const DROPDOWN_STYLE = {
  position: "absolute", top: "100%", left: 0, right: 0,
  background: "var(--sc-surface)",
  border: "1px solid var(--sc-border)", borderRadius: 6,
  boxShadow: "0 4px 16px rgba(0,0,0,0.1)", zIndex: 10,
  listStyle: "none", margin: 0, padding: 0, maxHeight: 240, overflowY: "auto",
};
const DROPDOWN_ITEM_STYLE = {
  padding: "10px 12px", cursor: "pointer",
  borderBottom: "1px solid var(--sc-border)", fontSize: 14,
};

// ── Página: Tabelas de Preço ────────────────────────────────────────────────

export default function TabelasPrecoPage() {
  const { hasPermission } = useAuth();
  const podeEditar = hasPermission(MODULO, "ver");
  const [tabelas, setTabelas]             = useState([]);
  const [grupos, setGrupos]               = useState([]);
  const [loading, setLoading]             = useState(true);
  const [selectedId, setSelectedId]       = useState(null);
  const [tabItens, setTabItens]           = useState({});
  const [showNova, setShowNova]           = useState(false);
  const [showAdd, setShowAdd]             = useState(null);
  const [editTabela, setEditTabela]       = useState(null);
  const [editForm, setEditForm]           = useState({ nome: "" });
  const [savingEdit, setSavingEdit]       = useState(false);
  const [errEdit, setErrEdit]             = useState(null);
  const [inativaOpen, setInativaOpen]     = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(null);
  const [toast, setToast]                 = useState(null);

  useEffect(() => {
    loadTabelas(true);
    getGrupos().then((d) => setGrupos(d || [])).catch(() => {});
  }, []);

  const loadTabelas = async (autoSelect = false) => {
    setLoading(true);
    try {
      const data = await getTabelasPreco() || [];
      setTabelas(data);
      if (autoSelect) {
        const first = data.find((t) => t.ativa !== false);
        if (first) {
          setSelectedId(first.id);
          const itens = await getItensTabelaPreco(first.id).catch(() => []);
          setTabItens((prev) => ({ ...prev, [first.id]: itens }));
        }
      }
    } catch {}
    finally { setLoading(false); }
  };

  const showToast = (text) => {
    setToast(text);
    setTimeout(() => setToast(null), 4000);
  };

  const handleSelect = async (tab) => {
    setSelectedId(tab.id);
    if (!tabItens[tab.id]) {
      try {
        const data = await getItensTabelaPreco(tab.id);
        setTabItens((prev) => ({ ...prev, [tab.id]: data || [] }));
      } catch {
        setTabItens((prev) => ({ ...prev, [tab.id]: [] }));
      }
    }
  };

  const reloadItens = async (tabelaId) => {
    try {
      const data = await getItensTabelaPreco(tabelaId);
      setTabItens((prev) => ({ ...prev, [tabelaId]: data || [] }));
    } catch {}
  };

  const handleInativar = async (tab) => {
    try {
      await updateTabelaPreco(tab.id, { ativa: false });
      if (selectedId === tab.id) setSelectedId(null);
      await loadTabelas();
    } catch (e) { showToast(e.message); }
  };

  const handleAtivar = async (tab) => {
    try {
      await updateTabelaPreco(tab.id, { ativa: true });
      await loadTabelas();
    } catch (e) { showToast(e.message); }
  };

  const handleDelete = async (tab) => {
    if ((tab.num_itens ?? 0) > 0) {
      showToast("Remova os produtos antes de excluir esta tabela.");
      return;
    }
    try {
      await deleteTabelaPreco(tab.id);
      if (selectedId === tab.id) setSelectedId(null);
      await loadTabelas();
    } catch (e) { showToast(e.message); }
  };

  const abrirEdit = (tab) => {
    setEditForm({ nome: tab.nome });
    setEditTabela(tab);
    setErrEdit(null);
  };

  const handleSaveEdit = async () => {
    if (!editTabela) return;
    if (!editForm.nome.trim()) { setErrEdit({ nome: "Informe o nome da tabela." }); return; }
    setSavingEdit(true); setErrEdit(null);
    try {
      await updateTabelaPreco(editTabela.id, { nome: editForm.nome.trim() });
      await loadTabelas();
      setEditTabela(null);
    } catch (e) {
      setErrEdit({ geral: e.message });
    } finally {
      setSavingEdit(false);
    }
  };

  const handleRemoveItem = async (tabelaId, grupoId) => {
    try {
      await removeItemTabelaPreco(tabelaId, grupoId);
      setConfirmRemove(null);
      await reloadItens(tabelaId);
      await loadTabelas();
    } catch {}
  };

  const ativas      = tabelas.filter((t) => t.ativa !== false);
  const inativas    = tabelas.filter((t) => t.ativa === false);
  const selectedTab = tabelas.find((t) => t.id === selectedId) ?? null;
  const itens       = selectedId ? (tabItens[selectedId] ?? []) : [];

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Tabelas de Preço</h1>
      </div>

      <div className={styles.tabelasLayout}>

        {/* ── Left column — card list ── */}
        <div className={styles.tabelasLeft}>
          <div className={styles.tabelasLeftHeader}>
            <span className={styles.tabelasLeftTitle}>Tabelas</span>
            {podeEditar && (
              <button className={styles.btnNovo} onClick={() => setShowNova(true)}>+ Nova</button>
            )}
          </div>

          {toast && (
            <div className={styles.msgErro} style={{ margin: "8px 10px", fontSize: 12 }}>{toast}</div>
          )}

          {loading ? (
            <p className={styles.tabelasEmptyLeft}>Carregando…</p>
          ) : ativas.length === 0 ? (
            <p className={styles.tabelasEmptyLeft}>Nenhuma tabela ativa.</p>
          ) : (
            ativas.map((tab) => (
              <div
                key={tab.id}
                className={`${styles.tabelaCard} ${selectedId === tab.id ? styles.tabelaCardSel : ""}`}
                onClick={() => handleSelect(tab)}
              >
                <div className={styles.tabelaCardHead}>
                  <span className={styles.tabelaCardNome}>{tab.nome}</span>
                  {podeEditar && (
                    <div className={styles.tabelaCardActions}>
                      <button
                        className={styles.tabelaCardActionBtn}
                        title="Editar"
                        onClick={(e) => { e.stopPropagation(); abrirEdit(tab); }}
                      >✏</button>
                      <button
                        className={`${styles.tabelaCardActionBtn} ${styles.tabelaCardActionBtnDanger}`}
                        title="Excluir"
                        onClick={(e) => { e.stopPropagation(); handleDelete(tab); }}
                      >×</button>
                    </div>
                  )}
                </div>
                <div className={styles.tabelaCardMeta}>
                  <span className={styles.tabelaBadgeAtiva}>Ativa</span>
                </div>
                <span className={styles.tabelaCardCount}>
                  {tab.num_itens ?? 0} produto{(tab.num_itens ?? 0) !== 1 ? "s" : ""}
                </span>
              </div>
            ))
          )}

          {inativas.length > 0 && (
            <>
              <button
                className={styles.inativasToggle}
                onClick={() => setInativaOpen(!inativaOpen)}
              >
                {inativaOpen ? "▴" : "▾"} Inativas ({inativas.length})
              </button>
              {inativaOpen && inativas.map((tab) => (
                <div
                  key={tab.id}
                  className={`${styles.tabelaCard} ${styles.inativaCard} ${selectedId === tab.id ? styles.tabelaCardSel : ""}`}
                  onClick={() => handleSelect(tab)}
                >
                  <div className={styles.tabelaCardHead}>
                    <span className={styles.tabelaCardNome}>{tab.nome}</span>
                    {podeEditar && (
                      <div className={styles.tabelaCardActions}>
                        <button
                          className={styles.tabelaCardActionBtn}
                          title="Ativar"
                          onClick={(e) => { e.stopPropagation(); handleAtivar(tab); }}
                        >↑</button>
                      </div>
                    )}
                  </div>
                  <div className={styles.tabelaCardMeta}>
                    <span className={styles.tabelaBadgeInativa}>Inativa</span>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        {/* ── Right panel — detail ── */}
        <div className={styles.tabelasRight}>
          {!selectedTab ? (
            <div className={styles.tabelasEmptyRight}>
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                <rect x="6" y="6" width="28" height="28" rx="6"
                  stroke="var(--sc-border-strong)" strokeWidth="2"/>
                <path d="M13 14h14M13 20h10M13 26h7"
                  stroke="var(--sc-border-strong)" strokeWidth="2" strokeLinecap="round"/>
              </svg>
              <p>Selecione uma tabela de preço</p>
            </div>
          ) : (
            <>
              <div className={styles.tabelasRightHeader}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                    <h3 className={styles.tabelasRightNome}>{selectedTab.nome}</h3>
                    <span className={selectedTab.ativa !== false ? styles.tabelaBadgeAtiva : styles.tabelaBadgeInativa}>
                      {selectedTab.ativa !== false ? "Ativa" : "Inativa"}
                    </span>
                  </div>
                </div>
                {podeEditar && (
                  <div className={styles.tabelasRightBtns}>
                    <button className={styles.btnSecondary} onClick={() => abrirEdit(selectedTab)}>
                      Editar
                    </button>
                    {selectedTab.ativa !== false
                      ? <button className={styles.btnSecondary} onClick={() => handleInativar(selectedTab)}>
                          Inativar
                        </button>
                      : <button className={styles.btnSecondary} onClick={() => handleAtivar(selectedTab)}>
                          Ativar
                        </button>
                    }
                  </div>
                )}
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--sc-text-primary)" }}>
                  Produtos ({itens.length})
                </span>
                {selectedTab.ativa !== false && podeEditar && (
                  <button className={styles.btnSecondary} onClick={() => setShowAdd(selectedId)}>
                    + Adicionar produto
                  </button>
                )}
              </div>

              {itens.length === 0 ? (
                <div className={styles.tabelasEmptyRight} style={{ minHeight: 180 }}>
                  <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                    <circle cx="16" cy="16" r="13" stroke="var(--sc-border-strong)" strokeWidth="2"/>
                    <path d="M10 16h12M16 10v12"
                      stroke="var(--sc-border-strong)" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                  <p>Nenhum produto nesta tabela.</p>
                  {selectedTab.ativa !== false && podeEditar && (
                    <button className={styles.btnSecondary} style={{ marginTop: 8 }}
                      onClick={() => setShowAdd(selectedId)}>
                      + Adicionar produto
                    </button>
                  )}
                </div>
              ) : (
                <table className={styles.prodTable}>
                  <thead>
                    <tr>
                      <th className={styles.prodTh}>Ref</th>
                      <th className={styles.prodTh}>Produto</th>
                      <th className={styles.prodTh}>À vista</th>
                      <th className={styles.prodTh}>A prazo</th>
                      <th className={styles.prodTh} style={{ width: 40 }} />
                    </tr>
                  </thead>
                  <tbody>
                    {itens.map((item) => (
                      <tr key={item.grupo_id} className={styles.prodTr}>
                        <td className={styles.prodTd}>
                          <span className={styles.refBadge}>{item.codigo || "—"}</span>
                        </td>
                        <td className={styles.prodTd}>{item.nome}</td>
                        <td className={styles.prodTd}>
                          <span className={styles.priceValue}>{fmtR(item.preco_avista)}</span>
                        </td>
                        <td className={styles.prodTd}>
                          <span className={styles.priceValue}>{fmtR(item.preco_aprazo)}</span>
                        </td>
                        <td className={styles.prodTd} style={{ textAlign: "right" }}>
                          {confirmRemove === `${selectedId}-${item.grupo_id}` ? (
                            <span style={{ display: "inline-flex", gap: 4 }}>
                              <button
                                style={{ background: "var(--sc-danger-text)", color: "#fff", border: "none", borderRadius: 4, padding: "2px 7px", cursor: "pointer", fontSize: 11 }}
                                onClick={() => handleRemoveItem(selectedId, item.grupo_id)}
                              >Sim</button>
                              <button
                                style={{ background: "none", border: "none", cursor: "pointer", fontSize: 11, color: "var(--sc-text-secondary)" }}
                                onClick={() => setConfirmRemove(null)}
                              >Não</button>
                            </span>
                          ) : podeEditar ? (
                            <button
                              className={styles.prodRemoveBtn}
                              onClick={() => setConfirmRemove(`${selectedId}-${item.grupo_id}`)}
                            >×</button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              <PrecosProdutoTabela
                key={selectedTab.id}
                tabelaId={selectedTab.id}
                editavel={podeEditar && selectedTab.ativa !== false}
              />
            </>
          )}
        </div>

        {/* Modals */}
        {showNova && (
          <ModalNovaTabela
            onClose={() => setShowNova(false)}
            onCreated={async () => { setShowNova(false); await loadTabelas(); }}
          />
        )}

        {showAdd && (
          <ModalAddItem
            tabelaId={showAdd}
            grupos={grupos}
            onClose={() => setShowAdd(null)}
            onAdded={async () => {
              const id = showAdd;
              setShowAdd(null);
              await reloadItens(id);
              await loadTabelas();
            }}
          />
        )}

        {editTabela && (
          <div className={styles.modalPillOverlay}>
            <div className={styles.modalPill}>
              <h3 className={styles.modalPillTitle}>Editar Tabela</h3>
              <label className={styles.field}>
                <span>Nome</span>
                <input className={styles.input} value={editForm.nome}
                  style={{ ...UPPER, ...(errEdit?.nome ? ERRO_CAMPO : {}) }}
                  title={errEdit?.nome || ""}
                  onChange={(e) => { setErrEdit(null); setEditForm((f) => ({ ...f, nome: e.target.value.toUpperCase() })); }}
                  onKeyDown={(e) => { if (e.key === "Enter") handleSaveEdit(); }} />
              </label>
              <div className={styles.modalPillActions}>
                <button className={styles.btnPillSecondary} onClick={() => setEditTabela(null)}>Cancelar</button>
                <button className={styles.btnPillPrimary} onClick={handleSaveEdit} disabled={savingEdit}
                  style={errEdit?.geral ? ERRO_BOTAO : undefined} title={errEdit?.geral || ""}>
                  {savingEdit ? "…" : "Salvar"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ModalNovaTabela({ onClose, onCreated }) {
  const [form, setForm]     = useState({ nome: "" });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState(null);   // { nome } | { geral }

  const handleSave = async () => {
    if (!form.nome.trim()) { setErr({ nome: "Informe o nome da tabela." }); return; }
    setSaving(true); setErr(null);
    try {
      await createTabelaPreco({ nome: form.nome.trim() });
      onCreated();
    } catch (e) {
      setErr({ geral: e.message });
      setSaving(false);
    }
  };

  return (
    <div className={styles.modalPillOverlay}>
      <div className={styles.modalPill}>
        <h3 className={styles.modalPillTitle}>Nova Tabela de Preço</h3>
        <label className={styles.field}>
          <span>Nome</span>
          <input className={styles.input} value={form.nome}
            style={{ ...UPPER, ...(err?.nome ? ERRO_CAMPO : {}) }}
            title={err?.nome || ""}
            onChange={(e) => { setErr(null); setForm((f) => ({ ...f, nome: e.target.value.toUpperCase() })); }}
            onKeyDown={(e) => { if (e.key === "Enter") handleSave(); }}
            placeholder="EX.: ATACADO SUL"
            autoFocus />
        </label>
        <div className={styles.modalPillActions}>
          <button className={styles.btnPillSecondary} onClick={onClose}>Cancelar</button>
          <button className={styles.btnPillPrimary} onClick={handleSave} disabled={saving}
            style={err?.geral ? ERRO_BOTAO : undefined} title={err?.geral || ""}>
            {saving ? "Criando…" : "Criar Tabela"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ModalAddItem({ tabelaId, grupos, onClose, onAdded }) {
  const [search, setSearch]     = useState("");
  const [grupoSel, setGrupoSel] = useState(null);
  const [form, setForm]         = useState({
    preco_avista: "", preco_aprazo: "",
    tem_plus_size: false, preco_avista_plus: "", preco_aprazo_plus: "",
  });
  const [saving, setSaving]     = useState(false);
  const [err, setErr]           = useState(null);

  const filtered = search.trim().length >= 1
    ? grupos.filter((g) =>
        (g.codigo && g.codigo.toLowerCase().includes(search.toLowerCase())) ||
        g.nome.toLowerCase().includes(search.toLowerCase())
      ).slice(0, 10)
    : [];

  const toggleTemPlusSize = (checked) => {
    setForm((f) => ({
      ...f,
      tem_plus_size: checked,
      ...(checked ? {} : { preco_avista_plus: "", preco_aprazo_plus: "" }),
    }));
  };

  const handleSave = async () => {
    if (!grupoSel)                                { setErr("Selecione um produto."); return; }
    if (!form.preco_avista || !form.preco_aprazo)  { setErr("Informe os preços."); return; }
    setSaving(true); setErr(null);
    try {
      await addItemTabelaPreco(tabelaId, {
        grupo_id:          grupoSel.id,
        preco_avista:      parseFloat(form.preco_avista),
        preco_aprazo:      parseFloat(form.preco_aprazo),
        tem_plus_size:     form.tem_plus_size,
        preco_avista_plus: form.tem_plus_size && form.preco_avista_plus ? parseFloat(form.preco_avista_plus) : null,
        preco_aprazo_plus: form.tem_plus_size && form.preco_aprazo_plus ? parseFloat(form.preco_aprazo_plus) : null,
      });
      onAdded();
    } catch (e) {
      setErr(e.message);
      setSaving(false);
    }
  };

  return (
    <div className={styles.modalPillOverlay}>
      <div className={`${styles.modalPill} ${styles.modalPillWide}`}>
        <h3 className={styles.modalPillTitle}>Adicionar Produto</h3>

        {grupoSel ? (
          <div style={{ marginBottom: 16, padding: "10px 14px", background: "var(--sc-bg-secondary)", borderRadius: 10, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              {grupoSel.codigo && (
                <span className={styles.refBadge} style={{ display: "inline-block", marginBottom: 4 }}>
                  {grupoSel.codigo}
                </span>
              )}
              <div style={{ fontWeight: 600, fontSize: 14 }}>{grupoSel.nome}</div>
            </div>
            <button
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--sc-text-secondary)", textDecoration: "underline", fontSize: 13, padding: 0 }}
              onClick={() => { setGrupoSel(null); setSearch(""); }}
            >Trocar</button>
          </div>
        ) : (
          <div style={{ position: "relative", marginBottom: 16 }}>
            <label className={styles.field}>
              <span>Buscar por código ou nome</span>
              <input className={styles.input} value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Digite para buscar…" autoFocus />
            </label>
            {filtered.length > 0 && (
              <ul style={DROPDOWN_STYLE}>
                {filtered.map((g) => (
                  <li key={g.id} style={DROPDOWN_ITEM_STYLE}
                    onMouseDown={(e) => { e.preventDefault(); setGrupoSel(g); setSearch(""); }}>
                    {g.codigo ? <strong>{g.codigo}</strong> : null}
                    {g.codigo ? " · " : null}
                    {g.nome}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div style={{ display: "flex", gap: 12 }}>
          <label className={styles.field} style={{ flex: 1 }}>
            <span>Preço à vista (R$)</span>
            <input type="number" step="0.01" min="0" className={styles.input}
              value={form.preco_avista}
              onChange={(e) => setForm((f) => ({ ...f, preco_avista: e.target.value }))} />
          </label>
          <label className={styles.field} style={{ flex: 1 }}>
            <span>Preço a prazo (R$)</span>
            <input type="number" step="0.01" min="0" className={styles.input}
              value={form.preco_aprazo}
              onChange={(e) => setForm((f) => ({ ...f, preco_aprazo: e.target.value }))} />
          </label>
        </div>

        <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14, fontSize: 13, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={form.tem_plus_size}
            onChange={(e) => toggleTemPlusSize(e.target.checked)}
          />
          Esta referência possui tamanhos Plus Size (G1, G2, G3)
        </label>

        {form.tem_plus_size && (
          <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
            <label className={styles.field} style={{ flex: 1 }}>
              <span>Preço à vista Plus Size (R$)</span>
              <input type="number" step="0.01" min="0" className={styles.input}
                value={form.preco_avista_plus}
                onChange={(e) => setForm((f) => ({ ...f, preco_avista_plus: e.target.value }))} />
            </label>
            <label className={styles.field} style={{ flex: 1 }}>
              <span>Preço a prazo Plus Size (R$)</span>
              <input type="number" step="0.01" min="0" className={styles.input}
                value={form.preco_aprazo_plus}
                onChange={(e) => setForm((f) => ({ ...f, preco_aprazo_plus: e.target.value }))} />
            </label>
          </div>
        )}

        {err && <p className={styles.msgErro} style={{ marginTop: 10 }}>{err}</p>}

        <div className={styles.modalPillActions}>
          <button className={styles.btnPillSecondary} onClick={onClose}>Cancelar</button>
          <button className={styles.btnPillPrimary} onClick={handleSave} disabled={saving || !grupoSel}>
            {saving ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}
