import { useState, useEffect, useRef } from "react";
import {
  getCompras, createCompra, getCompra, uploadAnexo,
  updateCompra, deleteCompra,
} from "../../api/financeiro";
import FormularioCompraVenda from "./FormularioCompraVenda";
import ImportarXMLModal from "./ImportarXMLModal";
import styles from "./comprasVendas.module.css";

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const dataFmt = (iso) => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("T")[0].split("-");
  return `${d}/${m}/${y}`;
};

const STATUS_LABELS = { PAGO: "Pago", PENDENTE: "Pendente", CANCELADO: "Cancelado" };

function statusGeral(item) {
  const parcelas = item.parcelas || item.lancamentos || [];
  let total, pagas;
  if (parcelas.length > 0) {
    total = parcelas.length;
    pagas = parcelas.filter((p) => p.status === "PAGO").length;
  } else {
    total = item.num_parcelas ?? 0;
    pagas = item.parcelas_pagas ?? 0;
  }
  if (total === 0) return { label: "—",        cls: "stPendente" };
  if (pagas === total) return { label: "Quitado", cls: "stQuitado"  };
  if (pagas > 0)  return { label: `${pagas}/${total} pagas`, cls: "stParcial"  };
  return { label: "Pendente", cls: "stPendente" };
}

function extractParcelas(obj) {
  return obj.parcelas || obj.lancamentos || [];
}

export default function ComprasFinanceiro() {
  const [compras,       setCompras]       = useState([]);
  const [loading,       setLoading]       = useState(false);
  const [expandedId,    setExpandedId]    = useState(null);
  const [expandedData,  setExpandedData]  = useState({});
  const [loadingExpand, setLoadingExpand] = useState(false);
  const [modal,         setModal]         = useState(false);
  const [saving,        setSaving]        = useState(false);
  const [erro,          setErro]          = useState(null);

  // Edit
  const [modalEditar,    setModalEditar]    = useState(false);
  const [editandoCompra, setEditandoCompra] = useState(null);
  const [editForm,       setEditForm]       = useState({});
  const [savingEdit,     setSavingEdit]     = useState(false);
  const [erroEdit,       setErroEdit]       = useState(null);

  // Delete
  const [modalExcluir,    setModalExcluir]    = useState(false);
  const [excluindoCompra, setExcluindoCompra] = useState(null);
  const [deleting,        setDeleting]        = useState(false);
  const [erroExcluir,     setErroExcluir]     = useState(null);

  // Importar XML
  const fileInputRef = useRef(null);
  const [arquivosXml,    setArquivosXml]    = useState(null);
  const [modalImportar,  setModalImportar]  = useState(false);
  const [resultadoImport, setResultadoImport] = useState(null);

  const recarregarCompras = () => {
    setLoading(true);
    getCompras()
      .then((c) => setCompras(c || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    recarregarCompras();
  }, []);

  // ── Importar XML ──────────────────────────────────────────────────────────
  const handleAbrirSeletorXml = () => fileInputRef.current?.click();

  const handleArquivosSelecionados = (e) => {
    const arquivos = Array.from(e.target.files || []);
    e.target.value = "";
    if (arquivos.length === 0) return;
    setArquivosXml(arquivos);
    setResultadoImport(null);
    setModalImportar(true);
  };

  const handleConcluirImportacao = (sucesso, falhas) => {
    setModalImportar(false);
    setArquivosXml(null);
    setResultadoImport({ sucesso, falhas });
    if (sucesso > 0) recarregarCompras();
  };

  // ── Expand row ────────────────────────────────────────────────────────────
  const handleExpand = async (id) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    if (expandedData[id]) return;
    setLoadingExpand(true);
    try {
      const data = await getCompra(id);
      setExpandedData((prev) => ({ ...prev, [id]: data }));
    } catch {}
    setLoadingExpand(false);
  };

  // ── Criar compra ──────────────────────────────────────────────────────────
  const handleSalvar = async (formData, nfFile, boletos) => {
    if (!formData.fornecedor?.trim()) { setErro("Informe o fornecedor."); return; }
    if (!formData.valor_total || isNaN(formData.valor_total)) {
      setErro("Informe o valor total."); return;
    }
    if (!formData.primeiro_vencimento) { setErro("Informe o primeiro vencimento."); return; }

    setSaving(true);
    setErro(null);
    try {
      const criada = await createCompra(formData);

      let full = criada;
      if (extractParcelas(criada).length === 0 && criada.id) {
        full = await getCompra(criada.id);
      }
      const parcelas = extractParcelas(full);

      if (nfFile && parcelas.length > 0) {
        await Promise.all(
          parcelas.map((p) => uploadAnexo(p.id, nfFile, "NF").catch(() => {}))
        );
      }

      for (let i = 0; i < boletos.length; i++) {
        if (boletos[i] && parcelas[i]) {
          await uploadAnexo(parcelas[i].id, boletos[i], "BOLETO").catch(() => {});
        }
      }

      setCompras((prev) => [full, ...prev]);
      setExpandedData((prev) => ({ ...prev, [full.id]: full }));
      setModal(false);
    } catch (e) {
      setErro(e.message || "Erro ao criar compra.");
    }
    setSaving(false);
  };

  // ── Editar compra ─────────────────────────────────────────────────────────
  const handleAbrirEditar = (e, compra) => {
    e.stopPropagation();
    setEditandoCompra(compra);
    setEditForm({
      fornecedor:  compra.fornecedor  || "",
      descricao:   compra.descricao   || "",
      valor_total: compra.valor_total || "",
      data_compra: (compra.data_compra || "").split("T")[0],
    });
    setErroEdit(null);
    setModalEditar(true);
  };

  const setEF = (key) => (e) => setEditForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSalvarEdicao = async () => {
    setSavingEdit(true);
    setErroEdit(null);
    try {
      const dados = {
        fornecedor:  editForm.fornecedor.trim() || undefined,
        descricao:   editForm.descricao.trim()  || null,
        valor_total: parseFloat(editForm.valor_total) || undefined,
        data_compra: editForm.data_compra       || undefined,
      };
      const atualizada = await updateCompra(editandoCompra.id, dados);
      setCompras((prev) => prev.map((c) => (c.id === atualizada.id ? { ...c, ...atualizada } : c)));
      setModalEditar(false);
    } catch (e) {
      setErroEdit(e.message || "Erro ao salvar alterações.");
    }
    setSavingEdit(false);
  };

  // ── Excluir compra ────────────────────────────────────────────────────────
  const handleAbrirExcluir = (e, compra) => {
    e.stopPropagation();
    setExcluindoCompra(compra);
    setErroExcluir(null);
    setModalExcluir(true);
  };

  const handleConfirmarExclusao = async () => {
    setDeleting(true);
    setErroExcluir(null);
    try {
      await deleteCompra(excluindoCompra.id);
      setCompras((prev) => prev.filter((c) => c.id !== excluindoCompra.id));
      setModalExcluir(false);
    } catch (e) {
      setErroExcluir(e.message || "Erro ao excluir compra.");
    }
    setDeleting(false);
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className={styles.page}>

      <div className={styles.header}>
        <h1 className={styles.title}>Compras</h1>
        <div className={styles.headerActions}>
          <button className={styles.btnSecondary} onClick={handleAbrirSeletorXml}>
            Importar XMLs
          </button>
          <button className={styles.btnPrimary} onClick={() => { setModal(true); setErro(null); }}>
            + Nova Compra
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xml"
          multiple
          style={{ display: "none" }}
          onChange={handleArquivosSelecionados}
        />
      </div>

      {resultadoImport && (
        <p className={styles.importResultMsg}>
          {resultadoImport.sucesso} compra(s) importada(s) com sucesso.
          {resultadoImport.falhas > 0 && ` ${resultadoImport.falhas} falharam.`}
        </p>
      )}

      <div className={styles.card}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Fornecedor</th>
              <th>Data</th>
              <th>Valor Total</th>
              <th>Parcelas</th>
              <th>Status Geral</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {compras.map((c) => {
              const st      = statusGeral(c);
              const isOpen  = expandedId === c.id;
              const cached  = expandedData[c.id];
              const parcelas = cached ? extractParcelas(cached) : [];

              return [
                <tr
                  key={c.id}
                  className={styles.trClickable}
                  onClick={() => handleExpand(c.id)}
                >
                  <td title={c.fornecedor}>{c.fornecedor || "—"}</td>
                  <td>{dataFmt(c.data_emissao || c.created_at)}</td>
                  <td className={styles.tdValor}>{moeda(c.valor_total)}</td>
                  <td>
                    {(c.num_parcelas ?? extractParcelas(c).length) > 0
                      ? `${c.num_parcelas ?? extractParcelas(c).length}x`
                      : "—"}
                  </td>
                  <td>
                    <span className={`${styles.badge} ${styles[st.cls]}`}>{st.label}</span>
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className={styles.rowActions}>
                      <button
                        className={`${styles.btnExpand} ${isOpen ? styles.btnExpandOpen : ""}`}
                        onClick={() => handleExpand(c.id)}
                        title={isOpen ? "Recolher" : "Ver parcelas"}
                      >
                        ▶
                      </button>
                      <button
                        className={styles.btnIconEdit}
                        onClick={(e) => handleAbrirEditar(e, c)}
                        title="Editar compra"
                      >
                        ✎
                      </button>
                      <button
                        className={styles.btnIconDelete}
                        onClick={(e) => handleAbrirExcluir(e, c)}
                        title="Excluir compra"
                      >
                        ✕
                      </button>
                    </div>
                  </td>
                </tr>,

                isOpen && (
                  <tr key={`expand-${c.id}`} className={styles.expandRow}>
                    <td colSpan={6}>
                      <div className={styles.expandCell}>
                        {loadingExpand && !cached ? (
                          <p className={styles.expandLoading}>Carregando parcelas…</p>
                        ) : parcelas.length === 0 ? (
                          <p className={styles.expandLoading}>Nenhuma parcela encontrada.</p>
                        ) : (
                          <>
                            <p className={styles.parcelasTitle}>Parcelas</p>
                            <table className={styles.parcelasTable}>
                              <thead>
                                <tr>
                                  <th>#</th>
                                  <th>Vencimento</th>
                                  <th>Valor</th>
                                  <th>Status</th>
                                  <th>Pago em</th>
                                </tr>
                              </thead>
                              <tbody>
                                {parcelas.map((p, idx) => (
                                  <tr key={p.id}>
                                    <td>{p.parcela_num ?? p.numero_parcela ?? idx + 1}</td>
                                    <td>{dataFmt(p.vencimento)}</td>
                                    <td>{moeda(p.valor)}</td>
                                    <td>
                                      <span className={`${styles.badge} ${styles["st" + (p.status || "PENDENTE")]}`}>
                                        {STATUS_LABELS[p.status] || p.status || "Pendente"}
                                      </span>
                                    </td>
                                    <td>{dataFmt(p.data_pagamento)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ),
              ];
            })}

            {compras.length === 0 && (
              <tr>
                <td colSpan={6} className={styles.empty}>
                  {loading ? "Carregando…" : "Nenhuma compra cadastrada."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* ── Modal: Nova Compra ── */}
      {modal && (
        <div className={styles.overlay} onClick={() => !saving && setModal(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <FormularioCompraVenda
              tipo="compra"
              saving={saving}
              erro={erro}
              onSalvar={handleSalvar}
              onFechar={() => !saving && setModal(false)}
            />
          </div>
        </div>
      )}

      {/* ── Modal: Editar Compra ── */}
      {modalEditar && editandoCompra && (
        <div className={styles.overlay} onClick={() => !savingEdit && setModalEditar(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Editar Compra</h2>
              <button
                className={styles.btnClose}
                onClick={() => !savingEdit && setModalEditar(false)}
                disabled={savingEdit}
              >
                ×
              </button>
            </div>

            <div className={styles.modalBody}>
              <div className={styles.fieldGrid}>
                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Fornecedor *</span>
                  <input
                    className={styles.input}
                    value={editForm.fornecedor}
                    onChange={setEF("fornecedor")}
                  />
                </label>
                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Descrição</span>
                  <input
                    className={styles.input}
                    value={editForm.descricao}
                    onChange={setEF("descricao")}
                    placeholder="Descrição opcional"
                  />
                </label>
                <label className={styles.field}>
                  <span>Valor Total</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className={styles.input}
                    value={editForm.valor_total}
                    onChange={setEF("valor_total")}
                  />
                </label>
                <label className={styles.field}>
                  <span>Data da Compra</span>
                  <input
                    type="date"
                    className={styles.input}
                    value={editForm.data_compra}
                    onChange={setEF("data_compra")}
                  />
                </label>
              </div>
              {erroEdit && <p className={styles.erro}>{erroEdit}</p>}
            </div>

            <div className={styles.modalActions}>
              <button
                className={styles.btnSecondary}
                onClick={() => setModalEditar(false)}
                disabled={savingEdit}
              >
                Cancelar
              </button>
              <button
                className={styles.btnPrimary}
                onClick={handleSalvarEdicao}
                disabled={savingEdit}
              >
                {savingEdit ? "Salvando…" : "Salvar Alterações"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Confirmar Exclusão ── */}
      {modalExcluir && excluindoCompra && (
        <div className={styles.overlay} onClick={() => !deleting && setModalExcluir(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Excluir Compra</h2>
              <button
                className={styles.btnClose}
                onClick={() => !deleting && setModalExcluir(false)}
                disabled={deleting}
              >
                ×
              </button>
            </div>

            <div className={styles.modalBody}>
              <p className={styles.confirmText}>
                Tem certeza que deseja excluir a compra de{" "}
                <strong>{excluindoCompra.fornecedor}</strong>?{" "}
                Esta ação não pode ser desfeita.
              </p>
              {erroExcluir && <p className={styles.erro}>{erroExcluir}</p>}
            </div>

            <div className={styles.modalActions}>
              <button
                className={styles.btnSecondary}
                onClick={() => setModalExcluir(false)}
                disabled={deleting}
              >
                Cancelar
              </button>
              <button
                className={styles.btnDanger}
                onClick={handleConfirmarExclusao}
                disabled={deleting}
              >
                {deleting ? "Excluindo…" : "Excluir"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Importar XMLs ── */}
      {modalImportar && arquivosXml && (
        <ImportarXMLModal
          arquivos={arquivosXml}
          onFechar={() => { setModalImportar(false); setArquivosXml(null); }}
          onConcluido={handleConcluirImportacao}
        />
      )}
    </div>
  );
}
