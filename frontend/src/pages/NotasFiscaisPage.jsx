import { useState, useEffect, useCallback } from "react";
import { listar, criar, transmitir, cancelar, getDanfe, cartaCorrecao } from "../api/nfe";
import { useAuth } from "../auth/useAuth";
import styles from "./NotasFiscaisPage.module.css";
import useOverlayDismiss from "../hooks/useOverlayDismiss";

const MODULO = "fiscal_nfe";

const STATUS_OPCOES = [
  "Rascunho",
  "Aguardando",
  "Autorizada",
  "Rejeitada",
  "Cancelada",
  "Denegada",
];
const SERIE_OPCOES = ["001", "002", "ORC"];

const STATUS_BADGE = {
  Rascunho: "badge_rascunho",
  Aguardando: "badge_aguardando",
  Autorizada: "badge_autorizada",
  Rejeitada: "badge_rejeitada",
  Cancelada: "badge_cancelada",
  Denegada: "badge_denegada",
};

const hojeISO = () => new Date().toISOString().slice(0, 10);
const agoraHora = () => new Date().toTimeString().slice(0, 5);

const fmtData = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d) ? "—" : d.toLocaleDateString("pt-BR");
};

const fmtMoeda = (v) =>
  v == null
    ? "—"
    : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

export default function NotasFiscaisPage() {
  const modalNovaOverlay = useOverlayDismiss(() => setModalNova(null));
  const modalTransmitirOverlay = useOverlayDismiss(() => setModalTransmitir(null));
  const modalCancelarOverlay = useOverlayDismiss(() => setModalCancelar(null));
  const modalCartaOverlay = useOverlayDismiss(() => setModalCarta(null));
  const modalDetalhesOverlay = useOverlayDismiss(() => setModalDetalhes(null));

  const { hasPermission } = useAuth();
  const [lista, setLista] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filtroStatus, setFiltroStatus] = useState("");
  const [filtroSerie, setFiltroSerie] = useState("");

  const [modalNova, setModalNova] = useState(null);
  const [modalTransmitir, setModalTransmitir] = useState(null);
  const [modalCancelar, setModalCancelar] = useState(null);
  const [modalCarta, setModalCarta] = useState(null);
  const [modalDetalhes, setModalDetalhes] = useState(null);

  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState(null);
  const [resultadoTransmissao, setResultadoTransmissao] = useState(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      setLista((await listar({ status: filtroStatus, serie: filtroSerie })) || []);
    } catch {
      setLista([]);
    } finally {
      setLoading(false);
    }
  }, [filtroStatus, filtroSerie]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  // ── Nova NF-e (avulsa) ──────────────────────────────────────────────
  const abrirNova = () => {
    setModalNova({
      serie: "001",
      data_emissao: hojeISO(),
      data_saida: hojeISO(),
      hora_saida: agoraHora(),
    });
    setErro(null);
  };

  const confirmarNova = async () => {
    setSaving(true);
    setErro(null);
    try {
      await criar({
        serie: modalNova.serie,
        data_emissao: modalNova.data_emissao,
        data_saida: modalNova.data_saida,
        hora_saida: modalNova.hora_saida,
      });
      await carregar();
      setModalNova(null);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  // ── Transmitir ────────────────────────────────────────────────────────
  const abrirTransmitir = (nfe) => {
    setModalTransmitir(nfe);
    setResultadoTransmissao(null);
    setErro(null);
  };

  const confirmarTransmitir = async () => {
    setSaving(true);
    setErro(null);
    try {
      const resp = await transmitir(modalTransmitir.id);
      setResultadoTransmissao(resp.resultado);
      await carregar();
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  // ── Cancelar ──────────────────────────────────────────────────────────
  const abrirCancelar = (nfe) => {
    setModalCancelar(nfe);
    setErro(null);
  };

  const confirmarCancelar = async () => {
    setSaving(true);
    setErro(null);
    try {
      await cancelar(modalCancelar.id, "Cancelamento solicitado pelo emitente");
      await carregar();
      setModalCancelar(null);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  // ── DANFE ─────────────────────────────────────────────────────────────
  const handleDanfe = async (nfe) => {
    try {
      const blob = await getDanfe(nfe.id);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    } catch (e) {
      setErro(e.message);
    }
  };

  // ── Carta de Correção ──────────────────────────────────────────────────
  const abrirCarta = (nfe) => {
    setModalCarta({ nfe, texto: "" });
    setErro(null);
  };

  const confirmarCarta = async () => {
    setSaving(true);
    setErro(null);
    try {
      await cartaCorrecao(modalCarta.nfe.id, modalCarta.texto.trim());
      await carregar();
      setModalCarta(null);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Notas Fiscais</h1>
        {hasPermission(MODULO, "criar") && (
          <button className={styles.btnNovo} onClick={abrirNova}>
            + Nova NF-e
          </button>
        )}
      </div>

      <div className={styles.toolbar}>
        <select
          className={styles.select}
          value={filtroStatus}
          onChange={(e) => setFiltroStatus(e.target.value)}
        >
          <option value="">Todos os status</option>
          {STATUS_OPCOES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          className={styles.select}
          value={filtroSerie}
          onChange={(e) => setFiltroSerie(e.target.value)}
        >
          <option value="">Todas as séries</option>
          {SERIE_OPCOES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className={`sc-card ${styles.tableCard}`}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Número</th>
              <th>Série</th>
              <th>Data Emissão</th>
              <th>Destinatário</th>
              <th>Valor</th>
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className={styles.empty}>
                  Carregando…
                </td>
              </tr>
            ) : lista.length === 0 ? (
              <tr>
                <td colSpan={7} className={styles.empty}>
                  Nenhuma NF-e encontrada.
                </td>
              </tr>
            ) : (
              lista.map((n) => (
                <tr key={n.id}>
                  <td className={styles.tdMono}>{n.numero}</td>
                  <td className={styles.tdMono}>{n.serie}</td>
                  <td>{fmtData(n.data_emissao)}</td>
                  <td>{n.destinatario || "Avulsa"}</td>
                  <td>{fmtMoeda(n.valor_nf)}</td>
                  <td>
                    <span
                      className={`${styles.badge} ${styles[STATUS_BADGE[n.status] || "badge_rascunho"]}`}
                    >
                      {n.status}
                    </span>
                  </td>
                  <td>
                    <div className={styles.actions}>
                      {n.status === "Rascunho" &&
                        hasPermission("fiscal_transmitir", "executar") && (
                          <button className={styles.btnLink} onClick={() => abrirTransmitir(n)}>
                            Transmitir
                          </button>
                        )}
                      {n.status === "Autorizada" && hasPermission(MODULO, "ver") && (
                        <button className={styles.btnLink} onClick={() => handleDanfe(n)}>
                          DANFE
                        </button>
                      )}
                      {n.status === "Autorizada" &&
                        hasPermission("fiscal_carta_correcao", "criar") && (
                          <button className={styles.btnLink} onClick={() => abrirCarta(n)}>
                            Carta Correção
                          </button>
                        )}
                      {n.status === "Autorizada" &&
                        hasPermission("fiscal_cancelar", "cancelar") && (
                          <button
                            className={`${styles.btnLink} ${styles.btnDanger}`}
                            onClick={() => abrirCancelar(n)}
                          >
                            Cancelar
                          </button>
                        )}
                      <button className={styles.btnLink} onClick={() => setModalDetalhes(n)}>
                        Detalhes
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* ══ MODAL — Nova NF-e ══ */}
      {modalNova && (
        <div className={styles.overlay} {...modalNovaOverlay}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Nova NF-e</h2>
              <button className={styles.btnClose} onClick={() => setModalNova(null)}>
                ×
              </button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.fieldGrid}>
                <label className={styles.field}>
                  <span>Série</span>
                  <select
                    className={styles.input}
                    value={modalNova.serie}
                    onChange={(e) => setModalNova((m) => ({ ...m, serie: e.target.value }))}
                  >
                    {SERIE_OPCOES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={styles.field}>
                  <span>Data Emissão</span>
                  <input
                    type="date"
                    className={styles.input}
                    value={modalNova.data_emissao}
                    onChange={(e) => setModalNova((m) => ({ ...m, data_emissao: e.target.value }))}
                  />
                </label>
                <label className={styles.field}>
                  <span>Data Saída</span>
                  <input
                    type="date"
                    className={styles.input}
                    value={modalNova.data_saida}
                    onChange={(e) => setModalNova((m) => ({ ...m, data_saida: e.target.value }))}
                  />
                </label>
                <label className={styles.field}>
                  <span>Hora Saída</span>
                  <input
                    type="time"
                    className={styles.input}
                    value={modalNova.hora_saida}
                    onChange={(e) => setModalNova((m) => ({ ...m, hora_saida: e.target.value }))}
                  />
                </label>
              </div>
              <p className={styles.aviso}>
                Emissão avulsa, sem vínculo com um pedido de venda. Para emitir a NF-e de um pedido
                específico, use o botão "Emitir Nota Fiscal" na tela do pedido.
              </p>
              {erro && <p className={styles.erro}>{erro}</p>}
            </div>
            <div className={styles.modalActions}>
              <button
                className={styles.btnSecondary}
                onClick={() => setModalNova(null)}
                disabled={saving}
              >
                Cancelar
              </button>
              <button className={styles.btnPrimary} onClick={confirmarNova} disabled={saving}>
                {saving ? "Emitindo…" : "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Transmitir ══ */}
      {modalTransmitir && (
        <div className={styles.overlay} {...modalTransmitirOverlay}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Transmitir NF-e</h2>
              <button className={styles.btnClose} onClick={() => setModalTransmitir(null)}>
                ×
              </button>
            </div>
            <div className={styles.modalBody}>
              <p>Deseja transmitir esta NF-e para a SEFAZ?</p>
              <span
                className={`${styles.badge} ${modalTransmitir.ambiente === "Producao" ? styles.badge_autorizada : styles.badge_aguardando}`}
              >
                {modalTransmitir.ambiente === "Producao" ? "Produção" : "Homologação"}
              </span>
              {resultadoTransmissao && (
                <div
                  className={`${styles.resultado} ${resultadoTransmissao.cStat === "100" ? styles.resultadoSucesso : styles.resultadoErro}`}
                >
                  cStat {resultadoTransmissao.cStat || "—"}:{" "}
                  {resultadoTransmissao.xMotivo || "Sem retorno da SEFAZ."}
                </div>
              )}
              {erro && <p className={styles.erro}>{erro}</p>}
            </div>
            <div className={styles.modalActions}>
              <button
                className={styles.btnSecondary}
                onClick={() => setModalTransmitir(null)}
                disabled={saving}
              >
                Cancelar
              </button>
              <button className={styles.btnPrimary} onClick={confirmarTransmitir} disabled={saving}>
                {saving ? "Transmitindo…" : "Transmitir"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Cancelar ══ */}
      {modalCancelar && (
        <div className={styles.overlay} {...modalCancelarOverlay}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Cancelar NF-e</h2>
              <button className={styles.btnClose} onClick={() => setModalCancelar(null)}>
                ×
              </button>
            </div>
            <div className={styles.modalBody}>
              <p>Tem certeza que deseja cancelar esta NF-e?</p>
              <p className={styles.avisoDanger}>Esta ação não pode ser desfeita.</p>
              {erro && <p className={styles.erro}>{erro}</p>}
            </div>
            <div className={styles.modalActions}>
              <button
                className={styles.btnSecondary}
                onClick={() => setModalCancelar(null)}
                disabled={saving}
              >
                Voltar
              </button>
              <button
                className={styles.btnDangerFilled}
                onClick={confirmarCancelar}
                disabled={saving}
              >
                {saving ? "Cancelando…" : "Confirmar cancelamento"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Carta de Correção ══ */}
      {modalCarta && (
        <div className={styles.overlay} {...modalCartaOverlay}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Carta de Correção</h2>
              <button className={styles.btnClose} onClick={() => setModalCarta(null)}>
                ×
              </button>
            </div>
            <div className={styles.modalBody}>
              <label className={styles.field}>
                <span>Texto da correção</span>
                <textarea
                  className={`${styles.textarea} sc-upper`}
                  value={modalCarta.texto}
                  onChange={(e) =>
                    setModalCarta((m) => ({ ...m, texto: e.target.value.toUpperCase() }))
                  }
                  placeholder="Descreva a correção (mínimo 15 caracteres)…"
                />
              </label>
              <p className={styles.contador}>{modalCarta.texto.length} caracteres (mínimo 15)</p>
              {erro && <p className={styles.erro}>{erro}</p>}
            </div>
            <div className={styles.modalActions}>
              <button
                className={styles.btnSecondary}
                onClick={() => setModalCarta(null)}
                disabled={saving}
              >
                Cancelar
              </button>
              <button
                className={styles.btnPrimary}
                onClick={confirmarCarta}
                disabled={saving || modalCarta.texto.trim().length < 15}
              >
                {saving ? "Enviando…" : "Enviar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Detalhes ══ */}
      {modalDetalhes && (
        <div className={styles.overlay} {...modalDetalhesOverlay}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>
                NF-e {modalDetalhes.numero}/{modalDetalhes.serie}
              </h2>
              <button className={styles.btnClose} onClick={() => setModalDetalhes(null)}>
                ×
              </button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.detalheLinha}>
                <span className={styles.detalheLabel}>Status</span>
                <span className={styles.detalheValor}>{modalDetalhes.status}</span>
              </div>
              <div className={styles.detalheLinha}>
                <span className={styles.detalheLabel}>Ambiente</span>
                <span className={styles.detalheValor}>{modalDetalhes.ambiente}</span>
              </div>
              <div className={styles.detalheLinha}>
                <span className={styles.detalheLabel}>Chave de acesso</span>
                <span className={styles.detalheValor}>{modalDetalhes.chave_acesso || "—"}</span>
              </div>
              <div className={styles.detalheLinha}>
                <span className={styles.detalheLabel}>Protocolo</span>
                <span className={styles.detalheValor}>{modalDetalhes.protocolo || "—"}</span>
              </div>
              <div className={styles.detalheLinha}>
                <span className={styles.detalheLabel}>Data emissão</span>
                <span className={styles.detalheValor}>{fmtData(modalDetalhes.data_emissao)}</span>
              </div>
              <div className={styles.detalheLinha}>
                <span className={styles.detalheLabel}>Data autorização</span>
                <span className={styles.detalheValor}>
                  {fmtData(modalDetalhes.data_autorizacao)}
                </span>
              </div>
              {modalDetalhes.motivo_rejeicao && (
                <div className={styles.detalheLinha}>
                  <span className={styles.detalheLabel}>Motivo rejeição</span>
                  <span className={styles.detalheValor}>{modalDetalhes.motivo_rejeicao}</span>
                </div>
              )}
              {modalDetalhes.carta_correcao && (
                <div className={styles.detalheLinha}>
                  <span className={styles.detalheLabel}>Carta de correção</span>
                  <span className={styles.detalheValor}>{modalDetalhes.carta_correcao}</span>
                </div>
              )}
            </div>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setModalDetalhes(null)}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
