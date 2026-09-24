import { useState, useEffect, useCallback } from "react";
import { listar, criar, atualizar, excluir } from "../api/tes";
import { getFiscal } from "../api/configuracaoFiscal";
import { useAuth } from "../auth/useAuth";
import styles from "./TESPage.module.css";

const MODULO = "fiscal_nfe";

const CSOSN_OPCOES = [
  { valor: "101", label: "101 - Tributada pelo Simples com permissão de crédito" },
  { valor: "102", label: "102 - Tributada pelo Simples sem permissão de crédito" },
  { valor: "103", label: "103 - Isenção do ICMS para faixa de receita bruta" },
  { valor: "201", label: "201 - Com ICMS ST e permissão de crédito" },
  { valor: "202", label: "202 - Com ICMS ST sem permissão de crédito" },
  { valor: "203", label: "203 - Com ICMS ST e isenção para faixa de receita bruta" },
  { valor: "300", label: "300 - Imune" },
  { valor: "400", label: "400 - Não tributada pelo Simples Nacional" },
  { valor: "500", label: "500 - ICMS cobrado anteriormente por ST ou antecipação" },
  { valor: "900", label: "900 - Outros" },
];

const ORIGEM_OPCOES = [
  { valor: "0", label: "0 - Nacional" },
  { valor: "1", label: "1 - Estrangeira - Importação direta" },
  { valor: "2", label: "2 - Estrangeira - Adquirida no mercado interno" },
  { valor: "3", label: "3 - Nacional - Conteúdo importado acima de 40%" },
  { valor: "4", label: "4 - Nacional - Processos produtivos básicos" },
  { valor: "5", label: "5 - Nacional - Conteúdo importado até 40%" },
  { valor: "6", label: "6 - Estrangeira - Importação direta sem similar nacional" },
  { valor: "7", label: "7 - Estrangeira - Mercado interno sem similar nacional" },
  { valor: "8", label: "8 - Nacional - Conteúdo importado acima de 70%" },
];

const MODALIDADE_BC_OPCOES = [
  { valor: "0", label: "0 - Margem Valor Agregado" },
  { valor: "1", label: "1 - Pauta" },
  { valor: "2", label: "2 - Preço Tabelado Máximo" },
  { valor: "3", label: "3 - Valor da Operação" },
];

const CST_ICMS_OPCOES = [
  { valor: "00", label: "00 - Tributada integralmente" },
  { valor: "10", label: "10 - Tributada e com cobrança do ICMS por ST" },
  { valor: "20", label: "20 - Com redução de BC" },
  { valor: "30", label: "30 - Isenta ou não tributada e com cobrança do ICMS por ST" },
  { valor: "40", label: "40 - Isenta" },
  { valor: "41", label: "41 - Não tributada" },
  { valor: "50", label: "50 - Suspensão" },
  { valor: "51", label: "51 - Diferimento" },
  { valor: "60", label: "60 - ICMS cobrado anteriormente por ST" },
  { valor: "70", label: "70 - Com redução de BC e cobrança do ICMS por ST" },
  { valor: "90", label: "90 - Outras" },
];

const VAZIO = {
  codigo: "",
  descricao: "",
  tipo: "Saída",
  natureza_operacao: "",
  cfop: "",
  csosn: "101",
  cst_icms: "00",
  origem: "0",
  modalidade_bc_icms: "3",
  reducao_bc_icms: "0",
  aliquota_icms: "0",
  valor_icms: "0",
  pis_cst: "",
  pis_aliquota: "0",
  cofins_cst: "",
  cofins_aliquota: "0",
  gera_financeiro: true,
  movimenta_estoque: true,
  situacao: "Ativo",
};

const num2 = (v) => Number(parseFloat(v || 0).toFixed(2));

export default function TESPage() {
  const { hasPermission } = useAuth();
  const [lista, setLista] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState(null);
  const [regimeTributario, setRegimeTributario] = useState("Simples Nacional");

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      setLista((await listar()) || []);
    } catch {
      setLista([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  useEffect(() => {
    getFiscal()
      .then((d) => { if (d?.regime_tributario) setRegimeTributario(d.regime_tributario); })
      .catch(() => {});
  }, []);

  const usaCstIcms = regimeTributario === "Lucro Presumido" || regimeTributario === "Lucro Real";

  const abrirNovo = () => { setModal({ ...VAZIO }); setErro(null); };

  const abrirEditar = (t) => {
    setModal({
      id: t.id,
      codigo: t.codigo || "",
      descricao: t.descricao || "",
      tipo: t.tipo || "Saída",
      natureza_operacao: t.natureza_operacao || "",
      cfop: t.cfop || "",
      csosn: t.csosn || "101",
      cst_icms: t.cst_icms || "00",
      origem: t.origem || "0",
      modalidade_bc_icms: t.modalidade_bc_icms || "3",
      reducao_bc_icms: String(t.reducao_bc_icms ?? 0),
      aliquota_icms: String(t.aliquota_icms ?? 0),
      valor_icms: String(t.valor_icms ?? 0),
      pis_cst: t.pis_cst || "",
      pis_aliquota: String(t.pis_aliquota ?? 0),
      cofins_cst: t.cofins_cst || "",
      cofins_aliquota: String(t.cofins_aliquota ?? 0),
      gera_financeiro: t.gera_financeiro ?? true,
      movimenta_estoque: t.movimenta_estoque ?? true,
      situacao: t.situacao || "Ativo",
    });
    setErro(null);
  };

  const fecharModal = () => { setModal(null); setErro(null); };
  const setF = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.value }));
  const setFUpper = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.value.toUpperCase() }));
  const setCheck = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.checked }));

  const handleSalvar = async () => {
    if (!modal.codigo.trim()) { setErro("Código é obrigatório."); return; }
    if (!modal.descricao.trim()) { setErro("Descrição é obrigatória."); return; }
    if (!modal.natureza_operacao.trim()) { setErro("Natureza da operação é obrigatória."); return; }
    if (!modal.cfop.trim()) { setErro("CFOP é obrigatório."); return; }
    if (!modal.pis_cst.trim()) { setErro("CST do PIS é obrigatório."); return; }
    if (!modal.cofins_cst.trim()) { setErro("CST do COFINS é obrigatório."); return; }

    setSaving(true); setErro(null);
    try {
      const payload = {
        codigo: modal.codigo.trim(),
        descricao: modal.descricao.trim(),
        tipo: modal.tipo,
        natureza_operacao: modal.natureza_operacao.trim(),
        cfop: modal.cfop.trim(),
        csosn: modal.csosn,
        cst_icms: modal.cst_icms || null,
        origem: modal.origem,
        modalidade_bc_icms: modal.modalidade_bc_icms,
        reducao_bc_icms: num2(modal.reducao_bc_icms),
        aliquota_icms: num2(modal.aliquota_icms),
        valor_icms: num2(modal.valor_icms),
        pis_cst: modal.pis_cst.trim(),
        pis_aliquota: num2(modal.pis_aliquota),
        cofins_cst: modal.cofins_cst.trim(),
        cofins_aliquota: num2(modal.cofins_aliquota),
        gera_financeiro: modal.gera_financeiro,
        movimenta_estoque: modal.movimenta_estoque,
        situacao: modal.situacao,
      };
      if (modal.id) {
        await atualizar(modal.id, payload);
      } else {
        await criar(payload);
      }
      await carregar();
      fecharModal();
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleExcluir = async (id) => {
    if (!window.confirm("Deseja excluir este TES?")) return;
    try { await excluir(id); await carregar(); } catch {}
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>TES</h1>
        {hasPermission(MODULO, "criar") && (
          <button className={styles.btnNovo} onClick={abrirNovo}>+ Novo TES</button>
        )}
      </div>

      <div className={`sc-card ${styles.tableCard}`}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Código</th>
              <th>Descrição</th>
              <th>Tipo</th>
              <th>CFOP</th>
              <th>CSOSN</th>
              <th>Situação</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className={styles.empty}>Carregando…</td></tr>
            ) : lista.length === 0 ? (
              <tr><td colSpan={7} className={styles.empty}>Nenhum TES cadastrado.</td></tr>
            ) : lista.map((t) => (
              <tr key={t.id}>
                <td className={styles.tdMono}>{t.codigo}</td>
                <td>{t.descricao}</td>
                <td>
                  <span className={`${styles.badge} ${t.tipo === "Entrada" ? styles.badge_entrada : styles.badge_saida}`}>
                    {t.tipo}
                  </span>
                </td>
                <td className={styles.tdMono}>{t.cfop}</td>
                <td className={styles.tdMono}>{t.csosn}</td>
                <td>
                  <span className={`${styles.badge} ${t.situacao === "Ativo" ? styles.badge_ativo : styles.badge_inativo}`}>
                    {t.situacao}
                  </span>
                </td>
                <td>
                  <div className={styles.actions}>
                    {hasPermission(MODULO, "editar") && (
                      <button className={styles.btnLink} onClick={() => abrirEditar(t)}>Editar</button>
                    )}
                    {hasPermission(MODULO, "excluir") && (
                      <button className={`${styles.btnLink} ${styles.btnDanger}`} onClick={() => handleExcluir(t.id)}>
                        Excluir
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className={styles.overlay} onClick={fecharModal}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>{modal.id ? "Editar TES" : "Novo TES"}</h2>
              <button className={styles.btnClose} onClick={fecharModal}>×</button>
            </div>

            <div className={styles.modalBody}>
              <p className={styles.sectionLabel}>Identificação</p>
              <div className={styles.fieldGrid}>
                <label className={styles.field}>
                  <span>Código *</span>
                  <input className={styles.input} value={modal.codigo} onChange={setF("codigo")} placeholder="Ex: 5102" />
                </label>

                <label className={styles.field}>
                  <span>Tipo</span>
                  <select className={styles.input} value={modal.tipo} onChange={setF("tipo")}>
                    <option value="Entrada">Entrada</option>
                    <option value="Saída">Saída</option>
                  </select>
                </label>

                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Descrição *</span>
                  <input className={styles.input} value={modal.descricao} onChange={setFUpper("descricao")} placeholder="Ex: Venda de mercadoria" />
                </label>

                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Natureza da Operação *</span>
                  <input className={styles.input} value={modal.natureza_operacao} onChange={setFUpper("natureza_operacao")} placeholder="Texto que vai para o XML da NF-e" />
                </label>

                <label className={styles.field}>
                  <span>CFOP *</span>
                  <input className={styles.input} value={modal.cfop} onChange={setFUpper("cfop")} placeholder="Ex: 5102" maxLength={10} />
                </label>

                <label className={styles.field}>
                  <span>Situação</span>
                  <select className={styles.input} value={modal.situacao} onChange={setF("situacao")}>
                    <option value="Ativo">Ativo</option>
                    <option value="Inativo">Inativo</option>
                  </select>
                </label>
              </div>

              <p className={`${styles.sectionLabel} ${styles.sectionLabelMt}`}>ICMS</p>
              <div className={styles.fieldGrid}>
                {usaCstIcms ? (
                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>CST do ICMS</span>
                    <select className={styles.input} value={modal.cst_icms} onChange={setF("cst_icms")}>
                      {CST_ICMS_OPCOES.map((o) => (
                        <option key={o.valor} value={o.valor}>{o.label}</option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>CSOSN</span>
                    <select className={styles.input} value={modal.csosn} onChange={setF("csosn")}>
                      {CSOSN_OPCOES.map((o) => (
                        <option key={o.valor} value={o.valor}>{o.label}</option>
                      ))}
                    </select>
                  </label>
                )}

                <label className={styles.field}>
                  <span>Origem da Mercadoria</span>
                  <select className={styles.input} value={modal.origem} onChange={setF("origem")}>
                    {ORIGEM_OPCOES.map((o) => (
                      <option key={o.valor} value={o.valor}>{o.label}</option>
                    ))}
                  </select>
                </label>

                <label className={styles.field}>
                  <span>Modalidade BC ICMS</span>
                  <select className={styles.input} value={modal.modalidade_bc_icms} onChange={setF("modalidade_bc_icms")}>
                    {MODALIDADE_BC_OPCOES.map((o) => (
                      <option key={o.valor} value={o.valor}>{o.label}</option>
                    ))}
                  </select>
                </label>

                <label className={styles.field}>
                  <span>Redução BC ICMS (%)</span>
                  <input type="number" step="0.01" min="0" max="100" className={styles.input}
                    value={modal.reducao_bc_icms} onChange={setF("reducao_bc_icms")} />
                </label>

                <label className={styles.field}>
                  <span>Alíquota ICMS (%)</span>
                  <input type="number" step="0.01" min="0" max="100" className={styles.input}
                    value={modal.aliquota_icms} onChange={setF("aliquota_icms")} />
                </label>

                <label className={styles.field}>
                  <span>Valor ICMS (R$)</span>
                  <input type="number" step="0.01" min="0" className={styles.input}
                    value={modal.valor_icms} onChange={setF("valor_icms")} />
                </label>
              </div>

              <p className={`${styles.sectionLabel} ${styles.sectionLabelMt}`}>PIS / COFINS</p>
              <div className={styles.fieldGrid}>
                <label className={styles.field}>
                  <span>CST do PIS *</span>
                  <input className={styles.input} value={modal.pis_cst} onChange={setF("pis_cst")} placeholder="Ex: 01" maxLength={2} />
                </label>

                <label className={styles.field}>
                  <span>Alíquota PIS (%)</span>
                  <input type="number" step="0.01" min="0" max="100" className={styles.input}
                    value={modal.pis_aliquota} onChange={setF("pis_aliquota")} />
                </label>

                <label className={styles.field}>
                  <span>CST do COFINS *</span>
                  <input className={styles.input} value={modal.cofins_cst} onChange={setF("cofins_cst")} placeholder="Ex: 01" maxLength={2} />
                </label>

                <label className={styles.field}>
                  <span>Alíquota COFINS (%)</span>
                  <input type="number" step="0.01" min="0" max="100" className={styles.input}
                    value={modal.cofins_aliquota} onChange={setF("cofins_aliquota")} />
                </label>
              </div>

              <p className={`${styles.sectionLabel} ${styles.sectionLabelMt}`}>Comportamento</p>
              <div className={styles.checkRow}>
                <label className={styles.checkboxField}>
                  <input type="checkbox" checked={modal.gera_financeiro} onChange={setCheck("gera_financeiro")} />
                  <span>Gera lançamento financeiro</span>
                </label>
                <label className={styles.checkboxField}>
                  <input type="checkbox" checked={modal.movimenta_estoque} onChange={setCheck("movimenta_estoque")} />
                  <span>Movimenta estoque</span>
                </label>
              </div>

              {erro && <p className={styles.erro}>{erro}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharModal} disabled={saving}>Cancelar</button>
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
