import { useEffect, useState } from "react";
import { Routes, Route, NavLink, useNavigate } from "react-router-dom";
import styles from "./App.module.css";
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
      { to: "/pedidos",  label: "Pedidos",  Icon: IconPedidos  },
      { to: "/encaixes", label: "Encaixes", Icon: IconEncaixes },
    ],
  },
  {
    label: "GESTÃO",
    items: [
      { to: "/precificacao", label: "Precificação", Icon: IconPrecificacao },
      { to: "/projecao",     label: "Projeção",     Icon: IconProjecao     },
    ],
  },
];

export default function App() {
  const navigate = useNavigate();
  const [alertas, setAlertas] = useState([]);
  const [bannerFechado, setBannerFechado] = useState(false);

  useEffect(() => {
    lotesApi.listarAlertas().then(setAlertas).catch(() => {});
  }, []);

  const mostrarBanner = !bannerFechado && alertas.length > 0;

  return (
    <div className={styles.layout}>
      {/* ── Sidebar ── */}
      <nav className={styles.sidebar}>
        <div className={styles.logoWrap}>
          <span className={styles.logo}>SmartCut</span>
          <span className={styles.logoSub}>Gestão de Corte</span>
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

        <div className={styles.sidebarFooter}>
          <span className={styles.versao}>v1.0</span>
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
            <Route path="/"             element={<TecidosPage />} />
            <Route path="/tecidos"      element={<TecidosPage />} />
            <Route path="/moldes"       element={<MoldesPage />} />
            <Route path="/pedidos"      element={<PedidosPage />} />
            <Route path="/pedidos/:id"  element={<PedidoDetalhePage />} />
            <Route path="/encaixes"        element={<EncaixesPage />} />
            <Route path="/encaixes/:id"    element={<EncaixePage />} />
            <Route path="/precificacao"    element={<PrecificacaoPage />} />
            <Route path="/projecao"        element={<ProjecaoPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
