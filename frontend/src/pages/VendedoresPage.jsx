import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { vendedoresApi } from "../services/api";
import styles from "./VendedoresPage.module.css";

const MODAL_VAZIO = { nome: "", telefone: "", email: "" };

export default function VendedoresPage() {
  const [vendedores, setVendedores] = useState([]);
  const [modal, setModal]           = useState(null);
  const [saving, setSaving]         = useState(false);
  const [erro, setErro]             = useState(null);
  const navigate                    = useNavigate();

  const carregar = () =>
    vendedoresApi.list().then(setVendedores).catch(() => {});

  useEffect(() => { carregar(); }, []);

  const abrirModal = (v = null) =>
    setModal(v
      ? { id: v.id, nome: v.nome, telefone: v.telefone || "", email: v.email || "" }
      : { ...MODAL_VAZIO }
    );

  const fecharModal = () => { setModal(null); setErro(null); };

  const handleSalvar = async () => {
    if (!modal.nome.trim()) { setErro("Nome é obrigatório."); return; }
    setSaving(true); setErro(null);
    try {
      const payload = { nome: modal.nome.trim(), telefone: modal.telefone.trim(), email: modal.email.trim() };
      if (modal.id) await vendedoresApi.update(modal.id, payload);
      else           await vendedoresApi.create(payload);
      await carregar();
      fecharModal();
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Vendedores</h1>
        <button className={styles.btnPrimary} onClick={() => abrirModal()}>+ Novo Vendedor</button>
      </div>

      <div className={styles.card}>
        {vendedores.length === 0 ? (
          <p className={styles.empty}>Nenhum vendedor cadastrado.</p>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Nome</th>
                <th>Telefone</th>
                <th>E-mail</th>
                <th>Status</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {vendedores.map((v) => (
                <tr key={v.id}>
                  <td>{v.nome}</td>
                  <td>{v.telefone || "—"}</td>
                  <td>{v.email    || "—"}</td>
                  <td>
                    <span className={v.ativo !== false ? styles.badgeAtivo : styles.badgeInativo}>
                      {v.ativo !== false ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td>
                    <div className={styles.actions}>
                      <button className={styles.btnLink} onClick={() => abrirModal(v)}>Editar</button>
                      <button
                        className={styles.btnDash}
                        onClick={() => navigate(`/vendedores/${v.id}`)}
                      >
                        Ver dashboard
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {modal && (
        <div className={styles.overlay} onClick={fecharModal}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>{modal.id ? "Editar Vendedor" : "Novo Vendedor"}</h2>

            {[
              { key: "nome",      label: "Nome *"    },
              { key: "telefone",  label: "Telefone"  },
              { key: "email",     label: "E-mail"    },
            ].map(({ key, label }) => (
              <label key={key} className={styles.field}>
                <span>{label}</span>
                <input
                  className={styles.input}
                  value={modal[key]}
                  onChange={(e) => setModal((m) => ({ ...m, [key]: e.target.value }))}
                />
              </label>
            ))}

            {erro && <p className={styles.erro}>{erro}</p>}

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharModal}>Cancelar</button>
              <button className={styles.btnPrimary} onClick={handleSalvar} disabled={saving}>
                {saving ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
