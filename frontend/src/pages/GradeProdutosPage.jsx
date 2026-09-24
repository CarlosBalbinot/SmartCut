import { useState, useEffect, useCallback, useMemo } from "react";
import * as gradeProdutosApi from "../api/gradeProdutos";
import { gruposProdutoApi } from "../api/produtos";
import * as tabelasGradeApi from "../api/tabelasGrade";
import * as configuracaoGradeApi from "../api/configuracaoGrade";
import { useAuth } from "../auth/useAuth";
import styles from "./GradeProdutosPage.module.css";

const MODULO = "cadastros_produtos";

const WIZARD_VAZIO = {
  grupo_id: "",
  descricao: "",
  unidade: "",
  preco_venda: "0",
  custo: "0",
  status: "ativo",
  linha_grade_id: "",
  coluna_grade_id: "",
};

const comboKey = (linhaId, colunaId) => `${linhaId ?? "null"}|${colunaId ?? "null"}`;

export default function GradeProdutosPage() {
  const { hasPermission } = useAuth();
  const podeCriar = hasPermission(MODULO, "criar");
  const podeEditar = hasPermission(MODULO, "editar");

  const [produtos, setProdutos] = useState([]);
  const [grupos, setGrupos] = useState([]);
  const [tabelasGrade, setTabelasGrade] = useState([]);
  const [configGrade, setConfigGrade] = useState(null);
  const [skusCount, setSkusCount] = useState({});
  const [loading, setLoading] = useState(true);
  const [filtroGrupo, setFiltroGrupo] = useState("");
  const [toast, setToast] = useState(null);

  const [wizard, setWizard] = useState(null);
  const [savingWizard, setSavingWizard] = useState(false);
  const [erroWizard, setErroWizard] = useState(null);

  const showToast = (text) => { setToast(text); setTimeout(() => setToast(null), 6000); };

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const [g, t, cfg, todos] = await Promise.all([
        gruposProdutoApi.listar().catch(() => []),
        tabelasGradeApi.listar().catch(() => []),
        configuracaoGradeApi.obter().catch(() => null),
        gradeProdutosApi.listarProdutos(filtroGrupo ? { grupoId: filtroGrupo } : {}).catch(() => []),
      ]);
      setGrupos(g || []);
      setTabelasGrade(t || []);
      setConfigGrade(cfg);

      const grade = (todos || []).filter((p) => p.is_pai || p.linha_grade_id || p.coluna_grade_id);
      setProdutos(grade);

      const entradas = await Promise.all(
        grade.map(async (p) => [p.id, (await gradeProdutosApi.listarSkus(p.id).catch(() => [])).length])
      );
      setSkusCount(Object.fromEntries(entradas));
    } finally {
      setLoading(false);
    }
  }, [filtroGrupo]);

  useEffect(() => { carregar(); }, [carregar]);

  const gruposPorId = useMemo(() => {
    const map = {};
    grupos.forEach((g) => { map[g.id] = g; });
    return map;
  }, [grupos]);

  const tabelasPorId = useMemo(() => {
    const map = {};
    tabelasGrade.forEach((t) => { map[t.id] = t; });
    return map;
  }, [tabelasGrade]);

  // ── Wizard ──────────────────────────────────────────────────────────

  const abrirNovaGrade = () => {
    setWizard({
      step: 1, mode: "novo", produtoId: null,
      form: { ...WIZARD_VAZIO },
      existingSkus: [],
      selectedCombos: new Set(),
      ocultarLinhasDesmarcadas: false, ocultarColunasDesmarcadas: false,
      diff: { novos: [], removidos: [], mantidos: [] },
    });
    setErroWizard(null);
  };

  const abrirEditarGrade = async (produto) => {
    const skus = await gradeProdutosApi.listarSkus(produto.id).catch(() => []);
    const existingCombos = skus.map((s) => comboKey(s.linha_item_id, s.coluna_item_id));
    setWizard({
      step: 1, mode: "editar", produtoId: produto.id,
      form: {
        grupo_id: produto.grupo_id,
        descricao: produto.descricao,
        unidade: produto.unidade,
        preco_venda: String(produto.preco_venda ?? "0"),
        custo: String(produto.custo ?? "0"),
        status: produto.status || "ativo",
        linha_grade_id: produto.linha_grade_id || "",
        coluna_grade_id: produto.coluna_grade_id || "",
      },
      existingSkus: skus,
      selectedCombos: new Set(existingCombos),
      ocultarLinhasDesmarcadas: false, ocultarColunasDesmarcadas: false,
      diff: { novos: [], removidos: [], mantidos: [] },
    });
    setErroWizard(null);
  };

  const fecharWizard = () => { setWizard(null); setErroWizard(null); };

  const setWizardField = (key) => (e) => setWizard((w) => ({ ...w, form: { ...w.form, [key]: e.target.value } }));

  const linhaTabela = wizard?.form.linha_grade_id ? tabelasPorId[Number(wizard.form.linha_grade_id)] : null;
  const colunaTabela = wizard?.form.coluna_grade_id ? tabelasPorId[Number(wizard.form.coluna_grade_id)] : null;
  const linhaItens = useMemo(
    () => (linhaTabela?.itens || []).filter((i) => i.situacao === "Ativa").sort((a, b) => a.ordem - b.ordem),
    [linhaTabela]
  );
  const colunaItens = useMemo(
    () => (colunaTabela?.itens || []).filter((i) => i.situacao === "Ativa").sort((a, b) => a.ordem - b.ordem),
    [colunaTabela]
  );

  const temDoisEixos = linhaItens.length > 0 && colunaItens.length > 0;
  const temApenasLinha = linhaItens.length > 0 && colunaItens.length === 0;
  const temApenasColuna = colunaItens.length > 0 && linhaItens.length === 0;

  const allCombos = useMemo(() => {
    if (temDoisEixos) {
      const combos = [];
      linhaItens.forEach((li) => colunaItens.forEach((ci) => combos.push([li.id, ci.id])));
      return combos;
    }
    if (temApenasLinha) return linhaItens.map((li) => [li.id, null]);
    if (temApenasColuna) return colunaItens.map((ci) => [null, ci.id]);
    return [];
  }, [temDoisEixos, temApenasLinha, temApenasColuna, linhaItens, colunaItens]);

  const existingComboKeys = useMemo(
    () => new Set((wizard?.existingSkus || []).map((s) => comboKey(s.linha_item_id, s.coluna_item_id))),
    [wizard]
  );

  const toggleCombo = (linhaId, colunaId) => {
    setWizard((w) => {
      const key = comboKey(linhaId, colunaId);
      const next = new Set(w.selectedCombos);
      if (next.has(key)) next.delete(key); else next.add(key);
      return { ...w, selectedCombos: next };
    });
  };

  const selecionarTudo = () => {
    setWizard((w) => ({ ...w, selectedCombos: new Set(allCombos.map(([l, c]) => comboKey(l, c))) }));
  };

  const limparTudo = () => {
    setWizard((w) => ({ ...w, selectedCombos: new Set() }));
  };

  const linhaTemSelecao = (linhaId) =>
    colunaItens.some((ci) => wizard.selectedCombos.has(comboKey(linhaId, ci.id))) ||
    (temApenasLinha && wizard.selectedCombos.has(comboKey(linhaId, null)));

  const colunaTemSelecao = (colunaId) =>
    linhaItens.some((li) => wizard.selectedCombos.has(comboKey(li.id, colunaId))) ||
    (temApenasColuna && wizard.selectedCombos.has(comboKey(null, colunaId)));

  const linhasVisiveis = wizard?.ocultarLinhasDesmarcadas ? linhaItens.filter((li) => linhaTemSelecao(li.id)) : linhaItens;
  const colunasVisiveis = wizard?.ocultarColunasDesmarcadas ? colunaItens.filter((ci) => colunaTemSelecao(ci.id)) : colunaItens;

  const validarEtapa1 = () => {
    const f = wizard.form;
    if (!f.grupo_id) return "Selecione um grupo.";
    if (!f.descricao.trim()) return "Descrição é obrigatória.";
    if (!f.unidade.trim()) return "Unidade é obrigatória.";
    if (!f.linha_grade_id && !f.coluna_grade_id) return "Selecione ao menos uma Linha ou Coluna de Grade.";
    return null;
  };

  const avancarEtapa1 = async () => {
    const erro = validarEtapa1();
    if (erro) { setErroWizard(erro); return; }
    setSavingWizard(true); setErroWizard(null);
    try {
      const payload = {
        grupo_id: wizard.form.grupo_id,
        descricao: wizard.form.descricao.trim(),
        unidade: wizard.form.unidade.trim(),
        preco_venda: Number(wizard.form.preco_venda) || 0,
        custo: Number(wizard.form.custo) || 0,
        status: wizard.form.status,
        linha_grade_id: wizard.form.linha_grade_id ? Number(wizard.form.linha_grade_id) : null,
        coluna_grade_id: wizard.form.coluna_grade_id ? Number(wizard.form.coluna_grade_id) : null,
      };
      let produtoId = wizard.produtoId;
      if (wizard.mode === "editar" && produtoId) {
        await gradeProdutosApi.atualizarProdutoPai(produtoId, payload);
      } else {
        const criado = await gradeProdutosApi.criarProdutoPai(payload);
        produtoId = criado.id;
      }
      setWizard((w) => ({ ...w, produtoId, step: 2 }));
    } catch (e) {
      setErroWizard(e.message);
    } finally {
      setSavingWizard(false);
    }
  };

  const avancarEtapa2 = async () => {
    setErroWizard(null);
    const grupo = gruposPorId[wizard.form.grupo_id];
    const cfg = configGrade || { mascara: "{GRUPO}-{SEQ}-{COR}-{TAM}", separador: "-", tamanho_seq: 4 };
    const skusPorKey = new Map(wizard.existingSkus.map((s) => [comboKey(s.linha_item_id, s.coluna_item_id), s]));

    const novosKeys = [...wizard.selectedCombos].filter((k) => !existingComboKeys.has(k));
    const removidosKeys = [...existingComboKeys].filter((k) => !wizard.selectedCombos.has(k));
    const mantidosKeys = [...wizard.selectedCombos].filter((k) => existingComboKeys.has(k));

    const descPorId = (lista, id) => lista.find((i) => i.id === id)?.descricao || "—";

    const novos = await Promise.all(
      novosKeys.map(async (key, idx) => {
        const [l, c] = key.split("|");
        const linhaId = l === "null" ? null : Number(l);
        const colunaId = c === "null" ? null : Number(c);
        const linhaItem = linhaId ? linhaItens.find((i) => i.id === linhaId) : null;
        const colunaItem = colunaId ? colunaItens.find((i) => i.id === colunaId) : null;
        let codigo_preview = "—";
        try {
          const r = await configuracaoGradeApi.preview({
            mascara: cfg.mascara, separador: cfg.separador, tamanho_seq: cfg.tamanho_seq,
            grupo_prefixo: grupo?.prefixo || "", seq_exemplo: idx + 1,
            cor_codigo: linhaItem?.codigo_curto || null, tam_codigo: colunaItem?.codigo_curto || null,
          });
          codigo_preview = r.codigo_gerado;
        } catch { /* mantém "—" */ }
        return {
          key, linhaId, colunaId,
          linhaDesc: linhaId ? descPorId(linhaItens, linhaId) : "—",
          colunaDesc: colunaId ? descPorId(colunaItens, colunaId) : "—",
          codigo: codigo_preview,
        };
      })
    );

    const removidos = removidosKeys.map((key) => {
      const s = skusPorKey.get(key);
      return {
        key, skuId: s.id, codigo: s.codigo,
        linhaDesc: s.linha_item_descricao || "—", colunaDesc: s.coluna_item_descricao || "—",
      };
    });

    const mantidos = mantidosKeys.map((key) => {
      const s = skusPorKey.get(key);
      return {
        key, skuId: s.id, codigo: s.codigo,
        linhaDesc: s.linha_item_descricao || "—", colunaDesc: s.coluna_item_descricao || "—",
      };
    });

    setWizard((w) => ({ ...w, diff: { novos, removidos, mantidos }, step: 3 }));
  };

  const confirmarSincronizar = async () => {
    setSavingWizard(true); setErroWizard(null);
    try {
      const combinacoes = wizard.diff.novos.map((n) => ({ linha_item_id: n.linhaId, coluna_item_id: n.colunaId }));
      const removerSkuIds = wizard.diff.removidos.map((r) => r.skuId);
      const resp = await gradeProdutosApi.sincronizarSkus(wizard.produtoId, { combinacoes, removerSkuIds });
      const mantidosCount = wizard.diff.mantidos.length;
      let msg = `${resp.criados} criado(s), ${resp.removidos} removido(s), ${mantidosCount} mantido(s).`;
      if (resp.bloqueados.length > 0) {
        msg += ` ${resp.bloqueados.length} produto(s) não puderam ser removidos pois já possuem movimentação no sistema.`;
      }
      fecharWizard();
      await carregar();
      showToast(msg);
    } catch (e) {
      setErroWizard(e.message);
    } finally {
      setSavingWizard(false);
    }
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Grade de Produtos</h1>
        {podeCriar && (
          <button className={styles.btnNovo} onClick={abrirNovaGrade}>+ Nova Grade</button>
        )}
      </div>

      <div className={styles.toolbar}>
        <select className={styles.select} value={filtroGrupo} onChange={(e) => setFiltroGrupo(e.target.value)}>
          <option value="">Todos os grupos</option>
          {grupos.map((g) => (
            <option key={g.id} value={g.id}>{g.nome}</option>
          ))}
        </select>
      </div>

      {toast && <p className={styles.msgSucesso}>{toast}</p>}

      <div className={`sc-card ${styles.tableCard}`}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Código</th>
              <th>Descrição</th>
              <th>Grupo</th>
              <th>Linha Grade</th>
              <th>Coluna Grade</th>
              <th>QTD SKUs</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className={styles.empty}>Carregando…</td></tr>
            ) : produtos.length === 0 ? (
              <tr><td colSpan={7} className={styles.empty}>Nenhum produto com grade cadastrado.</td></tr>
            ) : produtos.map((p) => (
              <tr key={p.id}>
                <td className={styles.tdMono}>{p.codigo}</td>
                <td>{p.descricao}</td>
                <td>{gruposPorId[p.grupo_id]?.nome || "—"}</td>
                <td>{p.linha_grade_nome || "—"}</td>
                <td>{p.coluna_grade_nome || "—"}</td>
                <td>{skusCount[p.id] ?? "—"}</td>
                <td>
                  {podeEditar && (
                    <button className={styles.btnLink} onClick={() => abrirEditarGrade(p)}>Editar Grade</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {wizard && (
        <WizardModal
          wizard={wizard}
          grupos={grupos}
          tabelasGrade={tabelasGrade}
          linhaItens={linhaItens}
          colunaItens={colunaItens}
          linhasVisiveis={linhasVisiveis}
          colunasVisiveis={colunasVisiveis}
          temDoisEixos={temDoisEixos}
          temApenasLinha={temApenasLinha}
          temApenasColuna={temApenasColuna}
          existingComboKeys={existingComboKeys}
          saving={savingWizard}
          erro={erroWizard}
          onClose={fecharWizard}
          onFieldChange={setWizardField}
          onSetWizard={setWizard}
          onToggleCombo={toggleCombo}
          onSelecionarTudo={selecionarTudo}
          onLimparTudo={limparTudo}
          onAvancarEtapa1={avancarEtapa1}
          onAvancarEtapa2={avancarEtapa2}
          onConfirmar={confirmarSincronizar}
          onVoltar={() => setWizard((w) => ({ ...w, step: w.step - 1 }))}
        />
      )}
    </div>
  );
}

function WizardModal({
  wizard, grupos, tabelasGrade, linhasVisiveis, colunasVisiveis,
  temDoisEixos, temApenasLinha, temApenasColuna, existingComboKeys,
  saving, erro, onClose, onFieldChange, onSetWizard, onToggleCombo,
  onSelecionarTudo, onLimparTudo, onAvancarEtapa1, onAvancarEtapa2, onConfirmar, onVoltar,
}) {
  const grupoSelecionado = grupos.find((g) => g.id === wizard.form.grupo_id);
  const isCellSelected = (l, c) => wizard.selectedCombos.has(comboKey(l, c));
  const isCellExisting = (l, c) => existingComboKeys.has(comboKey(l, c));

  const semMudancas = wizard.step === 3 &&
    wizard.diff.novos.length === 0 && wizard.diff.removidos.length === 0;

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalWide} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHead}>
          <h2 className={styles.modalTitle}>{wizard.mode === "editar" ? "Editar Grade" : "Nova Grade"}</h2>
          <button className={styles.btnClose} onClick={onClose}>×</button>
        </div>

        <div className={styles.steps}>
          <span className={`${styles.step} ${wizard.step === 1 ? styles.stepAtivo : ""}`}>1. Dados do Produto</span>
          <span className={`${styles.step} ${wizard.step === 2 ? styles.stepAtivo : ""}`}>2. Combinações</span>
          <span className={`${styles.step} ${wizard.step === 3 ? styles.stepAtivo : ""}`}>3. Preview</span>
        </div>

        <div className={styles.modalBody}>
          {wizard.step === 1 && (
            <div className={styles.fieldGrid}>
              <label className={styles.field}>
                <span>Grupo *</span>
                <select className={styles.input} value={wizard.form.grupo_id} onChange={onFieldChange("grupo_id")}>
                  <option value="">Selecione…</option>
                  {grupos.filter((g) => g.situacao === "ativo").map((g) => (
                    <option key={g.id} value={g.id}>{g.nome} ({g.prefixo})</option>
                  ))}
                </select>
              </label>

              <label className={styles.field}>
                <span>Prefixo do grupo</span>
                <input className={styles.input} value={grupoSelecionado?.prefixo || "—"} readOnly />
                <span className={styles.hint}>Usado na geração do código dos SKUs filhos.</span>
              </label>

              <label className={`${styles.field} ${styles.fieldFull}`}>
                <span>Descrição *</span>
                <input className={styles.input} value={wizard.form.descricao}
                  onChange={(e) => onSetWizard((w) => ({ ...w, form: { ...w.form, descricao: e.target.value.toUpperCase() } }))} />
              </label>

              <label className={styles.field}>
                <span>Unidade *</span>
                <input className={styles.input} value={wizard.form.unidade} onChange={onFieldChange("unidade")} placeholder="PC, UN…" />
              </label>

              <label className={styles.field}>
                <span>Status</span>
                <select className={styles.input} value={wizard.form.status} onChange={onFieldChange("status")}>
                  <option value="ativo">Ativo</option>
                  <option value="inativo">Inativo</option>
                </select>
              </label>

              <label className={styles.field}>
                <span>Custo</span>
                <input type="number" step="0.01" className={styles.input} value={wizard.form.custo} onChange={onFieldChange("custo")} />
              </label>

              <label className={styles.field}>
                <span>Preço Venda</span>
                <input type="number" step="0.01" className={styles.input} value={wizard.form.preco_venda} onChange={onFieldChange("preco_venda")} />
              </label>

              <label className={styles.field}>
                <span>Linha Grade</span>
                <select className={styles.input} value={wizard.form.linha_grade_id} onChange={onFieldChange("linha_grade_id")}>
                  <option value="">Nenhuma</option>
                  {tabelasGrade.map((t) => (
                    <option key={t.id} value={t.id}>{t.codigo} - {t.descricao}</option>
                  ))}
                </select>
              </label>

              <label className={styles.field}>
                <span>Coluna Grade</span>
                <select className={styles.input} value={wizard.form.coluna_grade_id} onChange={onFieldChange("coluna_grade_id")}>
                  <option value="">Nenhuma</option>
                  {tabelasGrade.map((t) => (
                    <option key={t.id} value={t.id}>{t.codigo} - {t.descricao}</option>
                  ))}
                </select>
              </label>

              <p className={`${styles.hint} ${styles.fieldFull}`}>
                Selecione ao menos uma Linha ou Coluna de Grade — é a partir dela que a etapa seguinte monta o grid de combinações.
              </p>
            </div>
          )}

          {wizard.step === 2 && (
            <div>
              <div className={styles.gridToolbar}>
                <button className={styles.btnSecondary} onClick={onSelecionarTudo}>Selecionar Tudo</button>
                <button className={styles.btnSecondary} onClick={onLimparTudo}>Limpar Tudo</button>
                {temDoisEixos && (
                  <>
                    <label className={styles.checkboxLabel}>
                      <input type="checkbox" checked={wizard.ocultarLinhasDesmarcadas}
                        onChange={(e) => onSetWizard((w) => ({ ...w, ocultarLinhasDesmarcadas: e.target.checked }))} />
                      Ocultar Linhas Desmarcadas
                    </label>
                    <label className={styles.checkboxLabel}>
                      <input type="checkbox" checked={wizard.ocultarColunasDesmarcadas}
                        onChange={(e) => onSetWizard((w) => ({ ...w, ocultarColunasDesmarcadas: e.target.checked }))} />
                      Ocultar Colunas Desmarcadas
                    </label>
                  </>
                )}
              </div>

              <p className={styles.hint} style={{ marginBottom: 10 }}>
                Desmarcar uma célula já gerada marca o SKU correspondente para remoção — veja a prévia na próxima etapa.
              </p>

              {temDoisEixos ? (
                <div className={styles.gridWrap}>
                  <table className={styles.gridTable}>
                    <thead>
                      <tr>
                        <th></th>
                        {colunasVisiveis.map((ci) => (
                          <th key={ci.id}>{ci.descricao}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {linhasVisiveis.map((li) => (
                        <tr key={li.id}>
                          <th className={styles.gridRowHead}>{li.descricao}</th>
                          {colunasVisiveis.map((ci) => (
                            <td key={ci.id} className={`${styles.gridCell} ${isCellExisting(li.id, ci.id) ? styles.gridCellExistente : ""}`}>
                              <input
                                type="checkbox"
                                checked={isCellSelected(li.id, ci.id)}
                                onChange={() => onToggleCombo(li.id, ci.id)}
                              />
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : temApenasLinha ? (
                <ul className={styles.checkList}>
                  {linhasVisiveis.map((li) => (
                    <li key={li.id}>
                      <label className={styles.checkboxLabel}>
                        <input type="checkbox" checked={isCellSelected(li.id, null)}
                          onChange={() => onToggleCombo(li.id, null)} />
                        {li.descricao}
                      </label>
                    </li>
                  ))}
                </ul>
              ) : temApenasColuna ? (
                <ul className={styles.checkList}>
                  {colunasVisiveis.map((ci) => (
                    <li key={ci.id}>
                      <label className={styles.checkboxLabel}>
                        <input type="checkbox" checked={isCellSelected(null, ci.id)}
                          onChange={() => onToggleCombo(null, ci.id)} />
                        {ci.descricao}
                      </label>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className={styles.empty}>Nenhum item ativo na(s) tabela(s) de grade selecionada(s).</p>
              )}
            </div>
          )}

          {wizard.step === 3 && (
            <div>
              <DiffSection titulo="Será(ão) criado(s)" cor="novo" itens={wizard.diff.novos} />
              <DiffSection titulo="Será(ão) removido(s)" cor="removido" itens={wizard.diff.removidos} />
              <DiffSection titulo="Sem alteração" cor="mantido" itens={wizard.diff.mantidos} />
            </div>
          )}

          {erro && <p className={styles.msgErro}>{erro}</p>}
        </div>

        <div className={styles.modalActions}>
          <button className={styles.btnPillSecondary} onClick={onClose} disabled={saving}>Cancelar</button>
          {wizard.step > 1 && (
            <button className={styles.btnPillSecondary} onClick={onVoltar} disabled={saving}>Voltar</button>
          )}
          {wizard.step === 1 && (
            <button className={styles.btnPrimary} onClick={onAvancarEtapa1} disabled={saving}>
              {saving ? "Salvando…" : "Avançar"}
            </button>
          )}
          {wizard.step === 2 && (
            <button className={styles.btnPrimary} onClick={onAvancarEtapa2} disabled={saving}>
              Avançar
            </button>
          )}
          {wizard.step === 3 && (
            <button className={styles.btnPrimary} onClick={onConfirmar} disabled={saving || semMudancas}>
              {saving ? "Aplicando…" : "Confirmar e Gerar SKUs"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function DiffSection({ titulo, cor, itens }) {
  const corClass = cor === "novo" ? styles.diffNovo : cor === "removido" ? styles.diffRemovido : styles.diffMantido;
  return (
    <div className={styles.diffSection}>
      <h4 className={`${styles.diffTitle} ${corClass}`}>{titulo} ({itens.length})</h4>
      {itens.length === 0 ? (
        <p className={styles.hint}>Nenhum.</p>
      ) : (
        <table className={styles.skuTable}>
          <thead>
            <tr><th>Código</th><th>Linha</th><th>Coluna</th></tr>
          </thead>
          <tbody>
            {itens.map((i) => (
              <tr key={i.key}>
                <td className={styles.tdMono}>{i.codigo}</td>
                <td>{i.linhaDesc}</td>
                <td>{i.colunaDesc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
