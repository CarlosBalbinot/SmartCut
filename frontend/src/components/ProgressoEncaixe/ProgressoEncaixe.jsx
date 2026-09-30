import { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { cancelarJobOrdemCorte, getJobOrdemCorte } from "../../api/ordensCorte";
import useOverlayDismiss from "../../hooks/useOverlayDismiss";
import styles from "./ProgressoEncaixe.module.css";

/**
 * Progresso da geração de encaixes de uma OC (job em segundo plano, M2a) e
 * as peças que o Assistente e o Detalhe da OC mostram juntos: alerta de
 * mesa maior, moldes por mesa, grade do enfesto e o rótulo do motor.
 *
 * <ProgressoEncaixe ocId onConcluido onFim />
 * <ProgressoEncaixe consultarJob cancelarJob chave onConcluido onFim />
 *   Consulta GET /job a cada 1 s enquanto FILA/RODANDO. Sem ocId, quem
 *   chama passa as funções do job (Encaixe Rápido: api/encaixes) e uma
 *   `chave` que muda quando é outro job.
 *   onConcluido(estado) — CONCLUIDO (o pai recarrega a OC; estado.resultado
 *                         traz avisos e sugestao_mesa)
 *   onFim(estado|null)  — CANCELADO, ERRO dispensado pelo usuário, ou não há
 *                         job (null) — o pai volta a mostrar o botão
 */

const ATIVOS = ["FILA", "RODANDO"];
const INTERVALO_MS = 1000;

// Etapas do motor (última parte de `fase`, ver nesting_v2/motor.py).
const ETAPAS = {
  grandes: "peças grandes",
  pequenas: "peças pequenas",
  polimento: "refinando",
  faixa: "encaixando",
};

const QUALIDADE_LABEL = { RAPIDO: "Rápido", EQUILIBRADO: "Equilibrado", MAXIMO: "Máximo" };

const numBR = (v, casas = 2) =>
  v == null
    ? "—"
    : Number(v).toLocaleString("pt-BR", {
        minimumFractionDigits: casas,
        maximumFractionDigits: casas,
      });
const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const decorrido = (iso, agora) => {
  if (!iso) return "0:00";
  const s = Math.max(0, Math.floor((agora - new Date(iso).getTime()) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

// ── Ícones ────────────────────────────────────────────────────────────────────

const svgBase = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};

const IconeRelogio = () => (
  <svg width="12" height="12" viewBox="0 0 16 16" {...svgBase}>
    <circle cx="8" cy="8" r="6" />
    <polyline points="8 4.8 8 8 10.2 9.4" />
  </svg>
);

const IconeAlerta = () => (
  <svg width="14" height="14" viewBox="0 0 16 16" {...svgBase}>
    <path d="M8 2.2 14.2 13H1.8z" />
    <line x1="8" y1="6.5" x2="8" y2="9.3" />
    <line x1="8" y1="11.2" x2="8" y2="11.3" />
  </svg>
);

const IconeInfo = () => (
  <svg width="15" height="15" viewBox="0 0 16 16" {...svgBase}>
    <circle cx="8" cy="8" r="6.2" />
    <line x1="8" y1="7.2" x2="8" y2="11" />
    <line x1="8" y1="4.9" x2="8" y2="5" />
  </svg>
);

// ── Texto do progresso ────────────────────────────────────────────────────────

// fase = "MAXXI — PRETO · enfesto 1/1 · grandes" ou
//        "Simulando mesa de 200 cm · MAXXI — PRETO · enfesto 1/1 · pequenas" ou
//        (decisão do enfesto, antes de encaixar)
//        "Analisando as peças… · MAXXI — PRETO" /
//        "Comparando formas de enfesto… · MAXXI — PRETO · 2/4 Enfesto duplo, sem sobra"
function descrever(estado) {
  if (!estado || estado.status === "FILA") return { principal: "Na fila...", detalhe: "" };
  const partes = (estado.fase || "").split(" · ").filter(Boolean);
  if (partes[0]?.startsWith("Analisando") || partes[0]?.startsWith("Comparando")) {
    return { principal: partes[0], detalhe: partes.slice(1).join(" · ") };
  }
  const simulando = partes[0]?.startsWith("Simulando");
  const etapa = partes[partes.length - 1];
  const contexto = partes.slice(simulando ? 1 : 0, ETAPAS[etapa] ? -1 : undefined).join(" · ");
  const aprov =
    estado.aproveitamento_parcial != null
      ? ` · ${numBR(estado.aproveitamento_parcial * 100, 0)}% de aproveitamento`
      : "";

  if (simulando) {
    const mesa = partes[0].match(/\d+/)?.[0] || "";
    return {
      principal: mesa ? `Simulando mesas de ${mesa} cm…` : "Simulando mesas…",
      detalhe: "Os encaixes já foram gravados; falta só a comparação com a mesa maior.",
    };
  }
  const detalhe = [contexto, ETAPAS[etapa]].filter(Boolean).join(" · ");
  if (!estado.mesa_atual) return { principal: "Encaixando...", detalhe };
  const verbo = etapa === "polimento" ? "Refinando" : "Encaixando";
  return {
    principal: `${verbo} mesa ${estado.mesa_atual} de ${estado.total_mesas}${aprov}`,
    detalhe,
  };
}

// ── Componente principal ──────────────────────────────────────────────────────

export default function ProgressoEncaixe({
  ocId,
  consultarJob,
  cancelarJob,
  chave,
  onConcluido,
  onFim,
}) {
  const [estado, setEstado] = useState(null);
  const [agora, setAgora] = useState(Date.now());
  const [confirmando, setConfirmando] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [erroRede, setErroRede] = useState(null);

  // Callbacks por ref: o pai recria as funções a cada render e isso não
  // pode reiniciar a consulta.
  const cb = useRef({ onConcluido, onFim });
  cb.current = { onConcluido, onFim };
  const api = useRef(null);
  api.current = {
    consultar: consultarJob ?? (() => getJobOrdemCorte(ocId)),
    cancelar: cancelarJob ?? (() => cancelarJobOrdemCorte(ocId)),
  };
  const deOc = !consultarJob;

  useEffect(() => {
    let vivo = true;
    let timer = null;
    const consultar = async () => {
      try {
        const e = await api.current.consultar();
        if (!vivo) return;
        setErroRede(null);
        setEstado(e);
        if (!e) return cb.current.onFim?.(null);
        if (e.status === "CONCLUIDO") return cb.current.onConcluido?.(e);
        if (e.status === "CANCELADO") return cb.current.onFim?.(e);
        if (e.status === "ERRO") return; // fica na tela até o usuário dispensar
      } catch (err) {
        // Falha de rede não encerra: o job continua no servidor.
        if (vivo) setErroRede(err.message);
      }
      if (vivo) timer = setTimeout(consultar, INTERVALO_MS);
    };
    consultar();
    return () => {
      vivo = false;
      clearTimeout(timer);
    };
  }, [ocId, chave]);

  // Relógio do tempo decorrido.
  useEffect(() => {
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const cancelar = async () => {
    setConfirmando(false);
    setCancelando(true);
    try {
      setEstado(await api.current.cancelar());
    } catch (err) {
      // 404: o job terminou entre o clique e a confirmação — a próxima
      // consulta traz o estado final.
      if (err.status !== 404) setErroRede(err.message);
    } finally {
      setCancelando(false);
    }
  };

  if (estado?.status === "ERRO")
    return (
      <div className={styles.erro} role="alert">
        <IconeAlerta />
        <div className={styles.erroTexto}>
          {/* A mensagem vem pronta do servidor (nesting_jobs): motivo + o que
              foi preservado. Aqui não se acrescenta nada. */}
          <span>{estado.erro || "Não foi possível gerar o encaixe."}</span>
        </div>
        <button type="button" className={styles.btnSecundario} onClick={() => onFim?.(estado)}>
          Fechar
        </button>
      </div>
    );

  const rodando = estado?.status === "RODANDO";
  const { principal, detalhe } = estado
    ? descrever(estado)
    : { principal: "Iniciando...", detalhe: "" };
  const pct =
    rodando && estado.total_mesas && !principal.startsWith("Comparando")
      ? Math.min(100, Math.round((estado.mesa_atual / estado.total_mesas) * 100))
      : null;
  const cancelPedido = cancelando || estado?.cancelamento_pedido;

  return (
    <div className={styles.progresso} role="status" aria-live="polite">
      <div className={styles.linhaTopo}>
        <span className={styles.principal}>{cancelPedido ? "Cancelando..." : principal}</span>
        <span className={styles.tempo} title="Tempo decorrido">
          <IconeRelogio />
          {decorrido(estado?.iniciado_em || estado?.criado_em, agora)}
        </span>
        <button
          type="button"
          className={styles.btnSecundario}
          onClick={() => setConfirmando(true)}
          disabled={!estado || cancelPedido || !ATIVOS.includes(estado.status)}
        >
          Cancelar
        </button>
      </div>
      <div
        className={styles.trilho}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct ?? undefined}
      >
        {pct == null ? (
          <div className={styles.barraIndeterminada} />
        ) : (
          <div className={styles.barra} style={{ width: `${Math.max(pct, 4)}%` }} />
        )}
      </div>
      {(detalhe || erroRede) && (
        <span className={styles.nota}>
          {erroRede ? `Sem resposta do servidor (${erroRede}) — tentando de novo.` : detalhe}
        </span>
      )}

      {confirmando && (
        <ConfirmarCancelamento deOc={deOc} onSim={cancelar} onNao={() => setConfirmando(false)} />
      )}
    </div>
  );
}

// Confirmação própria em portal: o ConfirmModal compartilhado fica por baixo
// do assistente (z-index), e o Esc daqui não pode fechar o assistente junto.
function ConfirmarCancelamento({ deOc, onSim, onNao }) {
  const overlayProps = useOverlayDismiss(onNao);
  useEffect(() => {
    const esc = (e) => {
      if (e.key !== "Escape") return;
      e.stopPropagation();
      onNao();
    };
    window.addEventListener("keydown", esc, true);
    return () => window.removeEventListener("keydown", esc, true);
  }, [onNao]);

  return ReactDOM.createPortal(
    <div className={styles.overlay} {...overlayProps}>
      <div
        className={styles.dialogo}
        role="alertdialog"
        aria-modal="true"
        aria-label="Cancelar geração"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className={styles.dialogoTitulo}>Cancelar geração</h2>
        <p className={styles.dialogoTexto}>
          Interromper o encaixe em andamento?
          {deOc
            ? " Os encaixes anteriores desta OC serão mantidos."
            : " Nenhum encaixe será gravado."}
        </p>
        <div className={styles.dialogoAcoes}>
          <button type="button" className={styles.btnSecundario} onClick={onNao}>
            Continuar gerando
          </button>
          <button type="button" className={styles.btnPerigo} onClick={onSim} autoFocus>
            Cancelar geração
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

// ── Alerta de mesa maior ──────────────────────────────────────────────────────

/** oc.sugestao_mesa: { limite_cm, metros_atual, metros_sugerido, enfestos_atual,
 *  enfestos_sugerido, economia_m, economia_pct, economia_kg, economia_rs }. */
export function AlertaMesaMaior({ sugestao, limiteAtual, ocupado, onUsar, onManter }) {
  if (!sugestao) return null;
  const s = sugestao;
  const enfestos = (n) => `${n} ${n === 1 ? "enfesto" : "enfestos"}`;
  return (
    <div className={styles.alertaMesa} role="note">
      <IconeInfo />
      <div className={styles.alertaTexto}>
        <strong>Enfestos de até {s.limite_cm} cm economizariam tecido nesta OC.</strong>
        <span>
          {limiteAtual} cm: {numBR(s.metros_atual)} m em {enfestos(s.enfestos_atual)} ·{" "}
          {s.limite_cm} cm: {numBR(s.metros_sugerido)} m em {enfestos(s.enfestos_sugerido)}
        </span>
        <span>
          Economia: {numBR(s.economia_m)} m ({numBR(s.economia_pct, 1)}%) ·{" "}
          {numBR(s.economia_kg, 3)} kg · {moeda(s.economia_rs)}
        </span>
      </div>
      <div className={styles.alertaAcoes}>
        <button type="button" className={styles.btnPrimario} onClick={onUsar} disabled={ocupado}>
          Usar {s.limite_cm} cm
        </button>
        <button
          type="button"
          className={styles.btnSecundario}
          onClick={onManter}
          disabled={ocupado}
        >
          Manter {limiteAtual} cm
        </button>
      </div>
    </div>
  );
}

// ── Mesas e enfestos ──────────────────────────────────────────────────────────

/** Moldes que a mesa corta, por camada: "COSTAS G x2 · COSTAS M x2". */
export function textoMoldes(pecasParte) {
  return (pecasParte || [])
    .map((p) => {
      const nome = [p.peca || p.molde, p.tamanho].filter(Boolean).join(" ") || "Peça";
      return `${nome} x${p.por_camada ?? p.quantidade ?? 0}`;
    })
    .join(" · ");
}

export function MoldesMesa({ pecas }) {
  const texto = textoMoldes(pecas);
  if (!texto) return null;
  const espelhadas = (pecas || []).reduce((s, p) => s + (p.espelhadas || 0), 0);
  return (
    <div
      className={styles.moldes}
      title={espelhadas ? `${espelhadas} peça(s) espelhada(s) (metade de par)` : texto}
    >
      <span className={styles.moldesRotulo}>Moldes</span>
      <span className={styles.moldesLista}>{texto}</span>
    </div>
  );
}

/** Agrupa os encaixes (mesas) por enfesto, na ordem em que vêm. A grade por
 *  tamanho é do enfesto inteiro e vem só na parte 1. */
export function agruparEnfestos(encaixes) {
  const grupos = new Map();
  for (const e of encaixes || []) {
    // grupo_corte: lote + produto quando a OC é organizada por produto.
    const chave = e.enfesto != null ? `${e.grupo_corte || e.lote_id}|${e.enfesto}` : e.id;
    let g = grupos.get(chave);
    if (!g) {
      g = {
        chave,
        enfesto: e.enfesto,
        tecido_nome: e.produto_nome ? `${e.produto_nome} · ${e.tecido_nome}` : e.tecido_nome,
        lote_id: e.lote_id,
        mesas: [],
      };
      grupos.set(chave, g);
    }
    g.mesas.push(e);
    if (!g.grade && (e.pecas_por_tamanho || []).length) g.grade = e.pecas_por_tamanho;
    g.camadas = g.camadas ?? e.num_camadas;
  }
  return [...grupos.values()];
}

/** Cabeçalho do enfesto: tecido · Enfesto N · camadas · mesas e a grade por tamanho. */
export function ResumoEnfesto({ grupo, loteCodigo }) {
  const mesas = grupo.mesas.length;
  return (
    <div className={styles.enfesto}>
      <span className={styles.enfestoTitulo} title={loteCodigo ? `Lote ${loteCodigo}` : undefined}>
        {[
          grupo.tecido_nome,
          grupo.enfesto != null ? `Enfesto ${grupo.enfesto}` : "Encaixe",
        ]
          .filter(Boolean)
          .join(" · ") || "Encaixe"}
      </span>
      <span className={styles.enfestoInfo}>
        {grupo.camadas} {grupo.camadas === 1 ? "camada" : "camadas"} · {mesas}{" "}
        {mesas === 1 ? "mesa" : "mesas"}
      </span>
      {grupo.grade && (
        <span className={styles.grade}>
          {grupo.grade.map((p, i) => (
            <span
              key={i}
              className={styles.gradeTam}
              title={
                p.sobra > 0
                  ? `${p.sobra} ${p.sobra === 1 ? "peça" : "peças"} a mais que o pedido (sobra)`
                  : p.grupo_nome || ""
              }
            >
              {p.tamanho} <strong>{p.pecas}</strong>
              {p.sobra > 0 && <span className={styles.sobra}> +{p.sobra}</span>}
            </span>
          ))}
        </span>
      )}
    </div>
  );
}

const fmtEnc = (n) => (n != null ? `ENC-${String(n).padStart(3, "0")}` : "ENC-—");

/** Card de uma mesa (usado no assistente; o detalhe tem o card dele, com link). */
export function CardMesa({ encaixe: e }) {
  const parte = e.total_partes > 1 ? `parte ${e.parte_numero} de ${e.total_partes}` : "mesa única";
  return (
    <article className={styles.card}>
      <div className={styles.cardTopo}>
        <strong>{fmtEnc(e.numero_enc)}</strong>
        <span className={styles.cardParte}>{parte}</span>
      </div>
      <dl className={styles.cardMetricas}>
        <div>
          <dt>COMPR.</dt>
          <dd>{numBR(e.comp_metros)} m</dd>
        </div>
        <div>
          <dt>APROV.</dt>
          <dd>{e.aproveitamento_pct != null ? `${numBR(e.aproveitamento_pct, 1)}%` : "—"}</dd>
        </div>
        <div>
          <dt>PESO</dt>
          <dd>{numBR(e.peso_total_kg, 3)} kg</dd>
        </div>
        <div>
          <dt>CAMADAS</dt>
          <dd>{e.num_camadas != null ? numBR(e.num_camadas, 0) : "—"}</dd>
        </div>
      </dl>
      <MoldesMesa pecas={e.pecas_parte} />
    </article>
  );
}

export const cardsGridClass = styles.cards;

// ── Rótulo do motor ───────────────────────────────────────────────────────────

/**
 * "Motor v2 · Automático (Máximo)" | "Motor v2 · Equilibrado" | null.
 * O perfil concreto (qualidade_perfil) vem do mapa_json; quando a OC pediu
 * "Automático", o rótulo mostra o perfil que o motor escolheu.
 */
export function RotuloMotor({ encaixes }) {
  const e = (encaixes || []).find((x) => x.motor_usado);
  if (!e || e.motor_usado !== "v2") return null;
  const perfil = QUALIDADE_LABEL[e.qualidade_perfil || e.qualidade] || "Equilibrado";
  const texto = e.qualidade === "AUTOMATICO" ? `Motor v2 · Automático (${perfil})` : `Motor v2 · ${perfil}`;
  return (
    <span
      className={styles.motor}
      title={
        e.qualidade === "AUTOMATICO"
          ? "Qualidade Automática: o perfil é escolhido pelo número de peças do enfesto (poucas → Máximo, médias → Equilibrado, muitas → Rápido)."
          : undefined
      }
    >
      {texto}
    </span>
  );
}
