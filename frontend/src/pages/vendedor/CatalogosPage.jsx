import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import styles from "./CatalogosPage.module.css";
import { API_BASE } from "../../services/config";
import { vendedorFetch } from "../../services/vendedorApi";
import { tokenStore } from "../../services/tokenStore";

async function downloadCatalogo(id, nome) {
  // Item 1.4: token via safeStorage (Electron) ou cookie HttpOnly (navegador).
  const token = await tokenStore.obter("vendedor");
  const res = await fetch(`${API_BASE}/api/v1/vendedor/catalogos/${id}/download`, {
    credentials: "include",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const json = await res.json().catch(() => ({}));
    throw new Error(json.error || `Erro ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${nome}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

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

export default function CatalogosPage() {
  const [catalogos, setCatalogos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [baixando, setBaixando] = useState(null);

  useEffect(() => {
    vendedorFetch("/vendedor/catalogos")
      .then(setCatalogos)
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleDownload(cat) {
    setBaixando(cat.id);
    try {
      await downloadCatalogo(cat.id, cat.nome);
    } catch (e) {
      alert(e.message);
    } finally {
      setBaixando(null);
    }
  }

  function handleCompartilhar(cat) {
    const url = `${window.location.origin}/api/v1/vendedor/catalogos/${cat.id}/download`;
    if (navigator.share) {
      navigator.share({ title: cat.nome, url });
    } else {
      const msg = encodeURIComponent(`Confira o catálogo ${cat.nome}: ${url}`);
      window.open(`https://wa.me/?text=${msg}`, "_blank");
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.titulo}>Catálogos</h1>
      </header>

      <div className={styles.content}>
        {loading && <p className={styles.info}>Carregando…</p>}
        {erro && <p className={styles.erro}>{erro}</p>}
        {!loading && !erro && catalogos.length === 0 && (
          <p className={styles.info}>Nenhum catálogo disponível.</p>
        )}
        <div className={styles.grid}>
          {catalogos.map((cat) => (
            <div key={cat.id} className={styles.card}>
              <p className={styles.cardNome}>{cat.nome}</p>
              {cat.tabela && <p className={styles.cardSub}>{cat.tabela}</p>}
              <div className={styles.cardActions}>
                <button
                  className={styles.btnPrimary}
                  onClick={() => handleDownload(cat)}
                  disabled={baixando === cat.id}
                >
                  {baixando === cat.id ? "Baixando…" : "Baixar PDF"}
                </button>
                <button
                  className={styles.btnSecondary}
                  onClick={() => handleCompartilhar(cat)}
                >
                  Compartilhar
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <BottomNav />
    </div>
  );
}
