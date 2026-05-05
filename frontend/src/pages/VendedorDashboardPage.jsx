import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line,
} from "recharts";
import { vendedoresApi, pedidosVendaApi } from "../services/api";
import styles from "./VendedorDashboardPage.module.css";

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const dataLocal = (iso) =>
  iso ? new Date(iso).toLocaleDateString("pt-BR") : "—";

export default function VendedorDashboardPage() {
  const { id }          = useParams();
  const navigate        = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [editModal, setEditModal] = useState(null);
  const [saving, setSaving]       = useState(false);
  const [erro, setErro]           = useState(null);

  const carregar = async () => {
    setLoading(true);
    try {
      const d = await vendedoresApi.getDashboard(id);
      setData(d);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { carregar(); }, [id]);

  const marcarPago = async (pedidoId) => {
    try {
      await pedidosVendaApi.update(pedidoId, { comissao_paga: true });
      await carregar();
    } catch {}
  };

  const handleSalvarVendedor = async () => {
    if (!editModal.nome?.trim()) { setErro("Nome é obrigatório."); return; }
    setSaving(true); setErro(null);
    try {
      await vendedoresApi.update(id, {
        nome:      editModal.nome.trim(),
        telefone:  editModal.telefone.trim(),
        email:     editModal.email.trim(),
      });
      await carregar();
      setEditModal(null);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className={styles.page}><p className={styles.loading}>Carregando…</p></div>;
  }
  if (!data) {
    return (
      <div className={styles.page}>
        <button className={styles.btnBack} onClick={() => navigate("/vendedores")}>← Vendedores</button>
        <p className={styles.empty}>Vendedor não encontrado.</p>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.topRow}>
        <div>
          <button className={styles.btnBack} onClick={() => navigate("/vendedores")}>
            ← Vendedores
          </button>
          <h1 className={styles.title}>{data.nome}</h1>
          <div className={styles.contato}>
            {data.telefone && <span>{data.telefone}</span>}
            {data.email    && <span>{data.email}</span>}
          </div>
        </div>
        <button
          className={styles.btnSecondary}
          onClick={() =>
            setEditModal({ nome: data.nome, telefone: data.telefone || "", email: data.email || "" })
          }
        >
          Editar
        </button>
      </div>

      {/* Stat cards */}
      <div className={styles.statsGrid}>
        <div className={styles.statCard}>
          <p className={styles.statLabel}>Total vendido no mês</p>
          <p className={styles.statValue}>{moeda(data.total_vendido_mes)}</p>
        </div>
        <div className={styles.statCard}>
          <p className={styles.statLabel}>Nº de pedidos</p>
          <p className={styles.statValue}>{data.num_pedidos ?? 0}</p>
        </div>
        <div className={styles.statCard}>
          <p className={styles.statLabel}>Comissão a receber</p>
          <p className={styles.statValue}>{moeda(data.comissao_receber)}</p>
        </div>
        <div className={styles.statCard}>
          <p className={styles.statLabel}>Ticket médio</p>
          <p className={styles.statValue}>{moeda(data.ticket_medio)}</p>
        </div>
      </div>

      {/* Charts */}
      <div className={styles.chartsRow}>
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>Vendas por mês (R$)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={data.vendas_por_mes || []}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--sc-border)" />
              <XAxis
                dataKey="mes"
                tick={{ fontSize: 11, fill: "var(--sc-text-secondary)" }}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "var(--sc-text-secondary)" }}
                tickFormatter={(v) => `R$${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip formatter={(v) => [moeda(v), "Total"]} />
              <Bar dataKey="total" fill="var(--sc-action)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>Pedidos por mês</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart
              data={data.pedidos_por_mes || []}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--sc-border)" />
              <XAxis
                dataKey="mes"
                tick={{ fontSize: 11, fill: "var(--sc-text-secondary)" }}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11, fill: "var(--sc-text-secondary)" }}
              />
              <Tooltip formatter={(v) => [v, "Pedidos"]} />
              <Line
                type="monotone"
                dataKey="total"
                stroke="var(--sc-action)"
                strokeWidth={2}
                dot={{ r: 4, fill: "var(--sc-action)" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Orders table */}
      <div className={styles.card}>
        <h3 className={styles.sectionTitle}>Pedidos do mês</h3>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Nº</th>
              <th>Data</th>
              <th>Cliente</th>
              <th>Total</th>
              <th>Comissão</th>
              <th>Status comissão</th>
            </tr>
          </thead>
          <tbody>
            {(data.pedidos_mes || []).map((p) => (
              <tr key={p.id}>
                <td><code className={styles.num}>{p.numero}</code></td>
                <td>{dataLocal(p.data)}</td>
                <td>{p.cliente || "—"}</td>
                <td>{moeda(p.total)}</td>
                <td>{moeda(p.comissao)}</td>
                <td>
                  {p.comissao_paga ? (
                    <span className={styles.badgePago}>Pago</span>
                  ) : (
                    <span className={styles.badgeAPagar}>
                      A pagar
                      <button
                        className={styles.btnMarcar}
                        onClick={() => marcarPago(p.id)}
                      >
                        Marcar pago
                      </button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {(data.pedidos_mes || []).length === 0 && (
              <tr>
                <td colSpan={6} className={styles.empty}>Sem pedidos neste mês.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Edit modal */}
      {editModal && (
        <div className={styles.overlay} onClick={() => { setEditModal(null); setErro(null); }}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>Editar Vendedor</h2>

            {[
              { key: "nome",     label: "Nome *"   },
              { key: "telefone", label: "Telefone" },
              { key: "email",    label: "E-mail"   },
            ].map(({ key, label }) => (
              <label key={key} className={styles.field}>
                <span>{label}</span>
                <input
                  className={styles.input}
                  value={editModal[key]}
                  onChange={(e) => setEditModal((m) => ({ ...m, [key]: e.target.value }))}
                />
              </label>
            ))}

            {erro && <p className={styles.erro}>{erro}</p>}

            <div className={styles.modalActions}>
              <button
                className={styles.btnSecondary}
                onClick={() => { setEditModal(null); setErro(null); }}
              >
                Cancelar
              </button>
              <button className={styles.btnPrimary} onClick={handleSalvarVendedor} disabled={saving}>
                {saving ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
