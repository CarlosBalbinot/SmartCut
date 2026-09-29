import { useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { useNavigate } from "react-router-dom";
import {
  atualizarOrdemCorte,
  atualizarOrdemCorteDoPedido,
  definirTecidosOrdemCorte,
  gerarEncaixesOrdemCorte,
  getLotesDisponiveis,
  getOrdemCorte,
  simularOrdemCorte,
} from "../../api/ordensCorte";
import useOverlayDismiss from "../../hooks/useOverlayDismiss";
import styles from "./OrdemCorteAssistente.module.css";

/**
 * Assistente da Ordem de Corte (3 passos): Conferência → Tecidos → Encaixes.
 *
 * Tudo o que o usuário escolhe é gravado na hora (lote de cada produto/cor,
 * modo de camadas, comprimento máximo do enfesto) — fechar em qualquer passo deixa a OC em RASCUNHO com as
 * escolhas feitas, e reabrir continua de onde parou.
 *
 * Props:
 *   ocId     — id da Ordem de Corte
 *   onFechar — chamado ao fechar (a página recarrega o estado da OC)
 */

const PASSOS = ["Conferência", "Tecidos", "Encaixes"];

// Pendências de molde (bloqueiam o passo 1): texto curto na célula e o
// motivo + o que fazer no tooltip.
const PENDENCIAS_MOLDE = {
  SEM_GRUPO_MOLDE: {
    curto: "Sem grupo de moldes",
    dica: "Produto sem grupo de moldes vinculado. Vincule um grupo de moldes ao produto em Produção > Moldes.",
  },
  SEM_MOLDE_TAMANHO: {
    curto: "Sem molde do tamanho",
    dica: "O grupo de moldes não tem molde deste tamanho. Importe o molde do tamanho em Produção > Moldes.",
  },
  GRADE_SEM_TAMANHO: {
    curto: "Sem tamanho na grade",
    dica: "O SKU não tem coluna de tamanho na grade. Ajuste a grade do produto em Produtos > Grade.",
  },
};

const MODOS = [
  { valor: "SEM_SOBRA", rotulo: "Sem sobra", detalhe: "corta exatamente o pedido" },
  { valor: "MENOS_ENFESTOS", rotulo: "Menos enfestos", detalhe: "pode sobrar peças" },
];

const norm = (s) => (s || "").trim().toUpperCase();
const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;
const fmtNum = (v, casas = 2) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("pt-BR", {
        minimumFractionDigits: casas,
        maximumFractionDigits: casas,
      });
const fmtEnc = (n) => (n != null ? `ENC-${String(n).padStart(3, "0")}` : "ENC-—");
// "parte 1 de 3" — só para enfesto dividido (encaixes antigos só têm "1/2").
const fmtParte = (e) => {
  if (e.total_partes > 1) return `parte ${e.parte_numero} de ${e.total_partes}`;
  if (!e.parte) return "";
  const [n, total] = String(e.parte).split("/");
  return total ? `parte ${n} de ${total}` : `parte ${e.parte}`;
};

// Comprimento máximo do enfesto (limite da mesa de corte), em cm.
const COMP_MIN = 50;
const COMP_MAX = 2000;
const COMP_PADRAO = 150;

// ── Ícones ────────────────────────────────────────────────────────────────────

const svgBase = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};

function IconeFechar() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" {...svgBase}>
      <line x1="4" y1="4" x2="12" y2="12" />
      <line x1="12" y1="4" x2="4" y2="12" />
    </svg>
  );
}

function IconeLupa() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" {...svgBase}>
      <circle cx="7" cy="7" r="4.5" />
      <line x1="10.5" y1="10.5" x2="14" y2="14" />
    </svg>
  );
}

function IconeCheck() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" {...svgBase} strokeWidth="2.2">
      <polyline points="3.5 8.5 6.5 11.5 12.5 4.5" />
    </svg>
  );
}

function IconeAlerta() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" {...svgBase}>
      <path d="M8 2.2 14.2 13H1.8z" />
      <line x1="8" y1="6.5" x2="8" y2="9.3" />
      <line x1="8" y1="11.2" x2="8" y2="11.3" />
    </svg>
  );
}

// ── Assistente ────────────────────────────────────────────────────────────────

// passoInicial: 2 reabre direto em Tecidos (botão "Editar tecidos" da OC).
export default function OrdemCorteAssistente({ ocId, onFechar, passoInicial = 1 }) {
  const navigate = useNavigate();
  const [oc, setOc] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [passo, setPasso] = useState(passoInicial);
  const [erro, setErro] = useState(null);
  const [salvando, setSalvando] = useState(false);
  const [atualizando, setAtualizando] = useState(false);
  const [lookupLinha, setLookupLinha] = useState(null);
  const [lotes, setLotes] = useState(null);
  const [simulacao, setSimulacao] = useState(null);
  const [simulando, setSimulando] = useState(false);
  const [gerando, setGerando] = useState(false);
  const [avisosGeracao, setAvisosGeracao] = useState(null);

  const overlayProps = useOverlayDismiss(onFechar, { enabled: !lookupLinha });

  // Esc fecha o assistente — exceto com o lookup de lote aberto (ele trata o
  // próprio Esc).
  const lookupAberto = useRef(false);
  lookupAberto.current = !!lookupLinha;
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "Escape" && !lookupAberto.current) onFechar();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onFechar]);

  useEffect(() => {
    setCarregando(true);
    getOrdemCorte(ocId)
      .then(setOc)
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false));
  }, [ocId]);

  const editavel = oc?.status === "RASCUNHO";
  const pendencias = oc?.pendencias || [];
  const pendMolde = pendencias.filter((p) => PENDENCIAS_MOLDE[p.codigo]);
  const semTecido = (oc?.tecidos || []).some((t) => !t.lote_id);

  const pendPorItem = useMemo(() => {
    const mapa = {};
    for (const p of pendMolde) for (const n of p.numero_itens || []) mapa[n] = p;
    return mapa;
  }, [oc]);

  // ── Simulação dos dois modos (passo 2, com todos os lotes escolhidos) ──
  const chaveLotes = (oc?.tecidos || []).map((t) => t.lote_id || "-").join("|");
  useEffect(() => {
    if (passo !== 2 || !oc || semTecido) {
      setSimulacao(null);
      return;
    }
    let ativo = true;
    setSimulando(true);
    Promise.all([simularOrdemCorte(oc.id, "SEM_SOBRA"), simularOrdemCorte(oc.id, "MENOS_ENFESTOS")])
      .then(
        ([semSobra, menos]) => ativo && setSimulacao({ SEM_SOBRA: semSobra, MENOS_ENFESTOS: menos })
      )
      .catch((e) => ativo && setErro(e.message))
      .finally(() => ativo && setSimulando(false));
    return () => {
      ativo = false;
    };
  }, [passo, chaveLotes, oc?.itens?.length]);

  const irPara = (n) => {
    setErro(null);
    setPasso(n);
  };

  const abrirLookup = (linha) => {
    setLookupLinha(linha);
    if (!lotes) {
      // ?oc_id: a OC não entra na própria reserva — a tela mostra o que
      // sobraria para ela, não o que ela mesma travou.
      getLotesDisponiveis(oc.id)
        .then(setLotes)
        .catch((e) => {
          setLotes([]);
          setErro(e.message);
        });
    }
  };

  const escolherLote = async (linha, lote) => {
    setLookupLinha(null);
    setSalvando(true);
    setErro(null);
    try {
      setOc(
        await definirTecidosOrdemCorte(oc.id, [
          { produto_pai_id: linha.produto_pai_id, cor: linha.cor, lote_id: lote.id },
        ])
      );
    } catch (e) {
      setErro(e.message);
    } finally {
      setSalvando(false);
    }
  };

  const mudarModo = async (modo) => {
    if (modo === oc.modo_camadas) return;
    setSalvando(true);
    setErro(null);
    try {
      setOc(await atualizarOrdemCorte(oc.id, { modo_camadas: modo }));
    } catch (e) {
      setErro(e.message);
    } finally {
      setSalvando(false);
    }
  };

  // Grava na hora, como o modo. Devolve false se o valor for inválido (o
  // campo volta ao valor gravado).
  const mudarComprimento = async (cm) => {
    if (cm === oc.comprimento_max_cm) return true;
    if (!Number.isInteger(cm) || cm < COMP_MIN || cm > COMP_MAX) {
      setErro(
        `O comprimento máximo deve ser um número inteiro entre ${COMP_MIN} e ${COMP_MAX} cm.`
      );
      return false;
    }
    setSalvando(true);
    setErro(null);
    try {
      setOc(await atualizarOrdemCorte(oc.id, { comprimento_max_cm: cm }));
      return true;
    } catch (e) {
      setErro(e.message);
      return false;
    } finally {
      setSalvando(false);
    }
  };

  const atualizarDoPedido = async () => {
    setAtualizando(true);
    setErro(null);
    try {
      setOc(await atualizarOrdemCorteDoPedido(oc.id));
      setAvisosGeracao(null);
    } catch (e) {
      setErro(e.message);
    } finally {
      setAtualizando(false);
    }
  };

  const gerar = async () => {
    setGerando(true);
    setErro(null);
    try {
      const r = await gerarEncaixesOrdemCorte(oc.id);
      setAvisosGeracao(r.avisos || []);
      setOc(await getOrdemCorte(oc.id));
    } catch (e) {
      setErro(e.message);
      // 409 (pendência/desatualizada): o estado da OC pode ter mudado.
      if (e.status === 409)
        getOrdemCorte(oc.id)
          .then(setOc)
          .catch(() => {});
    } finally {
      setGerando(false);
    }
  };

  const concluir = () => {
    onFechar();
    navigate(`/producao/ordens-corte/${oc.id}`);
  };

  const podeAvancar =
    !!oc && !salvando && ((passo === 1 && pendMolde.length === 0) || (passo === 2 && !semTecido));
  const temEncaixes = (oc?.encaixes || []).length > 0;

  return (
    <div className={styles.overlay} {...overlayProps}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-label="Ordem de Corte"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.head}>
          <div>
            <h2 className={styles.titulo}>
              {oc ? `Ordem de Corte ${oc.numero_fmt}` : "Ordem de Corte"}
            </h2>
            {oc && (
              <p className={styles.subtitulo}>
                Pedido {oc.pedido_numero}
                {oc.cliente ? ` · ${oc.cliente}` : ""}
                {!editavel && ` · ${oc.status} (somente leitura)`}
              </p>
            )}
          </div>
          <button
            type="button"
            className={styles.btnIcone}
            onClick={onFechar}
            aria-label="Fechar"
            title="Fechar (Esc)"
          >
            <IconeFechar />
          </button>
        </div>

        <ol className={styles.passos}>
          {PASSOS.map((nome, i) => {
            const n = i + 1;
            const estado = n < passo ? styles.passoFeito : n === passo ? styles.passoAtual : "";
            return (
              <li key={nome} className={`${styles.passo} ${estado}`}>
                <button
                  type="button"
                  className={styles.passoBtn}
                  disabled={n >= passo}
                  onClick={() => irPara(n)}
                  aria-current={n === passo ? "step" : undefined}
                >
                  <span className={styles.passoNum}>{n < passo ? <IconeCheck /> : n}</span>
                  <span className={styles.passoNome}>{nome}</span>
                </button>
              </li>
            );
          })}
        </ol>

        <div className={styles.body}>
          {erro && (
            <div className={styles.boxErro} role="alert">
              <IconeAlerta />
              <span>{erro}</span>
            </div>
          )}

          {carregando ? (
            <p className={styles.estado}>Carregando…</p>
          ) : !oc ? null : passo === 1 ? (
            <PassoConferencia
              oc={oc}
              pendPorItem={pendPorItem}
              pendMolde={pendMolde}
              editavel={editavel}
              atualizando={atualizando}
              onAtualizar={atualizarDoPedido}
            />
          ) : passo === 2 ? (
            <PassoTecidos
              oc={oc}
              editavel={editavel}
              salvando={salvando}
              semTecido={semTecido}
              simulacao={simulacao}
              simulando={simulando}
              onLookup={abrirLookup}
              onModo={mudarModo}
              onComprimento={mudarComprimento}
            />
          ) : (
            <PassoEncaixes
              oc={oc}
              editavel={editavel}
              gerando={gerando}
              avisosGeracao={avisosGeracao}
              onGerar={gerar}
            />
          )}
        </div>

        <div className={styles.rodape}>
          <button type="button" className={styles.btnSecundario} onClick={onFechar}>
            Fechar
          </button>
          <div className={styles.rodapeDireita}>
            {passo > 1 && (
              <button
                type="button"
                className={styles.btnSecundario}
                onClick={() => irPara(passo - 1)}
              >
                Voltar
              </button>
            )}
            {passo < 3 ? (
              <button
                type="button"
                className={styles.btnPrimario}
                disabled={!podeAvancar}
                onClick={() => irPara(passo + 1)}
              >
                Avançar
              </button>
            ) : (
              <button
                type="button"
                className={styles.btnPrimario}
                disabled={!temEncaixes || gerando}
                onClick={concluir}
              >
                Concluir
              </button>
            )}
          </div>
        </div>
      </div>

      {lookupLinha && (
        <LoteLookup
          linha={lookupLinha}
          lotes={lotes}
          onSelecionar={(lote) => escolherLote(lookupLinha, lote)}
          onFechar={() => setLookupLinha(null)}
        />
      )}
    </div>
  );
}

// ── Passo 1 — Conferência ─────────────────────────────────────────────────────

function PassoConferencia({ oc, pendPorItem, pendMolde, editavel, atualizando, onAtualizar }) {
  const pecas = oc.itens.reduce((s, i) => s + i.quantidade, 0);
  return (
    <>
      {oc.desatualizada && (
        <div className={styles.boxAviso}>
          <IconeAlerta />
          <span>O pedido mudou depois da geração desta Ordem de Corte.</span>
          {editavel && (
            <button
              type="button"
              className={styles.btnSecundario}
              onClick={onAtualizar}
              disabled={atualizando}
            >
              {atualizando ? "Atualizando…" : "Atualizar do pedido"}
            </button>
          )}
        </div>
      )}

      <p className={styles.resumo}>
        {plural(oc.itens.length, "item", "itens")} · {plural(pecas, "peça", "peças")} ·{" "}
        {plural(oc.tecidos.length, "combinação produto/cor", "combinações produto/cor")}
      </p>

      <div className={styles.tabelaWrap}>
        <table className={styles.tabela}>
          <thead>
            <tr>
              <th className={styles.colItem}>Item</th>
              <th>Ref</th>
              <th>Descrição</th>
              <th>Cor</th>
              <th>Tamanho</th>
              <th className={styles.num}>Qtde</th>
              <th>Molde</th>
            </tr>
          </thead>
          <tbody>
            {oc.itens.map((i) => {
              const pend = pendPorItem[i.numero_item];
              const info = pend && PENDENCIAS_MOLDE[pend.codigo];
              return (
                <tr key={i.id} className={pend ? styles.linhaPendente : ""}>
                  <td className={styles.colItem}>{String(i.numero_item).padStart(3, "0")}</td>
                  <td>{i.sku_codigo || i.produto_codigo}</td>
                  <td>{i.produto_descricao}</td>
                  <td>{i.cor || "—"}</td>
                  <td>{i.tamanho || "—"}</td>
                  <td className={styles.num}>{i.quantidade}</td>
                  <td>
                    {info ? (
                      <span className={styles.pendencia} title={`${pend.mensagem}\n${info.dica}`}>
                        <IconeAlerta />
                        {info.curto}
                      </span>
                    ) : (
                      i.grupo_molde_nome || "—"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {pendMolde.length > 0 && (
        <p className={styles.notaErro}>
          Resolva as pendências de molde para continuar — passe o mouse sobre a pendência para ver o
          que fazer.
        </p>
      )}
    </>
  );
}

// ── Passo 2 — Tecidos ─────────────────────────────────────────────────────────

function PassoTecidos({
  oc,
  editavel,
  salvando,
  semTecido,
  simulacao,
  simulando,
  onLookup,
  onModo,
  onComprimento,
}) {
  const gravado = oc.comprimento_max_cm ?? COMP_PADRAO;
  const [comp, setComp] = useState(String(gravado));
  useEffect(() => setComp(String(gravado)), [gravado]);

  const salvarComprimento = async () => {
    const ok = await onComprimento(Number(comp.trim()));
    if (!ok) setComp(String(gravado));
  };

  return (
    <>
      <div className={styles.tabelaWrap}>
        <table className={styles.tabela}>
          <thead>
            <tr>
              <th>Produto</th>
              <th>Cor</th>
              <th className={styles.num}>Peças</th>
              <th className={styles.colLote}>Lote</th>
              <th className={styles.num}>Largura (cm)</th>
              <th className={styles.num}>Gramatura (g/m²)</th>
              <th className={styles.num}>Disponível (kg)</th>
            </tr>
          </thead>
          <tbody>
            {oc.tecidos.map((t) => (
              <tr key={t.id} className={t.lote ? "" : styles.linhaSemLote}>
                <td>{t.produto_descricao}</td>
                <td>{t.cor || "—"}</td>
                <td className={styles.num}>{t.quantidade}</td>
                <td className={styles.colLote}>
                  <button
                    type="button"
                    className={styles.loteBtn}
                    disabled={!editavel || salvando}
                    onClick={() => onLookup(t)}
                    title={
                      t.lote
                        ? `${t.lote.modelo} — ${t.lote.cor_tecido}`
                        : "Escolher o lote de tecido"
                    }
                  >
                    <span className={t.lote ? styles.loteValor : styles.lotePlaceholder}>
                      {t.lote
                        ? `${t.lote.codigo_lote} · ${t.lote.modelo} ${t.lote.cor_tecido}`
                        : "Selecionar lote"}
                    </span>
                    <IconeLupa />
                  </button>
                </td>
                <td className={styles.num}>{fmtNum(t.lote?.largura_util_cm, 0)}</td>
                <td className={styles.num}>{fmtNum(t.lote?.gramatura_g_m2, 0)}</td>
                <td className={styles.num}>{fmtNum(t.lote?.peso_disponivel_kg, 3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modo de camadas e comprimento máximo lado a lado (quebram em tela estreita). */}
      <div className={styles.modos}>
        <fieldset className={styles.modos} disabled={!editavel || salvando}>
          <legend className={styles.secao}>Modo de camadas</legend>
          {MODOS.map((m) => (
            <label key={m.valor} className={styles.modo}>
              <input
                type="radio"
                name="modo_camadas"
                value={m.valor}
                checked={oc.modo_camadas === m.valor}
                onChange={() => onModo(m.valor)}
              />
              <span>
                <strong>{m.rotulo}</strong> ({m.detalhe})
              </span>
            </label>
          ))}
        </fieldset>

        <fieldset className={styles.modos} disabled={!editavel || salvando}>
          <legend className={styles.secao}>
            <label htmlFor="oc-comprimento-max">Comprimento máximo do enfesto (cm)</label>
          </legend>
          <input
            id="oc-comprimento-max"
            className="sc-input"
            type="number"
            inputMode="numeric"
            min={COMP_MIN}
            max={COMP_MAX}
            step={1}
            style={{ width: "7rem" }}
            value={comp}
            onChange={(e) => setComp(e.target.value)}
            onBlur={salvarComprimento}
            onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
          />
          <span className={styles.nota}>
            Limite da mesa. Riscos menores saem com o tamanho real; maiores são divididos em partes.
          </span>
        </fieldset>
      </div>

      <h3 className={styles.secao}>Comparação dos modos</h3>
      {semTecido ? (
        <p className={styles.estado}>Escolha o lote de todas as linhas para comparar os modos.</p>
      ) : simulando && !simulacao ? (
        <p className={styles.estado}>Calculando…</p>
      ) : simulacao ? (
        <Comparacao simulacao={simulacao} modoAtual={oc.modo_camadas} />
      ) : null}
    </>
  );
}

function Comparacao({ simulacao, modoAtual }) {
  const semSobra = simulacao.SEM_SOBRA;
  const menos = simulacao.MENOS_ENFESTOS;
  const menosPorLote = Object.fromEntries(menos.grupos.map((g) => [g.lote_id, g]));
  const camadas = (g) => (g ? g.enfestos.map((e) => e.camadas).join(" + ") || "—" : "—");
  const cls = (modo) => (modo === modoAtual ? styles.colModoAtual : "");

  const celulas = (g, modo) => (
    <>
      <td className={`${styles.num} ${cls(modo)}`}>{g ? g.total_enfestos : "—"}</td>
      <td className={`${styles.num} ${cls(modo)}`}>{camadas(g)}</td>
      <td className={`${styles.num} ${cls(modo)}`}>{g ? g.sobra_total : "—"}</td>
    </>
  );

  return (
    <div className={styles.tabelaWrap}>
      <table className={`${styles.tabela} ${styles.tabelaCompacta}`}>
        <thead>
          <tr>
            <th rowSpan={2}>Tecido / lote</th>
            <th colSpan={3} className={`${styles.centro} ${cls("SEM_SOBRA")}`}>
              Sem sobra
            </th>
            <th colSpan={3} className={`${styles.centro} ${cls("MENOS_ENFESTOS")}`}>
              Menos enfestos
            </th>
          </tr>
          <tr>
            {["SEM_SOBRA", "MENOS_ENFESTOS"].map((m) => (
              <FragmentoCab key={m} classe={cls(m)} />
            ))}
          </tr>
        </thead>
        <tbody>
          {semSobra.grupos.map((g) => (
            <tr key={g.lote_id || g.produtos_cores.join()}>
              <td>
                {g.lote_codigo} · {g.tecido}
              </td>
              {celulas(g, "SEM_SOBRA")}
              {celulas(menosPorLote[g.lote_id], "MENOS_ENFESTOS")}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>Total</td>
            <td className={`${styles.num} ${cls("SEM_SOBRA")}`}>{semSobra.total_enfestos}</td>
            <td className={cls("SEM_SOBRA")} />
            <td className={`${styles.num} ${cls("SEM_SOBRA")}`}>{semSobra.sobra_total}</td>
            <td className={`${styles.num} ${cls("MENOS_ENFESTOS")}`}>{menos.total_enfestos}</td>
            <td className={cls("MENOS_ENFESTOS")} />
            <td className={`${styles.num} ${cls("MENOS_ENFESTOS")}`}>{menos.sobra_total}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function FragmentoCab({ classe }) {
  return (
    <>
      <th className={`${styles.num} ${classe}`}>Enfestos</th>
      <th className={`${styles.num} ${classe}`}>Camadas</th>
      <th className={`${styles.num} ${classe}`}>Sobra</th>
    </>
  );
}

// ── Passo 3 — Encaixes ────────────────────────────────────────────────────────

function PassoEncaixes({ oc, editavel, gerando, avisosGeracao, onGerar }) {
  const lotes = Object.fromEntries(
    oc.tecidos.filter((t) => t.lote).map((t) => [t.lote.id, t.lote])
  );
  // Sem geração nesta sessão, os avisos vêm da conferência da OC (estoque).
  const avisos = avisosGeracao ?? oc.pendencias.filter((p) => !p.bloqueia);
  const encaixes = oc.encaixes;

  // Sobra por enfesto (um enfesto dividido em partes repete a sobra).
  const vistos = new Set();
  let sobraTotal = 0;
  for (const e of encaixes) {
    const k = `${e.lote_id}|${e.enfesto}`;
    if (vistos.has(k)) continue;
    vistos.add(k);
    sobraTotal += e.sobra_total || 0;
  }
  const pesoTotal = encaixes.reduce((s, e) => s + (e.peso_total_kg || 0), 0);

  return (
    <>
      {editavel && (
        <div className={styles.barraGerar}>
          <button type="button" className={styles.btnPrimario} onClick={onGerar} disabled={gerando}>
            {gerando ? "Gerando encaixes…" : encaixes.length ? "Gerar novamente" : "Gerar encaixes"}
          </button>
          <span className={styles.nota}>
            {gerando
              ? "O cálculo do encaixe pode levar alguns segundos por tecido."
              : encaixes.length
                ? "Gerar novamente substitui os encaixes atuais desta OC."
                : `Modo: ${MODOS.find((m) => m.valor === oc.modo_camadas)?.rotulo.toLowerCase()} · comprimento máximo ${oc.comprimento_max_cm ?? COMP_PADRAO} cm.`}
          </span>
          {gerando && <span className={styles.spinner} aria-hidden="true" />}
        </div>
      )}

      {oc.encaixes_desatualizados && !gerando && (
        <div className={styles.boxAviso}>
          <IconeAlerta />
          <span>Regere os encaixes para aplicar o novo limite.</span>
        </div>
      )}

      {avisos.length > 0 && (
        <div className={styles.boxAviso}>
          <IconeAlerta />
          <ul className={styles.listaAvisos}>
            {avisos.map((a, i) => (
              <li key={i}>{a.mensagem}</li>
            ))}
          </ul>
        </div>
      )}

      {encaixes.length === 0 ? (
        <p className={styles.estado}>{gerando ? "" : "Nenhum encaixe gerado ainda."}</p>
      ) : (
        <div className={styles.tabelaWrap}>
          <table className={styles.tabela}>
            <thead>
              <tr>
                <th>Encaixe</th>
                <th>Tecido / lote</th>
                <th className={styles.num}>Camadas</th>
                <th className={styles.num}>Comprimento (m)</th>
                <th className={styles.num}>Peso total (kg)</th>
                <th className={styles.num}>Aproveitamento</th>
                <th className={styles.num}>Sobra</th>
              </tr>
            </thead>
            <tbody>
              {encaixes.map((e) => (
                <tr key={e.id}>
                  <td>
                    {fmtEnc(e.numero_enc)}
                    {fmtParte(e) && <span className={styles.parte}> · {fmtParte(e)}</span>}
                  </td>
                  <td>
                    {lotes[e.lote_id]?.codigo_lote || "—"} · {e.tecido_nome}
                  </td>
                  <td className={styles.num}>{e.num_camadas}</td>
                  <td className={styles.num}>{fmtNum(e.comp_metros, 2)}</td>
                  <td className={styles.num}>{fmtNum(e.peso_total_kg, 3)}</td>
                  <td className={styles.num}>
                    {e.aproveitamento_pct != null ? `${fmtNum(e.aproveitamento_pct, 1)}%` : "—"}
                  </td>
                  <td className={styles.num}>{e.sobra_total ?? "—"}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={4}>Total</td>
                <td className={styles.num}>{fmtNum(pesoTotal, 3)}</td>
                <td />
                <td className={styles.num}>{sobraTotal}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </>
  );
}

// ── Lookup de lote ────────────────────────────────────────────────────────────

function LoteLookup({ linha, lotes, onSelecionar, onFechar }) {
  const [busca, setBusca] = useState("");
  const [ativo, setAtivo] = useState(0);
  const overlayProps = useOverlayDismiss(onFechar);
  const listaRef = useRef(null);

  // Lotes da mesma cor do produto primeiro; dentro de cada bloco, a ordem da
  // API (modelo, cor, código).
  const corProduto = norm(linha.cor);
  const q = norm(busca);
  const filtrados = (lotes || [])
    .filter((l) => !q || norm(`${l.modelo} ${l.cor_tecido} ${l.codigo_lote}`).includes(q))
    .map((l, idx) => ({ l, idx, mesmaCor: !!corProduto && norm(l.cor_tecido) === corProduto }))
    .sort((a, b) => Number(b.mesmaCor) - Number(a.mesmaCor) || a.idx - b.idx);

  useEffect(() => {
    const idx = filtrados.findIndex((f) => f.l.id === linha.lote_id);
    setAtivo(idx >= 0 ? idx : 0);
  }, [lotes]);

  useEffect(() => {
    listaRef.current?.querySelector(`[data-idx="${ativo}"]`)?.scrollIntoView({ block: "nearest" });
  }, [ativo]);

  const handleKeyDown = (e) => {
    if (e.key === "Escape") {
      // Não deixa o Esc chegar ao listener do assistente (fecharia os dois).
      e.preventDefault();
      e.stopPropagation();
      onFechar();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setAtivo((i) => Math.min(i + 1, filtrados.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAtivo((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtrados[ativo]) onSelecionar(filtrados[ativo].l);
    }
  };

  return ReactDOM.createPortal(
    <div
      className={`${styles.overlay} ${styles.overlayLookup}`}
      {...overlayProps}
      onKeyDown={handleKeyDown}
    >
      <div className={styles.lookup} onClick={(e) => e.stopPropagation()}>
        <div className={styles.head}>
          <div>
            <h2 className={styles.titulo}>Selecionar lote de tecido</h2>
            <p className={styles.subtitulo}>
              {linha.produto_descricao}
              {linha.cor ? ` · ${linha.cor}` : ""} · {plural(linha.quantidade, "peça", "peças")}
            </p>
          </div>
          <button type="button" className={styles.btnIcone} onClick={onFechar} aria-label="Fechar">
            <IconeFechar />
          </button>
        </div>

        <div className={styles.lookupBody}>
          <input
            className={styles.busca}
            placeholder="Buscar por modelo, cor ou código do lote…"
            value={busca}
            onChange={(e) => {
              setBusca(e.target.value);
              setAtivo(0);
            }}
            autoFocus
          />
          <div className={styles.lookupLista} ref={listaRef}>
            <table className={styles.tabela}>
              <thead>
                <tr>
                  <th>Modelo</th>
                  <th>Cor</th>
                  <th>Lote</th>
                  <th className={styles.num}>Largura (cm)</th>
                  <th className={styles.num}>Gramatura (g/m²)</th>
                  <th
                    className={styles.num}
                    title="Disponível menos o que outras OCs já reservaram."
                  >
                    Livre (kg)
                  </th>
                </tr>
              </thead>
              <tbody>
                {lotes === null ? (
                  <tr>
                    <td colSpan={6} className={styles.estado}>
                      Carregando…
                    </td>
                  </tr>
                ) : filtrados.length === 0 ? (
                  <tr>
                    <td colSpan={6} className={styles.estado}>
                      Nenhum lote disponível encontrado.
                    </td>
                  </tr>
                ) : (
                  filtrados.map(({ l, mesmaCor }, idx) => (
                    <tr
                      key={l.id}
                      data-idx={idx}
                      className={`${styles.linhaLookup} ${idx === ativo ? styles.linhaAtiva : ""}`}
                      onClick={() => setAtivo(idx)}
                      onDoubleClick={() => onSelecionar(l)}
                    >
                      <td>{l.modelo}</td>
                      <td>
                        {l.cor_tecido}
                        {mesmaCor && <span className={styles.tagCor}>cor do produto</span>}
                      </td>
                      <td>{l.codigo_lote}</td>
                      <td className={styles.num}>{fmtNum(l.largura_util_cm, 0)}</td>
                      <td className={styles.num}>{fmtNum(l.gramatura_g_m2, 0)}</td>
                      <td
                        className={styles.num}
                        title={
                          l.reservado_kg
                            ? `${fmtNum(l.peso_disponivel_kg, 3)} kg disponíveis, ${fmtNum(l.reservado_kg, 3)} kg reservados por outras OCs em produção.`
                            : `${fmtNum(l.peso_disponivel_kg, 3)} kg disponíveis, sem reserva de outras OCs.`
                        }
                      >
                        {fmtNum(l.livre_kg, 3)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <p className={styles.nota}>Duplo clique ou Enter para selecionar.</p>
        </div>

        <div className={styles.rodape}>
          <span />
          <div className={styles.rodapeDireita}>
            <button type="button" className={styles.btnSecundario} onClick={onFechar}>
              Cancelar
            </button>
            <button
              type="button"
              className={styles.btnPrimario}
              disabled={!filtrados[ativo]}
              onClick={() => filtrados[ativo] && onSelecionar(filtrados[ativo].l)}
            >
              Selecionar
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
