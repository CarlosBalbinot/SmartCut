import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  ComposedChart, Bar, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import {
  getSaldoContas, getLancamentos, getProjecao, getMetas, createMeta,
} from "../../api/financeiro";
import { configuracaoEmpresaApi } from "../../services/api";
import styles from "./PainelFinanceiro.module.css";

/* ── Helpers ── */
const MESES = [
  "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
  "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro",
];

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

function addMonths(mes, ano, n) {
  let m = mes + n, a = ano;
  while (m > 12) { m -= 12; a++; }
  return { mes: m, ano: a };
}

function subMonths(mes, ano, n) {
  let m = mes - n, a = ano;
  while (m < 1) { m += 12; a--; }
  return { mes: m, ano: a };
}

function parseVenc(iso) {
  if (!iso) return null;
  const [y, m, d] = iso.split("T")[0].split("-").map(Number);
  return new Date(y, m - 1, d);
}

/* Campo flexível: tenta múltiplos nomes de campo */
const campo = (obj, ...keys) => {
  for (const k of keys) if (obj?.[k] != null) return Number(obj[k]);
  return 0;
};

const SEMAFORO_CLS = { verde: styles.semaforoVerde, amarelo: styles.semaforoAmarelo, vermelho: styles.semaforoVermelho };
const DOT_CLS      = { verde: styles.dotVerde,      amarelo: styles.dotAmarelo,      vermelho: styles.dotVermelho      };

/* ── Componente ── */
export default function PainelFinanceiro() {
  const navigate = useNavigate();
  const now      = new Date();

  const [mes, setMes] = useState(now.getMonth() + 1);
  const [ano, setAno] = useState(now.getFullYear());

  const [saldoContas,       setSaldoContas]       = useState([]);
  const [lancamentos,       setLancamentos]       = useState([]);
  const [projecaoHistorico, setProjecaoHistorico] = useState([]);
  const [projecaoCascata,   setProjecaoCascata]   = useState([]);
  const [metas,             setMetas]             = useState([]);
  const [reservaMinima,     setReservaMinima]     = useState(5000);
  const [temReservaConfig,  setTemReservaConfig]  = useState(false);
  const [loading,           setLoading]           = useState(false);

  /* Modal: definir meta */
  const [modalMeta,  setModalMeta]  = useState(false);
  const [metaInput,  setMetaInput]  = useState("");
  const [savingMeta, setSavingMeta] = useState(false);

  /* ── Carregar config (uma vez) ── */
  useEffect(() => {
    configuracaoEmpresaApi.get()
      .then((cfg) => {
        const rm = cfg?.reserva_minima_caixa;
        if (rm != null) {
          setReservaMinima(Number(rm));
          setTemReservaConfig(true);
        }
      })
      .catch(() => {});
  }, []);

  /* ── Carregar dados financeiros (por mês) ── */
  const carregarDados = useCallback(async () => {
    setLoading(true);
    try {
      const inicio = subMonths(mes, ano, 4);
      const prox   = addMonths(mes, ano, 1);

      const [lancs, saldos, hist, casc, mts] = await Promise.all([
        getLancamentos(mes, ano),
        getSaldoContas(mes, ano),
        getProjecao(inicio.mes, inicio.ano, 5),
        getProjecao(prox.mes, prox.ano, 3),
        getMetas(ano),
      ]);

      setLancamentos(lancs  || []);
      setSaldoContas(saldos || []);
      setProjecaoHistorico(Array.isArray(hist) ? hist : []);
      setProjecaoCascata(Array.isArray(casc)   ? casc : []);
      setMetas(mts || []);
    } catch {}
    setLoading(false);
  }, [mes, ano]);

  useEffect(() => { carregarDados(); }, [carregarDados]);

  /* ── Navegação de mês ── */
  const navegarMes = (delta) => {
    const novo = mes + delta;
    if (novo > 12) { setMes(1);  setAno((a) => a + 1); }
    else if (novo < 1) { setMes(12); setAno((a) => a - 1); }
    else { setMes(novo); }
  };

  /* ── Dados derivados ── */
  const pagar   = lancamentos.filter((l) => l.tipo === "PAGAR");
  const receber = lancamentos.filter((l) => l.tipo === "RECEBER");

  const aPagar     = pagar  .filter((l) => l.status !== "PAGO").reduce((s, l) => s + (l.valor || 0), 0);
  const aReceber   = receber.filter((l) => l.status !== "PAGO").reduce((s, l) => s + (l.valor || 0), 0);
  const jaPago     = pagar  .filter((l) => l.status === "PAGO").reduce((s, l) => s + (l.valor || 0), 0);
  const jaRecebido = receber.filter((l) => l.status === "PAGO").reduce((s, l) => s + (l.valor || 0), 0);
  const saldoTotal = saldoContas.reduce((s, c) => s + (c.saldo || 0), 0);
  const projecaoFinal = saldoTotal + aReceber - aPagar;

  /* ── Alertas ── */
  const hojeDia  = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const em7Limit = new Date(hojeDia); em7Limit.setDate(em7Limit.getDate() + 7);

  const pendentes  = lancamentos.filter((l) => l.status !== "PAGO" && l.status !== "CANCELADO");
  const atrasados  = pendentes.filter((l) => { const v = parseVenc(l.vencimento); return v && v < hojeDia; });
  const em7Dias    = pendentes.filter((l) => { const v = parseVenc(l.vencimento); return v && v >= hojeDia && v <= em7Limit; });
  const totalAtrasado = atrasados.reduce((s, l) => s + (l.valor || 0), 0);
  const totalEm7      = em7Dias  .reduce((s, l) => s + (l.valor || 0), 0);

  /* ── Meta do mês ── */
  const metaMes     = metas.find((m) => m.mes === mes && m.ano === ano);
  const metaValor   = metaMes?.valor_meta  || 0;
  const metaRealiz  = metaMes?.valor_realizado ?? jaRecebido;
  const metaPct     = metaValor > 0 ? Math.min(100, (metaRealiz / metaValor) * 100) : 0;

  /* ── Dados do gráfico histórico ── */
  const historicoChart = projecaoHistorico.map((p) => {
    const receita = campo(p, "total_receitas", "receitas", "a_receber_total");
    const despesa = campo(p, "total_despesas", "despesas", "a_pagar_total");
    return {
      nome:    MESES[(p.mes - 1)].slice(0, 3),
      Receita: receita,
      Despesa: despesa,
      Lucro:   receita - despesa,
    };
  });

  /* ── Cascata dos próximos 3 meses ── */
  const cascataMeses = projecaoCascata.map((p) => {
    const saldoInicial  = campo(p, "saldo_inicial");
    const aReceberP     = campo(p, "total_receitas", "a_receber_total", "a_receber");
    const aPagarP       = campo(p, "total_despesas", "a_pagar_total",   "a_pagar");
    const saldoProj     = campo(p, "saldo_final", "saldo_projetado") || (saldoInicial + aReceberP - aPagarP);
    const retirada      = Math.max(0, saldoProj - reservaMinima);
    const semaforo      = saldoProj >= reservaMinima * 2 ? "verde" : saldoProj >= reservaMinima ? "amarelo" : "vermelho";
    return { mes: p.mes, ano: p.ano, saldoInicial, aReceber: aReceberP, aPagar: aPagarP, saldoProj, retirada, semaforo };
  });

  /* ── Salvar meta ── */
  const handleSalvarMeta = async () => {
    const valor = parseFloat(metaInput);
    if (!valor || valor <= 0) return;
    setSavingMeta(true);
    try {
      const criada = await createMeta({ mes, ano, tipo: "RECEITA", valor_meta: valor });
      setMetas((prev) => [
        ...prev.filter((m) => !(m.mes === mes && m.ano === ano)),
        criada || { mes, ano, valor_meta: valor },
      ]);
      setModalMeta(false);
      setMetaInput("");
    } catch {}
    setSavingMeta(false);
  };

  /* ── Render ── */
  return (
    <div className={styles.pagina}>

      {/* ─── Header ─── */}
      <div className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>Painel Financeiro</h1>
        <div className={styles.navMes}>
          <button className={styles.btnNav} onClick={() => navegarMes(-1)}>‹</button>
          <span className={styles.mesLabel}>{MESES[mes - 1]} {ano}</span>
          <button className={styles.btnNav} onClick={() => navegarMes(1)}>›</button>
        </div>
      </div>

      {loading && <p className={styles.loading}>Carregando…</p>}

      {/* ─── LINHA 1 — Saldo por conta ─── */}
      <div className={styles.saldoGrid}>
        {saldoContas.map((c) => (
          <div key={c.id ?? c.nome} className={styles.saldoCard}>
            <span className={styles.saldoNome}>{c.nome}</span>
            <span className={`${styles.saldoValor} ${(c.saldo ?? 0) < 0 ? styles.saldoValorNeg : ""}`}>
              {moeda(c.saldo)}
            </span>
            {c.saldo_inicial != null && (
              <span className={styles.saldoInicial}>Inicial: {moeda(c.saldo_inicial)}</span>
            )}
          </div>
        ))}
        {/* Card total */}
        <div className={`${styles.saldoCard} ${styles.saldoCardTotal}`}>
          <span className={`${styles.saldoNome} ${styles.saldoNomeTotal}`}>Caixa Total</span>
          <span className={`${styles.saldoValor} ${styles.saldoValorTotal}`}>
            {moeda(saldoTotal)}
          </span>
          {saldoContas.length > 0 && (
            <span className={`${styles.saldoInicial} ${styles.saldoInicialTotal}`}>
              {saldoContas.length} conta{saldoContas.length > 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>

      {/* ─── LINHA 2 — Resumo do mês ─── */}
      <div className={styles.resumoGrid}>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>A Pagar</span>
          <span className={`${styles.statValor} ${styles.statNegativo}`}>{moeda(aPagar)}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>A Receber</span>
          <span className={`${styles.statValor} ${styles.statPositivo}`}>{moeda(aReceber)}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Já Pago</span>
          <span className={styles.statValor}>{moeda(jaPago)}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Já Recebido</span>
          <span className={`${styles.statValor} ${styles.statPositivo}`}>{moeda(jaRecebido)}</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statLabel}>Projeção Final</span>
          <span className={`${styles.statValor} ${projecaoFinal < 0 ? styles.statNegativo : ""}`}>
            {moeda(projecaoFinal)}
          </span>
        </div>
      </div>

      {/* ─── LINHA 3 — Alertas (condicional) ─── */}
      {(atrasados.length > 0 || em7Dias.length > 0) && (
        <div className={styles.alertasRow}>
          {atrasados.length > 0 && (
            <div className={`${styles.alertaCard} ${styles.alertaPerigo}`}>
              <span className={styles.alertaTexto}>
                <strong>{atrasados.length}</strong>{" "}
                lançamento{atrasados.length > 1 ? "s" : ""} atrasado{atrasados.length > 1 ? "s" : ""}
                {" — "}
                <span className={styles.alertaValor}>{moeda(totalAtrasado)}</span>
              </span>
              <button
                className={styles.btnAlertaLink}
                onClick={() => navigate("/financeiro/fluxo-caixa")}
              >
                Ver todos →
              </button>
            </div>
          )}
          {em7Dias.length > 0 && (
            <div className={`${styles.alertaCard} ${styles.alertaAviso}`}>
              <span className={styles.alertaTexto}>
                <strong>{em7Dias.length}</strong>{" "}
                vencem nos próximos 7 dias
                {" — "}
                <span className={styles.alertaValor}>{moeda(totalEm7)}</span>
              </span>
              <button
                className={styles.btnAlertaLink}
                onClick={() => navigate("/financeiro/fluxo-caixa")}
              >
                Ver todos →
              </button>
            </div>
          )}
        </div>
      )}

      {/* ─── LINHA 4 — Gráfico + Cascata ─── */}
      <div className={styles.bottomGrid}>

        {/* Gráfico: últimos 5 meses */}
        <div className={styles.graficoCard}>
          <h3 className={styles.graficoTitulo}>
            Receita × Despesa × Lucro — últimos 5 meses
          </h3>
          {historicoChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={230}>
              <ComposedChart data={historicoChart} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="nome" tick={{ fontSize: 11, fill: "#AEAEB2" }} />
                <YAxis
                  tick={{ fontSize: 11, fill: "#AEAEB2" }}
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  formatter={(v, name) => [moeda(v), name]}
                  contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid rgba(0,0,0,0.08)" }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="Receita" fill="#C7C7CC" radius={[3, 3, 0, 0]} />
                <Bar dataKey="Despesa" fill="#3A3A3C" radius={[3, 3, 0, 0]} />
                <Line
                  type="monotone"
                  dataKey="Lucro"
                  stroke="#1D1D1F"
                  strokeWidth={2}
                  dot={{ fill: "#1D1D1F", r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <p className={styles.loading}>Sem dados históricos disponíveis.</p>
          )}
        </div>

        {/* Cascata: próximos 3 meses */}
        <div className={styles.cascataCard}>
          <h3 className={styles.cascataCardTitulo}>Projeção — próximos 3 meses</h3>
          <div className={styles.cascataList}>
            {cascataMeses.length === 0 ? (
              <p className={styles.semDados}>Sem dados de projeção disponíveis.</p>
            ) : (
              cascataMeses.map((cm, idx) => (
                <div key={idx} className={styles.cascataMes}>
                  <p className={styles.cascataMesNome}>
                    {MESES[cm.mes - 1]} {cm.ano}
                  </p>

                  <div className={styles.cascataLinhas}>
                    <div className={styles.cascataLinha}>
                      <span>Saldo inicial</span>
                      <span>{moeda(cm.saldoInicial)}</span>
                    </div>
                    <div className={styles.cascataLinha}>
                      <span>+ A receber</span>
                      <span>{moeda(cm.aReceber)}</span>
                    </div>
                    <div className={styles.cascataLinha}>
                      <span>− A pagar</span>
                      <span>{moeda(cm.aPagar)}</span>
                    </div>
                  </div>

                  <hr className={styles.cascataDivisor} />

                  <div className={styles.cascataSaldoFinal}>
                    <span>Saldo projetado</span>
                    <span>{moeda(cm.saldoProj)}</span>
                  </div>

                  <div className={`${styles.cascataRetirada} ${SEMAFORO_CLS[cm.semaforo]}`}>
                    <div className={`${styles.semaforoDot} ${DOT_CLS[cm.semaforo]}`} />
                    <div>
                      <div className={styles.cascataRetiradaValor}>
                        Retirada sugerida: {moeda(cm.retirada)}
                      </div>
                      <div className={styles.cascataReservaTip}>
                        reserva mínima: {moeda(reservaMinima)}
                        {!temReservaConfig && (
                          <>
                            {" · "}
                            <button
                              className={styles.configLink}
                              onClick={() => navigate("/configuracoes")}
                            >
                              Configurar reserva
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* ─── LINHA 5 — Meta do mês ─── */}
      <div className={styles.metaCard}>
        {metaValor > 0 ? (
          <>
            <div className={styles.metaHeader}>
              <h3 className={styles.metaTitulo}>
                Meta de faturamento — {MESES[mes - 1]}
              </h3>
              <span className={styles.metaPercent}>{metaPct.toFixed(0)}%</span>
            </div>
            <div className={styles.metaBarWrap}>
              <div
                className={`${styles.metaBarFill} ${metaPct >= 100 ? styles.metaBarFillBoa : ""}`}
                style={{ width: `${metaPct}%` }}
              />
            </div>
            <p className={styles.metaValores}>
              {moeda(metaRealiz)} de {moeda(metaValor)}
            </p>
          </>
        ) : (
          <div className={styles.metaVazia}>
            <span>Nenhuma meta definida para {MESES[mes - 1]}.</span>
            <button
              className={styles.btnAlertaLink}
              onClick={() => { setMetaInput(""); setModalMeta(true); }}
            >
              Definir meta do mês →
            </button>
          </div>
        )}
      </div>

      {/* ─── Modal: definir meta ─── */}
      {modalMeta && (
        <div className={styles.overlay} onClick={() => setModalMeta(false)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>
              Meta de faturamento — {MESES[mes - 1]} {ano}
            </h2>
            <label className={styles.fieldLabel}>
              Valor da meta (R$)
              <input
                type="number"
                min="0"
                step="100"
                className={styles.fieldInput}
                value={metaInput}
                onChange={(e) => setMetaInput(e.target.value)}
                placeholder="Ex: 33000"
                autoFocus
              />
            </label>
            <div className={styles.modalActions}>
              <button className={styles.btnSecundario} onClick={() => setModalMeta(false)}>
                Cancelar
              </button>
              <button
                className={styles.btnPrimario}
                onClick={handleSalvarMeta}
                disabled={savingMeta}
              >
                {savingMeta ? "Salvando…" : "Salvar Meta"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
