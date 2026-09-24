import { useState, useEffect, useCallback } from "react";
import {
  BarChart, Bar, PieChart, Pie, Cell, Line, Area, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { getMetricasCompras, getMetricasResultado } from "../../api/financeiro";
import { getMetricasPedidosVenda } from "../../api/pedidos";
import styles from "./PainelFinanceiro.module.css";

/* ── Helpers ── */
const MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const moedaCompacta = (v) => {
  const n = Number(v) || 0;
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(0)}k`;
  return n.toFixed(0);
};

const pad = (n) => String(n).padStart(2, "0");
const isoDate = (dt) => `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`;

const truncar = (str, max) => {
  if (!str) return "—";
  return str.length > max ? `${str.slice(0, max - 1)}…` : str;
};

/* Cores fixas (paleta já usada no projeto: escala de cinzas + cor primária
   em destaque — mesmo padrão de ProjecaoPage.jsx). */
const GRAYSCALE = ["#1D1D1F", "#6E6E73", "#AEAEB2", "#C7C7CC", "#D1D1D6", "#E5E5EA"];
const COR_RECEITA = "#16a34a";
const COR_DESPESA = "#dc2626";

function corPizza(idx, corPrimaria) {
  // Maior fatia (idx 0, já vem ordenada desc do backend) em destaque.
  if (idx === 0) return corPrimaria;
  return GRAYSCALE[Math.min(idx, GRAYSCALE.length - 1)];
}

/* ── Períodos ── */
const PERIODOS = [
  { key: "hoje", label: "Hoje" },
  { key: "semana", label: "Esta semana" },
  { key: "mes", label: "Este mês" },
  { key: "ano", label: "Este ano" },
  { key: "personalizado", label: "Personalizado" },
];

function calcularPeriodo(periodo) {
  const hoje = new Date();
  const y = hoje.getFullYear(), m = hoje.getMonth(), d = hoje.getDate();

  if (periodo === "hoje") {
    const dt = new Date(y, m, d);
    return { inicio: isoDate(dt), fim: isoDate(dt) };
  }
  if (periodo === "semana") {
    const diaSemana = hoje.getDay(); // 0 = domingo
    const inicio = new Date(y, m, d - diaSemana);
    return { inicio: isoDate(inicio), fim: isoDate(new Date(y, m, d)) };
  }
  if (periodo === "ano") {
    return { inicio: `${y}-01-01`, fim: isoDate(new Date(y, m, d)) };
  }
  // "mes" (padrão)
  return { inicio: isoDate(new Date(y, m, 1)), fim: isoDate(new Date(y, m, d)) };
}

/* Janela imediatamente anterior, com a mesma duração — usada para calcular
   a variação percentual do faturamento do período. */
function periodoAnterior(inicio, fim) {
  const [iy, im, id] = inicio.split("-").map(Number);
  const [fy, fm, fd] = fim.split("-").map(Number);
  const dtInicio = new Date(iy, im - 1, id);
  const dtFim = new Date(fy, fm - 1, fd);
  const diffDias = Math.round((dtFim - dtInicio) / 86400000) + 1;

  const novoFim = new Date(dtInicio);
  novoFim.setDate(novoFim.getDate() - 1);
  const novoInicio = new Date(novoFim);
  novoInicio.setDate(novoInicio.getDate() - diffDias + 1);
  return { inicio: isoDate(novoInicio), fim: isoDate(novoFim) };
}

/* ── Componente ── */
export default function PainelFinanceiro() {
  const corPrimaria = getComputedStyle(document.documentElement)
    .getPropertyValue('--color-primary').trim() || '#2596be';
  const CORES_FORNECEDOR = [corPrimaria, "#1D1D1F", "#6E6E73", "#AEAEB2", "#C7C7CC"];

  const [periodo, setPeriodo] = useState("mes");
  const [customInicio, setCustomInicio] = useState("");
  const [customFim, setCustomFim] = useState("");

  const [loading, setLoading] = useState(false);
  const [metricasVendas, setMetricasVendas] = useState(null);
  const [faturamentoAnterior, setFaturamentoAnterior] = useState(0);
  const [metricasCompras, setMetricasCompras] = useState(null);
  const [metricasResultado, setMetricasResultado] = useState(null);

  const rangeAtual = periodo === "personalizado"
    ? { inicio: customInicio, fim: customFim }
    : calcularPeriodo(periodo);

  const carregarDados = useCallback(async () => {
    if (!rangeAtual.inicio || !rangeAtual.fim) return;
    setLoading(true);
    try {
      const anterior = periodoAnterior(rangeAtual.inicio, rangeAtual.fim);
      const [vendasAtual, vendasAnterior, compras, resultado] = await Promise.all([
        getMetricasPedidosVenda(rangeAtual.inicio, rangeAtual.fim),
        getMetricasPedidosVenda(anterior.inicio, anterior.fim),
        getMetricasCompras(rangeAtual.inicio, rangeAtual.fim),
        getMetricasResultado(),
      ]);
      setMetricasVendas(vendasAtual || null);
      setFaturamentoAnterior(vendasAnterior?.total_faturado || 0);
      setMetricasCompras(compras || null);
      setMetricasResultado(resultado || null);
    } catch {
      setMetricasVendas(null);
      setMetricasCompras(null);
      setMetricasResultado(null);
    }
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rangeAtual.inicio, rangeAtual.fim]);

  useEffect(() => { carregarDados(); }, [carregarDados]);

  /* ── KPIs ── */
  const totalFaturado = metricasVendas?.total_faturado || 0;
  const totalPedidos = metricasVendas?.total_pedidos || 0;
  const ticketMedio = metricasVendas?.ticket_medio || 0;
  const totalComprasPeriodo = metricasCompras?.total_compras || 0;

  const variacaoFaturamento = faturamentoAnterior > 0
    ? ((totalFaturado - faturamentoAnterior) / faturamentoAnterior) * 100
    : (totalFaturado > 0 ? 100 : 0);

  /* ── Dados dos gráficos ── */
  const faturamentoPorMes = (metricasVendas?.faturamento_por_mes || []).map((f) => ({
    nome: `${MESES_ABREV[f.mes - 1]}/${String(f.ano).slice(2)}`,
    total: f.total,
  }));

  const comprasPorFornecedor = metricasCompras?.compras_por_fornecedor || [];

  const topClientes = (metricasVendas?.top_clientes || []).map((c) => ({
    nome: truncar(c.cliente, 20),
    nomeCompleto: c.cliente,
    valor: c.total_valor,
  }));

  const resultadoPorMes = (metricasResultado?.resultado_por_mes || []).map((r) => ({
    nome: r.label,
    Receita: r.receita,
    Despesa: r.despesa,
    Lucro: r.lucro,
  }));

  const fornecedoresVolume = (metricasCompras?.volume_tecido_por_fornecedor || []).map((f) => f.fornecedor);
  const volumePorFornecedorMes = metricasCompras?.volume_tecido_por_fornecedor_mes || [];

  /* ── Render ── */
  return (
    <div className={styles.pagina}>
      <h1 className={styles.pageTitle}>Painel Financeiro</h1>

      {/* ─── Header + filtro de período ─── */}
      <div className={styles.pageHeader}>
        <div className={styles.filtroPeriodo}>
          {PERIODOS.map(({ key, label }) => (
            <button
              key={key}
              className={`${styles.filtroBtn} ${periodo === key ? styles.filtroBtnAtivo : ""}`}
              onClick={() => setPeriodo(key)}
            >
              {label}
            </button>
          ))}
        </div>
        {periodo === "personalizado" && (
          <div className={styles.filtroCustom}>
            <input
              type="date"
              className={styles.fieldInput}
              value={customInicio}
              onChange={(e) => setCustomInicio(e.target.value)}
            />
            <span className={styles.filtroCustomSep}>até</span>
            <input
              type="date"
              className={styles.fieldInput}
              value={customFim}
              onChange={(e) => setCustomFim(e.target.value)}
            />
          </div>
        )}
      </div>

      {loading && <p className={styles.loading}>Carregando…</p>}

      {/* ─── SEÇÃO 1 — KPIs ─── */}
      <div className={styles.kpiGrid}>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Faturamento do período</span>
          <span className={styles.kpiValor}>{moeda(totalFaturado)}</span>
          <span className={variacaoFaturamento >= 0 ? styles.kpiVariacaoPos : styles.kpiVariacaoNeg}>
            {variacaoFaturamento >= 0 ? "+" : ""}{variacaoFaturamento.toFixed(1)}% vs. período anterior
          </span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Total de pedidos</span>
          <span className={styles.kpiValor}>{totalPedidos}</span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Ticket médio</span>
          <span className={styles.kpiValor}>{moeda(ticketMedio)}</span>
        </div>
        <div className={styles.kpiCard}>
          <span className={styles.kpiLabel}>Total em compras</span>
          <span className={styles.kpiValor}>{moeda(totalComprasPeriodo)}</span>
        </div>
      </div>

      {/* ─── SEÇÃO 2 — Faturamento por mês ─── */}
      <div className={styles.secao}>
        <h2 className={styles.secaoTitulo}>Faturamento por mês — últimos 12 meses</h2>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={faturamentoPorMes} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="nome" tick={{ fontSize: 11, fill: "#AEAEB2" }} />
            <YAxis tick={{ fontSize: 11, fill: "#AEAEB2" }} tickFormatter={moedaCompacta} />
            <Tooltip
              formatter={(v) => [moeda(v), "Faturamento"]}
              contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid rgba(0,0,0,0.08)" }}
            />
            <Bar dataKey="total" fill={corPrimaria} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* ─── SEÇÃO 3 — Compras por fornecedor + Top clientes ─── */}
      <div className={styles.duasColunas}>
        <div className={styles.secao}>
          <h2 className={styles.secaoTitulo}>Compras por fornecedor</h2>
          {comprasPorFornecedor.length === 0 ? (
            <p className={styles.semDados}>Sem dados de compras no período.</p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={comprasPorFornecedor}
                    dataKey="total"
                    nameKey="fornecedor"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={false}
                  >
                    {comprasPorFornecedor.map((_, i) => (
                      <Cell key={i} fill={corPizza(i, corPrimaria)} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => moeda(v)} />
                </PieChart>
              </ResponsiveContainer>
              <div className={styles.legendaPizza}>
                {comprasPorFornecedor.map((f, i) => (
                  <div key={f.fornecedor} className={styles.legendaItem}>
                    <span
                      className={styles.legendaDot}
                      style={{ background: corPizza(i, corPrimaria) }}
                    />
                    <span className={styles.legendaNome}>{f.fornecedor}</span>
                    <span className={styles.legendaPct}>{(f.percentual || 0).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className={styles.secao}>
          <h2 className={styles.secaoTitulo}>Top 5 clientes — maior faturamento</h2>
          {topClientes.length === 0 ? (
            <p className={styles.semDados}>Sem dados de vendas no período.</p>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={topClientes}
                layout="vertical"
                margin={{ top: 4, right: 24, left: 8, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#AEAEB2" }} tickFormatter={moedaCompacta} />
                <YAxis type="category" dataKey="nome" width={130} tick={{ fontSize: 11, fill: "#6E6E73" }} />
                <Tooltip
                  formatter={(v) => [moeda(v), "Faturamento"]}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.nomeCompleto || ""}
                />
                <Bar dataKey="valor" fill={corPrimaria} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ─── SEÇÃO 4 — Receita × Despesa × Lucro ─── */}
      <div className={styles.secao}>
        <h2 className={styles.secaoTitulo}>Receita × Despesa × Lucro — últimos 12 meses</h2>
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={resultadoPorMes} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
            <XAxis dataKey="nome" tick={{ fontSize: 11, fill: "#AEAEB2" }} />
            <YAxis tick={{ fontSize: 11, fill: "#AEAEB2" }} tickFormatter={moedaCompacta} />
            <Tooltip
              formatter={(v, name) => [moeda(v), name]}
              contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid rgba(0,0,0,0.08)" }}
            />
            <Legend verticalAlign="top" wrapperStyle={{ fontSize: 12 }} />
            <Area
              type="monotone"
              dataKey="Lucro"
              stroke={corPrimaria}
              strokeWidth={2}
              fill={corPrimaria}
              fillOpacity={0.1}
              dot={{ fill: corPrimaria, r: 3 }}
            />
            <Line type="monotone" dataKey="Receita" stroke={COR_RECEITA} strokeWidth={2} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="Despesa" stroke={COR_DESPESA} strokeWidth={2} dot={{ r: 3 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* ─── SEÇÃO 5 — Volume de tecido por fornecedor ─── */}
      <div className={styles.secao}>
        <h2 className={styles.secaoTitulo}>Volume de compras de tecido por fornecedor</h2>
        {fornecedoresVolume.length === 0 ? (
          <p className={styles.semDados}>Sem dados de compras disponíveis.</p>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={volumePorFornecedorMes} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#AEAEB2" }} />
              <YAxis tick={{ fontSize: 11, fill: "#AEAEB2" }} tickFormatter={moedaCompacta} />
              <Tooltip
                formatter={(v, name) => [moeda(v), name]}
                contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid rgba(0,0,0,0.08)" }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {fornecedoresVolume.map((nome, i) => (
                <Bar key={nome} dataKey={nome} fill={CORES_FORNECEDOR[i % CORES_FORNECEDOR.length]} radius={[3, 3, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
