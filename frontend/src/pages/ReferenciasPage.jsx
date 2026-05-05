import { useState, useEffect } from "react";
import React from "react";
import { referenciasApi, tabelasPrecoApi, gruposApi } from "../services/api";
import styles from "./ReferenciasPage.module.css";

const MODAL_VAZIO = { codigo: "", nome: "", tem_plus: false, grupo_id: "" };

export default function ReferenciasPage() {
  const [refs, setRefs]               = useState([]);
  const [grupos, setGrupos]           = useState([]);
  const [tabelas, setTabelas]         = useState([]);
  const [expandedId, setExpandedId]   = useState(null);
  const [precosMap, setPrecosMap]     = useState({});
  const [editPrecos, setEditPrecos]   = useState({});
  const [savingPrecos, setSavingPrecos] = useState(false);
  const [modal, setModal]             = useState(null);
  const [saving, setSaving]           = useState(false);
  const [erro, setErro]               = useState(null);

  const carregar = async () => {
    const [r, g, t] = await Promise.all([
      referenciasApi.list(),
      gruposApi.listar(),
      tabelasPrecoApi.list(),
    ]);
    setRefs(r || []);
    setGrupos(g || []);
    setTabelas((t || []).filter((tab) => tab.ativo));
  };

  useEffect(() => { carregar().catch(() => {}); }, []);

  const toggleExpand = async (ref) => {
    if (expandedId === ref.id) { setExpandedId(null); return; }
    setExpandedId(ref.id);
    if (!precosMap[ref.id]) {
      try {
        const precos = await referenciasApi.getPrecos(ref.id);
        const lista = precos || [];
        setPrecosMap((m) => ({ ...m, [ref.id]: lista }));
        const init = {};
        lista.forEach((p) => {
          init[p.tabela_id] = { a_vista: p.a_vista ?? "", a_prazo: p.a_prazo ?? "" };
        });
        setEditPrecos((e) => ({ ...e, [ref.id]: init }));
      } catch {}
    }
  };

  const handlePrecoChange = (refId, tabId, field, val) => {
    setEditPrecos((e) => ({
      ...e,
      [refId]: {
        ...(e[refId] || {}),
        [tabId]: { ...(e[refId]?.[tabId] || {}), [field]: val },
      },
    }));
  };

  const salvarPrecos = async (refId) => {
    setSavingPrecos(true);
    try {
      const ep = editPrecos[refId] || {};
      for (const tabId of tabelas.map((t) => t.id)) {
        const { a_vista = 0, a_prazo = 0 } = ep[tabId] || {};
        await referenciasApi.setPreco(refId, {
          tabela_id: tabId,
          a_vista:   parseFloat(a_vista)  || 0,
          a_prazo:   parseFloat(a_prazo)  || 0,
        });
      }
      const precos = await referenciasApi.getPrecos(refId);
      setPrecosMap((m) => ({ ...m, [refId]: precos || [] }));
    } finally {
      setSavingPrecos(false);
    }
  };

  const abrirModal = (ref = null) =>
    setModal(ref
      ? { id: ref.id, codigo: ref.codigo, nome: ref.nome || "", tem_plus: ref.tem_plus ?? false, grupo_id: ref.grupo_id || "" }
      : { ...MODAL_VAZIO }
    );

  const handleSalvar = async () => {
    if (!modal.codigo.trim()) { setErro("Código é obrigatório."); return; }
    setSaving(true); setErro(null);
    try {
      const payload = {
        codigo:    modal.codigo.trim(),
        nome:      modal.nome.trim(),
        tem_plus:  modal.tem_plus,
        grupo_id:  modal.grupo_id ? Number(modal.grupo_id) : null,
      };
      if (modal.id) await referenciasApi.update(modal.id, payload);
      else           await referenciasApi.create(payload);
      await carregar();
      setModal(null);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  const grupoNome = (gid) => grupos.find((g) => g.id === gid)?.nome ?? "—";

  const getEP = (refId, tabId) =>
    editPrecos[refId]?.[tabId] || { a_vista: "", a_prazo: "" };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Referências e Preços</h1>
        <button className={styles.btnPrimary} onClick={() => abrirModal()}>+ Nova Referência</button>
      </div>

      <div className={styles.card}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.thExpand} />
              <th>Código</th>
              <th>Nome</th>
              <th>Plus</th>
              <th>Grupo vinculado</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {refs.map((ref) => (
              <React.Fragment key={ref.id}>
                <tr
                  className={styles.refRow}
                  onClick={() => toggleExpand(ref)}
                >
                  <td className={styles.expandIcon}>
                    {expandedId === ref.id ? "▾" : "▸"}
                  </td>
                  <td><code className={styles.code}>{ref.codigo}</code></td>
                  <td>{ref.nome || "—"}</td>
                  <td>
                    <span className={ref.tem_plus ? styles.badgeSim : styles.badgeNao}>
                      {ref.tem_plus ? "Sim" : "Não"}
                    </span>
                  </td>
                  <td>{grupoNome(ref.grupo_id)}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button className={styles.btnLink} onClick={() => abrirModal(ref)}>Editar</button>
                  </td>
                </tr>

                {expandedId === ref.id && (
                  <tr className={styles.expandRow}>
                    <td colSpan={6} className={styles.expandCell}>
                      <div className={styles.precosWrap}>
                        <table className={styles.precosTable}>
                          <thead>
                            <tr>
                              <th>Tabela</th>
                              <th>À Vista (R$)</th>
                              <th>À Prazo (R$)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {tabelas.map((tab) => {
                              const ep = getEP(ref.id, tab.id);
                              return (
                                <tr key={tab.id}>
                                  <td>{tab.nome}</td>
                                  <td>
                                    <input
                                      className={styles.precoInput}
                                      type="number"
                                      step="0.01"
                                      placeholder="0,00"
                                      value={ep.a_vista}
                                      onChange={(e) =>
                                        handlePrecoChange(ref.id, tab.id, "a_vista", e.target.value)
                                      }
                                    />
                                  </td>
                                  <td>
                                    <input
                                      className={styles.precoInput}
                                      type="number"
                                      step="0.01"
                                      placeholder="0,00"
                                      value={ep.a_prazo}
                                      onChange={(e) =>
                                        handlePrecoChange(ref.id, tab.id, "a_prazo", e.target.value)
                                      }
                                    />
                                  </td>
                                </tr>
                              );
                            })}
                            {tabelas.length === 0 && (
                              <tr>
                                <td colSpan={3} className={styles.emptyPrecos}>
                                  Nenhuma tabela ativa.
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                        <div className={styles.precosSalvar}>
                          <button
                            className={styles.btnPrimary}
                            onClick={() => salvarPrecos(ref.id)}
                            disabled={savingPrecos}
                          >
                            {savingPrecos ? "Salvando…" : "Salvar preços desta referência"}
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
            {refs.length === 0 && (
              <tr>
                <td colSpan={6} className={styles.empty}>Nenhuma referência cadastrada.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className={styles.overlay} onClick={() => { setModal(null); setErro(null); }}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>{modal.id ? "Editar Referência" : "Nova Referência"}</h2>

            <label className={styles.field}>
              <span>Código *</span>
              <input
                className={styles.input}
                value={modal.codigo}
                onChange={(e) => setModal((m) => ({ ...m, codigo: e.target.value }))}
              />
            </label>

            <label className={styles.field}>
              <span>Nome</span>
              <input
                className={styles.input}
                value={modal.nome}
                onChange={(e) => setModal((m) => ({ ...m, nome: e.target.value }))}
              />
            </label>

            <div className={styles.toggleRow}>
              <span className={styles.toggleLabel}>Tem Plus</span>
              <button
                type="button"
                className={modal.tem_plus ? styles.toggleOn : styles.toggleOff}
                onClick={() => setModal((m) => ({ ...m, tem_plus: !m.tem_plus }))}
              >
                {modal.tem_plus ? "Sim" : "Não"}
              </button>
            </div>

            <label className={styles.field}>
              <span>Vincular a grupo de molde (opcional)</span>
              <select
                className={styles.input}
                value={modal.grupo_id}
                onChange={(e) => setModal((m) => ({ ...m, grupo_id: e.target.value }))}
              >
                <option value="">— Nenhum —</option>
                {grupos.map((g) => (
                  <option key={g.id} value={g.id}>{g.nome}</option>
                ))}
              </select>
            </label>

            {erro && <p className={styles.erro}>{erro}</p>}

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => { setModal(null); setErro(null); }}>
                Cancelar
              </button>
              <button className={styles.btnPrimary} onClick={handleSalvar} disabled={saving}>
                {saving ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
