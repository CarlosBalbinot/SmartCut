import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { pedidosApi } from "../services/api";
import Modal from "../components/Modal/Modal";
import ConfirmModal from "../components/ConfirmModal/ConfirmModal";
import { useToast } from "../contexts/ToastContext";
import styles from "./Page.module.css";
import ps from "./PedidosPage.module.css";

const STATUS = {
  rascunho:    { label: "Rascunho",    cor: "cinza" },
  processando: { label: "Em produção", cor: "azul"  },
  concluido:   { label: "Concluído",   cor: "verde" },
};

const FORM_INICIAL = {
  num_pedido: "",
  cliente: "",
  data_pedido: new Date().toISOString().slice(0, 10),
};

export default function PedidosPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();

  const [pedidos, setPedidos] = useState([]);
  const [modalAberto, setModalAberto] = useState(false);
  const [form, setForm] = useState(FORM_INICIAL);
  const [salvando, setSalvando] = useState(false);
  const [erroForm, setErroForm] = useState(null);

  // Menu ⋮
  const [menuAberto, setMenuAberto] = useState(null);
  const [menuPos, setMenuPos] = useState({ top: 0, right: 0 });
  const menuRef = useRef(null);

  // ConfirmModal de exclusão
  const [confirmExcluir, setConfirmExcluir] = useState(null);

  // ── Carregamento ──────────────────────────────────────────────────

  useEffect(() => {
    pedidosApi.listar().then(setPedidos).catch((e) => addToast(e.message, "erro"));
  }, [addToast]);

  // Fecha menu ao clicar fora
  useEffect(() => {
    function fecharMenu(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuAberto(null);
      }
    }
    document.addEventListener("mousedown", fecharMenu);
    return () => document.removeEventListener("mousedown", fecharMenu);
  }, []);

  // ── Modal Novo Pedido ─────────────────────────────────────────────

  async function abrirModal() {
    setErroForm(null);
    setModalAberto(true);
    try {
      const numero = await pedidosApi.proximoNumero();
      setForm({ ...FORM_INICIAL, num_pedido: numero });
    } catch {
      setForm(FORM_INICIAL);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSalvando(true);
    setErroForm(null);
    try {
      const novo = await pedidosApi.criar({
        num_pedido: form.num_pedido,
        cliente: form.cliente || null,
        data_pedido: form.data_pedido,
        tecido_ids: [],
      });
      setModalAberto(false);
      navigate(`/pedidos/${novo.id}?modo=editar`);
    } catch (ex) {
      const match = ex.message.match(/Sugerimos o número: (\S+)/);
      if (match) {
        const sugerido = match[1];
        setForm((prev) => ({ ...prev, num_pedido: sugerido }));
        addToast(ex.message, "aviso");
      } else {
        setErroForm(ex.message);
      }
    } finally {
      setSalvando(false);
    }
  }

  // ── Ações do menu ⋮ ───────────────────────────────────────────────

  async function duplicarPedido(p) {
    setMenuAberto(null);
    try {
      const novo = await pedidosApi.duplicar(p.id);
      addToast(`Pedido ${novo.num_pedido} criado como cópia de ${p.num_pedido}.`, "sucesso");
      navigate(`/pedidos/${novo.id}?modo=editar`);
    } catch (ex) {
      addToast(ex.message, "erro");
    }
  }

  function pedirExclusao(p) {
    setMenuAberto(null);
    setConfirmExcluir(p);
  }

  async function confirmarExclusao() {
    const p = confirmExcluir;
    setConfirmExcluir(null);
    try {
      await pedidosApi.deletar(p.id);
      setPedidos((prev) => prev.filter((x) => x.id !== p.id));
      addToast(`Pedido ${p.num_pedido} excluído.`, "sucesso");
    } catch (ex) {
      addToast(ex.message, "erro");
    }
  }

  // ── Render ────────────────────────────────────────────────────────

  return (
    <div>
      <div className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>Pedidos</h1>
        <button className={styles.btnNovo} onClick={abrirModal}>
          + Novo Pedido
        </button>
      </div>

      <table className={styles.tabela}>
        <thead>
          <tr>
            <th>Nº Pedido</th>
            <th>Cliente</th>
            <th>Data</th>
            <th>Grupos</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {pedidos.map((p) => {
            const st = STATUS[p.status] ?? { label: p.status, cor: "cinza" };
            return (
              <tr
                key={p.id}
                onDoubleClick={() => navigate(`/pedidos/${p.id}`)}
                className={ps.linhaTabela}
              >
                <td className={ps.numPedido}>{p.num_pedido}</td>
                <td>{p.cliente ?? "—"}</td>
                <td>{p.data_pedido}</td>
                <td className={ps.totalGrupos}>
                  {p.total_grupos > 0
                    ? `${p.total_grupos} grupo${p.total_grupos !== 1 ? "s" : ""}`
                    : "—"}
                </td>
                <td>
                  <span className={`${ps.badge} ${ps[`badge_${st.cor}`]}`}>
                    {st.label}
                  </span>
                </td>
                <td className={ps.acoesCell}>
                  <button
                    className={ps.btnAbrir}
                    onClick={() => navigate(`/pedidos/${p.id}`)}
                  >
                    Abrir →
                  </button>

                  {/* Menu ⋮ */}
                  <div className={ps.menuWrapper}>
                    <button
                      className={ps.btnMenu}
                      onClick={(e) => {
                        e.stopPropagation();
                        if (menuAberto === p.id) {
                          setMenuAberto(null);
                        } else {
                          const rect = e.currentTarget.getBoundingClientRect();
                          setMenuPos({
                            top: rect.bottom + 4,
                            right: window.innerWidth - rect.right,
                          });
                          setMenuAberto(p.id);
                        }
                      }}
                      title="Mais ações"
                    >
                      ⋮
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
          {pedidos.length === 0 && (
            <tr>
              <td colSpan={6} className={styles.vazio}>
                Nenhum pedido cadastrado.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* ── Modal: Novo Pedido ── */}
      {modalAberto && (
        <Modal titulo="Novo Pedido" onClose={() => setModalAberto(false)}>
          <form className={styles.form} onSubmit={handleSubmit}>
            {erroForm && <p className={styles.erroForm}>{erroForm}</p>}

            <div className={styles.fileiraDupla}>
              <div className={styles.campo}>
                <label className={styles.label}>Nº Pedido *</label>
                <input
                  className={styles.input}
                  value={form.num_pedido}
                  onChange={(e) => setForm((p) => ({ ...p, num_pedido: e.target.value }))}
                  required
                  autoFocus
                />
              </div>
              <div className={styles.campo}>
                <label className={styles.label}>Data *</label>
                <input
                  className={styles.input}
                  type="date"
                  value={form.data_pedido}
                  onChange={(e) => setForm((p) => ({ ...p, data_pedido: e.target.value }))}
                  required
                />
              </div>
            </div>

            <div className={styles.campo}>
              <label className={styles.label}>Cliente</label>
              <input
                className={styles.input}
                value={form.cliente}
                onChange={(e) => setForm((p) => ({ ...p, cliente: e.target.value }))}
                placeholder="Nome do cliente (opcional)"
              />
            </div>

            <div className={styles.formActions}>
              <button
                type="button"
                className={styles.btnSecondary}
                onClick={() => setModalAberto(false)}
              >
                Cancelar
              </button>
              <button type="submit" className={styles.btnPrimary} disabled={salvando}>
                {salvando ? "Criando..." : "Criar Pedido"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── ConfirmModal: Excluir pedido ── */}
      <ConfirmModal
        isOpen={!!confirmExcluir}
        titulo="Excluir pedido"
        mensagem={`Tem certeza que deseja excluir o pedido "${confirmExcluir?.num_pedido}"? Esta ação não pode ser desfeita.`}
        labelConfirmar="Excluir"
        variante="perigo"
        onConfirmar={confirmarExclusao}
        onCancelar={() => setConfirmExcluir(null)}
      />

      {/* ── Dropdown fixo (fora da tabela) ── */}
      {menuAberto && (
        <div
          ref={menuRef}
          className={ps.dropdown}
          style={{ top: menuPos.top, right: menuPos.right }}
        >
          {pedidos.filter((p) => p.id === menuAberto).map((p) => (
            <div key={p.id}>
              <button
                className={ps.dropdownItem}
                onClick={() => { setMenuAberto(null); navigate(`/pedidos/${p.id}?modo=editar`); }}
              >
                ✏ Editar
              </button>
              <button
                className={ps.dropdownItem}
                onClick={() => duplicarPedido(p)}
              >
                ⧉ Duplicar pedido
              </button>
              <div className={ps.dropdownDivider} />
              <button
                className={`${ps.dropdownItem} ${ps.dropdownItemPerigo}`}
                onClick={() => pedirExclusao(p)}
              >
                ✕ Excluir
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
