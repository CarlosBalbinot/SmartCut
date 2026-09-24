import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import styles from "./LeadsPage.module.css";
import { vendedorFetch } from "../../services/vendedorApi";

const STATUS_LIST = ["todos", "novo", "visitado", "orcamento", "cliente"];
const STATUS_LABEL = {
  todos: "Todos",
  novo: "Novo",
  visitado: "Visitado",
  orcamento: "Orçamento",
  cliente: "Cliente",
};
const STATUS_COLORS = {
  novo: { bg: "#E8F4FD", color: "#0071E3" },
  visitado: { bg: "#FFF8E8", color: "#B45309" },
  orcamento: { bg: "#F0EDFF", color: "#6940D4" },
  cliente: { bg: "#E8F8E8", color: "#1A7F37" },
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

export default function LeadsPage() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [filtro, setFiltro] = useState("todos");
  const [sheet, setSheet] = useState(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    vendedorFetch("/vendedor/leads")
      .then(setLeads)
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, []);

  const leadsFiltrados = filtro === "todos" ? leads : leads.filter((l) => l.status === filtro);

  function abrirSheet(lead) {
    setSheet({ lead, novoStatus: lead.status, obs: lead.observacao || "" });
  }

  async function salvarStatus() {
    setSalvando(true);
    try {
      const updated = await vendedorFetch(`/vendedor/leads/${sheet.lead.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: sheet.novoStatus, observacao: sheet.obs }),
      });
      setLeads((prev) => prev.map((l) => (l.id === sheet.lead.id ? { ...l, ...updated } : l)));
      setSheet(null);
    } catch (e) {
      alert(e.message);
    } finally {
      setSalvando(false);
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.titulo}>Meus Leads</h1>
      </header>

      <div className={styles.filtros}>
        {STATUS_LIST.map((s) => (
          <button
            key={s}
            className={filtro === s ? styles.pillActive : styles.pill}
            onClick={() => setFiltro(s)}
          >
            {STATUS_LABEL[s]}
          </button>
        ))}
      </div>

      <div className={styles.content}>
        {loading && <p className={styles.info}>Carregando…</p>}
        {erro && <p className={styles.erro}>{erro}</p>}
        {!loading && !erro && leadsFiltrados.length === 0 && (
          <p className={styles.info}>Nenhum lead encontrado.</p>
        )}
        {leadsFiltrados.map((lead) => {
          const sc = STATUS_COLORS[lead.status] || { bg: "#F5F5F7", color: "#6E6E73" };
          return (
            <div key={lead.id} className={styles.card}>
              <div className={styles.cardTop}>
                <div className={styles.cardInfo}>
                  <p className={styles.nome}>{lead.nome}</p>
                  <p className={styles.sub}>
                    {[lead.segmento, lead.cidade].filter(Boolean).join(" · ")}
                  </p>
                </div>
                <span className={styles.badge} style={{ background: sc.bg, color: sc.color }}>
                  {STATUS_LABEL[lead.status] || lead.status}
                </span>
              </div>
              <div className={styles.cardActions}>
                {lead.telefone && (
                  <a href={`tel:${lead.telefone}`} className={styles.actionBtn}>
                    Ligar
                  </a>
                )}
                {lead.endereco && (
                  <a
                    href={`https://www.google.com/maps/search/${encodeURIComponent(lead.endereco)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.actionBtn}
                  >
                    Maps
                  </a>
                )}
                <button className={styles.actionBtnPrimary} onClick={() => abrirSheet(lead)}>
                  Atualizar status
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {sheet && (
        <div className={styles.overlay} onClick={() => setSheet(null)}>
          <div className={styles.sheetPanel} onClick={(e) => e.stopPropagation()}>
            <p className={styles.sheetTitulo}>Atualizar — {sheet.lead.nome}</p>
            <select
              className={styles.sheetSelect}
              value={sheet.novoStatus}
              onChange={(e) => setSheet((s) => ({ ...s, novoStatus: e.target.value }))}
            >
              {STATUS_LIST.filter((s) => s !== "todos").map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
            <textarea
              className={styles.sheetTextarea}
              placeholder="Observação (opcional)"
              value={sheet.obs}
              onChange={(e) => setSheet((s) => ({ ...s, obs: e.target.value }))}
              rows={3}
            />
            <div className={styles.sheetBtns}>
              <button className={styles.sheetCancel} onClick={() => setSheet(null)}>
                Cancelar
              </button>
              <button className={styles.sheetSalvar} onClick={salvarStatus} disabled={salvando}>
                {salvando ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      <BottomNav />
    </div>
  );
}
