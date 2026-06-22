import { useState, useEffect, useCallback } from "react";
import {
  getLancamentos,
  getSaldoContas,
  getContasBancarias,
  confirmarPagamento as apiConfirmarPagamento,
  getAnexos,
  downloadAnexo,
  createLancamento,
} from "../../api/financeiro";
import styles from "./FluxoCaixa.module.css";

const MESES = [
  "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
  "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro",
];

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const hojeISO = () => new Date().toISOString().split("T")[0];

const dataFmt = (iso) => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("T")[0].split("-");
  return `${d}/${m}/${y}`;
};

const STATUS_LABELS = { PAGO: "Pago", PENDENTE: "Pendente", CANCELADO: "Cancelado" };

function rowStatusClass(item) {
  if (item.status === "PAGO") return styles.rowPago;
  if (item.status === "CANCELADO") return "";
  const vencStr = (item.vencimento || "").split("T")[0];
  if (!vencStr) return "";
  const [y, m, d] = vencStr.split("-").map(Number);
  const hoje = new Date();
  const hojeDia  = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  const vencDia  = new Date(y, m - 1, d);
  const amanha   = new Date(hojeDia);
  amanha.setDate(amanha.getDate() + 1);
  if (vencDia < hojeDia) return styles.rowAtrasado;
  if (vencDia <= amanha)  return styles.rowAlerta;
  return "";
}

const LANC_VAZIO = {
  tipo: "PAGAR", descricao: "", valor: "",
  vencimento: hojeISO(), categoria: "", parcelas: "1",
};

export default function FluxoCaixa() {
  const now = new Date();
  const [mes, setMes] = useState(now.getMonth() + 1);
  const [ano, setAno] = useState(now.getFullYear());

  const [lancamentos,    setLancamentos]    = useState([]);
  const [saldoContas,    setSaldoContas]    = useState([]);
  const [contasBanc,     setContasBanc]     = useState([]);
  const [loading,        setLoading]        = useState(false);

  // Modal confirmar pagamento/recebimento
  const [modalPag,   setModalPag]   = useState(null);
  const [pagForm,    setPagForm]    = useState({ conta_bancaria_id: "", data_pagamento: hojeISO() });
  const [erroPag,    setErroPag]    = useState(null);
  const [savingPag,  setSavingPag]  = useState(false);

  // Modal anexos
  const [modalAnexos,    setModalAnexos]    = useState(null);
  const [anexos,         setAnexos]         = useState([]);
  const [loadingAnexos,  setLoadingAnexos]  = useState(false);

  // Modal novo lançamento
  const [modalLanc,    setModalLanc]    = useState(false);
  const [lancForm,     setLancForm]     = useState(LANC_VAZIO);
  const [erroLanc,     setErroLanc]     = useState(null);
  const [savingLanc,   setSavingLanc]   = useState(false);

  const carregarDados = useCallback(async () => {
    setLoading(true);
    try {
      const [lancs, saldos] = await Promise.all([
        getLancamentos(mes, ano),
        getSaldoContas(mes, ano),
      ]);
      setLancamentos(lancs  || []);
      setSaldoContas(saldos || []);
    } catch {}
    setLoading(false);
  }, [mes, ano]);

  useEffect(() => { carregarDados(); }, [carregarDados]);

  useEffect(() => {
    getContasBancarias().then((c) => setContasBanc(c || [])).catch(() => {});
  }, []);

  // ── Navegação de mês ──────────────────────────────────────────────────────
  const navegarMes = (delta) => {
    const novo = mes + delta;
    if (novo > 12) { setMes(1);  setAno((a) => a + 1); }
    else if (novo < 1) { setMes(12); setAno((a) => a - 1); }
    else { setMes(novo); }
  };

  // ── Derived ──────────────────────────────────────────────────────────────
  const pagar       = lancamentos.filter((l) => l.tipo === "PAGAR");
  const receber     = lancamentos.filter((l) => l.tipo === "RECEBER");
  const totalPagar  = pagar.filter((l)   => l.status !== "PAGO").reduce((s, l) => s + (l.valor || 0), 0);
  const totalReceber= receber.filter((l) => l.status !== "PAGO").reduce((s, l) => s + (l.valor || 0), 0);
  const saldoTotal  = saldoContas.reduce((s, c) => s + (c.saldo || 0), 0);
  const projecao    = saldoTotal + totalReceber - totalPagar;

  // ── Confirmar pagamento ───────────────────────────────────────────────────
  const abrirModalPag = (l) => {
    setModalPag(l);
    setPagForm({ conta_bancaria_id: "", data_pagamento: hojeISO() });
    setErroPag(null);
  };

  const handleConfirmarPag = async () => {
    if (!pagForm.conta_bancaria_id) { setErroPag("Selecione a conta bancária."); return; }
    if (!pagForm.data_pagamento)    { setErroPag("Informe a data."); return; }
    setSavingPag(true);
    try {
      await apiConfirmarPagamento(
        modalPag.id,
        pagForm.conta_bancaria_id,
        pagForm.data_pagamento,
      );
      setLancamentos((prev) =>
        prev.map((l) => l.id === modalPag.id ? { ...l, status: "PAGO" } : l)
      );
      setModalPag(null);
      getSaldoContas(mes, ano).then((s) => setSaldoContas(s || [])).catch(() => {});
    } catch (e) {
      setErroPag(e.message);
    }
    setSavingPag(false);
  };

  // ── Anexos ────────────────────────────────────────────────────────────────
  const abrirAnexos = async (lancamentoId) => {
    setModalAnexos({ lancamentoId });
    setAnexos([]);
    setLoadingAnexos(true);
    try {
      setAnexos((await getAnexos(lancamentoId)) || []);
    } catch {}
    setLoadingAnexos(false);
  };

  const handleDownload = async (anexoId, nome) => {
    try {
      const blob = await downloadAnexo(anexoId);
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = nome || "anexo";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {}
  };

  // ── Novo lançamento ───────────────────────────────────────────────────────
  const setLanc = (key) => (e) =>
    setLancForm((f) => ({ ...f, [key]: e.target.value }));

  const abrirModalLanc = () => {
    setLancForm(LANC_VAZIO);
    setErroLanc(null);
    setModalLanc(true);
  };

  const handleCriarLanc = async () => {
    if (!lancForm.descricao.trim()) { setErroLanc("Informe a descrição."); return; }
    if (!lancForm.valor || isNaN(parseFloat(lancForm.valor))) {
      setErroLanc("Informe o valor."); return;
    }
    if (!lancForm.vencimento) { setErroLanc("Informe o vencimento."); return; }
    setSavingLanc(true);
    try {
      await createLancamento({
        tipo:       lancForm.tipo,
        descricao:  lancForm.descricao.trim(),
        valor:      parseFloat(lancForm.valor),
        vencimento: lancForm.vencimento,
        categoria:  lancForm.categoria  || null,
        parcelas:   parseInt(lancForm.parcelas) || 1,
      });
      setModalLanc(false);
      await carregarDados();
    } catch (e) {
      setErroLanc(e.message);
    }
    setSavingLanc(false);
  };

  // ── Tabela helper ─────────────────────────────────────────────────────────
  const renderTabela = (itens, tipo) => {
    const labelParte = tipo === "PAGAR" ? "Fornecedor" : "Cliente";
    const labelAcao  = tipo === "PAGAR" ? "✓ Pagar"    : "✓ Receber";
    return (
      <div className={styles.card}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Descrição</th>
              <th>{labelParte}</th>
              <th>Vencimento</th>
              <th>Valor</th>
              <th>Parcela</th>
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {itens.map((l) => (
              <tr key={l.id} className={rowStatusClass(l)}>
                <td title={l.descricao || ""}>{l.descricao || "—"}</td>
                <td title={(tipo === "PAGAR" ? l.fornecedor : l.cliente) || l.origem || ""}>
                  {(tipo === "PAGAR" ? l.fornecedor : l.cliente) || l.origem || "—"}
                </td>
                <td>{dataFmt(l.vencimento)}</td>
                <td className={styles.tdValor}>{moeda(l.valor)}</td>
                <td>
                  {l.parcela_atual && l.total_parcelas
                    ? `${l.parcela_atual}/${l.total_parcelas}`
                    : "—"}
                </td>
                <td>
                  <span className={`${styles.badge} ${styles["st" + (l.status || "PENDENTE")]}`}>
                    {STATUS_LABELS[l.status] || l.status || "Pendente"}
                  </span>
                </td>
                <td>
                  <div className={styles.rowActions}>
                    {l.status !== "PAGO" && l.status !== "CANCELADO" && (
                      <button
                        className={styles.btnSmall}
                        title={tipo === "PAGAR" ? "Confirmar pagamento" : "Confirmar recebimento"}
                        onClick={() => abrirModalPag(l)}
                      >
                        {labelAcao}
                      </button>
                    )}
                    <button
                      className={styles.btnIcon}
                      title="Ver anexos"
                      onClick={() => abrirAnexos(l.id)}
                    >
                      📎
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {itens.length === 0 && (
              <tr>
                <td colSpan={7} className={styles.empty}>
                  {loading
                    ? "Carregando…"
                    : `Nenhum lançamento a ${tipo === "PAGAR" ? "pagar" : "receber"}.`}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    );
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className={styles.page}>

      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}>Fluxo de Caixa</h1>
          <div className={styles.navMes}>
            <button className={styles.btnNav} onClick={() => navegarMes(-1)}>‹</button>
            <span className={styles.mesLabel}>{MESES[mes - 1]} {ano}</span>
            <button className={styles.btnNav} onClick={() => navegarMes(1)}>›</button>
          </div>
        </div>
        <button className={styles.btnPrimary} onClick={abrirModalLanc}>
          + Lançamento Manual
        </button>
      </div>

      {/* Saldo das contas */}
      <div className={styles.saldoGrid}>
        {saldoContas.map((c) => (
          <div key={c.id ?? c.nome} className={styles.saldoCard}>
            <span className={styles.saldoNome}>{c.nome}</span>
            <span className={`${styles.saldoValor} ${(c.saldo ?? 0) < 0 ? styles.negativo : ""}`}>
              {moeda(c.saldo)}
            </span>
          </div>
        ))}
        {saldoContas.length === 0 && !loading && (
          <span className={styles.semContas}>Nenhuma conta cadastrada.</span>
        )}
      </div>

      {/* Resumo */}
      <div className={styles.resumoGrid}>
        <div className={`${styles.resumoCard} ${styles.resumoPerigo}`}>
          <span className={styles.resumoLabel}>A Pagar</span>
          <span className={styles.resumoValor}>{moeda(totalPagar)}</span>
        </div>
        <div className={`${styles.resumoCard} ${styles.resumoSucesso}`}>
          <span className={styles.resumoLabel}>A Receber</span>
          <span className={styles.resumoValor}>{moeda(totalReceber)}</span>
        </div>
        <div className={`${styles.resumoCard} ${projecao < 0 ? styles.resumoPerigo : styles.resumoNeutro}`}>
          <span className={styles.resumoLabel}>Projeção Final</span>
          <span className={styles.resumoValor}>{moeda(projecao)}</span>
        </div>
      </div>

      {/* Tabelas */}
      <div className={styles.tablesGrid}>
        <section className={styles.tableSection}>
          <h2 className={styles.tableTitle}>Contas a Pagar</h2>
          {renderTabela(pagar, "PAGAR")}
        </section>
        <section className={styles.tableSection}>
          <h2 className={styles.tableTitle}>Contas a Receber</h2>
          {renderTabela(receber, "RECEBER")}
        </section>
      </div>

      {/* ── Modal: Confirmar Pagamento / Recebimento ── */}
      {modalPag && (
        <div className={styles.overlay} onClick={() => setModalPag(null)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>
                {modalPag.tipo === "PAGAR" ? "Confirmar Pagamento" : "Confirmar Recebimento"}
              </h2>
              <button className={styles.btnClose} onClick={() => setModalPag(null)}>×</button>
            </div>
            <div className={styles.modalBody}>
              <p className={styles.confirmText}>
                {modalPag.descricao} — {moeda(modalPag.valor)}
                {modalPag.vencimento && (
                  <> &nbsp;·&nbsp; vence {dataFmt(modalPag.vencimento)}</>
                )}
              </p>
              <label className={styles.field}>
                <span>Conta bancária *</span>
                <select
                  className={styles.input}
                  value={pagForm.conta_bancaria_id}
                  onChange={(e) => setPagForm((f) => ({ ...f, conta_bancaria_id: e.target.value }))}
                >
                  <option value="">— Selecionar —</option>
                  {contasBanc.map((c) => (
                    <option key={c.id} value={c.id}>{c.nome}</option>
                  ))}
                </select>
              </label>
              <label className={`${styles.field} ${styles.fieldSpacer}`}>
                <span>Data do {modalPag.tipo === "PAGAR" ? "pagamento" : "recebimento"} *</span>
                <input
                  type="date"
                  className={styles.input}
                  value={pagForm.data_pagamento}
                  onChange={(e) => setPagForm((f) => ({ ...f, data_pagamento: e.target.value }))}
                />
              </label>
              {erroPag && <p className={styles.erro}>{erroPag}</p>}
            </div>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setModalPag(null)}>
                Cancelar
              </button>
              <button
                className={styles.btnPrimary}
                onClick={handleConfirmarPag}
                disabled={savingPag}
              >
                {savingPag ? "Confirmando…" : "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Ver Anexos ── */}
      {modalAnexos && (
        <div className={styles.overlay} onClick={() => setModalAnexos(null)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Anexos</h2>
              <button className={styles.btnClose} onClick={() => setModalAnexos(null)}>×</button>
            </div>
            <div className={styles.modalBody}>
              {loadingAnexos ? (
                <p className={styles.confirmText}>Carregando…</p>
              ) : anexos.length === 0 ? (
                <p className={styles.confirmText}>Nenhum anexo neste lançamento.</p>
              ) : (
                <ul className={styles.attachList}>
                  {anexos.map((a) => (
                    <li key={a.id} className={styles.attachItem}>
                      <span className={styles.attachIcon}>📄</span>
                      <span className={styles.attachNome} title={a.nome || a.arquivo}>
                        {a.nome || a.arquivo || "Arquivo"}
                      </span>
                      {a.tipo && (
                        <span className={styles.attachTipo}>{a.tipo}</span>
                      )}
                      <button
                        className={styles.btnSmall}
                        onClick={() => handleDownload(a.id, a.nome || a.arquivo)}
                      >
                        ↓ Download
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setModalAnexos(null)}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Novo Lançamento Manual ── */}
      {modalLanc && (
        <div className={styles.overlay} onClick={() => setModalLanc(false)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Novo Lançamento Manual</h2>
              <button className={styles.btnClose} onClick={() => setModalLanc(false)}>×</button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.fieldGrid}>
                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Tipo *</span>
                  <select className={styles.input} value={lancForm.tipo} onChange={setLanc("tipo")}>
                    <option value="PAGAR">A Pagar</option>
                    <option value="RECEBER">A Receber</option>
                  </select>
                </label>
                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Descrição *</span>
                  <input
                    className={styles.input}
                    value={lancForm.descricao}
                    onChange={setLanc("descricao")}
                    placeholder="Ex: Aluguel, Energia elétrica…"
                  />
                </label>
                <label className={styles.field}>
                  <span>Valor *</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className={styles.input}
                    value={lancForm.valor}
                    onChange={setLanc("valor")}
                    placeholder="0,00"
                  />
                </label>
                <label className={styles.field}>
                  <span>Vencimento *</span>
                  <input
                    type="date"
                    className={styles.input}
                    value={lancForm.vencimento}
                    onChange={setLanc("vencimento")}
                  />
                </label>
                <label className={styles.field}>
                  <span>Categoria</span>
                  <input
                    className={styles.input}
                    value={lancForm.categoria}
                    onChange={setLanc("categoria")}
                    placeholder="Ex: Fornecedores"
                  />
                </label>
                <label className={styles.field}>
                  <span>Nº de parcelas</span>
                  <input
                    type="number"
                    min="1"
                    max="48"
                    className={styles.input}
                    value={lancForm.parcelas}
                    onChange={setLanc("parcelas")}
                  />
                </label>
              </div>
              {erroLanc && <p className={styles.erro}>{erroLanc}</p>}
            </div>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setModalLanc(false)}>
                Cancelar
              </button>
              <button
                className={styles.btnPrimary}
                onClick={handleCriarLanc}
                disabled={savingLanc}
              >
                {savingLanc ? "Criando…" : "Criar Lançamento"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
