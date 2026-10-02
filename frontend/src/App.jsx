import { useEffect, useState } from "react";
import { Routes, Route, Navigate, NavLink, useNavigate, useLocation } from "react-router-dom";
import { FolderArchive, Package } from "lucide-react";
import styles from "./App.module.css";
import appIcon from "./assets/android-chrome-192x192.png";
import DashboardPage from "./pages/DashboardPage";
import TecidosPage from "./pages/TecidosPage";
import MoldesPage from "./pages/MoldesPage";
import EncaixesPage from "./pages/EncaixesPage";
import EncaixePage from "./pages/EncaixePage";
import OrdensCortePage from "./pages/OrdensCortePage";
import OrdemCorteDetalhePage from "./pages/OrdemCorteDetalhePage";
import PrecificacaoPage from "./pages/PrecificacaoPage";
import ProjecaoPage from "./pages/ProjecaoPage";
import { getAlertasLotes } from "./api/tecidos";
import PedidosVendaPage from "./pages/PedidosVendaPage";
import PedidoVendaDetalhePage from "./pages/PedidoVendaDetalhePage";
import TabelasPrecoPage from "./pages/TabelasPrecoPage";
import UsuarioConfiguracoesPage from "./pages/UsuarioConfiguracoesPage";
import UsuarioConfiguracaoUsuarioPage from "./pages/UsuarioConfiguracaoUsuarioPage";
import UsuarioConfiguracaoEmpresaPage from "./pages/UsuarioConfiguracaoEmpresaPage";
import UsuarioConfiguracoesGeraisPage from "./pages/UsuarioConfiguracoesGeraisPage";
import UsuarioConfiguracoesFiscaisPage from "./pages/UsuarioConfiguracoesFiscaisPage";
import EncaixeRapidoPage from "./pages/EncaixeRapidoPage";
import PainelFinanceiro from "./pages/financeiro/PainelFinanceiro";
import FluxoCaixa from "./pages/financeiro/FluxoCaixa";
import ComprasFinanceiro from "./pages/financeiro/ComprasFinanceiro";
import VendasFinanceiro from "./pages/financeiro/VendasFinanceiro";
import ContabilidadeFinanceiro from "./pages/financeiro/ContabilidadeFinanceiro";
import ClientesPage from "./pages/ClientesPage";
import ProdutosPage from "./pages/ProdutosPage";
import TransportadorasPage from "./pages/TransportadorasPage";
import VendedoresPage from "./pages/VendedoresPage";
import CondicoesPagamentoPage from "./pages/CondicoesPagamentoPage";
import TabelasGradePage from "./pages/TabelasGradePage";
import GradeProdutosPage from "./pages/GradeProdutosPage";
import LoginPage from "./pages/LoginPage";
import UsuariosPage from "./pages/UsuariosPage";
import TESPage from "./pages/TESPage";
import NotasFiscaisPage from "./pages/NotasFiscaisPage";
import { useAuth } from "./auth/useAuth";
import ProtectedRoute from "./auth/ProtectedRoute";

/* ── Ícones SVG inline 15×15 ── */
const IconDashboard = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="1.5" y="1.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
    <rect x="8.5" y="1.5" width="5" height="8" rx="1" stroke="currentColor" strokeWidth="1.5" />
    <rect x="1.5" y="8.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
    <rect x="8.5" y="11.5" width="5" height="2" rx="1" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);

const IconTecidos = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path
      d="M2 4h11M2 7.5h11M2 11h11"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
  </svg>
);

const IconMoldes = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <circle cx="3.5" cy="3.5" r="2" stroke="currentColor" strokeWidth="1.5" />
    <circle cx="3.5" cy="11.5" r="2" stroke="currentColor" strokeWidth="1.5" />
    <path
      d="M12 2L5.5 5.5M10 13L5.5 9.5M5.5 5.5L5.5 9.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
  </svg>
);

const IconOrdemCorte = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="2" y="1.5" width="11" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
    <path
      d="M5 5H10M5 7.5H10M5 10H8"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
  </svg>
);

const IconEncaixes = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="1.5" y="1.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
    <rect x="8.5" y="1.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
    <rect x="8.5" y="8.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
    <rect x="1.5" y="8.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);

const IconPrecificacao = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <circle cx="7.5" cy="7.5" r="6" stroke="currentColor" strokeWidth="1.5" />
    <path
      d="M5.5 9.5C5.5 9.5 6 10.5 7.5 10.5C9 10.5 9.5 9.5 9.5 8.5C9.5 7 7.5 7 7.5 7C7.5 7 5.5 7 5.5 5.5C5.5 4.5 6.5 4 7.5 4C8.5 4 9 4.5 9 4.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
    <path
      d="M7.5 3.5V4M7.5 11V10.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
  </svg>
);

const IconProjecao = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path
      d="M2 11L5.5 7L8 9.5L12 4.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M10 4.5H12V6.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const IconDocVenda = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="2.5" y="1.5" width="10" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
    <path
      d="M5 5.5h5M5 8h5M5 10.5h3"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
  </svg>
);

const IconClientes = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <circle cx="7.5" cy="4.5" r="2.5" stroke="currentColor" strokeWidth="1.5" />
    <path
      d="M2 13c0-2.76 2.46-5 5.5-5s5.5 2.24 5.5 5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
  </svg>
);

const IconRelampago = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path d="M8.5 2L4.5 8.5H7.5L6.5 13L11 6.5H8L8.5 2Z" fill="currentColor" />
  </svg>
);

const IconTrendingUp = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path
      d="M1 11L5 7L8 9.5L14 3"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M10 3H14V7"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const IconCalendar = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="1.5" y="2.5" width="12" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
    <path d="M1.5 6.5h12" stroke="currentColor" strokeWidth="1.5" />
    <path d="M5 1.5v2M10 1.5v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const IconShoppingCart = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path
      d="M1 1.5h2l2 8h7l1.5-5.5H4.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <circle cx="6" cy="12.5" r="1" fill="currentColor" />
    <circle cx="11" cy="12.5" r="1" fill="currentColor" />
  </svg>
);

const IconDollarSign = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path d="M7.5 1.5v12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <path
      d="M10 4.5C10 4.5 9 3.5 7.5 3.5C6 3.5 5 4.25 5 5.5C5 6.75 6.5 7.25 7.5 7.5C8.5 7.75 10 8.25 10 9.5C10 10.75 9 11.5 7.5 11.5C6 11.5 5 10.5 5 10.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
  </svg>
);

const IconContabilidade = () => <FolderArchive size={15} strokeWidth={1.75} />;
const IconProdutosGrupo = () => <Package size={15} strokeWidth={1.75} />;

const IconProdutos = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path
      d="M7.5 1.5L13 4.5V10.5L7.5 13.5L2 10.5V4.5L7.5 1.5Z"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
    <path
      d="M2 4.5L7.5 7.5M7.5 7.5L13 4.5M7.5 7.5V13.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
  </svg>
);

const IconTransportadoras = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path
      d="M1.5 10.5V4.5H8.5V10.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
    <path
      d="M8.5 6.5H11.5L13 8.5V10.5H8.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
    <circle cx="4" cy="11.5" r="1.3" stroke="currentColor" strokeWidth="1.3" />
    <circle cx="10.5" cy="11.5" r="1.3" stroke="currentColor" strokeWidth="1.3" />
  </svg>
);

const IconVendedores = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <circle cx="6" cy="4.5" r="2.5" stroke="currentColor" strokeWidth="1.5" />
    <path
      d="M1.5 13c0-2.76 2.01-5 4.5-5s4.5 2.24 4.5 5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
    <path
      d="M10 3.5L11 4.5L13 2.2"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

const IconTabelaGrade = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="1.5" y="1.5" width="12" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
    <path
      d="M1.5 5.5h12M1.5 9.5h12M5.5 1.5v12M9.5 1.5v12"
      stroke="currentColor"
      strokeWidth="1.3"
    />
  </svg>
);

const IconGradeProdutos = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="1.5" y="1.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
    <rect x="8.5" y="1.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
    <rect x="1.5" y="8.5" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.5" />
    <path d="M9.7 11h4M11.7 9v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const IconCondicaoPagamento = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <rect x="1.5" y="2.5" width="12" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
    <path d="M1.5 5.5h12" stroke="currentColor" strokeWidth="1.5" />
    <path
      d="M4 8.5h2.5M8.5 8.5h2.5M4 10.5h2.5M8.5 10.5h2.5"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinecap="round"
    />
  </svg>
);

const IconTabelaPreco = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path
      d="M1.5 2.5h5L13 9L9 13L2.5 6.5V1.5Z"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
    <circle cx="4.5" cy="4.5" r="1" fill="currentColor" />
  </svg>
);

const IconLogout = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path
      d="M6 13.5H2.5a1 1 0 0 1-1-1v-10a1 1 0 0 1 1-1H6"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M10 10.5L13.5 7L10 3.5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path d="M13.5 7H5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

const IconFiscal = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <path
      d="M3.5 1.5h5L11.5 5v8.5a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1Z"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
    <path d="M8.5 1.5V5h3" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    <path
      d="M4.5 8h6M4.5 10.5h6M4.5 13h3.5"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinecap="round"
    />
  </svg>
);

const IconUsuariosAdmin = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
    <circle cx="7.5" cy="5" r="2.3" stroke="currentColor" strokeWidth="1.5" />
    <path
      d="M2.5 13c0-2.76 2.24-5 5-5s5 2.24 5 5"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
    />
    <path
      d="M11 2.5L11.8 4.1L13.5 4.3L12.25 5.5L12.55 7.2L11 6.4L9.45 7.2L9.75 5.5L8.5 4.3L10.2 4.1L11 2.5Z"
      fill="currentColor"
    />
  </svg>
);

const DASHBOARD_ITEM = {
  to: "/dashboard",
  label: "Dashboard",
  Icon: IconDashboard,
  modulo: "financeiro_painel",
};

const SECTIONS = [
  {
    label: "CADASTROS",
    Icon: IconClientes,
    items: [
      {
        to: "/cadastros/clientes",
        label: "Clientes",
        Icon: IconClientes,
        modulo: "cadastros_clientes",
      },
      {
        to: "/cadastros/transportadoras",
        label: "Transportadoras",
        Icon: IconTransportadoras,
        modulo: "cadastros_transportadoras",
      },
      {
        to: "/cadastros/vendedores",
        label: "Vendedores",
        Icon: IconVendedores,
        modulo: "cadastros_vendedores",
      },
      {
        to: "/cadastros/condicoes-pagamento",
        label: "Cond. de Pagamento",
        Icon: IconCondicaoPagamento,
        modulo: "configuracoes_ver",
      },
    ],
  },
  {
    label: "PRODUTOS",
    Icon: IconProdutosGrupo,
    items: [
      {
        to: "/produtos/lista",
        label: "Produtos",
        Icon: IconProdutos,
        modulo: "cadastros_produtos",
      },
      {
        to: "/produtos/grade",
        label: "Grade de Produtos",
        Icon: IconGradeProdutos,
        modulo: "cadastros_produtos",
      },
      {
        to: "/produtos/tabelas-grade",
        label: "Tabelas da Grade",
        Icon: IconTabelaGrade,
        modulo: "configuracoes_ver",
      },
    ],
  },
  {
    label: "PRODUÇÃO",
    Icon: IconEncaixes,
    items: [
      { to: "/producao/tecidos", label: "Tecidos", Icon: IconTecidos, modulo: "tecidos" },
      { to: "/producao/moldes", label: "Moldes", Icon: IconMoldes, modulo: "moldes" },
      {
        to: "/producao/encaixe-rapido",
        label: "Encaixe Rápido",
        Icon: IconRelampago,
        modulo: "encaixe_rapido",
      },
      {
        to: "/producao/ordens-corte",
        label: "Ordens de Corte",
        Icon: IconOrdemCorte,
        modulo: "encaixes",
      },
      { to: "/producao/encaixes", label: "Encaixes", Icon: IconEncaixes, modulo: "encaixes" },
    ],
  },
  {
    label: "GESTÃO",
    Icon: IconPrecificacao,
    items: [
      {
        to: "/gestao/precificacao",
        label: "Precificação",
        Icon: IconPrecificacao,
        modulo: "precificacao",
      },
      { to: "/gestao/projecao", label: "Projeção", Icon: IconProjecao, modulo: "projecao" },
    ],
  },
  {
    label: "VENDAS",
    Icon: IconDocVenda,
    items: [
      {
        to: "/vendas/pedidos",
        label: "Pedidos de Venda",
        Icon: IconDocVenda,
        modulo: "pedidos_ver",
      },
      { to: "/vendas/nfe", label: "Notas Fiscais", Icon: IconFiscal, modulo: "fiscal_nfe" },
      {
        to: "/vendas/tabelas-preco",
        label: "Tabelas de Preço",
        Icon: IconTabelaPreco,
        modulo: "configuracoes_ver",
      },
    ],
  },
  {
    label: "FINANCEIRO",
    Icon: IconDollarSign,
    items: [
      {
        to: "/financeiro/painel",
        label: "Painel",
        Icon: IconTrendingUp,
        modulo: "financeiro_painel",
      },
      {
        to: "/financeiro/fluxo-caixa",
        label: "Fluxo de Caixa",
        Icon: IconCalendar,
        modulo: "financeiro_fluxo",
      },
      {
        to: "/financeiro/compras",
        label: "Compras",
        Icon: IconShoppingCart,
        modulo: "financeiro_compras",
      },
      {
        to: "/financeiro/vendas",
        label: "Vendas Fin.",
        Icon: IconDollarSign,
        modulo: "financeiro_vendas",
      },
      {
        to: "/financeiro/contabilidade",
        label: "Contabilidade",
        Icon: IconContabilidade,
        modulo: "financeiro_contabilidade",
      },
    ],
  },
  {
    label: "FISCAL",
    Icon: IconFiscal,
    items: [{ to: "/fiscal/tes", label: "TES", Icon: IconFiscal, modulo: "fiscal_nfe" }],
  },
  {
    label: "SISTEMA",
    Icon: IconUsuariosAdmin,
    items: [
      {
        to: "/sistema/usuarios",
        label: "Usuários",
        Icon: IconUsuariosAdmin,
        modulo: "usuarios_admin",
      },
    ],
  },
];

const SIDEBAR_OPEN_KEY = "smartcut_sidebar";

function isPathActive(pathname, to) {
  return pathname === to || pathname.startsWith(`${to}/`);
}

// "CADASTROS" → "Cadastros" — usado no título do popover de categoria no modo recolhido.
function toTitulo(label) {
  return label.charAt(0) + label.slice(1).toLowerCase();
}

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const isUsuarioConfigActive = location.pathname.startsWith("/usuario/");
  const [alertas, setAlertas] = useState([]);
  const [bannerFechado, setBannerFechado] = useState(false);
  const { usuario, hasPermission, logout } = useAuth();
  const isLoginRoute = location.pathname === "/login";

  const isSectionActive = (items) => items.some((item) => isPathActive(location.pathname, item.to));

  // Accordion: só um grupo aberto por vez. Abre automaticamente o grupo
  // que contém a rota ativa (no mount e sempre que a rota mudar) e fecha
  // qualquer grupo aberto quando a rota ativa não pertence a nenhum grupo
  // (ex.: Dashboard) — sem isso o grupo anterior ficava expandido junto
  // com o Dashboard destacado.
  const [openSection, setOpenSection] = useState(() => {
    const found = SECTIONS.find((s) => isSectionActive(s.items));
    return found ? found.label : null;
  });

  useEffect(() => {
    const found = SECTIONS.find((s) => isSectionActive(s.items));
    setOpenSection(found ? found.label : null);
  }, [location.pathname]);

  // Tooltip do modo recolhido: popover com a lista de submenus da
  // categoria sob o mouse. Renderizado fora da <nav> (ver abaixo) para
  // não ser cortado pelo overflow-x:hidden do sidebar recolhido.
  const [tooltipSection, setTooltipSection] = useState(null);

  const [sidebarOpen, setSidebarOpen] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_OPEN_KEY) !== "false";
    } catch {
      return true;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_OPEN_KEY, sidebarOpen);
    } catch {}
  }, [sidebarOpen]);

  useEffect(() => {
    getAlertasLotes()
      .then(setAlertas)
      .catch(() => {});
  }, []);

  const mostrarBanner = !bannerFechado && alertas.length > 0;

  const visibleSections = SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) => hasPermission(item.modulo, "ver")),
  })).filter((section) => section.items.length > 0);

  if (isLoginRoute) {
    return <LoginPage />;
  }

  const toggleSection = (label, items) => {
    if (!sidebarOpen) return; // grupos não expandem com o sidebar recolhido
    const abrindo = openSection !== label;
    setOpenSection(abrindo ? label : null);
    if (abrindo && items.length > 0) {
      navigate(items[0].to);
    }
  };

  return (
    <div className={styles.layout}>
      {/* ── Sidebar ── */}
      <nav className={`${styles.sidebar} ${!sidebarOpen ? styles.sidebarCollapsed : ""}`}>
        <button
          type="button"
          className={styles.sidebarToggle}
          onClick={() => setSidebarOpen((o) => !o)}
          title={sidebarOpen ? "Recolher menu" : "Expandir menu"}
          aria-label={sidebarOpen ? "Recolher menu" : "Expandir menu"}
        >
          {sidebarOpen ? "☰" : "→"}
        </button>

        {/* scrollable nav content */}
        <div style={{ flex: 1, overflowY: "auto", overflowX: "hidden", minHeight: 0 }}>
          {/* Marca do sistema — sempre SmartCut, mesmo com logo da empresa cadastrado. */}
          <div className={styles.logoWrap}>
            <div className={styles.brand}>
              <img src={appIcon} alt="SmartCut" className={styles.sidebarLogoIcon} />
              <span className={`${styles.logo} ${styles.labelText}`}>SmartCut</span>
            </div>
          </div>

          {hasPermission(DASHBOARD_ITEM.modulo, "ver") && (
            <div className={styles.navLinkTopWrap}>
              <NavLink
                to={DASHBOARD_ITEM.to}
                className={({ isActive }) =>
                  isActive ? styles.navLinkTopActive : styles.navLinkTop
                }
                data-tooltip={DASHBOARD_ITEM.label}
              >
                {({ isActive }) => (
                  <>
                    <span className={`${styles.navIcon} ${isActive ? styles.navIconActive : ""}`}>
                      <DASHBOARD_ITEM.Icon />
                    </span>
                    <span className={styles.labelText}>{DASHBOARD_ITEM.label}</span>
                  </>
                )}
              </NavLink>
            </div>
          )}

          {visibleSections.map(({ label, items, Icon }) => {
            const isOpen = sidebarOpen && openSection === label;

            return (
              <div
                key={label}
                className={`${styles.section} ${isOpen ? styles.sectionExpanded : ""}`}
              >
                <div
                  className={styles.tooltipWrapper}
                  onMouseEnter={(e) => {
                    if (sidebarOpen) return;
                    setTooltipSection({
                      label,
                      items,
                      top: e.currentTarget.getBoundingClientRect().top,
                    });
                  }}
                  onMouseLeave={() => setTooltipSection(null)}
                >
                  <button
                    type="button"
                    className={styles.sectionHeader}
                    onClick={() => toggleSection(label, items)}
                    aria-expanded={isOpen}
                  >
                    <span
                      className={`${styles.sectionLabel} ${isOpen ? styles.sectionLabelExpanded : ""}`}
                    >
                      <span className={styles.sectionIcon}>
                        <Icon />
                      </span>
                      <span className={styles.labelText}>{label}</span>
                    </span>
                  </button>
                </div>
                <div className={`${styles.navListOuter} ${isOpen ? styles.navListOpen : ""}`}>
                  <div className={styles.navListInner}>
                    <ul className={styles.navList}>
                      {items.map(({ to, label: itemLabel }) => (
                        <li key={to}>
                          <NavLink
                            to={to}
                            className={({ isActive }) =>
                              isActive ? styles.navLinkActive : styles.navLink
                            }
                          >
                            {itemLabel}
                          </NavLink>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer fixo — usuário logado (clicável → configurações) + logout */}
        {usuario && (
          <div className={styles.sidebarUserItem}>
            <div
              className={`${styles.sidebarUserClickable} ${isUsuarioConfigActive ? styles.sidebarUserClickableActive : ""}`}
              onClick={() => navigate("/usuario/configuracoes")}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && navigate("/usuario/configuracoes")}
              title={!sidebarOpen ? usuario.nome_completo : "Configurações"}
            >
              <div className={styles.sidebarUserAvatar}>
                {(usuario.nome_completo || usuario.username || "?").charAt(0).toUpperCase()}
              </div>
              <span className={`${styles.sidebarUserName} ${styles.labelText}`}>
                {usuario.nome_completo}
              </span>
            </div>
            <button
              type="button"
              className={styles.sidebarLogoutBtn}
              onClick={logout}
              title="Sair"
              aria-label="Sair"
            >
              <IconLogout />
            </button>
          </div>
        )}

        <div className={styles.sidebarVersion}>v1.4.0</div>
      </nav>

      {/* Popover do modo recolhido — fora da <nav> de propósito: se
          ficasse dentro, o overflow-x:hidden do sidebar recolhido (que
          resolve o scroll lateral) cortaria esse balão, já que ele
          precisa se estender além dos 56px do sidebar. */}
      {!sidebarOpen && tooltipSection && (
        <div
          className={styles.tooltipMenu}
          style={{ top: tooltipSection.top }}
          onMouseEnter={() => setTooltipSection(tooltipSection)}
          onMouseLeave={() => setTooltipSection(null)}
        >
          <p className={styles.tooltipTitle}>{toTitulo(tooltipSection.label)}</p>
          {tooltipSection.items.map((item) => (
            <a
              key={item.to}
              onClick={() => {
                navigate(item.to);
                setTooltipSection(null);
              }}
            >
              {item.label}
            </a>
          ))}
        </div>
      )}

      {/* ── Área principal ── */}
      <div className={styles.mainArea}>
        {mostrarBanner && (
          <div className={styles.alertaBanner}>
            <span>
              ⚠ {alertas.length}{" "}
              {alertas.length === 1 ? "lote com estoque baixo" : "lotes com estoque baixo"} —{" "}
              <button
                className={styles.alertaBannerLink}
                onClick={() => {
                  navigate("/producao/tecidos");
                  setBannerFechado(true);
                }}
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
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute modulo="financeiro_painel">
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/cadastros/clientes"
              element={
                <ProtectedRoute modulo="cadastros_clientes">
                  <ClientesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/cadastros/transportadoras"
              element={
                <ProtectedRoute modulo="cadastros_transportadoras">
                  <TransportadorasPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/cadastros/vendedores"
              element={
                <ProtectedRoute modulo="cadastros_vendedores">
                  <VendedoresPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/cadastros/condicoes-pagamento"
              element={
                <ProtectedRoute modulo="configuracoes_ver">
                  <CondicoesPagamentoPage />
                </ProtectedRoute>
              }
            />

            <Route
              path="/produtos/lista"
              element={
                <ProtectedRoute modulo="cadastros_produtos">
                  <ProdutosPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/produtos/grade"
              element={
                <ProtectedRoute modulo="cadastros_produtos">
                  <GradeProdutosPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/produtos/tabelas-grade"
              element={
                <ProtectedRoute modulo="configuracoes_ver">
                  <TabelasGradePage />
                </ProtectedRoute>
              }
            />

            {/* Redirects de compatibilidade — URLs antigas sem o prefixo de grupo */}
            <Route path="/tecidos" element={<Navigate to="/producao/tecidos" replace />} />
            <Route path="/moldes" element={<Navigate to="/producao/moldes" replace />} />
            <Route path="/produtos" element={<Navigate to="/produtos/lista" replace />} />
            <Route path="/clientes" element={<Navigate to="/cadastros/clientes" replace />} />
            <Route
              path="/transportadoras"
              element={<Navigate to="/cadastros/transportadoras" replace />}
            />
            <Route path="/vendedores" element={<Navigate to="/cadastros/vendedores" replace />} />

            {/* Redirects — reorganização do menu PRODUTOS (movidos de CADASTROS) */}
            <Route path="/cadastros/produtos" element={<Navigate to="/produtos/lista" replace />} />
            <Route
              path="/cadastros/grade-produtos"
              element={<Navigate to="/produtos/grade" replace />}
            />
            <Route
              path="/cadastros/tabelas-grade"
              element={<Navigate to="/produtos/tabelas-grade" replace />}
            />

            {/* Redirects — Tecidos e Moldes movidos de CADASTROS para PRODUÇÃO */}
            <Route
              path="/cadastros/tecidos"
              element={<Navigate to="/producao/tecidos" replace />}
            />
            <Route path="/cadastros/moldes" element={<Navigate to="/producao/moldes" replace />} />

            {/* Pedidos de corte: fluxo antigo removido na item 7.2 — hoje o
                fluxo vivo é o Pedido de Venda em /vendas/pedidos. */}

            <Route
              path="/producao/tecidos"
              element={
                <ProtectedRoute modulo="tecidos">
                  <TecidosPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/producao/moldes"
              element={
                <ProtectedRoute modulo="moldes">
                  <MoldesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/producao/encaixe-rapido"
              element={
                <ProtectedRoute modulo="encaixe_rapido">
                  <EncaixeRapidoPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/producao/ordens-corte"
              element={
                <ProtectedRoute modulo="encaixes">
                  <OrdensCortePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/producao/ordens-corte/:id"
              element={
                <ProtectedRoute modulo="encaixes">
                  <OrdemCorteDetalhePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/producao/encaixes"
              element={
                <ProtectedRoute modulo="encaixes">
                  <EncaixesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/producao/encaixes/:id"
              element={
                <ProtectedRoute modulo="encaixes">
                  <EncaixePage />
                </ProtectedRoute>
              }
            />

            <Route
              path="/gestao/precificacao"
              element={
                <ProtectedRoute modulo="precificacao">
                  <PrecificacaoPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/gestao/projecao"
              element={
                <ProtectedRoute modulo="projecao">
                  <ProjecaoPage />
                </ProtectedRoute>
              }
            />

            <Route
              path="/vendas/pedidos"
              element={
                <ProtectedRoute modulo="pedidos_ver">
                  <PedidosVendaPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/vendas/pedidos/:id"
              element={
                <ProtectedRoute modulo="pedidos_ver">
                  <PedidoVendaDetalhePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/vendas/nfe"
              element={
                <ProtectedRoute modulo="fiscal_nfe">
                  <NotasFiscaisPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/vendas/tabelas-preco"
              element={
                <ProtectedRoute modulo="configuracoes_ver">
                  <TabelasPrecoPage />
                </ProtectedRoute>
              }
            />

            <Route
              path="/financeiro/painel"
              element={
                <ProtectedRoute modulo="financeiro_painel">
                  <PainelFinanceiro />
                </ProtectedRoute>
              }
            />
            <Route
              path="/financeiro/fluxo-caixa"
              element={
                <ProtectedRoute modulo="financeiro_fluxo">
                  <FluxoCaixa />
                </ProtectedRoute>
              }
            />
            <Route
              path="/financeiro/compras"
              element={
                <ProtectedRoute modulo="financeiro_compras">
                  <ComprasFinanceiro />
                </ProtectedRoute>
              }
            />
            <Route
              path="/financeiro/vendas"
              element={
                <ProtectedRoute modulo="financeiro_vendas">
                  <VendasFinanceiro />
                </ProtectedRoute>
              }
            />
            <Route
              path="/financeiro/contabilidade"
              element={
                <ProtectedRoute modulo="financeiro_contabilidade">
                  <ContabilidadeFinanceiro />
                </ProtectedRoute>
              }
            />

            <Route
              path="/fiscal/tes"
              element={
                <ProtectedRoute modulo="fiscal_nfe">
                  <TESPage />
                </ProtectedRoute>
              }
            />
            <Route path="/fiscal/nfe" element={<Navigate to="/vendas/nfe" replace />} />

            <Route
              path="/usuario/configuracoes"
              element={
                <ProtectedRoute>
                  <UsuarioConfiguracoesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/usuario/configuracao-usuario"
              element={
                <ProtectedRoute>
                  <UsuarioConfiguracaoUsuarioPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/usuario/configuracao-empresa"
              element={
                <ProtectedRoute modulo="configuracoes_ver">
                  <UsuarioConfiguracaoEmpresaPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/usuario/configuracoes-gerais"
              element={
                <ProtectedRoute modulo="configuracoes_ver">
                  <UsuarioConfiguracoesGeraisPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/usuario/configuracoes-fiscais"
              element={
                <ProtectedRoute modulo="configuracoes_ver">
                  <UsuarioConfiguracoesFiscaisPage />
                </ProtectedRoute>
              }
            />

            {/* Rotas antigas de configuração — redirecionam para o novo hub /usuario/* */}
            <Route
              path="/configuracoes"
              element={<Navigate to="/usuario/configuracoes" replace />}
            />
            <Route
              path="/configuracoes/*"
              element={<Navigate to="/usuario/configuracoes" replace />}
            />

            <Route
              path="/sistema/usuarios"
              element={
                <ProtectedRoute adminOnly>
                  <UsuariosPage />
                </ProtectedRoute>
              }
            />
            <Route path="/admin/usuarios" element={<Navigate to="/sistema/usuarios" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
