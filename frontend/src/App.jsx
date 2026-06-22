import { useEffect, useState } from "react";
import { Routes, Route, NavLink, useNavigate, useLocation } from "react-router-dom";
import styles from "./App.module.css";
import { useLogo } from "./contexts/LogoContext";
import TecidosPage from "./pages/TecidosPage";
import PedidosPage from "./pages/PedidosPage";
import PedidoDetalhePage from "./pages/PedidoDetalhePage";
import MoldesPage from "./pages/MoldesPage";
import EncaixesPage from "./pages/EncaixesPage";
import EncaixePage from "./pages/EncaixePage";
import PrecificacaoPage from "./pages/PrecificacaoPage";
import ProjecaoPage from "./pages/ProjecaoPage";
import Topbar from "./components/Topbar/Topbar";
import { lotesApi } from "./services/api";
import PedidosVendaPage from "./pages/PedidosVendaPage";
import PedidoVendaDetalhePage from "./pages/PedidoVendaDetalhePage";
import ConfiguracoesPage from "./pages/ConfiguracoesPage";
import EncaixeRapidoPage from "./pages/EncaixeRapidoPage";
import PainelFinanceiro from "./pages/financeiro/PainelFinanceiro";
import FluxoCaixa from "./pages/financeiro/FluxoCaixa";
import ComprasFinanceiro from "./pages/financeiro/ComprasFinanceiro";
import VendasFinanceiro from "./pages/financeiro/VendasFinanceiro";

/* ── Ícones SVG inline 15×15 ── */
const IconTecidos = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path d="M2 4h11M2 7.5h11M2 11h11"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const IconMoldes = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <circle cx="3.5" cy="3.5" r="2" stroke="currentColor" strokeWidth="1.5"/>
    <circle cx="3.5" cy="11.5" r="2" stroke="currentColor" strokeWidth="1.5"/>
    <path d="M12 2L5.5 5.5M10 13L5.5 9.5M5.5 5.5L5.5 9.5"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const IconPedidos = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="2" y="1.5" width="11" height="12" rx="1.5"
      stroke="currentColor" strokeWidth="1.5"/>
    <path d="M5 5.5h5M5 8h5M5 10.5h3"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const IconEncaixes = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="1.5" y="1.5" width="5"  height="5"  rx="1" stroke="currentColor" strokeWidth="1.5"/>
    <rect x="8.5" y="1.5" width="5"  height="5"  rx="1" stroke="currentColor" strokeWidth="1.5"/>
    <rect x="8.5" y="8.5" width="5"  height="5"  rx="1" stroke="currentColor" strokeWidth="1.5"/>
    <rect x="1.5" y="8.5" width="5"  height="5"  rx="1" stroke="currentColor" strokeWidth="1.5"/>
  </svg>
);

const IconPrecificacao = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <circle cx="7.5" cy="7.5" r="6" stroke="currentColor" strokeWidth="1.5"/>
    <path d="M5.5 9.5C5.5 9.5 6 10.5 7.5 10.5C9 10.5 9.5 9.5 9.5 8.5C9.5 7 7.5 7 7.5 7C7.5 7 5.5 7 5.5 5.5C5.5 4.5 6.5 4 7.5 4C8.5 4 9 4.5 9 4.5"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    <path d="M7.5 3.5V4M7.5 11V10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const IconProjecao = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path d="M2 11L5.5 7L8 9.5L12 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M10 4.5H12V6.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const IconDocVenda = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="2.5" y="1.5" width="10" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
    <path d="M5 5.5h5M5 8h5M5 10.5h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const IconEngrenagem = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <circle cx="7.5" cy="7.5" r="2" stroke="currentColor" strokeWidth="1.5"/>
    <path d="M7.5 1v1.5M7.5 12.5V14M14 7.5h-1.5M2.5 7.5H1M11.7 3.3l-1.1 1.1M4.4 10.6l-1.1 1.1M11.7 11.7l-1.1-1.1M4.4 4.4L3.3 3.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const IconRelampago = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path d="M8.5 2L4.5 8.5H7.5L6.5 13L11 6.5H8L8.5 2Z" fill="currentColor" />
  </svg>
);

const IconTrendingUp = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path d="M1 11L5 7L8 9.5L14 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M10 3H14V7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const IconCalendar = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="1.5" y="2.5" width="12" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
    <path d="M1.5 6.5h12" stroke="currentColor" strokeWidth="1.5"/>
    <path d="M5 1.5v2M10 1.5v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const IconShoppingCart = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path d="M1 1.5h2l2 8h7l1.5-5.5H4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <circle cx="6" cy="12.5" r="1" fill="currentColor"/>
    <circle cx="11" cy="12.5" r="1" fill="currentColor"/>
  </svg>
);

const IconDollarSign = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path d="M7.5 1.5v12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    <path d="M10 4.5C10 4.5 9 3.5 7.5 3.5C6 3.5 5 4.25 5 5.5C5 6.75 6.5 7.25 7.5 7.5C8.5 7.75 10 8.25 10 9.5C10 10.75 9 11.5 7.5 11.5C6 11.5 5 10.5 5 10.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const SECTIONS = [
  {
    label: "CADASTROS",
    items: [
      { to: "/tecidos",  label: "Tecidos",  Icon: IconTecidos  },
      { to: "/moldes",   label: "Moldes",   Icon: IconMoldes   },
    ],
  },
  {
    label: "PRODUÇÃO",
    items: [
      { to: "/encaixe-rapido", label: "Encaixe Rápido", Icon: IconRelampago },
      { to: "/encaixes",       label: "Encaixes",      Icon: IconEncaixes  },
    ],
  },
  {
    label: "GESTÃO",
    items: [
      { to: "/precificacao", label: "Precificação", Icon: IconPrecificacao },
      { to: "/projecao",     label: "Projeção",     Icon: IconProjecao     },
    ],
  },
  {
    label: "VENDAS",
    items: [
      { to: "/pedidos-venda", label: "Pedidos de Venda", Icon: IconDocVenda },
    ],
  },
  {
    label: "FINANCEIRO",
    items: [
      { to: "/financeiro/painel",      label: "Painel",        Icon: IconTrendingUp  },
      { to: "/financeiro/fluxo-caixa", label: "Fluxo de Caixa", Icon: IconCalendar   },
      { to: "/financeiro/compras",     label: "Compras",        Icon: IconShoppingCart },
      { to: "/financeiro/vendas",      label: "Vendas Fin.",    Icon: IconDollarSign  },
    ],
  },
];

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const isConfigActive = location.pathname.startsWith("/configuracoes");
  const [alertas, setAlertas] = useState([]);
  const [bannerFechado, setBannerFechado] = useState(false);
  const { logoUrl } = useLogo();

  useEffect(() => {
    lotesApi.listarAlertas().then(setAlertas).catch(() => {});
  }, []);

  const mostrarBanner = !bannerFechado && alertas.length > 0;

  return (
    <div className={styles.layout}>
      {/* ── Sidebar ── */}
      <nav className={styles.sidebar}>
        {/* scrollable nav content */}
        <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
          <div className={styles.logoWrap}>
            {logoUrl ? (
              <img src={logoUrl} alt="Logo da empresa" className={styles.sidebarLogoImg} />
            ) : (
              <>
                <span className={styles.logo}>SmartCut</span>
                <span className={styles.logoSub}>Gestão de Corte</span>
              </>
            )}
          </div>

          {SECTIONS.map(({ label, items }) => (
            <div key={label} className={styles.section}>
              <span className={styles.sectionLabel}>{label}</span>
              <ul className={styles.navList}>
                {items.map(({ to, label: itemLabel, Icon }) => (
                  <li key={to}>
                    <NavLink
                      to={to}
                      className={({ isActive }) =>
                        isActive ? styles.navLinkActive : styles.navLink
                      }
                    >
                      <span className={styles.navIcon}><Icon /></span>
                      {itemLabel}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Footer fixo — Configurações */}
        <div
          className={`${styles.sidebarConfigItem} ${isConfigActive ? styles.sidebarConfigItemActive : ""}`}
          onClick={() => navigate("/configuracoes")}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && navigate("/configuracoes")}
        >
          <span className={styles.navIcon} style={{ color: isConfigActive ? "var(--sc-text-primary)" : "var(--sc-text-muted)", flexShrink: 0 }}>
            <IconEngrenagem />
          </span>
          <span style={{
            flex: 1,
            fontSize: 13,
            color: isConfigActive ? "var(--sc-text-primary)" : "var(--sc-text-muted)",
            fontWeight: isConfigActive ? 600 : 400,
          }}>
            Configurações
          </span>
          <span style={{ fontSize: 11, color: "var(--sc-text-muted)", opacity: 0.6 }}>·</span>
          <span style={{ fontSize: 11, color: "var(--sc-text-muted)", opacity: 0.6 }}>v1.0</span>
        </div>
      </nav>

      {/* ── Área principal ── */}
      <div className={styles.mainArea}>
        <Topbar />

        {mostrarBanner && (
          <div className={styles.alertaBanner}>
            <span>
              ⚠ {alertas.length}{" "}
              {alertas.length === 1 ? "lote com estoque baixo" : "lotes com estoque baixo"} —{" "}
              <button
                className={styles.alertaBannerLink}
                onClick={() => { navigate("/tecidos"); setBannerFechado(true); }}
              >
                Ver tecidos
              </button>
            </span>
            <button
              className={styles.alertaBannerFechar}
              onClick={() => setBannerFechado(true)}
              aria-label="Fechar alerta"
            >
              ×
            </button>
          </div>
        )}

        <main className={styles.content}>
          <Routes>
            <Route path="/"                  element={<TecidosPage />} />
            <Route path="/tecidos"           element={<TecidosPage />} />
            <Route path="/moldes"            element={<MoldesPage />} />
            <Route path="/pedidos"           element={<PedidosPage />} />
            <Route path="/pedidos/:id"       element={<PedidoDetalhePage />} />
            <Route path="/encaixes"          element={<EncaixesPage />} />
            <Route path="/encaixes/:id"      element={<EncaixePage />} />
            <Route path="/precificacao"      element={<PrecificacaoPage />} />
            <Route path="/projecao"          element={<ProjecaoPage />} />
            <Route path="/encaixe-rapido"   element={<EncaixeRapidoPage />} />
            <Route path="/pedidos-venda"     element={<PedidosVendaPage />} />
            <Route path="/pedidos-venda/:id" element={<PedidoVendaDetalhePage />} />
            <Route path="/configuracoes"     element={<ConfiguracoesPage />} />
            <Route path="/configuracoes/*"   element={<ConfiguracoesPage />} />
            <Route path="/financeiro/painel"      element={<PainelFinanceiro />} />
            <Route path="/financeiro/fluxo-caixa" element={<FluxoCaixa />} />
            <Route path="/financeiro/compras"     element={<ComprasFinanceiro />} />
            <Route path="/financeiro/vendas"      element={<VendasFinanceiro />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
