import { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { validarTes } from "../../api/tes";
import styles from "./TesInput.module.css";

/**
 * Campo de TES por código digitado (sem select). Valida no blur/Enter via
 * GET /tes/validar; lupa (ou F2) abre o modal de seleção.
 *
 * Props:
 *   tesId     — id da TES atual (ou null)
 *   tesList   — lista de TES já carregada pela página (modal + descrição)
 *   readOnly
 *   onChange  — ({ id, codigo }) => Promise; rejeitar mostra o erro no campo
 */
export default function TesInput({ tesId, tesList = [], readOnly = false, onChange }) {
  const atual = tesList.find((t) => t.id === tesId) || null;
  const codigoAtual = atual?.codigo || "";

  const [texto, setTexto] = useState(codigoAtual);
  const [focado, setFocado] = useState(false);
  const [erro, setErro] = useState(null);
  const [salvando, setSalvando] = useState(false);
  const [modalAberto, setModalAberto] = useState(false);
  const inputRef = useRef(null);

  // Valor externo mudou (outra edição, recarga) — só reflete se o usuário
  // não está digitando nem com erro pendente.
  useEffect(() => {
    if (!focado && !erro) setTexto(codigoAtual);
  }, [codigoAtual]); // eslint-disable-line react-hooks/exhaustive-deps

  const aplicar = async (tes) => {
    setSalvando(true);
    try {
      await onChange?.({ id: tes.id, codigo: tes.codigo });
      setTexto(tes.codigo);
      setErro(null);
      return true;
    } catch (e) {
      setErro(e.message || "Erro ao salvar TES.");
      return false;
    } finally {
      setSalvando(false);
    }
  };

  const validar = async () => {
    const codigo = texto.trim().toUpperCase();
    if (!codigo) { setTexto(codigoAtual); setErro(null); return true; }
    if (codigo === codigoAtual.toUpperCase()) { setTexto(codigoAtual); setErro(null); return true; }
    let tes;
    try {
      tes = await validarTes(codigo);
    } catch (e) {
      setErro(e.message || "Código de TES inválido");
      return false;
    }
    return aplicar(tes);
  };

  const handleKeyDown = async (e) => {
    if (readOnly || salvando) return;
    if (e.key === "F2") {
      e.preventDefault();
      setModalAberto(true);
    } else if (e.key === "Enter") {
      e.preventDefault();
      await validar();
    } else if (e.key === "Escape") {
      e.preventDefault();
      setTexto(codigoAtual);
      setErro(null);
    }
  };

  const handleBlur = () => {
    setFocado(false);
    // Blur causado pela abertura do modal não valida o texto parcial.
    if (!readOnly && !modalAberto) validar();
  };

  const selecionarNoModal = async (tes) => {
    setModalAberto(false);
    await aplicar(tes);
    inputRef.current?.focus();
  };

  return (
    <div className={styles.wrap}>
      <div className={styles.campo}>
        <input
          ref={inputRef}
          className={`${styles.input} ${erro ? styles.inputErro : ""}`}
          value={texto}
          readOnly={readOnly || salvando}
          tabIndex={readOnly ? -1 : 0}
          title={erro || atual?.descricao || ""}
          placeholder={readOnly ? "" : "CÓDIGO"}
          onChange={(e) => setTexto(e.target.value.toUpperCase())}
          onFocus={(e) => { setFocado(true); e.target.select(); }}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
        />
        {!readOnly && (
          <button
            type="button"
            className={styles.lupa}
            tabIndex={-1}
            title="Buscar TES (F2)"
            aria-label="Buscar TES"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setModalAberto(true)}
          >
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor"
              strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
              <circle cx="7" cy="7" r="4.5" />
              <line x1="10.5" y1="10.5" x2="14" y2="14" />
            </svg>
          </button>
        )}
      </div>
      {erro && <div className={styles.erro} title={erro}>{erro}</div>}

      {modalAberto && (
        <TesModal
          tesList={tesList}
          selecionadoId={tesId}
          onSelecionar={selecionarNoModal}
          onFechar={() => { setModalAberto(false); inputRef.current?.focus(); }}
        />
      )}
    </div>
  );
}

function TesModal({ tesList, selecionadoId, onSelecionar, onFechar }) {
  const [busca, setBusca] = useState("");
  const [ativo, setAtivo] = useState(0);
  const overlayMouseDown = useRef(null);
  const listaRef = useRef(null);

  const q = busca.trim().toLowerCase();
  const filtradas = q
    ? tesList.filter((t) => `${t.codigo} ${t.descricao}`.toLowerCase().includes(q))
    : tesList;

  // Abre com a TES atual destacada; nova busca volta para a primeira linha.
  useEffect(() => {
    const idx = tesList.findIndex((t) => t.id === selecionadoId);
    setAtivo(idx >= 0 ? idx : 0);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    listaRef.current?.querySelector(`[data-idx="${ativo}"]`)?.scrollIntoView({ block: "nearest" });
  }, [ativo]);

  const handleKeyDown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault(); e.stopPropagation();
      onFechar();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setAtivo((i) => Math.min(i + 1, filtradas.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAtivo((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtradas[ativo]) onSelecionar(filtradas[ativo]);
    }
  };

  return ReactDOM.createPortal(
    <div
      className={styles.overlay}
      onMouseDown={(e) => { overlayMouseDown.current = e.target; }}
      onClick={(e) => {
        if (e.target === e.currentTarget && overlayMouseDown.current === e.currentTarget) onFechar();
      }}
      onKeyDown={handleKeyDown}
    >
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHead}>
          <h2 className={styles.modalTitle}>Selecionar TES</h2>
          <button className={styles.btnClose} onClick={onFechar} aria-label="Fechar">×</button>
        </div>

        <div className={styles.modalScroll}>
          <input
            className={styles.busca}
            placeholder="BUSCAR POR CÓDIGO OU DESCRIÇÃO..."
            value={busca}
            onChange={(e) => { setBusca(e.target.value.toUpperCase()); setAtivo(0); }}
            autoFocus
          />

          <div className={styles.lista} ref={listaRef}>
            <table className={styles.tabela}>
              <thead>
                <tr>
                  <th className={styles.colCodigo}>Código</th>
                  <th>Descrição</th>
                  <th className={styles.colCfop}>CFOP</th>
                </tr>
              </thead>
              <tbody>
                {filtradas.length === 0 ? (
                  <tr><td colSpan={3} className={styles.vazio}>Nenhuma TES encontrada.</td></tr>
                ) : filtradas.map((t, idx) => (
                  <tr
                    key={t.id}
                    data-idx={idx}
                    className={`${idx === ativo ? styles.linhaAtiva : ""} ${t.id === selecionadoId ? styles.linhaSelecionada : ""}`}
                    onClick={() => setAtivo(idx)}
                    onDoubleClick={() => onSelecionar(t)}
                  >
                    <td title={t.codigo}>{t.codigo}</td>
                    <td title={t.descricao}>{t.descricao}</td>
                    <td title={t.cfop}>{t.cfop}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className={styles.dica}>Duplo clique ou Enter para selecionar.</p>
        </div>

        <div className={styles.modalActions}>
          <button className={styles.btnSecondary} onClick={onFechar}>Cancelar</button>
          <button
            className={styles.btnPrimary}
            disabled={!filtradas[ativo]}
            onClick={() => filtradas[ativo] && onSelecionar(filtradas[ativo])}
          >
            Selecionar
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
