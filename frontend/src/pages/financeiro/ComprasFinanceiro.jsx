import { useState, useEffect, useRef, Fragment } from "react";
import { FileText } from "lucide-react";
import {
  getCompras,
  createCompra,
  getCompra,
  uploadAnexo,
  updateCompra,
  deleteCompra,
  createLancamento,
  updateLancamento,
  deleteLancamento,
  downloadAnexo,
  deleteAnexo,
  importarLoteCompras,
  importarCompraFinal,
} from "../../api/financeiro";
import FormularioCompraVenda from "./FormularioCompraVenda";
import ImportarXMLModal from "./ImportarXMLModal";
import DocumentosFiscaisCard from "./DocumentosFiscaisCard";
import { useAuth } from "../../auth/useAuth";
import styles from "./comprasVendas.module.css";

const MODULO = "financeiro_compras";

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const dataFmt = (iso) => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("T")[0].split("-");
  return `${d}/${m}/${y}`;
};

const STATUS_LABELS = { PAGO: "Pago", PENDENTE: "Pendente", CANCELADO: "Cancelado" };

function statusGeralInfo(total, pagas) {
  if (total === 0) return { label: "—", cls: "stPendente" };
  if (pagas === total) return { label: "Quitado", cls: "stQuitado" };
  if (pagas > 0) return { label: `${pagas}/${total} pagas`, cls: "stParcial" };
  return { label: "Pendente", cls: "stPendente" };
}

function extractParcelas(obj) {
  return obj.parcelas || obj.lancamentos || [];
}

// Decide o tipo do anexo de nota fiscal pela extensão do arquivo: XML (dados
// estruturados, usado para gerar a DANFE Simplificada) ou NF (PDF).
function tipoAnexoPorArquivo(arquivo) {
  return (arquivo?.name || "").toLowerCase().endsWith(".xml") ? "XML" : "NF";
}

// Um anexo é "XML" se foi marcado como tal OU se o nome do arquivo termina em
// .xml (cobre anexos antigos, salvos com tipo='NF' antes dessa distinção
// existir). "PDF da NF" é tipo='NF' que NÃO seja, na prática, um XML.
function ehAnexoXml(a) {
  return a?.tipo === "XML" || (a?.nome_original || "").toLowerCase().endsWith(".xml");
}
function ehAnexoNfPdf(a) {
  return a?.tipo === "NF" && !(a?.nome_original || "").toLowerCase().endsWith(".xml");
}

function truncarNome(nome) {
  if (!nome) return "";
  return nome.length > 40 ? nome.substring(0, 37) + "..." : nome;
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
  if (p.status === "PAGO") return { label: "Pago", cls: "stPAGO" };
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

// Agrupa por mês/ano do campo de data informado (ex.: "data_compra").
// Datas são strings "AAAA-MM-DD" e são parseadas manualmente (em vez de
// `new Date(string)`) para evitar o parse como UTC do JS deslocar o dia 1º
// de cada mês para o mês anterior em fusos horários negativos (ex.: BRT).
function agruparPorMes(itens, campoData) {
  const grupos = {};
  itens.forEach((item) => {
    const dataStr = (item[campoData] || "").split("T")[0];
    if (!dataStr) return;
    const [ano, mes] = dataStr.split("-").map(Number);
    if (!ano || !mes) return;
    const chave = `${ano}-${String(mes).padStart(2, "0")}`;
    if (!grupos[chave]) {
      const label = new Date(ano, mes - 1, 1)
        .toLocaleDateString("pt-BR", { month: "long", year: "numeric" })
        .replace(/^\w/, (c) => c.toUpperCase());
      grupos[chave] = { label, chave, itens: [] };
    }
    grupos[chave].itens.push(item);
  });
  return Object.values(grupos).sort((a, b) => b.chave.localeCompare(a.chave));
}

const totalGrupo = (itens) =>
  itens.reduce((acc, item) => acc + (parseFloat(item.valor_total) || 0), 0);

export default function ComprasFinanceiro() {
  const { hasPermission } = useAuth();
  const [compras, setCompras] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [expandedData, setExpandedData] = useState({});
  const [loadingExpand, setLoadingExpand] = useState(false);
  const [modal, setModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState(null);

  // Edit
  const [modalEditar, setModalEditar] = useState(false);
  const [editandoCompra, setEditandoCompra] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [savingEdit, setSavingEdit] = useState(false);
  const [erroEdit, setErroEdit] = useState(null);

  // Edit — parcelas e anexos
  const [editParcelas, setEditParcelas] = useState([]);
  const [parcelasRemovidas, setParcelasRemovidas] = useState([]);
  const [loadingEditParcelas, setLoadingEditParcelas] = useState(false);

  // Delete
  const [modalExcluir, setModalExcluir] = useState(false);
  const [excluindoCompra, setExcluindoCompra] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [erroExcluir, setErroExcluir] = useState(null);

  // Importar XML
  const fileInputRef = useRef(null);
  const [arquivosXml, setArquivosXml] = useState(null);
  const [modalImportar, setModalImportar] = useState(false);
  const [resultadoImport, setResultadoImport] = useState(null);

  // Agrupamento por mês — chave do mês → true quando aberto (default: fechado)
  const [mesesAbertos, setMesesAbertos] = useState({});
  const toggleColapso = (chave) => setMesesAbertos((prev) => ({ ...prev, [chave]: !prev[chave] }));

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
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
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
    if (!formData.fornecedor?.trim()) {
      setErro("Informe o fornecedor.");
      return;
    }
    if (!formData.valor_total || isNaN(formData.valor_total)) {
      setErro("Informe o valor total.");
      return;
    }
    if (!formData.primeiro_vencimento) {
      setErro("Informe o primeiro vencimento.");
      return;
    }

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
        const tipoNf = tipoAnexoPorArquivo(nfFile);
        await Promise.all(parcelas.map((p) => uploadAnexo(p.id, nfFile, tipoNf).catch(() => {})));
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
  const handleAbrirEditar = async (e, compra) => {
    e.stopPropagation();
    setEditandoCompra(compra);
    setEditForm({
      fornecedor: compra.fornecedor || "",
      descricao: compra.descricao || "",
      valor_total: compra.valor_total || "",
      data_compra: (compra.data_compra || "").split("T")[0],
    });
    setErroEdit(null);
    setEditParcelas([]);
    setParcelasRemovidas([]);
    setModalEditar(true);
    setLoadingEditParcelas(true);
    try {
      const full = await getCompra(compra.id);
      setExpandedData((prev) => ({ ...prev, [compra.id]: full }));
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
      {
        key: `novo-${Date.now()}-${prev.length}`,
        id: null,
        parcela_numero: null,
        vencimento: "",
        valor: "",
        status: "PENDENTE",
        anexos: [],
      },
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
      setEditParcelas((prev) =>
        prev.map((p) =>
          p.key === parcela.key ? { ...p, anexos: [...(p.anexos || []), anexo] } : p
        )
      );
    } catch (err) {
      setErroEdit(err.message || "Erro ao anexar arquivo.");
    }
  };

  const handleRemoverAnexo = async (parcela, anexo) => {
    try {
      await deleteAnexo(anexo.id);
      setEditParcelas((prev) =>
        prev.map((p) =>
          p.key === parcela.key
            ? { ...p, anexos: (p.anexos || []).filter((a) => a.id !== anexo.id) }
            : p
        )
      );
    } catch (err) {
      setErroEdit(err.message || "Erro ao remover anexo.");
    }
  };

  const handleDownloadAnexo = async (anexo) => {
    try {
      const blob = await downloadAnexo(anexo.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
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
        fornecedor: editForm.fornecedor.trim() || undefined,
        descricao: editForm.descricao.trim() || null,
        valor_total: parseFloat(editForm.valor_total) || undefined,
        data_compra: editForm.data_compra || undefined,
      };
      await updateCompra(editandoCompra.id, dados);

      for (const id of parcelasRemovidas) {
        await deleteLancamento(id).catch(() => {});
      }

      const descricaoBase = dados.descricao || dados.fornecedor || editandoCompra.fornecedor;
      for (const p of editParcelas) {
        if (p.id) {
          await updateLancamento(p.id, {
            data_vencimento: p.vencimento,
            valor: parseFloat(p.valor),
          });
        } else {
          await createLancamento({
            tipo: "PAGAR",
            descricao: descricaoBase,
            valor: parseFloat(p.valor),
            data_vencimento: p.vencimento,
            compra_id: editandoCompra.id,
          });
        }
      }

      const full = await getCompra(editandoCompra.id);
      setCompras((prev) => prev.map((c) => (c.id === full.id ? { ...c, ...full } : c)));
      setExpandedData((prev) => ({ ...prev, [full.id]: full }));
      setModalEditar(false);
    } catch (e) {
      setErroEdit(e.message || "Erro ao salvar alterações.");
    }
    setSavingEdit(false);
  };

  // ── Documentos Fiscais (card) ─────────────────────────────────────────────
  const [docCard, setDocCard] = useState(null); // { compra, anchor, full, carregando }

  const handleAbrirDocCard = async (e, compra) => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    const anchor = {
      x: Math.min(rect.left, window.innerWidth - 296),
      y: rect.bottom + 6,
    };
    const cache = expandedData[compra.id];
    setDocCard({ compra, anchor, full: cache || null, carregando: !cache });
    if (!cache) {
      try {
        const full = await getCompra(compra.id);
        setExpandedData((prev) => ({ ...prev, [compra.id]: full }));
        setDocCard((prev) =>
          prev && prev.compra.id === compra.id ? { ...prev, full, carregando: false } : prev
        );
      } catch {
        setDocCard((prev) =>
          prev && prev.compra.id === compra.id ? { ...prev, carregando: false } : prev
        );
      }
    }
  };

  const handleFecharDocCard = () => setDocCard(null);

  const docCardAnexos = docCard?.full
    ? extractParcelas(docCard.full).flatMap((p) => p.anexos || [])
    : [];
  const docCardAnexoXml = docCardAnexos.find(ehAnexoXml);
  const docCardAnexoNf = docCardAnexos.find(ehAnexoNfPdf);

  const handleDownloadXmlCard = () => {
    if (docCardAnexoXml) handleDownloadAnexo(docCardAnexoXml);
    setDocCard(null);
  };

  const handleDownloadNfCard = () => {
    if (docCardAnexoNf) handleDownloadAnexo(docCardAnexoNf);
    setDocCard(null);
  };

  const handleAnexarDocumentoCard = () => {
    const compra = docCard?.compra;
    setDocCard(null);
    if (compra) handleAbrirEditar({ stopPropagation: () => {} }, compra);
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
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Compras</h1>
        <div className={styles.headerActions}>
          {hasPermission(MODULO, "criar") && (
            <>
              <button className={styles.btnSecondary} onClick={handleAbrirSeletorXml}>
                Importar XMLs
              </button>
              <button
                className={styles.btnNovo}
                onClick={() => {
                  setModal(true);
                  setErro(null);
                }}
              >
                + Nova Compra
              </button>
            </>
          )}
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

      <div className={`sc-card ${styles.tableCard}`}>
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Fornecedor</th>
                <th style={{ textAlign: "center" }}>Data</th>
                <th style={{ textAlign: "center" }}>Valor Total</th>
                <th style={{ textAlign: "center" }}>Parcelas</th>
                <th style={{ textAlign: "center" }}>Status</th>
                <th
                  className={styles.acoesCell}
                  style={{
                    width: "180px",
                    minWidth: "180px",
                    maxWidth: "180px",
                    textAlign: "center",
                  }}
                >
                  Ações
                </th>
              </tr>
            </thead>
            <tbody>
              {agruparPorMes(compras, "data_compra").map((grupo) => {
                const colapsado = !mesesAbertos[grupo.chave];
                return (
                  <Fragment key={grupo.chave}>
                    <tr className={styles.monthHeaderRow}>
                      <td colSpan={6}>
                        <div
                          className={styles.monthHeader}
                          onClick={() => toggleColapso(grupo.chave)}
                        >
                          <span className={styles.monthHeaderChevron}>{colapsado ? "▶" : "▼"}</span>
                          <span>
                            {grupo.label} &nbsp;•&nbsp; {grupo.itens.length} nota
                            {grupo.itens.length !== 1 ? "s" : ""} &nbsp;•&nbsp; Total:{" "}
                            {moeda(totalGrupo(grupo.itens))}
                          </span>
                        </div>
                      </td>
                    </tr>

                    {!colapsado &&
                      grupo.itens.map((c) => {
                        const isOpen = expandedId === c.id;
                        const cached = expandedData[c.id];
                        const parcelas = cached ? extractParcelas(cached) : [];
                        const { total: totalParcelas, pagas: parcelasPagas } = contarParcelas(
                          c,
                          cached
                        );
                        const st = statusGeralInfo(totalParcelas, parcelasPagas);

                        return (
                          <Fragment key={c.id}>
                            <tr className={styles.trClickable} onClick={() => handleExpand(c.id)}>
                              <td title={c.fornecedor}>
                                <div className={styles.fornecedorCell}>
                                  <span className={styles.fornecedorNome}>
                                    {c.fornecedor || "—"}
                                  </span>
                                  {c.descricao && (
                                    <span className={styles.fornecedorSub}>{c.descricao}</span>
                                  )}
                                </div>
                              </td>
                              <td style={{ textAlign: "center" }}>
                                <div className={styles.dataCell}>
                                  <span>NF: {dataFmt(c.data_compra)}</span>
                                  <span className={styles.dataCellSub}>
                                    Import.: {dataFmt(c.created_at)}
                                  </span>
                                </div>
                              </td>
                              <td className={styles.tdValor} style={{ textAlign: "center" }}>
                                {moeda(c.valor_total)}
                              </td>
                              <td style={{ textAlign: "center" }}>
                                {totalParcelas > 0 ? `${totalParcelas}x` : "—"}
                              </td>
                              <td style={{ textAlign: "center" }}>
                                <span className={`${styles.badge} ${styles[st.cls]}`}>
                                  {st.label}
                                </span>
                              </td>
                              <td
                                className={styles.acoesCell}
                                onClick={(e) => e.stopPropagation()}
                                style={{ width: "180px", minWidth: "180px", maxWidth: "180px" }}
                              >
                                <div
                                  className={styles.rowActions}
                                  style={{
                                    display: "flex",
                                    flexDirection: "row",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    gap: "6px",
                                    width: "100%",
                                    flexWrap: "nowrap",
                                  }}
                                >
                                  {hasPermission(MODULO, "editar") && (
                                    <button
                                      className={styles.btnEditar}
                                      onClick={(e) => handleAbrirEditar(e, c)}
                                      title="Editar"
                                      style={{
                                        height: "30px",
                                        padding: "0 10px",
                                        fontSize: "13px",
                                        flexShrink: 0,
                                      }}
                                    >
                                      Editar
                                    </button>
                                  )}
                                  <button
                                    className={styles.btnIconAction}
                                    onClick={(e) => handleAbrirDocCard(e, c)}
                                    title="Documentos Fiscais"
                                    style={{ height: "30px", width: "30px", flexShrink: 0 }}
                                  >
                                    <FileText size={15} strokeWidth={1.75} />
                                  </button>
                                  {hasPermission(MODULO, "excluir") && (
                                    <button
                                      className={styles.btnIconDelete}
                                      onClick={(e) => handleAbrirExcluir(e, c)}
                                      title="Excluir"
                                      style={{ height: "30px", width: "30px", flexShrink: 0 }}
                                    >
                                      ✕
                                    </button>
                                  )}
                                </div>
                              </td>
                            </tr>

                            {isOpen && (
                              <tr className={styles.expandRow}>
                                <td colSpan={6}>
                                  <div className={styles.expandCell}>
                                    {loadingExpand && !cached ? (
                                      <p className={styles.expandLoading}>Carregando parcelas…</p>
                                    ) : parcelas.length === 0 ? (
                                      <p className={styles.expandLoading}>
                                        Nenhuma parcela encontrada.
                                      </p>
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
                                            {parcelas.map((p, idx) => {
                                              const pst = parcelaStatusInfo(p);
                                              return (
                                                <tr key={p.id}>
                                                  <td>{p.parcela_numero ?? idx + 1}</td>
                                                  <td>{dataFmt(p.data_vencimento)}</td>
                                                  <td>{moeda(p.valor)}</td>
                                                  <td>
                                                    <span
                                                      className={`${styles.badge} ${styles[pst.cls]}`}
                                                    >
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
                            )}
                          </Fragment>
                        );
                      })}
                  </Fragment>
                );
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
          <div
            className={`${styles.modal} ${styles.modalLarge}`}
            onClick={(e) => e.stopPropagation()}
          >
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

              {/* ── Parcelas ── */}
              <div className={styles.uploadSection}>
                <div className={styles.parcelasEditHeader}>
                  <p className={styles.uploadSectionLabel} style={{ margin: 0 }}>
                    Parcelas
                  </p>
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
                        type="number"
                        min="0"
                        step="0.01"
                        className={styles.input}
                        value={p.valor}
                        onChange={updateEditParcela(p.key, "valor")}
                        disabled={p.status === "PAGO"}
                      />
                      <span
                        className={`${styles.badge} ${styles["st" + (p.status || "PENDENTE")]}`}
                      >
                        {STATUS_LABELS[p.status] || "Pendente"}
                      </span>
                      <button
                        type="button"
                        className={styles.btnRemoveParcela}
                        onClick={() => removeEditParcela(p)}
                        disabled={p.status === "PAGO"}
                        title={
                          p.status === "PAGO"
                            ? "Parcela paga não pode ser removida"
                            : "Remover parcela"
                        }
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
                        <span className={styles.anexoRowLabel}>
                          Parcela {p.parcela_numero ?? idx + 1}
                        </span>
                        {boleto ? (
                          <>
                            <span className={styles.anexoRowNome} title={boleto.nome_original}>
                              {truncarNome(boleto.nome_original)}
                            </span>
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

              {/* ── Nota Fiscal — XML ── */}
              <div className={styles.uploadSection}>
                <p className={styles.uploadSectionLabel}>Nota Fiscal — XML</p>
                {(() => {
                  const primeiraParcela = editParcelas[0];
                  const xmlAnexo = primeiraParcela?.anexos?.find(ehAnexoXml);
                  if (xmlAnexo) {
                    return (
                      <div className={styles.anexoRow}>
                        <span className={styles.anexoRowNome} title={xmlAnexo.nome_original}>
                          {truncarNome(xmlAnexo.nome_original)}
                        </span>
                        <button
                          type="button"
                          className={styles.btnLinkSmall}
                          onClick={() => handleDownloadAnexo(xmlAnexo)}
                        >
                          Download
                        </button>
                        <button
                          type="button"
                          className={styles.btnLinkSmall}
                          onClick={() => handleRemoverAnexo(primeiraParcela, xmlAnexo)}
                        >
                          Remover
                        </button>
                      </div>
                    );
                  }
                  if (primeiraParcela?.id) {
                    return (
                      <label className={styles.btnLinkSmall}>
                        Anexar XML
                        <input
                          type="file"
                          accept=".xml,text/xml,application/xml"
                          className={styles.inputFileHidden}
                          onChange={(e) => {
                            const f = e.target.files[0];
                            if (f) handleUploadAnexoParcela(primeiraParcela, f, "XML");
                            e.target.value = "";
                          }}
                        />
                      </label>
                    );
                  }
                  return <p className={styles.expandLoading}>Salve a compra para anexar o XML.</p>;
                })()}
              </div>

              {/* ── Nota Fiscal — DANFE (PDF) ── */}
              <div className={styles.uploadSection}>
                <p className={styles.uploadSectionLabel}>Nota Fiscal — DANFE (PDF)</p>
                {(() => {
                  const primeiraParcela = editParcelas[0];
                  const pdfAnexo = primeiraParcela?.anexos?.find(ehAnexoNfPdf);
                  if (pdfAnexo) {
                    return (
                      <div className={styles.anexoRow}>
                        <span className={styles.anexoRowNome} title={pdfAnexo.nome_original}>
                          {truncarNome(pdfAnexo.nome_original)}
                        </span>
                        <button
                          type="button"
                          className={styles.btnLinkSmall}
                          onClick={() => handleDownloadAnexo(pdfAnexo)}
                        >
                          Download
                        </button>
                        <button
                          type="button"
                          className={styles.btnLinkSmall}
                          onClick={() => handleRemoverAnexo(primeiraParcela, pdfAnexo)}
                        >
                          Remover
                        </button>
                      </div>
                    );
                  }
                  if (primeiraParcela?.id) {
                    return (
                      <label className={styles.btnLinkSmall}>
                        Anexar DANFE PDF
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
                  return (
                    <p className={styles.expandLoading}>Salve a compra para anexar o DANFE.</p>
                  );
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
                <strong>{excluindoCompra.fornecedor}</strong>? Esta ação não pode ser desfeita.
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
          tipo="compra"
          importarLote={importarLoteCompras}
          importarFinal={importarCompraFinal}
          onFechar={() => {
            setModalImportar(false);
            setArquivosXml(null);
          }}
          onConcluido={handleConcluirImportacao}
        />
      )}

      {/* ── Card: Documentos Fiscais ── */}
      {docCard && (
        <DocumentosFiscaisCard
          anchor={docCard.anchor}
          titulo="Documentos Fiscais"
          subtitulo={`${docCard.compra.descricao || "Documento"} — ${docCard.compra.fornecedor || ""}`}
          carregando={docCard.carregando}
          anexoXml={docCardAnexoXml}
          anexoNf={docCardAnexoNf}
          mostrarGerarDanfe={false}
          onDownloadXml={handleDownloadXmlCard}
          onDownloadNf={handleDownloadNfCard}
          onAnexarDocumento={handleAnexarDocumentoCard}
          onFechar={handleFecharDocCard}
        />
      )}
    </div>
  );
}
