import { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { API_BASE } from "../../services/config";
import { apiFetch } from "../../services/api";
// Mesmo visual do TesInput (campo + lupa + modal de seleção).
import useOverlayDismiss from "../../hooks/useOverlayDismiss";
import styles from "../TesInput/TesInput.module.css";

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

// GET /produtos/skus/validar e /produtos/skus — só SKUs filhos ativos.
// tabela_preco_id / tipo_preco fazem o backend devolver preco_resolvido
// (mesma regra da troca de SKU no lote de itens).
async function getSkus(path, params) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v != null) qs.set(k, v);
  const res = await apiFetch(`${API_BASE}/api/v1/produtos/skus${path}?${qs}`);
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || json.error || `Erro ${res.status}`);
  return json.data;
}

const ERRO_CODIGO = "Código de produto inválido";

/**
 * Campo de SKU (produto filho) por código digitado. Valida no blur/Enter
 * via GET /produtos/skus/validar; lupa (ou F2) abre o modal de busca.
 *
 * Props:
 *   codigo        — código do SKU atual
 *   readOnly      — sem edição e sem lupa
 *   onChange      — (sku) => void; sku = { id, codigo, descricao_completa,
 *                   preco_venda, preco_resolvido, origem_preco }
 *   onProximo     — Enter com código válido (navegação da tabela)
 *   inputRef      — ref (callback) do input
 *   erroServidor  — erro vindo de fora (422 do lote); vai no tooltip
 *   tabelaPrecoId, tipoPreco — tabela e condição do pedido (preço resolvido)
 *   className     — classe extra no contêiner
 *   variant       — "full" | "code" (campo estreito, como no TesInput)
 */
export default function ProdutoSkuInput({
  codigo = "",
  readOnly = false,
  onChange,
  onProximo,
  inputRef,
  erroServidor,
  tabelaPrecoId,
  tipoPreco,
  className = "",
  variant = "full",
}) {
  const [texto, setTexto] = useState(codigo);
  const [focado, setFocado] = useState(false);
  const [erro, setErro] = useState(null);
  const [validando, setValidando] = useState(false);
  const [modalAberto, setModalAberto] = useState(false);
  const modalAbertoRef = useRef(false);
  const ignorarBlur = useRef(false);
  const campoRef = useRef(null);

  const precoParams = { tabela_preco_id: tabelaPrecoId || null, tipo_preco: tipoPreco ?? "" };

  // Valor externo mudou (troca aplicada, descarte, recarga) — só reflete se
  // o usuário não está digitando nem com erro pendente.
  useEffect(() => {
    if (!focado && !erro) setTexto(codigo);
  }, [codigo]);

  const abrirModal = (aberto) => {
    modalAbertoRef.current = aberto;
    setModalAberto(aberto);
  };

  const setRef = (el) => {
    campoRef.current = el;
    if (typeof inputRef === "function") inputRef(el);
  };

  // true = código válido (ou vazio/igual ao atual, que não altera nada).
  const validar = async () => {
    const digitado = texto.trim().toUpperCase();
    if (!digitado || digitado === codigo.toUpperCase()) {
      setTexto(codigo);
      setErro(null);
      return true;
    }
    setValidando(true);
    try {
      const sku = await getSkus("/validar", { codigo: digitado, ...precoParams });
      setErro(null);
      setTexto(sku.codigo);
      onChange?.(sku);
      return true;
    } catch {
      // Linha não muda: o texto inválido fica no campo, marcado.
      setErro(ERRO_CODIGO);
      return false;
    } finally {
      setValidando(false);
    }
  };

  const reverter = () => {
    setTexto(codigo);
    setErro(null);
  };

  const handleKeyDown = async (e) => {
    if (readOnly || validando) return;
    if (e.key === "F2") {
      e.preventDefault();
      abrirModal(true);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (await validar()) {
        ignorarBlur.current = true;
        onProximo?.();
        ignorarBlur.current = false;
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      reverter();
    }
  };

  const handleBlur = () => {
    setFocado(false);
    // Blur causado pelo Enter (já validou) ou pela abertura do modal.
    if (readOnly || ignorarBlur.current || modalAbertoRef.current) return;
    validar();
  };

  const selecionarNoModal = (sku) => {
    abrirModal(false);
    setErro(null);
    setTexto(sku.codigo);
    if (sku.codigo.toUpperCase() !== codigo.toUpperCase()) onChange?.(sku);
    campoRef.current?.focus();
  };

  const erroExibido = erro || erroServidor;
  return (
    <div className={`${styles.wrap} ${variant === "code" ? styles.wrapCodigo : ""} ${className}`}>
      <div className={styles.campo}>
        <input
          ref={setRef}
          className={`${styles.input} ${erroExibido ? "sc-campo-erro" : ""} sc-upper`}
          value={texto}
          readOnly={readOnly || validando}
          tabIndex={readOnly ? -1 : 0}
          title={erroExibido || codigo}
          placeholder={readOnly ? "" : "CÓDIGO"}
          autoComplete="off"
          onChange={(e) => setTexto(e.target.value.toUpperCase())}
          onFocus={(e) => {
            setFocado(true);
            e.target.select();
          }}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
        />
        {!readOnly && (
          <button
            type="button"
            className={styles.lupa}
            tabIndex={-1}
            title="Buscar produto (F2)"
            aria-label="Buscar produto"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => abrirModal(true)}
          >
            <svg
              width="13"
              height="13"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <circle cx="7" cy="7" r="4.5" />
              <line x1="10.5" y1="10.5" x2="14" y2="14" />
            </svg>
          </button>
        )}
      </div>

      {modalAberto && (
        <SkuModal
          precoParams={precoParams}
          codigoAtual={codigo}
          onSelecionar={selecionarNoModal}
          onFechar={() => {
            abrirModal(false);
            campoRef.current?.focus();
          }}
        />
      )}
    </div>
  );
}

const LIMITE_BUSCA = 50;

function SkuModal({ precoParams, codigoAtual, onSelecionar, onFechar }) {
  const [busca, setBusca] = useState("");
  const [resultado, setResultado] = useState({ itens: [], total: 0 });
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [ativo, setAtivo] = useState(0);
  const overlayProps = useOverlayDismiss(() => onFechar());
  const listaRef = useRef(null);
  const seqBusca = useRef(0);

  // Busca no servidor com debounce; só a resposta mais recente vale.
  useEffect(() => {
    const seq = ++seqBusca.current;
    setCarregando(true);
    const t = setTimeout(
      async () => {
        try {
          const data = await getSkus("", { busca, limit: LIMITE_BUSCA, ...precoParams });
          if (seq !== seqBusca.current) return;
          setResultado(data);
          setErro(null);
          const idx = busca ? -1 : data.itens.findIndex((s) => s.codigo === codigoAtual);
          setAtivo(idx >= 0 ? idx : 0);
        } catch (e) {
          if (seq === seqBusca.current) setErro(e.message);
        } finally {
          if (seq === seqBusca.current) setCarregando(false);
        }
      },
      busca ? 250 : 0
    );
    return () => clearTimeout(t);
  }, [busca]);

  const itens = resultado.itens;

  useEffect(() => {
    listaRef.current?.querySelector(`[data-idx="${ativo}"]`)?.scrollIntoView({ block: "nearest" });
  }, [ativo]);

  const handleKeyDown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      onFechar();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setAtivo((i) => Math.min(i + 1, itens.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAtivo((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      if (itens[ativo]) onSelecionar(itens[ativo]);
    }
  };

  const preco = (s) => s.preco_resolvido ?? s.preco_venda;

  return ReactDOM.createPortal(
    <div className={styles.overlay} {...overlayProps} onKeyDown={handleKeyDown}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHead}>
          <h2 className={styles.modalTitle}>Selecionar produto</h2>
          <button className={styles.btnClose} onClick={onFechar} aria-label="Fechar">
            ×
          </button>
        </div>

        <div className={styles.modalScroll}>
          <input
            className={styles.busca}
            placeholder="BUSCAR POR CÓDIGO OU DESCRIÇÃO..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            autoFocus
          />

          <div className={styles.lista} ref={listaRef}>
            <table className={styles.tabela}>
              <thead>
                <tr>
                  <th style={{ width: 130 }}>Código</th>
                  <th>Descrição</th>
                  <th style={{ width: 110, textAlign: "right" }}>Preço</th>
                </tr>
              </thead>
              <tbody>
                {itens.length === 0 ? (
                  <tr>
                    <td colSpan={3} className={styles.vazio}>
                      {carregando ? "Buscando…" : erro || "Nenhum produto encontrado."}
                    </td>
                  </tr>
                ) : (
                  itens.map((s, idx) => (
                    <tr
                      key={s.id}
                      data-idx={idx}
                      className={`${idx === ativo ? styles.linhaAtiva : ""} ${s.codigo === codigoAtual ? styles.linhaSelecionada : ""}`}
                      onClick={() => setAtivo(idx)}
                      onDoubleClick={() => onSelecionar(s)}
                    >
                      <td title={s.codigo}>{s.codigo}</td>
                      <td title={s.descricao_completa}>{s.descricao_completa}</td>
                      <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                        {preco(s) != null ? moeda(preco(s)) : "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <p className={styles.dica}>
            {resultado.total > itens.length
              ? `Mostrando ${itens.length} de ${resultado.total} — refine a busca. `
              : ""}
            Duplo clique ou Enter para selecionar.
          </p>
        </div>

        <div className={styles.modalActions}>
          <button className={styles.btnSecondary} onClick={onFechar}>
            Cancelar
          </button>
          <button
            className={styles.btnPrimary}
            disabled={!itens[ativo]}
            onClick={() => itens[ativo] && onSelecionar(itens[ativo])}
          >
            Selecionar
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
