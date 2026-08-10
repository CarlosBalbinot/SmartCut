import { useState, useEffect, useRef } from "react";
import {
  getVendasFinanceiras, createVendaFinanceira, getVendaFinanceira, uploadAnexo,
  updateVendaFinanceira, deleteVendaFinanceira,
  createLancamento, updateLancamento, deleteLancamento,
  downloadAnexo, deleteAnexo,
  importarLoteVendas, importarVendaFinal,
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

const STATUS_LABELS = { PAGO: "Recebido", PENDENTE: "Pendente", CANCELADO: "Cancelado" };

function statusGeralInfo(total, pagas) {
  if (total === 0) return { label: "—",        cls: "stPendente" };
  if (pagas === total) return { label: "Quitado", cls: "stQuitado"  };
  if (pagas > 0)  return { label: `${pagas}/${total} recebidas`, cls: "stParcial"  };
  return { label: "Pendente", cls: "stPendente" };
}

function extractParcelas(obj) {
  return obj.parcelas || obj.lancamentos || [];
}

// Resolve total/pagas na melhor fonte disponível: parcelas já carregadas no
// próprio item (criação/edição), parcelas em cache (linha expandida) ou, por
// último, o count vindo do backend (sempre presente na listagem).
function contarParcelas(item, cached) {
  const arr = cached ? extractParcelas(cached) : extractParcelas(item);
  if (arr.length > 0) {
    return { total: arr.length, pagas: arr.filter((p) => p.status === "PAGO").length };
  }
  return { total: item.total_parcelas ?? 0, pagas: item.parcelas_pagas ?? 0 };
}

function parcelaStatusInfo(p) {
  if (p.status === "PAGO") return { label: "Recebido", cls: "stPAGO" };
  if (p.status === "CANCELADO") return { label: "Cancelado", cls: "stCANCELADO" };
  const venc = (p.data_vencimento || "").split("T")[0];
  if (venc) {
    const [y, m, d] = venc.split("-").map(Number);
    const hoje = new Date();
    const hojeDia = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
    const vencDia = new Date(y, m - 1, d);
    if (vencDia < hojeDia) return { label: "Atrasado", cls: "stATRASADO" };
  }
  return { label: "Pendente", cls: "stPENDENTE" };
}

export default function VendasFinanceiro() {
  const [vendas,        setVendas]        = useState([]);
  const [loading,       setLoading]       = useState(false);
  const [expandedId,    setExpandedId]    = useState(null);
  const [expandedData,  setExpandedData]  = useState({});
  const [loadingExpand, setLoadingExpand] = useState(false);
  const [modal,         setModal]         = useState(false);
  const [saving,        setSaving]        = useState(false);
  const [erro,          setErro]          = useState(null);

  // Edit
  const [modalEditar,    setModalEditar]    = useState(false);
  const [editandoVenda,  setEditandoVenda]  = useState(null);
  const [editForm,       setEditForm]       = useState({});
  const [savingEdit,     setSavingEdit]     = useState(false);
  const [erroEdit,       setErroEdit]       = useState(null);

  // Edit — parcelas e anexos
  const [editParcelas,        setEditParcelas]        = useState([]);
  const [parcelasRemovidas,   setParcelasRemovidas]   = useState([]);
  const [loadingEditParcelas, setLoadingEditParcelas]  = useState(false);

  // Delete
  const [modalExcluir,    setModalExcluir]    = useState(false);
  const [excluindoVenda,  setExcluindoVenda]  = useState(null);
  const [deleting,        setDeleting]        = useState(false);
  const [erroExcluir,     setErroExcluir]     = useState(null);

  // Importar XML
  const fileInputRef = useRef(null);
  const [arquivosXml,    setArquivosXml]    = useState(null);
  const [modalImportar,  setModalImportar]  = useState(false);
  const [resultadoImport, setResultadoImport] = useState(null);

  const recarregarVendas = () => {
    setLoading(true);
    getVendasFinanceiras()
      .then((v) => setVendas(v || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    recarregarVendas();
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
    if (sucesso > 0) recarregarVendas();
  };

  // ── Expand row ────────────────────────────────────────────────────────────
  const handleExpand = async (id) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    if (expandedData[id]) return;
    setLoadingExpand(true);
    try {
      const data = await getVendaFinanceira(id);
      setExpandedData((prev) => ({ ...prev, [id]: data }));
    } catch {}
    setLoadingExpand(false);
  };

  // ── Criar venda ───────────────────────────────────────────────────────────
  const handleSalvar = async (formData, nfFile, boletos) => {
    if (!formData.cliente?.trim()) { setErro("Informe o cliente."); return; }
    if (!formData.valor_total || isNaN(formData.valor_total)) {
      setErro("Informe o valor total."); return;
    }
    if (!formData.primeiro_vencimento) { setErro("Informe o primeiro vencimento."); return; }

    setSaving(true);
    setErro(null);
    try {
      const criada = await createVendaFinanceira(formData);

      let full = criada;
      if (extractParcelas(criada).length === 0 && criada.id) {
        full = await getVendaFinanceira(criada.id);
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

      setVendas((prev) => [full, ...prev]);
      setExpandedData((prev) => ({ ...prev, [full.id]: full }));
      setModal(false);
    } catch (e) {
      setErro(e.message || "Erro ao criar venda.");
    }
    setSaving(false);
  };

  // ── Editar venda ──────────────────────────────────────────────────────────
  const handleAbrirEditar = async (e, venda) => {
    e.stopPropagation();
    setEditandoVenda(venda);
    setEditForm({
      cliente:     venda.cliente     || "",
      descricao:   venda.descricao   || "",
      valor_total: venda.valor_total || "",
      data_venda:  (venda.data_venda || "").split("T")[0],
    });
    setErroEdit(null);
    setEditParcelas([]);
    setParcelasRemovidas([]);
    setModalEditar(true);
    setLoadingEditParcelas(true);
    try {
      const full = await getVendaFinanceira(venda.id);
      setExpandedData((prev) => ({ ...prev, [venda.id]: full }));
      const parcelas = extractParcelas(full)
        .slice()
        .sort((a, b) => (a.parcela_numero ?? 0) - (b.parcela_numero ?? 0))
        .map((p) => ({
          key: p.id,
          id: p.id,
          parcela_numero: p.parcela_numero,
          vencimento: (p.data_vencimento || "").split("T")[0],
          valor: String(p.valor ?? ""),
          status: p.status,
          anexos: p.anexos || [],
        }));
      setEditParcelas(parcelas);
    } catch (err) {
      setErroEdit(err.message || "Erro ao carregar parcelas.");
    }
    setLoadingEditParcelas(false);
  };

  const setEF = (key) => (e) => setEditForm((f) => ({ ...f, [key]: e.target.value }));

  const updateEditParcela = (key, campo) => (e) => {
    const valor = e.target.value;
    setEditParcelas((prev) => prev.map((p) => (p.key === key ? { ...p, [campo]: valor } : p)));
  };

  const addEditParcela = () => {
    setEditParcelas((prev) => [
      ...prev,
      { key: `novo-${Date.now()}-${prev.length}`, id: null, parcela_numero: null, vencimento: "", valor: "", status: "PENDENTE", anexos: [] },
    ]);
  };

  const removeEditParcela = (parcela) => {
    if (parcela.status === "PAGO") return;
    if (parcela.id) setParcelasRemovidas((prev) => [...prev, parcela.id]);
    setEditParcelas((prev) => prev.filter((p) => p.key !== parcela.key));
  };

  const handleUploadAnexoParcela = async (parcela, file, tipo) => {
    if (!parcela.id || !file) return;
    try {
      const anexo = await uploadAnexo(parcela.id, file, tipo);
      setEditParcelas((prev) => prev.map((p) => (
        p.key === parcela.key ? { ...p, anexos: [...(p.anexos || []), anexo] } : p
      )));
    } catch (err) {
      setErroEdit(err.message || "Erro ao anexar arquivo.");
    }
  };

  const handleRemoverAnexo = async (parcela, anexo) => {
    try {
      await deleteAnexo(anexo.id);
      setEditParcelas((prev) => prev.map((p) => (
        p.key === parcela.key ? { ...p, anexos: (p.anexos || []).filter((a) => a.id !== anexo.id) } : p
      )));
    } catch (err) {
      setErroEdit(err.message || "Erro ao remover anexo.");
    }
  };

  const handleDownloadAnexo = async (anexo) => {
    try {
      const blob = await downloadAnexo(anexo.id);
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = anexo.nome_original || "anexo";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {}
  };

  const handleSalvarEdicao = async () => {
    if (editParcelas.length === 0) {
      setErroEdit("Inclua ao menos uma parcela.");
      return;
    }
    const parcelaInvalida = editParcelas.some(
      (p) => !p.vencimento || !p.valor || isNaN(parseFloat(p.valor)) || parseFloat(p.valor) <= 0
    );
    if (parcelaInvalida) {
      setErroEdit("Preencha data de vencimento e valor em todas as parcelas.");
      return;
    }

    setSavingEdit(true);
    setErroEdit(null);
    try {
      const dados = {
        cliente:     editForm.cliente.trim() || undefined,
        descricao:   editForm.descricao.trim()  || null,
        valor_total: parseFloat(editForm.valor_total) || undefined,
        data_venda:  editForm.data_venda       || undefined,
      };
      await updateVendaFinanceira(editandoVenda.id, dados);

      for (const id of parcelasRemovidas) {
        await deleteLancamento(id).catch(() => {});
      }

      const descricaoBase = dados.descricao || dados.cliente || editandoVenda.cliente;
      for (const p of editParcelas) {
        if (p.id) {
          await updateLancamento(p.id, {
            data_vencimento: p.vencimento,
            valor: parseFloat(p.valor),
          });
        } else {
          await createLancamento({
            tipo: "RECEBER",
            descricao: descricaoBase,
            valor: parseFloat(p.valor),
            data_vencimento: p.vencimento,
            venda_id: editandoVenda.id,
          });
        }
      }

      const full = await getVendaFinanceira(editandoVenda.id);
      setVendas((prev) => prev.map((v) => (v.id === full.id ? { ...v, ...full } : v)));
      setExpandedData((prev) => ({ ...prev, [full.id]: full }));
      setModalEditar(false);
    } catch (e) {
      setErroEdit(e.message || "Erro ao salvar alterações.");
    }
    setSavingEdit(false);
  };

  // ── Excluir venda ─────────────────────────────────────────────────────────
  const handleAbrirExcluir = (e, venda) => {
    e.stopPropagation();
    setExcluindoVenda(venda);
    setErroExcluir(null);
    setModalExcluir(true);
  };

  const handleConfirmarExclusao = async () => {
    setDeleting(true);
    setErroExcluir(null);
    try {
      await deleteVendaFinanceira(excluindoVenda.id);
      setVendas((prev) => prev.filter((v) => v.id !== excluindoVenda.id));
      setModalExcluir(false);
    } catch (e) {
      setErroExcluir(e.message || "Erro ao excluir venda.");
    }
    setDeleting(false);
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className={styles.page}>

      <div className={styles.header}>
        <h1 className={styles.title}>Vendas — Contas a Receber</h1>
        <div className={styles.headerActions}>
          <button className={styles.btnSecondary} onClick={handleAbrirSeletorXml}>
            Importar XMLs
          </button>
          <button className={styles.btnPrimary} onClick={() => { setModal(true); setErro(null); }}>
            + Nova Venda
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
          {resultadoImport.sucesso} venda(s) importada(s) com sucesso.
          {resultadoImport.falhas > 0 && ` ${resultadoImport.falhas} falharam.`}
        </p>
      )}

      <div className={styles.card}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Cliente</th>
              <th>Data</th>
              <th>Valor Total</th>
              <th>Parcelas</th>
              <th>Status Geral</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {vendas.map((v) => {
              const isOpen  = expandedId === v.id;
              const cached  = expandedData[v.id];
              const parcelas = cached ? extractParcelas(cached) : [];
              const { total: totalParcelas, pagas: parcelasPagas } = contarParcelas(v, cached);
              const st = statusGeralInfo(totalParcelas, parcelasPagas);

              return [
                <tr
                  key={v.id}
                  className={styles.trClickable}
                  onClick={() => handleExpand(v.id)}
                >
                  <td title={v.cliente}>
                    <div className={styles.fornecedorCell}>
                      <span className={styles.fornecedorNome}>{v.cliente || "—"}</span>
                      {v.descricao && <span className={styles.fornecedorSub}>{v.descricao}</span>}
                    </div>
                  </td>
                  <td>
                    <div className={styles.dataCell}>
                      <span>NF: {dataFmt(v.data_venda)}</span>
                      <span className={styles.dataCellSub}>Import.: {dataFmt(v.created_at)}</span>
                    </div>
                  </td>
                  <td className={styles.tdValor}>{moeda(v.valor_total)}</td>
                  <td>{totalParcelas > 0 ? `${totalParcelas}x` : "—"}</td>
                  <td>
                    <span className={`${styles.badge} ${styles[st.cls]}`}>{st.label}</span>
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className={styles.rowActions}>
                      <button
                        className={`${styles.btnExpand} ${isOpen ? styles.btnExpandOpen : ""}`}
                        onClick={() => handleExpand(v.id)}
                        title={isOpen ? "Recolher" : "Ver parcelas"}
                      >
                        ▶
                      </button>
                      <button
                        className={styles.btnEditar}
                        onClick={(e) => handleAbrirEditar(e, v)}
                        title="Editar"
                      >
                        <span aria-hidden="true">✎</span> Editar
                      </button>
                      <button
                        className={styles.btnIconDelete}
                        onClick={(e) => handleAbrirExcluir(e, v)}
                        title="Excluir"
                      >
                        ✕
                      </button>
                    </div>
                  </td>
                </tr>,

                isOpen && (
                  <tr key={`expand-${v.id}`} className={styles.expandRow}>
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
                                  <th>Recebido em</th>
                                </tr>
                              </thead>
                              <tbody>
                                {parcelas.map((p, idx) => {
                                  const pst = parcelaStatusInfo(p);
                                  return (
                                    <tr key={p.id}>
                                      <td>{p.parcela_numero ?? idx + 1}</td>
                                      <td>{dataFmt(p.data_vencimento)}</td>
                                      <td>{moeda(p.valor)}</td>
                                      <td>
                                        <span className={`${styles.badge} ${styles[pst.cls]}`}>
                                          {pst.label}
                                        </span>
                                      </td>
                                      <td>{dataFmt(p.data_pagamento)}</td>
                                    </tr>
                                  );
                                })}
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

            {vendas.length === 0 && (
              <tr>
                <td colSpan={6} className={styles.empty}>
                  {loading ? "Carregando…" : "Nenhuma venda cadastrada."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* ── Modal: Nova Venda ── */}
      {modal && (
        <div className={styles.overlay} onClick={() => !saving && setModal(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <FormularioCompraVenda
              tipo="venda"
              saving={saving}
              erro={erro}
              onSalvar={handleSalvar}
              onFechar={() => !saving && setModal(false)}
            />
          </div>
        </div>
      )}

      {/* ── Modal: Editar Venda ── */}
      {modalEditar && editandoVenda && (
        <div className={styles.overlay} onClick={() => !savingEdit && setModalEditar(false)}>
          <div className={`${styles.modal} ${styles.modalLarge}`} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Editar Venda</h2>
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
                  <span>Cliente *</span>
                  <input
                    className={styles.input}
                    value={editForm.cliente}
                    onChange={setEF("cliente")}
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
                  <span>Data da Venda</span>
                  <input
                    type="date"
                    className={styles.input}
                    value={editForm.data_venda}
                    onChange={setEF("data_venda")}
                  />
                </label>
              </div>

              {/* ── Parcelas ── */}
              <div className={styles.uploadSection}>
                <div className={styles.parcelasEditHeader}>
                  <p className={styles.uploadSectionLabel} style={{ margin: 0 }}>Parcelas</p>
                  <button type="button" className={styles.btnAddParcela} onClick={addEditParcela}>
                    + Adicionar Parcela
                  </button>
                </div>
                {loadingEditParcelas ? (
                  <p className={styles.expandLoading}>Carregando parcelas…</p>
                ) : editParcelas.length === 0 ? (
                  <p className={styles.expandLoading}>Nenhuma parcela.</p>
                ) : (
                  editParcelas.map((p, idx) => (
                    <div key={p.key} className={styles.parcelaEditRow}>
                      <span className={styles.parcelaEditNum}>{p.parcela_numero ?? idx + 1}</span>
                      <input
                        type="date"
                        className={styles.input}
                        value={p.vencimento}
                        onChange={updateEditParcela(p.key, "vencimento")}
                        disabled={p.status === "PAGO"}
                      />
                      <input
                        type="number" min="0" step="0.01"
                        className={styles.input}
                        value={p.valor}
                        onChange={updateEditParcela(p.key, "valor")}
                        disabled={p.status === "PAGO"}
                      />
                      <span className={`${styles.badge} ${styles["st" + (p.status || "PENDENTE")]}`}>
                        {STATUS_LABELS[p.status] || "Pendente"}
                      </span>
                      <button
                        type="button"
                        className={styles.btnRemoveParcela}
                        onClick={() => removeEditParcela(p)}
                        disabled={p.status === "PAGO"}
                        title={p.status === "PAGO" ? "Parcela recebida não pode ser removida" : "Remover parcela"}
                      >
                        ×
                      </button>
                    </div>
                  ))
                )}
              </div>

              {/* ── Boletos ── */}
              <div className={styles.uploadSection}>
                <p className={styles.uploadSectionLabel}>Boletos Anexados</p>
                {editParcelas.length === 0 ? (
                  <p className={styles.expandLoading}>Nenhuma parcela.</p>
                ) : (
                  editParcelas.map((p, idx) => {
                    const boleto = (p.anexos || []).find((a) => a.tipo === "BOLETO");
                    return (
                      <div key={p.key} className={styles.anexoRow}>
                        <span className={styles.anexoRowLabel}>Parcela {p.parcela_numero ?? idx + 1}</span>
                        {boleto ? (
                          <>
                            <span className={styles.anexoRowNome}>{boleto.nome_original}</span>
                            <button
                              type="button"
                              className={styles.btnLinkSmall}
                              onClick={() => handleDownloadAnexo(boleto)}
                            >
                              Download
                            </button>
                            <button
                              type="button"
                              className={styles.btnLinkSmall}
                              onClick={() => handleRemoverAnexo(p, boleto)}
                            >
                              Remover
                            </button>
                          </>
                        ) : p.id ? (
                          <label className={styles.btnLinkSmall}>
                            Anexar Boleto PDF
                            <input
                              type="file"
                              accept=".pdf,application/pdf"
                              className={styles.inputFileHidden}
                              onChange={(e) => {
                                const f = e.target.files[0];
                                if (f) handleUploadAnexoParcela(p, f, "BOLETO");
                                e.target.value = "";
                              }}
                            />
                          </label>
                        ) : (
                          <span className={styles.anexoRowNome}>Salve para anexar boleto</span>
                        )}
                      </div>
                    );
                  })
                )}
              </div>

              {/* ── Nota Fiscal ── */}
              <div className={styles.uploadSection}>
                <p className={styles.uploadSectionLabel}>Nota Fiscal</p>
                {(() => {
                  const primeiraParcela = editParcelas[0];
                  const nfAnexo = primeiraParcela?.anexos?.find((a) => a.tipo === "NF");
                  if (nfAnexo) {
                    return (
                      <div className={styles.anexoRow}>
                        <span className={styles.anexoRowNome}>{nfAnexo.nome_original}</span>
                        <button
                          type="button"
                          className={styles.btnLinkSmall}
                          onClick={() => handleDownloadAnexo(nfAnexo)}
                        >
                          Download
                        </button>
                        <button
                          type="button"
                          className={styles.btnLinkSmall}
                          onClick={() => handleRemoverAnexo(primeiraParcela, nfAnexo)}
                        >
                          Remover
                        </button>
                      </div>
                    );
                  }
                  if (primeiraParcela?.id) {
                    return (
                      <label className={styles.btnLinkSmall}>
                        Anexar NF PDF
                        <input
                          type="file"
                          accept=".pdf,application/pdf"
                          className={styles.inputFileHidden}
                          onChange={(e) => {
                            const f = e.target.files[0];
                            if (f) handleUploadAnexoParcela(primeiraParcela, f, "NF");
                            e.target.value = "";
                          }}
                        />
                      </label>
                    );
                  }
                  return <p className={styles.expandLoading}>Salve a venda para anexar a Nota Fiscal.</p>;
                })()}
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
      {modalExcluir && excluindoVenda && (
        <div className={styles.overlay} onClick={() => !deleting && setModalExcluir(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Excluir Venda</h2>
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
                Tem certeza que deseja excluir a venda de{" "}
                <strong>{excluindoVenda.cliente}</strong>?{" "}
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
          tipo="venda"
          importarLote={importarLoteVendas}
          importarFinal={importarVendaFinal}
          onFechar={() => { setModalImportar(false); setArquivosXml(null); }}
          onConcluido={handleConcluirImportacao}
        />
      )}
    </div>
  );
}
