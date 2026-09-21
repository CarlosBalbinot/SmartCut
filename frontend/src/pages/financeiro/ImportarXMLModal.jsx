import { useEffect, useState } from "react";
import { getCompra, getVendaFinanceira, uploadAnexo } from "../../api/financeiro";
import styles from "./comprasVendas.module.css";

const hojeISO = () => new Date().toISOString().split("T")[0];

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(v) || 0);

const dataFmt = (iso) => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("T")[0].split("-");
  return `${d}/${m}/${y}`;
};

function toItem(resultado, idx) {
  if (!resultado.sucesso) {
    return { key: idx, sucesso: false, erro: resultado.erro || "Erro ao processar XML." };
  }
  const d = resultado.dados;
  return {
    key: idx,
    sucesso: true,
    incluir: true,
    expandido: false,
    fornecedor: d.fornecedor || "",
    cnpj_fornecedor: d.cnpj_fornecedor || "",
    numero_nf: d.numero_nf || "",
    valor_total: String(d.valor_total ?? ""),
    data_emissao: (d.data_emissao || hojeISO()).split("T")[0],
    parcelas: (d.parcelas || []).map((p) => ({
      vencimento: (p.vencimento || "").split("T")[0],
      valor: String(p.valor ?? ""),
    })),
  };
}

/*
 * Props:
 *   arquivos      — File[] (XMLs selecionados)
 *   tipo          — "compra" | "venda" (default "compra")
 *   importarLote  — (arquivos: File[]) => Promise<ImportacaoXMLResultOut[]>
 *   importarFinal — (dados) => Promise (cria a compra/venda com as parcelas revisadas)
 *   onFechar      — () => void
 *   onConcluido   — (sucesso: number, falhas: number) => void
 */
export default function ImportarXMLModal({
  arquivos, tipo = "compra", importarLote, importarFinal, onFechar, onConcluido,
}) {
  const isCompra = tipo === "compra";
  const parceiroLabel = isCompra ? "Fornecedor" : "Cliente";
  const campoParceiro = isCompra ? "fornecedor" : "cliente";
  const campoData     = isCompra ? "data_compra" : "data_venda";

  const [carregando, setCarregando] = useState(true);
  const [erroGeral,  setErroGeral]  = useState(null);
  const [itens,      setItens]      = useState([]);
  const [importando, setImportando] = useState(false);

  useEffect(() => {
    importarLote(arquivos)
      .then((resultados) => setItens((resultados || []).map(toItem)))
      .catch((e) => setErroGeral(e.message || "Erro ao importar XMLs."))
      .finally(() => setCarregando(false));
  }, [arquivos, importarLote]);

  const toggleIncluir = (key) => (e) => {
    e.stopPropagation();
    setItens((prev) => prev.map((it) => (it.key === key ? { ...it, incluir: !it.incluir } : it)));
  };

  const toggleExpandido = (key) => {
    setItens((prev) => prev.map((it) => (it.key === key ? { ...it, expandido: !it.expandido } : it)));
  };

  const updateCampo = (key, campo) => (e) => {
    const valor = e.target.value;
    setItens((prev) => prev.map((it) => (it.key === key ? { ...it, [campo]: valor } : it)));
  };

  const updateParcela = (key, idx, campo) => (e) => {
    const valor = e.target.value;
    setItens((prev) => prev.map((it) => {
      if (it.key !== key) return it;
      return { ...it, parcelas: it.parcelas.map((p, i) => (i === idx ? { ...p, [campo]: valor } : p)) };
    }));
  };

  const addParcela = (key) => (e) => {
    e.stopPropagation();
    setItens((prev) => prev.map((it) => (
      it.key === key
        ? { ...it, parcelas: [...it.parcelas, { vencimento: hojeISO(), valor: "" }] }
        : it
    )));
  };

  const removeParcela = (key, idx) => (e) => {
    e.stopPropagation();
    setItens((prev) => prev.map((it) => (
      it.key === key ? { ...it, parcelas: it.parcelas.filter((_, i) => i !== idx) } : it
    )));
  };

  const totalSelecionados = itens.filter((it) => it.sucesso && it.incluir).length;

  const handleConfirmar = async () => {
    const selecionados = itens.filter((it) => it.sucesso && it.incluir);
    const invalido = selecionados.some((it) =>
      it.parcelas.length === 0 ||
      it.parcelas.some((p) => !p.vencimento || !p.valor || isNaN(parseFloat(p.valor)))
    );
    if (invalido) {
      setErroGeral(
        "Existe uma NF selecionada com parcela sem data de vencimento ou valor. " +
        "Preencha os campos ou desmarque a NF."
      );
      return;
    }

    setImportando(true);
    setErroGeral(null);
    let sucesso = 0;
    let falhas = 0;
    for (const it of selecionados) {
      try {
        const criada = await importarFinal({
          [campoParceiro]: it.fornecedor.trim(),
          descricao: it.numero_nf ? `NF ${it.numero_nf}` : null,
          numero_nf: it.numero_nf || null,
          valor_total: parseFloat(it.valor_total) || 0,
          [campoData]: it.data_emissao,
          parcelas: it.parcelas.map((p) => ({
            vencimento: p.vencimento,
            valor: parseFloat(p.valor) || 0,
          })),
        });
        sucesso += 1;

        // Guarda o XML original como anexo (tipo='XML') na primeira parcela,
        // para que ele possa ser recuperado depois sem precisar reimportar.
        const arquivoOriginal = arquivos[it.key];
        if (arquivoOriginal && criada?.id) {
          try {
            const full = isCompra
              ? await getCompra(criada.id)
              : await getVendaFinanceira(criada.id);
            const primeiraParcela = (full.lancamentos || full.parcelas || [])[0];
            if (primeiraParcela) {
              await uploadAnexo(primeiraParcela.id, arquivoOriginal, "XML");
            }
          } catch {}
        }
      } catch {
        falhas += 1;
      }
    }
    setImportando(false);
    onConcluido(sucesso, falhas);
  };

  return (
    <div className={styles.overlay} onClick={() => !importando && onFechar()}>
      <div className={`${styles.modal} ${styles.modalLarge}`} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHead}>
          <h2 className={styles.modalTitle}>
            Revisar Importação de NFs {isCompra ? "— Compras" : "— Vendas"}
          </h2>
          <button className={styles.btnClose} onClick={onFechar} disabled={importando}>×</button>
        </div>

        <div className={styles.modalBody}>
          {carregando ? (
            <p className={styles.expandLoading}>Lendo XMLs…</p>
          ) : (
            <>
              {isCompra && !!window.electronAPI?.openComprasFolder && (
                <button
                  type="button"
                  className={styles.folderLink}
                  onClick={() => window.electronAPI.openComprasFolder()}
                >
                  📁 Abrir pasta de Compras
                </button>
              )}

              <div className={styles.importList}>
                {itens.map((it) => {
                  if (!it.sucesso) {
                    return (
                      <div key={it.key} className={`${styles.importCard} ${styles.importErrorCard}`}>
                        <p className={styles.importErrorText}>✕ {it.erro}</p>
                      </div>
                    );
                  }
                  return (
                    <div key={it.key} className={styles.importCard}>
                      <div className={styles.importCardHeader} onClick={() => toggleExpandido(it.key)}>
                        <input
                          type="checkbox"
                          className={styles.importCheckbox}
                          checked={it.incluir}
                          onChange={toggleIncluir(it.key)}
                          onClick={(e) => e.stopPropagation()}
                        />
                        <div className={styles.importSummary}>
                          <span><strong>{parceiroLabel}:</strong> {it.fornecedor || "—"}</span>
                          <span><strong>NF:</strong> {it.numero_nf || "—"}</span>
                          <span><strong>Data:</strong> {dataFmt(it.data_emissao)}</span>
                          <span><strong>Total:</strong> {moeda(it.valor_total)}</span>
                        </div>
                        <button
                          type="button"
                          className={`${styles.btnExpand} ${it.expandido ? styles.btnExpandOpen : ""}`}
                        >
                          ▶
                        </button>
                      </div>

                      {it.expandido && (
                        <div className={styles.importCardBody}>
                          <div className={styles.fieldGrid}>
                            <label className={`${styles.field} ${styles.fieldFull}`}>
                              <span>{parceiroLabel}</span>
                              <input
                                className={styles.input}
                                value={it.fornecedor}
                                onChange={updateCampo(it.key, "fornecedor")}
                              />
                            </label>
                            <label className={styles.field}>
                              <span>Valor Total</span>
                              <input
                                type="number" min="0" step="0.01"
                                className={styles.input}
                                value={it.valor_total}
                                onChange={updateCampo(it.key, "valor_total")}
                              />
                            </label>
                            <label className={styles.field}>
                              <span>Data de Emissão</span>
                              <input
                                type="date"
                                className={styles.input}
                                value={it.data_emissao}
                                onChange={updateCampo(it.key, "data_emissao")}
                              />
                            </label>
                          </div>

                          <div className={styles.uploadSection}>
                            <p className={styles.uploadSectionLabel}>Parcelas</p>
                            {it.parcelas.length === 0 && (
                              <p className={styles.expandLoading}>
                                Nenhuma parcela lida do XML — adicione manualmente.
                              </p>
                            )}
                            {it.parcelas.map((p, idx) => (
                              <div key={idx} className={styles.parcelaEditRow}>
                                <input
                                  type="date"
                                  className={styles.input}
                                  value={p.vencimento}
                                  onChange={updateParcela(it.key, idx, "vencimento")}
                                />
                                <input
                                  type="number" min="0" step="0.01"
                                  className={styles.input}
                                  value={p.valor}
                                  onChange={updateParcela(it.key, idx, "valor")}
                                  placeholder="Valor"
                                />
                                <button
                                  type="button"
                                  className={styles.btnRemoveParcela}
                                  onClick={removeParcela(it.key, idx)}
                                  title="Remover parcela"
                                >
                                  ×
                                </button>
                              </div>
                            ))}
                            <button
                              type="button"
                              className={styles.btnAddParcela}
                              onClick={addParcela(it.key)}
                            >
                              + Adicionar parcela
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

                {itens.length === 0 && (
                  <p className={styles.expandLoading}>Nenhum arquivo processado.</p>
                )}
              </div>

              {erroGeral && <p className={styles.erro}>{erroGeral}</p>}
            </>
          )}
        </div>

        <div className={styles.modalActions}>
          <button className={styles.btnSecondary} onClick={onFechar} disabled={importando}>
            Cancelar
          </button>
          <button
            className={styles.btnPrimary}
            onClick={handleConfirmar}
            disabled={importando || carregando || totalSelecionados === 0}
          >
            {importando ? "Importando…" : `Confirmar Importação (${totalSelecionados})`}
          </button>
        </div>
      </div>
    </div>
  );
}
