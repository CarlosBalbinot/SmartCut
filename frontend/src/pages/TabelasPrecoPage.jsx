import { useState, useEffect } from "react";
import { tabelasPrecoApi } from "../services/api";
import styles from "./TabelasPrecoPage.module.css";

const PADROES = [
  { nome: "Ultra Baixa",     comissao: 5  },
  { nome: "Baixa",           comissao: 7  },
  { nome: "Média (Padrão)", comissao: 10 },
  { nome: "Alta",            comissao: 10 },
  { nome: "Ultra Alta",      comissao: 10 },
  { nome: "Premium",         comissao: 12 },
];

export default function TabelasPrecoPage() {
  const [tabelas, setTabelas] = useState([]);
  const [modal, setModal]     = useState(null);
  const [saving, setSaving]   = useState(false);
  const [erro, setErro]       = useState(null);

  const carregar = async () => {
    const data = await tabelasPrecoApi.list();
    if ((data || []).length === 0) {
      for (const t of PADROES) {
        await tabelasPrecoApi.create({ nome: t.nome, comissao: t.comissao, ativo: true });
      }
      const novas = await tabelasPrecoApi.list();
      setTabelas(novas || []);
    } else {
      setTabelas(data);
    }
  };

  useEffect(() => { carregar().catch(() => {}); }, []);

  const abrirModal = (t = null) =>
    setModal(t
      ? { id: t.id, nome: t.nome, comissao: String(t.comissao) }
      : { nome: "", comissao: "" }
    );

  const fecharModal = () => { setModal(null); setErro(null); };

  const handleSalvar = async () => {
    if (!modal.nome.trim()) { setErro("Nome é obrigatório."); return; }
    setSaving(true);
    setErro(null);
    try {
      const payload = { nome: modal.nome.trim(), comissao: parseFloat(modal.comissao) || 0 };
      if (modal.id) {
        await tabelasPrecoApi.update(modal.id, payload);
      } else {
        await tabelasPrecoApi.create({ ...payload, ativo: true });
      }
      await carregar();
      fecharModal();
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  const toggleAtivo = async (t) => {
    await tabelasPrecoApi.update(t.id, { ativo: !t.ativo });
    await carregar();
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Tabelas de Preço</h1>
        <button className={styles.btnPrimary} onClick={() => abrirModal()}>+ Nova Tabela</button>
      </div>

      <div className={styles.card}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Nome</th>
              <th>Comissão %</th>
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {tabelas.map((t) => (
              <tr key={t.id}>
                <td>{t.nome}</td>
                <td>{t.comissao}%</td>
                <td>
                  <span className={t.ativo ? styles.badgeAtivo : styles.badgeInativo}>
                    {t.ativo ? "Ativa" : "Inativa"}
                  </span>
                </td>
                <td>
                  <div className={styles.actions}>
                    <button className={styles.btnLink} onClick={() => abrirModal(t)}>Editar</button>
                    <button className={styles.btnLink} onClick={() => toggleAtivo(t)}>
                      {t.ativo ? "Desativar" : "Ativar"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {tabelas.length === 0 && (
              <tr><td colSpan={4} className={styles.empty}>Carregando…</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className={styles.overlay} onClick={fecharModal}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>{modal.id ? "Editar Tabela" : "Nova Tabela"}</h2>

            <label className={styles.field}>
              <span>Nome</span>
              <input
                className={styles.input}
                value={modal.nome}
                onChange={(e) => setModal((m) => ({ ...m, nome: e.target.value }))}
              />
            </label>

            <label className={styles.field}>
              <span>Comissão (%)</span>
              <input
                className={styles.input}
                type="number"
                step="0.5"
                min="0"
                value={modal.comissao}
                onChange={(e) => setModal((m) => ({ ...m, comissao: e.target.value }))}
              />
            </label>

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
