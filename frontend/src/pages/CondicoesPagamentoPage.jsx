import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { listar, criar, atualizar, excluir, simular } from "../api/condicoesPagamento";
import { useAuth } from "../auth/useAuth";
import styles from "./CondicoesPagamentoPage.module.css";
import useOverlayDismiss from "../hooks/useOverlayDismiss";

const MODULO = "configuracoes_editar";

const TIPO_LABEL = { intervalo: "Intervalo de Dias", fixo: "Dias Específicos" };

const PLACEHOLDER_CONDICAO = {
  intervalo: "ex: 30/60/90 ou X12:30",
  fixo: "ex: 10/15/10 ou X12:10",
};

const POPOVER_CONDICAO = {
  intervalo: (
    <>
      <strong>Como definir a condição de pagamento</strong>
      <br />
      <br />
      O campo Condição define quando cada parcela vence, contando os dias a partir da data de
      emissão.
      <br />
      <br />
      <strong>Exemplos:</strong>
      <br />• <code>0</code> → À vista — vence na data de emissão
      <br />• <code>30</code> → 1 parcela, vence em 30 dias
      <br />• <code>15/30</code> → 2 parcelas: 1ª em 15 dias, 2ª em 30 dias
      <br />• <code>30/60/90</code> → 3 parcelas: 30, 60 e 90 dias
      <br />• <code>X2:15</code> → 2 parcelas a cada 15 dias (15 e 30 dias)
      <br />• <code>X3:30</code> → 3 parcelas a cada 30 dias (30, 60 e 90 dias)
      <br />• <code>X12:30</code> → 12 parcelas mensais
      <br />
      <br />
      <strong>Formato X[qtd]:[intervalo]</strong> — use quando todas as parcelas têm o mesmo
      intervalo. Separe intervalos diferentes com barra (/).
    </>
  ),
  fixo: (
    <>
      <strong>Como definir a condição de pagamento</strong>
      <br />
      <br />
      O campo Condição define em qual dia fixo do mês cada parcela vence.
      <br />
      <br />
      <strong>Exemplos:</strong>
      <br />• <code>10</code> → 1 parcela no dia 10 do próximo mês
      <br />• <code>10/15</code> → 2 parcelas: dia 10 e dia 15 de meses consecutivos
      <br />• <code>10/15/10</code> → 3 parcelas: dia 10, dia 15, dia 10 dos próximos 3 meses
      <br />• <code>10:0/15:1</code> → 2 parcelas: dia 10 deste mês (:0) e dia 15 do próximo mês
      (:1)
      <br />• <code>X12:10</code> → 12 parcelas sempre no dia 10 de cada mês
      <br />
      <br />
      <strong>Dica:</strong> use :0 para vencer no mesmo mês da emissão e :1 para o próximo mês. Se
      o dia não existir no mês (ex: dia 31 em fevereiro), o sistema usa o último dia do mês
      automaticamente.
    </>
  ),
};

const VALOR_PREVIEW = "1000.00";

const VAZIO = {
  codigo: "",
  descricao: "",
  tipo: "intervalo",
  condicao: "",
  acrescimo: "0",
  desconto: "0",
  situacao: "Ativa",
};

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const dataLocal = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR") : "");

const hojeISO = () => new Date().toISOString().split("T")[0];

export default function CondicoesPagamentoPage() {
  const fecharModalOverlay = useOverlayDismiss(() => fecharModal());

  const { hasPermission } = useAuth();
  const podeEditar = hasPermission(MODULO, "ver");

  const [condicoes, setCondicoes] = useState([]);
  const [filtroSituacao, setFiltroSituacao] = useState("");
  const [loading, setLoading] = useState(true);

  const [modal, setModal] = useState(null);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState(null);

  const [preview, setPreview] = useState(null);
  const [previewErro, setPreviewErro] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewTimer = useRef(null);

  const [tooltipPos, setTooltipPos] = useState(null);
  const helpRef = useRef(null);

  const handleHelpEnter = () => {
    const rect = helpRef.current.getBoundingClientRect();
    const largura = 300;
    let left = rect.right + 10;
    if (left + largura > window.innerWidth) {
      left = rect.left - largura - 10;
    }
    setTooltipPos({ top: rect.top + rect.height / 2, left });
  };

  const handleHelpLeave = () => setTooltipPos(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      setCondicoes((await listar(filtroSituacao ? { situacao: filtroSituacao } : {})) || []);
    } catch {
      setCondicoes([]);
    } finally {
      setLoading(false);
    }
  }, [filtroSituacao]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const abrirNovo = () => {
    setModal({ ...VAZIO });
    setErro(null);
    setPreview(null);
    setPreviewErro(null);
  };

  const abrirEditar = (c) => {
    setModal({
      id: c.id,
      codigo: c.codigo || "",
      descricao: c.descricao || "",
      tipo: c.tipo || "intervalo",
      condicao: c.condicao || "",
      acrescimo: String(c.acrescimo ?? "0"),
      desconto: String(c.desconto ?? "0"),
      situacao: c.situacao || "Ativa",
    });
    setErro(null);
    setPreview(null);
    setPreviewErro(null);
  };

  const fecharModal = () => {
    clearTimeout(previewTimer.current);
    setModal(null);
    setErro(null);
    setPreview(null);
    setPreviewErro(null);
    setTooltipPos(null);
  };

  const setF = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.value }));
  const setFUpper = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.value.toUpperCase() }));

  // ── Preview de parcelas — debounce 600ms, valor de exemplo fixo ──────────
  useEffect(() => {
    if (!modal) return;
    clearTimeout(previewTimer.current);
    if (!modal.condicao.trim()) {
      setPreview(null);
      setPreviewErro(null);
      return;
    }
    previewTimer.current = setTimeout(async () => {
      setPreviewLoading(true);
      setPreviewErro(null);
      try {
        const resp = await simular({
          tipo: modal.tipo,
          condicao: modal.condicao.trim(),
          acrescimo: parseFloat(modal.acrescimo) || 0,
          desconto: parseFloat(modal.desconto) || 0,
          valor: VALOR_PREVIEW,
          data_emissao: hojeISO(),
        });
        setPreview(resp.parcelas || []);
      } catch (e) {
        setPreview(null);
        setPreviewErro(e.message);
      } finally {
        setPreviewLoading(false);
      }
    }, 600);
    return () => clearTimeout(previewTimer.current);
  }, [modal?.condicao, modal?.tipo, modal?.acrescimo, modal?.desconto]);

  const handleSalvar = async () => {
    if (!modal.codigo.trim() || !modal.descricao.trim() || !modal.condicao.trim()) {
      setErro("Código, descrição e condição são obrigatórios.");
      return;
    }
    setSaving(true);
    setErro(null);
    try {
      const payload = {
        codigo: modal.codigo.trim(),
        descricao: modal.descricao.trim(),
        tipo: modal.tipo,
        condicao: modal.condicao.trim(),
        acrescimo: parseFloat(modal.acrescimo) || 0,
        desconto: parseFloat(modal.desconto) || 0,
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

  const handleExcluir = async (c) => {
    if (!window.confirm(`Excluir a condição "${c.codigo} — ${c.descricao}"?`)) return;
    try {
      await excluir(c.id);
      await carregar();
    } catch (e) {
      alert(e.message);
    }
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Condições de Pagamento</h1>
        {podeEditar && (
          <button className={styles.btnNovo} onClick={abrirNovo}>
            + Nova Condição
          </button>
        )}
      </div>

      <div className={styles.toolbar}>
        <select
          className={styles.select}
          value={filtroSituacao}
          onChange={(e) => setFiltroSituacao(e.target.value)}
        >
          <option value="">Todas</option>
          <option value="Ativa">Ativa</option>
          <option value="Inativa">Inativa</option>
        </select>
      </div>

      <div className={`sc-card ${styles.tableCard}`}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Código</th>
              <th>Descrição</th>
              <th>Tipo</th>
              <th>Condição</th>
              <th>Acréscimo</th>
              <th>Desconto</th>
              <th>Situação</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className={styles.empty}>
                  Carregando…
                </td>
              </tr>
            ) : condicoes.length === 0 ? (
              <tr>
                <td colSpan={8} className={styles.empty}>
                  Nenhuma condição de pagamento cadastrada.
                </td>
              </tr>
            ) : (
              condicoes.map((c) => (
                <tr key={c.id}>
                  <td className={styles.tdMono}>{c.codigo}</td>
                  <td>{c.descricao}</td>
                  <td>{TIPO_LABEL[c.tipo] || c.tipo}</td>
                  <td className={styles.tdMono}>{c.condicao}</td>
                  <td className={styles.tdMono}>{Number(c.acrescimo || 0).toFixed(2)}%</td>
                  <td className={styles.tdMono}>{Number(c.desconto || 0).toFixed(2)}%</td>
                  <td>
                    <span
                      className={`${styles.badge} ${c.situacao === "Ativa" ? styles.badgeAtiva : styles.badgeInativa}`}
                    >
                      {c.situacao}
                    </span>
                  </td>
                  <td>
                    <div className={styles.actions}>
                      {podeEditar && (
                        <button className={styles.btnLink} onClick={() => abrirEditar(c)}>
                          Editar
                        </button>
                      )}
                      {podeEditar && (
                        <button
                          className={`${styles.btnLink} ${styles.btnDanger}`}
                          onClick={() => handleExcluir(c)}
                        >
                          Excluir
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className={styles.overlay} {...fecharModalOverlay}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>
                {modal.id ? "Editar Condição" : "Nova Condição"}
              </h2>
              <button className={styles.btnClose} onClick={fecharModal}>
                ×
              </button>
            </div>

            <div className={styles.modalBody}>
              <div className={styles.fieldGrid}>
                <label className={styles.field}>
                  <span>Código *</span>
                  <input
                    className={`${styles.input} sc-upper`}
                    value={modal.codigo}
                    onChange={setFUpper("codigo")}
                    maxLength={10}
                  />
                </label>
                <label className={styles.field}>
                  <span>Situação</span>
                  <select
                    className={styles.input}
                    value={modal.situacao}
                    onChange={setF("situacao")}
                  >
                    <option value="Ativa">Ativa</option>
                    <option value="Inativa">Inativa</option>
                  </select>
                </label>

                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Descrição *</span>
                  <input
                    className={`${styles.input} sc-upper`}
                    value={modal.descricao}
                    onChange={setFUpper("descricao")}
                    maxLength={100}
                  />
                </label>

                <label className={styles.field}>
                  <span>Tipo</span>
                  <select
                    className={styles.input}
                    value={modal.tipo}
                    onChange={(e) => setModal((m) => ({ ...m, tipo: e.target.value }))}
                  >
                    <option value="intervalo">Intervalo de Dias</option>
                    <option value="fixo">Dias Específicos</option>
                  </select>
                </label>
                <label className={styles.field}>
                  <span>
                    Condição *
                    <span
                      ref={helpRef}
                      className={styles.helpWrapper}
                      onMouseEnter={handleHelpEnter}
                      onMouseLeave={handleHelpLeave}
                    >
                      <svg
                        className={styles.helpIcon}
                        width="15"
                        height="15"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <circle cx="12" cy="12" r="10" />
                        <line x1="12" y1="16" x2="12" y2="12" />
                        <line x1="12" y1="8" x2="12.01" y2="8" />
                      </svg>
                    </span>
                    {tooltipPos &&
                      createPortal(
                        <div
                          className={styles.helpPopover}
                          style={{
                            position: "fixed",
                            top: tooltipPos.top,
                            left: tooltipPos.left,
                            transform: "translateY(-50%)",
                            zIndex: 99999,
                          }}
                        >
                          {POPOVER_CONDICAO[modal.tipo]}
                        </div>,
                        document.body
                      )}
                  </span>
                  <input
                    className={styles.input}
                    value={modal.condicao}
                    onChange={setF("condicao")}
                    placeholder={PLACEHOLDER_CONDICAO[modal.tipo]}
                    maxLength={70}
                  />
                </label>

                <label className={styles.field}>
                  <span>Acréscimo (%)</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    className={styles.input}
                    value={modal.acrescimo}
                    onChange={setF("acrescimo")}
                  />
                </label>
                <label className={styles.field}>
                  <span>Desconto (%)</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    className={styles.input}
                    value={modal.desconto}
                    onChange={setF("desconto")}
                  />
                </label>
              </div>

              {erro && <p className={styles.erro}>{erro}</p>}

              <div className={styles.previewBox}>
                <div className={styles.previewLabel}>
                  Preview — parcelas para {moeda(VALOR_PREVIEW)}
                </div>
                {previewLoading ? (
                  <p className={styles.previewMuted}>Calculando…</p>
                ) : previewErro ? (
                  <p className={styles.previewMuted}>{previewErro}</p>
                ) : preview && preview.length > 0 ? (
                  <table className={styles.previewTable}>
                    <thead>
                      <tr>
                        <th>Parcela</th>
                        <th>Vencimento</th>
                        <th>Valor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.map((p) => (
                        <tr key={p.parcela}>
                          <td>{p.descricao}</td>
                          <td>{dataLocal(p.vencimento)}</td>
                          <td>{moeda(p.valor)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className={styles.previewMuted}>Digite a condição para ver o preview.</p>
                )}
              </div>
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharModal} disabled={saving}>
                Cancelar
              </button>
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
