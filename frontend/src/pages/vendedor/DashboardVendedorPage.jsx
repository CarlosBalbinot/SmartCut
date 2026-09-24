import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import styles from "./DashboardVendedorPage.module.css";
import { vendedorFetch, vendedorFetchRaw, logoutVendedor } from "../../services/vendedorApi";

const fmt = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v ?? 0);

const STATUS_COLORS = {
  aprovado: { bg: "#E8F8E8", color: "#1A7F37" },
  pendente: { bg: "#FFF8E8", color: "#B45309" },
  cancelado: { bg: "#FFF0EF", color: "#FF3B30" },
  enviado: { bg: "#E8F4FD", color: "#0071E3" },
  faturado: { bg: "#F0EDFF", color: "#6940D4" },
};

const IconHome = () => (
  <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
    <path
      d="M3 9.5L11 3L19 9.5V19H14V14H8V19H3V9.5Z"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
  </svg>
);
const IconBook = () => (
  <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
    <path
      d="M4 4h6a2 2 0 0 1 2 2v12a2 2 0 0 0-2-2H4V4z"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
    <path
      d="M18 4h-6a2 2 0 0 0-2 2v12a2 2 0 0 1 2-2h6V4z"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
  </svg>
);
const IconDoc = () => (
  <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
    <rect x="4" y="2" width="14" height="18" rx="2" stroke="currentColor" strokeWidth="1.8" />
    <path d="M8 8h6M8 12h6M8 16h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
);
const IconUsers = () => (
  <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
    <circle cx="8" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.8" />
    <path
      d="M2 18c0-3.3 2.7-6 6-6s6 2.7 6 6"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
    <path
      d="M16 6c1.7 0 3 1.3 3 3s-1.3 3-3 3"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
    <path
      d="M20 18c0-2.8-1.8-5.2-4.3-6.1"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    />
  </svg>
);

function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const items = [
    { label: "Dashboard", path: "/vendedor/dashboard", Icon: IconHome },
    { label: "Catálogos", path: "/vendedor/catalogos", Icon: IconBook },
    { label: "Pedidos", path: "/vendedor/pedidos", Icon: IconDoc },
    { label: "Leads", path: "/vendedor/leads", Icon: IconUsers },
  ];
  return (
    <nav className={styles.bottomNav}>
      {items.map(({ label, path, Icon }) => (
        <button
          key={path}
          className={location.pathname === path ? styles.navItemActive : styles.navItem}
          onClick={() => navigate(path)}
        >
          <Icon />
          <span>{label}</span>
        </button>
      ))}
    </nav>
  );
}

export default function DashboardVendedorPage() {
  const navigate = useNavigate();
  const [nome, setNome] = useState("Vendedor");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");

  function logout() {
    // Item 1.4: revoga o token no backend (jti) e limpa a sessão local
    // (safeStorage no Electron / cookie no navegador).
    logoutVendedor().finally(() => navigate("/vendedor/login"));
  }

  useEffect(() => {
    vendedorFetch("/vendedor/perfil")
      .then((d) => {
        if (d?.nome) setNome(d.nome);
      })
      .catch(() => {});

    vendedorFetchRaw("/vendedor/dashboard")
      .then(setData)
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, []);

  const now = new Date();
  const mesNomeBruto = now.toLocaleString("pt-BR", { month: "long" });
  const mesLabel =
    mesNomeBruto.charAt(0).toUpperCase() + mesNomeBruto.slice(1) + " " + now.getFullYear();

  const fat = data?.total_vendido_mes ?? 0;
  const meta = data?.meta?.meta_ativacao ?? 0;
  const bonusLogistica = data?.meta?.bonus_logistica ?? 0;
  const novosClientes = data?.novos_clientes_mes ?? 0;
  const metaNovosClientes = data?.meta?.meta_novos_clientes ?? 5;
  const bonusExpansao = data?.meta?.bonus_expansao ?? 0;
  const bonusLogisticaAtingido = data?.bonus_logistica_atingido ?? false;
  const comissaoMes = data?.comissao_mes ?? 0;
  const ultimos3 = data?.ultimos_3_pedidos ?? [];

  const progresso = meta > 0 ? Math.min(100, (fat / meta) * 100) : 0;
  const falta = Math.max(0, meta - fat);
  const clientesNoIntervalo = metaNovosClientes > 0 ? novosClientes % metaNovosClientes : 0;

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <p className={styles.saudacao}>Olá, {nome}! 👋</p>
          <p className={styles.subtitulo}>{mesLabel}</p>
        </div>
        <button className={styles.logoutBtn} onClick={logout}>
          Sair
        </button>
      </header>

      <div className={styles.content}>
        {loading && <p className={styles.info}>Carregando…</p>}
        {erro && <p className={styles.erro}>{erro}</p>}

        {!loading && !erro && (
          <>
            <div
              className={`${styles.card} ${bonusLogisticaAtingido ? styles.cardMetaSuccess : styles.cardMeta}`}
            >
              <p className={styles.cardLabel}>🎯 Meta do Mês</p>
              <p className={styles.cardValueLarge}>{fmt(fat)}</p>
              <div className={styles.progressBar}>
                <div className={styles.progressFill} style={{ width: `${progresso}%` }} />
              </div>
              <p className={styles.progressMeta}>
                {progresso.toFixed(0)}% da meta de {fmt(meta)}
              </p>
              {bonusLogisticaAtingido ? (
                <p className={styles.successMsg}>✅ Meta atingida! Bônus garantido 🎉</p>
              ) : (
                <p className={styles.warningMsg}>
                  Falta {fmt(falta)} para garantir {fmt(bonusLogistica)}
                </p>
              )}
            </div>

            <div className={styles.bonusRow}>
              <div className={styles.bonusCard}>
                <span className={styles.bonusIcon}>🚗</span>
                <p className={styles.bonusTitle}>Bônus Logística</p>
                {bonusLogisticaAtingido ? (
                  <p className={styles.bonusStatusOk}>Garantido ✓</p>
                ) : (
                  <p className={styles.bonusStatusPending}>{fmt(falta)} faltando</p>
                )}
                <p className={styles.bonusValue}>{fmt(bonusLogistica)}</p>
              </div>
              <div className={styles.bonusCard}>
                <span className={styles.bonusIcon}>🌟</span>
                <p className={styles.bonusTitle}>Novos Clientes</p>
                <p className={styles.bonusProgress}>
                  {clientesNoIntervalo} de {metaNovosClientes} para próx. bônus
                </p>
                <p className={styles.bonusValue}>{fmt(bonusExpansao)}</p>
              </div>
            </div>

            <div className={styles.card}>
              <p className={styles.cardLabel}>💰 Comissão Acumulada</p>
              <p className={styles.cardValueLarge}>{fmt(comissaoMes)}</p>
            </div>

            {ultimos3.length > 0 && (
              <div className={styles.section}>
                <p className={styles.sectionTitle}>Últimos pedidos</p>
                {ultimos3.map((p) => {
                  const sc = STATUS_COLORS[p.status] || { bg: "#F5F5F7", color: "#6E6E73" };
                  return (
                    <div key={p.numero} className={styles.pedidoCard}>
                      <div className={styles.pedidoInfo}>
                        <span className={styles.pedidoNum}>#{p.numero}</span>
                        <span className={styles.pedidoCliente}>{p.cliente}</span>
                      </div>
                      <div className={styles.pedidoRight}>
                        <span className={styles.pedidoTotal}>{fmt(p.total)}</span>
                        <span
                          className={styles.badge}
                          style={{ background: sc.bg, color: sc.color }}
                        >
                          {p.status}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      <BottomNav />
    </div>
  );
}
