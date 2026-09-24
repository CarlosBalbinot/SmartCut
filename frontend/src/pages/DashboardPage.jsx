import { useState, useEffect, useCallback } from "react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Legend,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import { getDashboardResumo } from "../api/dashboard";
import { useAuth } from "../auth/useAuth";
import styles from "./DashboardPage.module.css";

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

function saudacaoPorHora(hora) {
  if (hora < 12) return "Bom dia";
  if (hora < 18) return "Boa tarde";
  return "Boa noite";
}

const CORES_FORNECEDOR = [
  "#2596be",
  "#6366f1",
  "#f59e0b",
  "#22c55e",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#f97316",
  "#64748b",
];

export default function DashboardPage() {
  const { usuario } = useAuth();
  const [agora, setAgora] = useState(new Date());
  const [dados, setDados] = useState(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(false);

  useEffect(() => {
    const id = setInterval(() => setAgora(new Date()), 60000);
    return () => clearInterval(id);
  }, []);

  const carregar = useCallback(() => {
    setLoading(true);
    setErro(false);
    getDashboardResumo()
      .then(setDados)
      .catch(() => setErro(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  if (erro) {
    return (
      <div className={styles.estadoErro}>
        <p>Não foi possível carregar o dashboard</p>
        <button className={styles.btnTentarNovamente} onClick={carregar}>
          Tentar novamente
        </button>
      </div>
    );
  }

  if (loading || !dados) {
    return <DashboardSkeleton />;
  }

  const saudacao = saudacaoPorHora(agora.getHours());
  const primeiroNome = (usuario?.nome_completo || usuario?.username || "").split(" ")[0];

  const { pedidos, frete, evolucao_semanal, compras_fornecedor, top5_clientes } = dados;
  const totalCompras = compras_fornecedor.reduce((s, c) => s + c.valor, 0);

  return (
    <div className={styles.page}>
      <div className={styles.saudacao}>
        <h1 className={styles.saudacaoTitulo}>
          {saudacao}, {primeiroNome}
        </h1>
        <p className={styles.saudacaoPeriodo}>{dados.periodo}</p>
      </div>

      {/* LINHA 1 — cards de métricas */}
      <div className={styles.metricasGrid}>
        <div className={styles.metricaCard}>
          <span className={styles.metricaLabel}>Pedidos no Mês</span>
          <span className={styles.metricaValor}>{pedidos.total_mes}</span>
        </div>
        <div className={styles.metricaCard}>
          <span className={styles.metricaLabel}>Notas Geradas</span>
          <span className={styles.metricaValor}>{pedidos.notas_geradas}</span>
          <span className={styles.metricaSub}>{moeda(pedidos.valor_notas)} total</span>
        </div>
        <div className={styles.metricaCard}>
          <span className={styles.metricaLabel}>Frete a Pagar</span>
          <span className={styles.metricaValor}>{moeda(frete.total_pagar_mes)}</span>
          <span className={styles.metricaSub}>frete CIF do mês</span>
        </div>
      </div>

      {/* LINHA 2 — pedidos por semana + compras por fornecedor */}
      <div className={styles.graficosGrid}>
        <div className={styles.painelEsquerdo}>
          <h2 className={styles.painelTitulo}>Pedidos por Semana</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={evolucao_semanal} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
              <CartesianGrid vertical={false} stroke="var(--sc-border)" />
              <XAxis dataKey="semana" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip formatter={(v) => [v, "pedidos"]} labelFormatter={(l) => l} />
              <Bar dataKey="pedidos" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className={styles.painelDireito}>
          <h2 className={styles.painelTitulo}>Compras por Fornecedor</h2>
          {compras_fornecedor.length === 0 ? (
            <div className={styles.semDadosGrafico}>
              <p className={styles.semDados}>Sem compras no período</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={compras_fornecedor}
                  dataKey="valor"
                  nameKey="nome"
                  cx="50%"
                  cy="45%"
                  outerRadius={65}
                  label={false}
                >
                  {compras_fornecedor.map((c, i) => (
                    <Cell key={c.nome} fill={CORES_FORNECEDOR[i % CORES_FORNECEDOR.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v, _name, item) => {
                    const pct = totalCompras > 0 ? ((v / totalCompras) * 100).toFixed(0) : 0;
                    return [`${moeda(v)} (${pct}%)`, item?.payload?.nome];
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} layout="horizontal" />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* LINHA 3 — top 5 clientes */}
      <div className={styles.tabelaCard}>
        <h2 className={styles.painelTitulo}>Top 5 Clientes — Últimos 3 Meses</h2>
        {top5_clientes.length === 0 ? (
          <p className={styles.semDados}>Nenhum pedido nos últimos 3 meses</p>
        ) : (
          <table className={styles.tabela}>
            <thead>
              <tr>
                <th className={styles.colPos}>#</th>
                <th>Cliente</th>
                <th className={styles.colCentro}>Pedidos</th>
                <th className={styles.colValor}>Valor Total</th>
              </tr>
            </thead>
            <tbody>
              {top5_clientes.map((c, i) => (
                <tr key={c.nome} className={i === 0 ? styles.linhaDestaque : ""}>
                  <td className={styles.colPos}>{i + 1}</td>
                  <td>{c.nome}</td>
                  <td className={styles.colCentro}>{c.qtd_pedidos}</td>
                  <td className={styles.colValor}>{moeda(c.valor_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className={styles.page}>
      <div className={styles.saudacao}>
        <div className={`${styles.skeleton} ${styles.skeletonTitulo}`} />
        <div className={`${styles.skeleton} ${styles.skeletonSubtitulo}`} />
      </div>
      <div className={styles.metricasGrid}>
        {[0, 1, 2].map((i) => (
          <div key={i} className={`${styles.skeleton} ${styles.skeletonCard}`} />
        ))}
      </div>
      <div className={styles.graficosGrid}>
        <div className={`${styles.skeleton} ${styles.skeletonPainel}`} />
        <div className={`${styles.skeleton} ${styles.skeletonPainel}`} />
      </div>
      <div className={`${styles.skeleton} ${styles.skeletonTabela}`} />
    </div>
  );
}
