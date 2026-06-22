import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import styles from "./PedidosVendedorPage.module.css";

const fmt = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v ?? 0);

const fmtData = (d) =>
  d ? new Date(d).toLocaleDateString("pt-BR") : "—";

function vendedorFetch(path, options = {}) {
  const token = localStorage.getItem("smartcut_vendedor_token");
  return fetch(`/api/v1${path}`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
    ...options,
  }).then(async (res) => {
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || json.detail || `Erro ${res.status}`);
    return json.data;
  });
}

const STATUS_COLORS = {
  aprovado: { bg: "#E8F8E8", color: "#1A7F37" },
  pendente: { bg: "#FFF8E8", color: "#B45309" },
  cancelado: { bg: "#FFF0EF", color: "#FF3B30" },
  enviado: { bg: "#E8F4FD", color: "#0071E3" },
  faturado: { bg: "#F0EDFF", color: "#6940D4" },
};

const IconHome = () => (
  <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
    <path d="M3 9.5L11 3L19 9.5V19H14V14H8V19H3V9.5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/>
  </svg>
);
const IconBook = () => (
  <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
    <path d="M4 4h6a2 2 0 0 1 2 2v12a2 2 0 0 0-2-2H4V4z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/>
    <path d="M18 4h-6a2 2 0 0 0-2 2v12a2 2 0 0 1 2-2h6V4z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/>
  </svg>
);
const IconDoc = () => (
  <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
    <rect x="4" y="2" width="14" height="18" rx="2" stroke="currentColor" strokeWidth="1.8"/>
    <path d="M8 8h6M8 12h6M8 16h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
  </svg>
);
const IconUsers = () => (
  <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
    <circle cx="8" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.8"/>
    <path d="M2 18c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
    <path d="M16 6c1.7 0 3 1.3 3 3s-1.3 3-3 3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
    <path d="M20 18c0-2.8-1.8-5.2-4.3-6.1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
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

function formatMesLabel(key) {
  const [ano, mes] = key.split("-");
  const d = new Date(parseInt(ano), parseInt(mes) - 1, 1);
  const mesNome = d.toLocaleString("pt-BR", { month: "long" });
  return mesNome.charAt(0).toUpperCase() + mesNome.slice(1) + " " + ano;
}

export default function PedidosVendedorPage() {
  const [pedidos, setPedidos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [openMonths, setOpenMonths] = useState(new Set());

  useEffect(() => {
    vendedorFetch("/vendedor/pedidos")
      .then((data) => {
        const lista = data ?? [];
        setPedidos(lista);
        if (lista.length > 0) {
          const primeiroKey = lista[0].data ? lista[0].data.substring(0, 7) : "sem-data";
          setOpenMonths(new Set([primeiroKey]));
        }
      })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, []);

  function toggleMes(key) {
    setOpenMonths((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const grupos = pedidos.reduce((acc, p) => {
    const key = p.data ? p.data.substring(0, 7) : "sem-data";
    if (!acc[key]) acc[key] = [];
    acc[key].push(p);
    return acc;
  }, {});

  const mesesKeys = Object.keys(grupos).sort().reverse();

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.titulo}>Meus Pedidos</h1>
      </header>

      <div className={styles.content}>
        {loading && <p className={styles.info}>Carregando…</p>}
        {erro && <p className={styles.erro}>{erro}</p>}
        {!loading && !erro && pedidos.length === 0 && (
          <p className={styles.info}>Nenhum pedido encontrado.</p>
        )}

        {mesesKeys.map((key) => {
          const lista = grupos[key];
          const isOpen = openMonths.has(key);
          const totalMes = lista.reduce((s, p) => s + (p.total ?? 0), 0);
          const comissaoMes = lista.reduce((s, p) => s + (p.comissao ?? 0), 0);

          return (
            <div key={key} className={styles.mesBloco}>
              <button
                className={styles.mesHeader}
                onClick={() => toggleMes(key)}
              >
                <div className={styles.mesHeaderLeft}>
                  <span className={styles.mesNome}>
                    {key === "sem-data" ? "Sem data" : formatMesLabel(key)}
                  </span>
                  <span className={styles.mesBadgeCount}>{lista.length} pedido{lista.length !== 1 ? "s" : ""}</span>
                </div>
                <div className={styles.mesHeaderRight}>
                  <span className={styles.mesFaturamento}>{fmt(totalMes)}</span>
                  <span className={styles.mesComissao}>Comissão: {fmt(comissaoMes)}</span>
                </div>
                <span className={styles.mesArrow}>{isOpen ? "▲" : "▼"}</span>
              </button>

              {isOpen && (
                <div className={styles.pedidosList}>
                  {lista.map((p) => {
                    const sc = STATUS_COLORS[p.status] || { bg: "#F5F5F7", color: "#6E6E73" };
                    return (
                      <div key={p.numero ?? p.data} className={styles.pedidoItem}>
                        <div className={styles.itemTop}>
                          <div className={styles.itemLeft}>
                            <span className={styles.itemNum}>#{p.numero}</span>
                            <span className={styles.itemData}>{fmtData(p.data)}</span>
                          </div>
                          <span
                            className={styles.badge}
                            style={{ background: sc.bg, color: sc.color }}
                          >
                            {p.status}
                          </span>
                        </div>
                        <p className={styles.itemCliente}>{p.cliente}</p>
                        <div className={styles.itemBottom}>
                          <div>
                            <p className={styles.itemFooterLabel}>Total</p>
                            <p className={styles.itemTotal}>{fmt(p.total)}</p>
                          </div>
                          {p.comissao != null && (
                            <div>
                              <p className={styles.itemFooterLabel}>Comissão</p>
                              <p className={styles.itemComissao}>{fmt(p.comissao)}</p>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <BottomNav />
    </div>
  );
}
