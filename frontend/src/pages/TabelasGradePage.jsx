import { useState, useEffect, useCallback } from "react";
import * as tabelasGradeApi from "../api/tabelasGrade";
import { useAuth } from "../auth/useAuth";
import styles from "./TabelasGradePage.module.css";

const MODULO = "configuracoes_editar";

const TABELA_VAZIA = { codigo: "", descricao: "", situacao: "Ativa" };
const ITEM_VAZIO = { codigo_curto: "", descricao: "", ordem: 0, situacao: "Ativa" };

export default function TabelasGradePage() {
  const { hasPermission } = useAuth();
  const podeEditar = hasPermission(MODULO, "ver");

  const [tabelas, setTabelas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [itens, setItens] = useState([]);
  const [loadingItens, setLoadingItens] = useState(false);
  const [toast, setToast] = useState(null);

  const [modalTabela, setModalTabela] = useState(null); // { id?, codigo, descricao, situacao }
  const [savingTabela, setSavingTabela] = useState(false);
  const [erroTabela, setErroTabela] = useState(null);

  const [modalItem, setModalItem] = useState(null); // { id?, codigo_curto, descricao, ordem, situacao }
  const [savingItem, setSavingItem] = useState(false);
  const [erroItem, setErroItem] = useState(null);

  const carregarTabelas = useCallback(async () => {
    setLoading(true);
    try {
      setTabelas((await tabelasGradeApi.listar()) || []);
    } catch {
      setTabelas([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    carregarTabelas();
  }, [carregarTabelas]);

  const showToast = (text) => {
    setToast(text);
    setTimeout(() => setToast(null), 4000);
  };

  const carregarItens = async (tabelaId) => {
    setLoadingItens(true);
    try {
      setItens((await tabelasGradeApi.listarItens(tabelaId)) || []);
    } catch {
      setItens([]);
    } finally {
      setLoadingItens(false);
    }
  };

  const handleSelect = (tabela) => {
    setSelectedId(tabela.id);
    carregarItens(tabela.id);
  };

  const selectedTabela = tabelas.find((t) => t.id === selectedId) ?? null;

  // ── Tabela: criar/editar ──────────────────────────────────────────────

  const abrirNovaTabela = () => {
    setModalTabela({ ...TABELA_VAZIA });
    setErroTabela(null);
  };
  const abrirEditarTabela = (t) => {
    setModalTabela({ id: t.id, codigo: t.codigo, descricao: t.descricao, situacao: t.situacao });
    setErroTabela(null);
  };
  const fecharModalTabela = () => setModalTabela(null);

  const salvarTabela = async () => {
    if (!modalTabela.codigo.trim() || !modalTabela.descricao.trim()) {
      setErroTabela("Código e descrição são obrigatórios.");
      return;
    }
    setSavingTabela(true);
    setErroTabela(null);
    try {
      const payload = {
        codigo: modalTabela.codigo.trim(),
        descricao: modalTabela.descricao.trim(),
        situacao: modalTabela.situacao,
      };
      if (modalTabela.id) {
        await tabelasGradeApi.atualizar(modalTabela.id, payload);
      } else {
        await tabelasGradeApi.criar(payload);
      }
      await carregarTabelas();
      fecharModalTabela();
    } catch (e) {
      setErroTabela(e.message);
    } finally {
      setSavingTabela(false);
    }
  };

  const excluirTabela = async (tabela) => {
    if (!window.confirm(`Excluir a tabela "${tabela.descricao}"?`)) return;
    try {
      await tabelasGradeApi.excluir(tabela.id);
      if (selectedId === tabela.id) {
        setSelectedId(null);
        setItens([]);
      }
      await carregarTabelas();
    } catch (e) {
      showToast(e.message);
    }
  };

  // ── Item: criar/editar ────────────────────────────────────────────────

  const abrirNovoItem = () => {
    setModalItem({ ...ITEM_VAZIO });
    setErroItem(null);
  };
  const abrirEditarItem = (i) => {
    setModalItem({
      id: i.id,
      codigo_curto: i.codigo_curto,
      descricao: i.descricao,
      ordem: i.ordem,
      situacao: i.situacao,
    });
    setErroItem(null);
  };
  const fecharModalItem = () => setModalItem(null);

  const salvarItem = async () => {
    if (!modalItem.codigo_curto.trim() || !modalItem.descricao.trim()) {
      setErroItem("Código curto e descrição são obrigatórios.");
      return;
    }
    setSavingItem(true);
    setErroItem(null);
    try {
      const payload = {
        codigo_curto: modalItem.codigo_curto.trim().toUpperCase(),
        descricao: modalItem.descricao.trim(),
        ordem: Number(modalItem.ordem) || 0,
        situacao: modalItem.situacao,
      };
      if (modalItem.id) {
        await tabelasGradeApi.atualizarItem(selectedId, modalItem.id, payload);
      } else {
        await tabelasGradeApi.criarItem(selectedId, payload);
      }
      await carregarItens(selectedId);
      await carregarTabelas();
      fecharModalItem();
    } catch (e) {
      setErroItem(e.message);
    } finally {
      setSavingItem(false);
    }
  };

  const excluirItem = async (item) => {
    if (!window.confirm(`Excluir o item "${item.descricao}"?`)) return;
    try {
      await tabelasGradeApi.excluirItem(selectedId, item.id);
      await carregarItens(selectedId);
      await carregarTabelas();
    } catch (e) {
      showToast(e.message);
    }
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Tabelas da Grade</h1>
      </div>

      <div className={`sc-card ${styles.layout}`}>
        {/* ── Painel esquerdo — lista de tabelas ── */}
        <div className={styles.left}>
          <div className={styles.leftHeader}>
            <span className={styles.leftTitle}>Tabelas</span>
            {podeEditar && (
              <button className={styles.btnNovo} onClick={abrirNovaTabela}>
                + Nova Tabela
              </button>
            )}
          </div>

          {toast && (
            <p className={styles.msgErro} style={{ margin: "8px 10px" }}>
              {toast}
            </p>
          )}

          {loading ? (
            <p className={styles.emptyLeft}>Carregando…</p>
          ) : tabelas.length === 0 ? (
            <p className={styles.emptyLeft}>Nenhuma tabela cadastrada.</p>
          ) : (
            tabelas.map((t) => (
              <div
                key={t.id}
                className={`${styles.card} ${selectedId === t.id ? styles.cardSel : ""}`}
                onClick={() => handleSelect(t)}
              >
                <div className={styles.cardHead}>
                  <span className={styles.cardCodigo}>{t.codigo}</span>
                </div>
                <div className={styles.cardDescricao}>{t.descricao}</div>
                <div className={styles.cardMeta}>
                  <span className={styles.cardCount}>
                    {t.itens.length} ite{t.itens.length !== 1 ? "ns" : "m"}
                  </span>
                  <span
                    className={t.situacao === "Ativa" ? styles.badgeAtiva : styles.badgeInativa}
                  >
                    {t.situacao}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* ── Painel direito — itens da tabela selecionada ── */}
        <div className={styles.right}>
          {!selectedTabela ? (
            <div className={styles.emptyRight}>
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                <rect
                  x="6"
                  y="6"
                  width="28"
                  height="28"
                  rx="6"
                  stroke="var(--sc-border-strong)"
                  strokeWidth="2"
                />
                <path
                  d="M13 14h14M13 20h10M13 26h7"
                  stroke="var(--sc-border-strong)"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
              <p>Selecione uma tabela à esquerda</p>
            </div>
          ) : (
            <>
              <div className={styles.rightHeader}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                    <h3 className={styles.rightNome}>{selectedTabela.descricao}</h3>
                    <span
                      className={
                        selectedTabela.situacao === "Ativa"
                          ? styles.badgeAtiva
                          : styles.badgeInativa
                      }
                    >
                      {selectedTabela.situacao}
                    </span>
                  </div>
                </div>
                {podeEditar && (
                  <div className={styles.rightBtns}>
                    <button
                      className={styles.btnSecondary}
                      onClick={() => abrirEditarTabela(selectedTabela)}
                    >
                      Editar
                    </button>
                    <button
                      className={styles.btnSecondary}
                      onClick={() => excluirTabela(selectedTabela)}
                    >
                      Excluir
                    </button>
                    <button className={styles.btnNovo} onClick={abrirNovoItem}>
                      + Novo Item
                    </button>
                  </div>
                )}
              </div>

              {loadingItens ? (
                <p className={styles.emptyLeft}>Carregando…</p>
              ) : itens.length === 0 ? (
                <div className={styles.emptyRight} style={{ minHeight: 180 }}>
                  <p>Nenhum item cadastrado nesta tabela.</p>
                </div>
              ) : (
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th className={styles.th}>Código</th>
                      <th className={styles.th}>Cód. Curto</th>
                      <th className={styles.th}>Descrição</th>
                      <th className={styles.th}>Ordem</th>
                      <th className={styles.th}>Situação</th>
                      <th className={styles.th}>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {itens.map((i) => (
                      <tr key={i.id} className={styles.tr}>
                        <td className={`${styles.td} ${styles.tdMono}`}>{i.id}</td>
                        <td className={styles.td}>
                          <span className={styles.codigoCurtoBadge}>{i.codigo_curto}</span>
                        </td>
                        <td className={styles.td}>{i.descricao}</td>
                        <td className={styles.td}>{i.ordem}</td>
                        <td className={styles.td}>
                          <span
                            className={
                              i.situacao === "Ativa" ? styles.badgeAtiva : styles.badgeInativa
                            }
                          >
                            {i.situacao}
                          </span>
                        </td>
                        <td className={styles.td}>
                          {podeEditar && (
                            <div className={styles.actions}>
                              <button className={styles.btnLink} onClick={() => abrirEditarItem(i)}>
                                Editar
                              </button>
                              <button
                                className={`${styles.btnLink} ${styles.btnDanger}`}
                                onClick={() => excluirItem(i)}
                              >
                                Excluir
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Modal Nova/Editar Tabela ── */}
      {modalTabela && (
        <div className={styles.modalOverlay} onClick={fecharModalTabela}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h3 className={styles.modalTitle}>
              {modalTabela.id ? "Editar Tabela" : "Nova Tabela"}
            </h3>

            <label className={styles.field}>
              <span>Código *</span>
              <input
                className={styles.input}
                value={modalTabela.codigo}
                onChange={(e) => setModalTabela((m) => ({ ...m, codigo: e.target.value }))}
                placeholder="Ex.: 001"
                autoFocus
              />
            </label>

            <label className={styles.field}>
              <span>Descrição *</span>
              <input
                className={styles.input}
                value={modalTabela.descricao}
                onChange={(e) =>
                  setModalTabela((m) => ({ ...m, descricao: e.target.value.toUpperCase() }))
                }
                placeholder="Ex.: COR"
              />
            </label>

            <label className={styles.field}>
              <span>Situação</span>
              <select
                className={styles.input}
                value={modalTabela.situacao}
                onChange={(e) => setModalTabela((m) => ({ ...m, situacao: e.target.value }))}
              >
                <option value="Ativa">Ativa</option>
                <option value="Inativa">Inativa</option>
              </select>
            </label>

            {erroTabela && <p className={styles.msgErro}>{erroTabela}</p>}

            <div className={styles.modalActions}>
              <button
                className={styles.btnPillSecondary}
                onClick={fecharModalTabela}
                disabled={savingTabela}
              >
                Cancelar
              </button>
              <button className={styles.btnPrimary} onClick={salvarTabela} disabled={savingTabela}>
                {savingTabela ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal Novo/Editar Item ── */}
      {modalItem && (
        <div className={styles.modalOverlay} onClick={fecharModalItem}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h3 className={styles.modalTitle}>{modalItem.id ? "Editar Item" : "Novo Item"}</h3>

            <label className={styles.field}>
              <span>Código Curto *</span>
              <input
                className={styles.input}
                value={modalItem.codigo_curto}
                maxLength={4}
                onChange={(e) =>
                  setModalItem((m) => ({ ...m, codigo_curto: e.target.value.toUpperCase() }))
                }
                placeholder="Ex.: AZU"
                autoFocus
              />
              <span className={styles.hint}>
                Máx. 4 caracteres — usado na geração de código do produto (ex: AZU, VRM, M, GG)
              </span>
            </label>

            <label className={styles.field}>
              <span>Descrição *</span>
              <input
                className={styles.input}
                value={modalItem.descricao}
                onChange={(e) =>
                  setModalItem((m) => ({ ...m, descricao: e.target.value.toUpperCase() }))
                }
                placeholder="Ex.: AZUL BIC"
              />
            </label>

            <label className={styles.field}>
              <span>Ordem</span>
              <input
                type="number"
                className={styles.input}
                value={modalItem.ordem}
                onChange={(e) => setModalItem((m) => ({ ...m, ordem: e.target.value }))}
              />
            </label>

            <label className={styles.field}>
              <span>Situação</span>
              <select
                className={styles.input}
                value={modalItem.situacao}
                onChange={(e) => setModalItem((m) => ({ ...m, situacao: e.target.value }))}
              >
                <option value="Ativa">Ativa</option>
                <option value="Inativa">Inativa</option>
              </select>
            </label>

            {erroItem && <p className={styles.msgErro}>{erroItem}</p>}

            <div className={styles.modalActions}>
              <button
                className={styles.btnPillSecondary}
                onClick={fecharModalItem}
                disabled={savingItem}
              >
                Cancelar
              </button>
              <button className={styles.btnPrimary} onClick={salvarItem} disabled={savingItem}>
                {savingItem ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
