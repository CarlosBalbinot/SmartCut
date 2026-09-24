import { useState, useEffect, useCallback } from "react";
import { getClientes, deleteCliente } from "../api/clientes";
import ClienteFormModal from "../components/ClienteFormModal/ClienteFormModal";
import { useAuth } from "../auth/useAuth";
import styles from "./ClientesPage.module.css";

const MODULO = "cadastros_clientes";

const displayCnpj = (raw) => {
  if (!raw) return null;
  const d = raw.replace(/\D/g, "");
  if (d.length !== 14) return raw;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
};

const TIPO_REGISTRO_LABEL = { cliente: "Cliente", fornecedor: "Fornecedor", ambos: "Ambos" };

export default function ClientesPage() {
  const { hasPermission } = useAuth();
  const [clientes, setClientes]       = useState([]);
  const [busca, setBusca]             = useState("");
  const [filtroTipo, setFiltroTipo]   = useState("");
  const [loading, setLoading]         = useState(true);
  // Modal de cadastro: null = fechado; { id: null } = novo; { id } = editar.
  const [modal, setModal]             = useState(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      setClientes((await getClientes(busca, filtroTipo)) || []);
    } catch {
      setClientes([]);
    } finally {
      setLoading(false);
    }
  }, [busca, filtroTipo]);

  useEffect(() => { carregar(); }, [carregar]);

  const abrirNovo   = ()  => setModal({ id: null });
  const abrirEditar = (c) => setModal({ id: c.id });

  const handleExcluir = async (id) => {
    if (!window.confirm("Deseja excluir este cadastro?")) return;
    try { await deleteCliente(id); await carregar(); } catch {}
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Clientes</h1>
        {hasPermission(MODULO, "criar") && (
          <button className={styles.btnNovo} onClick={abrirNovo}>+ Novo Cadastro</button>
        )}
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <input
            className={styles.busca}
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por nome, CNPJ ou CPF…"
          />
        </div>
        <select className={styles.select} value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
          <option value="">Todos</option>
          <option value="cliente">Clientes</option>
          <option value="fornecedor">Fornecedores</option>
        </select>
      </div>

      <div className={`sc-card ${styles.tableCard}`}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Código</th>
              <th>Razão Social</th>
              <th>Tipo</th>
              <th>CNPJ / CPF</th>
              <th>Cidade / UF</th>
              <th>Telefone</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className={styles.empty}>Carregando…</td></tr>
            ) : clientes.length === 0 ? (
              <tr><td colSpan={7} className={styles.empty}>Nenhum cadastro encontrado.</td></tr>
            ) : clientes.map((c) => (
              <tr key={c.id}>
                <td className={styles.tdMono}>{c.codigo || "—"}</td>
                <td>{c.razao_social}</td>
                <td>
                  <span className={`${styles.badge} ${styles["badge_" + (c.tipo_registro || "cliente")]}`}>
                    {TIPO_REGISTRO_LABEL[c.tipo_registro] || "Cliente"}
                  </span>
                </td>
                <td className={styles.tdMono}>{displayCnpj(c.cnpj) || c.cpf || "—"}</td>
                <td>{c.cidade && c.estado ? `${c.cidade} / ${c.estado}` : c.cidade || "—"}</td>
                <td>{c.telefone || "—"}</td>
                <td>
                  <div className={styles.actions}>
                    {hasPermission(MODULO, "editar") && (
                      <button className={styles.btnLink} onClick={() => abrirEditar(c)}>Editar</button>
                    )}
                    {hasPermission(MODULO, "excluir") && (
                      <button className={`${styles.btnLink} ${styles.btnDanger}`} onClick={() => handleExcluir(c.id)}>
                        Excluir
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal && (
        <ClienteFormModal
          clienteId={modal.id}
          onClose={() => setModal(null)}
          onSaved={async () => { await carregar(); setModal(null); }}
        />
      )}
    </div>
  );
}
