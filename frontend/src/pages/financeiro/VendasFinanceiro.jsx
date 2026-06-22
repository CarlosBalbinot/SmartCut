import { useState, useEffect } from "react";
import {
  getVendasFinanceiras,
  createVendaFinanceira,
  getVendaFinanceira,
  uploadAnexo,
} from "../../api/financeiro";
import FormularioCompraVenda from "./FormularioCompraVenda";
import styles from "./comprasVendas.module.css";

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const dataFmt = (iso) => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("T")[0].split("-");
  return `${d}/${m}/${y}`;
};

const STATUS_LABELS = { PAGO: "Recebido", PENDENTE: "Pendente", CANCELADO: "Cancelado" };

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
  if (total === 0) return { label: "—",          cls: "stPendente" };
  if (pagas === total) return { label: "Quitado",   cls: "stQuitado"  };
  if (pagas > 0)  return { label: `${pagas}/${total} receb.`, cls: "stParcial"  };
  return { label: "Pendente", cls: "stPendente" };
}

function extractParcelas(obj) {
  return obj.parcelas || obj.lancamentos || [];
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

  useEffect(() => {
    setLoading(true);
    getVendasFinanceiras()
      .then((v) => setVendas(v || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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

      // Garantir que temos as parcelas — buscar detalhe se necessário
      let full = criada;
      if (extractParcelas(criada).length === 0 && criada.id) {
        full = await getVendaFinanceira(criada.id);
      }
      const parcelas = extractParcelas(full);

      // Anexar NF em todas as parcelas
      if (nfFile && parcelas.length > 0) {
        await Promise.all(
          parcelas.map((p) => uploadAnexo(p.id, nfFile, "NF").catch(() => {}))
        );
      }

      // Anexar cada boleto na parcela correspondente
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

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className={styles.page}>

      <div className={styles.header}>
        <h1 className={styles.title}>Vendas — Contas a Receber</h1>
        <button className={styles.btnPrimary} onClick={() => { setModal(true); setErro(null); }}>
          + Nova Venda
        </button>
      </div>

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
              const st      = statusGeral(v);
              const isOpen  = expandedId === v.id;
              const cached  = expandedData[v.id];
              const parcelas = cached ? extractParcelas(cached) : [];

              return [
                <tr
                  key={v.id}
                  className={styles.trClickable}
                  onClick={() => handleExpand(v.id)}
                >
                  <td title={v.cliente}>{v.cliente || "—"}</td>
                  <td>{dataFmt(v.data_emissao || v.created_at)}</td>
                  <td className={styles.tdValor}>{moeda(v.valor_total)}</td>
                  <td>
                    {(v.num_parcelas ?? extractParcelas(v).length) > 0
                      ? `${v.num_parcelas ?? extractParcelas(v).length}x`
                      : "—"}
                  </td>
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
    </div>
  );
}
