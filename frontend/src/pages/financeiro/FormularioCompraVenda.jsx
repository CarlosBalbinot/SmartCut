import { useState } from "react";
import styles from "./comprasVendas.module.css";

const hojeISO = () => new Date().toISOString().split("T")[0];

const FORM_VAZIO = {
  parceiro: "",
  descricao: "",
  valor_total: "",
  num_parcelas: "1",
  primeiro_vencimento: hojeISO(),
  categoria: "",
};

/*
 * Props:
 *   tipo     — "compra" | "venda"
 *   saving   — bool
 *   erro     — string | null
 *   onSalvar — (formData, nfFile, boletos[]) => void
 *   onFechar — () => void
 */
export default function FormularioCompraVenda({ tipo, saving, erro, onSalvar, onFechar }) {
  const isCompra  = tipo === "compra";
  const [form, setForm]     = useState(FORM_VAZIO);
  const [nfFile, setNfFile] = useState(null);
  const [boletos, setBoletos] = useState([null]);

  const setF = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const numParcelas = Math.max(1, Math.min(12, parseInt(form.num_parcelas) || 1));

  const handleParcelasChange = (e) => {
    const n = Math.max(1, Math.min(12, parseInt(e.target.value) || 1));
    setForm((f) => ({ ...f, num_parcelas: String(n) }));
    setBoletos((prev) => Array.from({ length: n }, (_, i) => prev[i] ?? null));
  };

  const handleBoleto = (i) => (e) => {
    const file = e.target.files[0] ?? null;
    setBoletos((prev) => { const next = [...prev]; next[i] = file; return next; });
  };

  const handleSubmit = () => {
    const parceiro = form.parceiro.trim();
    const formData = {
      ...(isCompra ? { fornecedor: parceiro } : { cliente: parceiro }),
      descricao:           form.descricao.trim() || null,
      valor_total:         parseFloat(form.valor_total),
      data_compra:         hojeISO(),
      parcelas:            numParcelas,
      primeiro_vencimento: form.primeiro_vencimento,
    };
    onSalvar(formData, nfFile, boletos.slice(0, numParcelas));
  };

  const parceiroLabel = isCompra ? "Fornecedor" : "Cliente";
  const btnLabel      = saving ? "Salvando…" : isCompra ? "Criar Compra" : "Criar Venda";

  return (
    <>
      <div className={styles.modalHead}>
        <h2 className={styles.modalTitle}>
          {isCompra ? "Nova Compra" : "Nova Venda"}
        </h2>
        <button className={styles.btnClose} onClick={onFechar} disabled={saving}>×</button>
      </div>

      <div className={styles.modalBody}>
        <div className={styles.fieldGrid}>
          <label className={`${styles.field} ${styles.fieldFull}`}>
            <span>{parceiroLabel} *</span>
            <input
              className={styles.input}
              value={form.parceiro}
              onChange={setF("parceiro")}
              placeholder={isCompra ? "Nome do fornecedor" : "Nome do cliente"}
            />
          </label>

          <label className={`${styles.field} ${styles.fieldFull}`}>
            <span>Descrição</span>
            <input
              className={styles.input}
              value={form.descricao}
              onChange={setF("descricao")}
              placeholder="Descrição opcional"
            />
          </label>

          <label className={styles.field}>
            <span>Valor Total *</span>
            <input
              type="number"
              min="0"
              step="0.01"
              className={styles.input}
              value={form.valor_total}
              onChange={setF("valor_total")}
              placeholder="0,00"
            />
          </label>

          <label className={styles.field}>
            <span>Categoria</span>
            <input
              className={styles.input}
              value={form.categoria}
              onChange={setF("categoria")}
              placeholder="Ex: Matéria-prima"
            />
          </label>

          <label className={styles.field}>
            <span>Nº de Parcelas *</span>
            <select
              className={styles.input}
              value={form.num_parcelas}
              onChange={handleParcelasChange}
            >
              {Array.from({ length: 12 }, (_, i) => (
                <option key={i + 1} value={i + 1}>{i + 1}x</option>
              ))}
            </select>
          </label>

          <label className={styles.field}>
            <span>1º Vencimento *</span>
            <input
              type="date"
              className={styles.input}
              value={form.primeiro_vencimento}
              onChange={setF("primeiro_vencimento")}
            />
          </label>
        </div>

        {/* ── Anexos ── */}
        <div className={styles.uploadSection}>
          <p className={styles.uploadSectionLabel}>Anexos</p>

          <label className={styles.field}>
            <span>Nota Fiscal (PDF)</span>
            <input
              type="file"
              accept=".pdf,application/pdf"
              className={styles.inputFile}
              onChange={(e) => setNfFile(e.target.files[0] ?? null)}
            />
          </label>

          <div className={styles.boletosGrid}>
            {Array.from({ length: numParcelas }, (_, i) => (
              <label key={i} className={styles.field}>
                <span>Boleto {numParcelas > 1 ? i + 1 : ""} (PDF)</span>
                <input
                  type="file"
                  accept=".pdf,application/pdf"
                  className={styles.inputFile}
                  onChange={handleBoleto(i)}
                />
              </label>
            ))}
          </div>
        </div>

        {erro && <p className={styles.erro}>{erro}</p>}
      </div>

      <div className={styles.modalActions}>
        <button className={styles.btnSecondary} onClick={onFechar} disabled={saving}>
          Cancelar
        </button>
        <button className={styles.btnPrimary} onClick={handleSubmit} disabled={saving}>
          {btnLabel}
        </button>
      </div>
    </>
  );
}
