import { useCallback, useEffect, useState } from "react";
import {
  getContabilidade, gerarPacoteContabil, gerarResumoInternoContabil,
} from "../../api/financeiro";
import { API_BASE } from "../../services/config";
import styles from "./Contabilidade.module.css";

const MESES = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const dataFmt = (iso) => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("T")[0].split("-");
  return `${d}/${m}/${y}`;
};

const somaValores = (itens, getValor) =>
  itens.reduce((acc, item) => acc + (parseFloat(getValor(item)) || 0), 0);

// Converte o caminho relativo salvo no backend (ex.: "uploads/financeiro/...")
// na URL pública servida pelo StaticFiles montado em /uploads.
function arquivoUrl(caminho) {
  if (!caminho) return null;
  const rel = caminho.replace(/\\/g, "/").split("uploads/").pop();
  return `${API_BASE}/uploads/${rel}`;
}

function abrirArquivo(caminho) {
  const url = arquivoUrl(caminho);
  if (url) window.open(url, "_blank");
}

function baixarBlob(blob, nomeArquivo) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nomeArquivo;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function ContabilidadeFinanceiro() {
  const now = new Date();
  const [mes, setMes] = useState(now.getMonth() + 1);
  const [ano, setAno] = useState(now.getFullYear());

  const [dados,   setDados]   = useState({ notas_venda: [], notas_compra: [], boletos_pagos: [] });
  const [loading, setLoading] = useState(false);
  const [erro,    setErro]    = useState(null);

  const [gerandoPacote, setGerandoPacote] = useState(false);
  const [gerandoResumo, setGerandoResumo] = useState(false);

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro(null);
    try {
      const r = await getContabilidade(mes, ano);
      setDados(r || { notas_venda: [], notas_compra: [], boletos_pagos: [] });
    } catch (e) {
      setErro(e.message || "Erro ao carregar dados contábeis.");
    }
    setLoading(false);
  }, [mes, ano]);

  useEffect(() => { carregar(); }, [carregar]);

  const navegarMes = (delta) => {
    const novo = mes + delta;
    if (novo > 12) { setMes(1); setAno((a) => a + 1); }
    else if (novo < 1) { setMes(12); setAno((a) => a - 1); }
    else { setMes(novo); }
  };

  const totalVendas  = somaValores(dados.notas_venda, (v) => v.valor_total);
  const totalCompras = somaValores(dados.notas_compra, (c) => c.valor_total);
  const totalPago    = somaValores(dados.boletos_pagos, (b) => b.valor);
  const resultado    = totalVendas - totalCompras;

  const handleGerarPacote = async () => {
    setGerandoPacote(true);
    setErro(null);
    try {
      const blob = await gerarPacoteContabil(mes, ano);
      baixarBlob(blob, `Contabilidade-${String(mes).padStart(2, "0")}-${ano}.zip`);
    } catch (e) {
      setErro(e.message || "Erro ao gerar pacote contábil.");
    }
    setGerandoPacote(false);
  };

  const handleGerarResumoInterno = async () => {
    setGerandoResumo(true);
    setErro(null);
    try {
      const blob = await gerarResumoInternoContabil(mes, ano);
      const url = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
      window.open(url, "_blank");
    } catch (e) {
      setErro(e.message || "Erro ao gerar resumo interno.");
    }
    setGerandoResumo(false);
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Contabilidade</h1>
        <div className={styles.headerActions}>
          <div className={styles.navMes}>
            <button className={styles.btnNav} onClick={() => navegarMes(-1)}>‹</button>
            <span className={styles.mesLabel}>{MESES[mes - 1]} {ano}</span>
            <button className={styles.btnNav} onClick={() => navegarMes(1)}>›</button>
          </div>
          <button
            className={styles.btnSecondary}
            onClick={handleGerarResumoInterno}
            disabled={gerandoResumo}
          >
            {gerandoResumo ? "Gerando…" : "Resumo Interno (PDF)"}
          </button>
          <button
            className={styles.btnNovo}
            onClick={handleGerarPacote}
            disabled={gerandoPacote}
          >
            {gerandoPacote ? "Gerando…" : "Gerar Pacote Contábil (.zip)"}
          </button>
        </div>
      </div>

      {erro && <p className={styles.erro}>{erro}</p>}

      <div className={styles.resumoGrid}>
        <div className={`${styles.resumoCard} ${styles.resumoBorderSucesso}`}>
          <span className={styles.resumoLabel}>Total Vendas</span>
          <span className={styles.resumoValor}>{moeda(totalVendas)}</span>
          <span className={styles.resumoSub}>{dados.notas_venda.length} nota(s) com NF</span>
        </div>
        <div className={`${styles.resumoCard} ${styles.resumoBorderPerigo}`}>
          <span className={styles.resumoLabel}>Total Compras</span>
          <span className={styles.resumoValor}>{moeda(totalCompras)}</span>
          <span className={styles.resumoSub}>{dados.notas_compra.length} nota(s) com NF</span>
        </div>
        <div className={`${styles.resumoCard} ${styles.resumoBorderNeutro}`}>
          <span className={styles.resumoLabel}>Boletos Pagos</span>
          <span className={styles.resumoValor}>{moeda(totalPago)}</span>
          <span className={styles.resumoSub}>{dados.boletos_pagos.length} boleto(s)</span>
        </div>
        <div className={`${styles.resumoCard} ${resultado < 0 ? styles.resumoBorderPerigo : styles.resumoBorderNeutro}`}>
          <span className={styles.resumoLabel}>Resultado</span>
          <span className={styles.resumoValor}>{moeda(resultado)}</span>
          <span className={styles.resumoSub}>Vendas − Compras (NF)</span>
        </div>
      </div>

      {/* ── Notas de Venda ── */}
      <section className={styles.section}>
        <div className={`sc-card ${styles.tableCard}`}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTitle}>Notas Fiscais de Venda</span>
            <span className={styles.sectionMeta}>Total: {moeda(totalVendas)}</span>
          </div>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>NF</th>
                  <th>Data</th>
                  <th>Valor</th>
                  <th>Documento</th>
                </tr>
              </thead>
              <tbody>
                {dados.notas_venda.map((v) => (
                  <tr key={v.id}>
                    <td>{v.cliente}</td>
                    <td>{v.numero_nf || "—"}</td>
                    <td>{dataFmt(v.data_venda)}</td>
                    <td className={styles.tdValor}>{moeda(v.valor_total)}</td>
                    <td>
                      <button className={styles.btnLink} onClick={() => abrirArquivo(v.nf_pdf_path)}>
                        {v.nf_nome || "Abrir"}
                      </button>
                    </td>
                  </tr>
                ))}
                {dados.notas_venda.length === 0 && (
                  <tr>
                    <td colSpan={5} className={styles.empty}>
                      {loading ? "Carregando…" : "Nenhuma venda com NF anexada neste mês."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── Notas de Compra ── */}
      <section className={styles.section}>
        <div className={`sc-card ${styles.tableCard}`}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTitle}>Notas Fiscais de Compra</span>
            <span className={styles.sectionMeta}>Total: {moeda(totalCompras)}</span>
          </div>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Fornecedor</th>
                  <th>NF</th>
                  <th>Data</th>
                  <th>Valor</th>
                  <th>Documento</th>
                </tr>
              </thead>
              <tbody>
                {dados.notas_compra.map((c) => (
                  <tr key={c.id}>
                    <td>{c.fornecedor}</td>
                    <td>{c.numero_nf || "—"}</td>
                    <td>{dataFmt(c.data_compra)}</td>
                    <td className={styles.tdValor}>{moeda(c.valor_total)}</td>
                    <td>
                      <button className={styles.btnLink} onClick={() => abrirArquivo(c.nf_pdf_path)}>
                        {c.nf_nome || "Abrir"}
                      </button>
                    </td>
                  </tr>
                ))}
                {dados.notas_compra.length === 0 && (
                  <tr>
                    <td colSpan={5} className={styles.empty}>
                      {loading ? "Carregando…" : "Nenhuma compra com NF anexada neste mês."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── Boletos Pagos ── */}
      <section className={styles.section}>
        <div className={`sc-card ${styles.tableCard}`}>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTitle}>Boletos Pagos</span>
            <span className={styles.sectionMeta}>Total: {moeda(totalPago)}</span>
          </div>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Fornecedor/Cliente</th>
                  <th>NF</th>
                  <th>Parcela</th>
                  <th>Data Pagto</th>
                  <th>Valor</th>
                  <th>Boleto</th>
                  <th>Nota Fiscal</th>
                </tr>
              </thead>
              <tbody>
                {dados.boletos_pagos.map((b) => (
                  <tr key={b.lancamento_id}>
                    <td>{b.fornecedor_cliente}</td>
                    <td>{b.numero_nf || "—"}</td>
                    <td>
                      {b.parcela_numero && b.parcela_total
                        ? `${b.parcela_numero}/${b.parcela_total}`
                        : "Único"}
                    </td>
                    <td>{dataFmt(b.data_pagamento)}</td>
                    <td className={styles.tdValor}>{moeda(b.valor)}</td>
                    <td>
                      <button className={styles.btnLink} onClick={() => abrirArquivo(b.boleto_pdf_path)}>
                        Abrir
                      </button>
                    </td>
                    <td>
                      <button
                        className={styles.btnLink}
                        onClick={() => abrirArquivo(b.nf_pdf_path)}
                        disabled={!b.nf_pdf_path}
                      >
                        {b.nf_pdf_path ? "Abrir" : "—"}
                      </button>
                    </td>
                  </tr>
                ))}
                {dados.boletos_pagos.length === 0 && (
                  <tr>
                    <td colSpan={7} className={styles.empty}>
                      {loading ? "Carregando…" : "Nenhum boleto pago neste mês."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
