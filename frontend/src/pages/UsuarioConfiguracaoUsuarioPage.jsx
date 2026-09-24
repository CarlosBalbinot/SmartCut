import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import styles from "./UsuarioConfiguracaoUsuarioPage.module.css";

export default function UsuarioConfiguracaoUsuarioPage() {
  const navigate = useNavigate();
  const { usuario, atualizarMe } = useAuth();

  const [form, setForm] = useState({
    nome_completo: usuario?.nome_completo || "",
    username: usuario?.username || "",
    senha_atual: "",
    senha_nova: "",
    senha_confirmar: "",
  });
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState(null);
  const [sucesso, setSucesso] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSalvar = async () => {
    setErro(null);
    setSucesso(false);

    if (!form.nome_completo.trim()) {
      setErro("Nome completo é obrigatório.");
      return;
    }
    if (!form.username.trim()) {
      setErro("Login é obrigatório.");
      return;
    }

    const querTrocarSenha = form.senha_nova || form.senha_confirmar || form.senha_atual;
    if (querTrocarSenha) {
      if (!form.senha_atual) {
        setErro("Informe a senha atual.");
        return;
      }
      if (!form.senha_nova) {
        setErro("Informe a nova senha.");
        return;
      }
      if (form.senha_nova !== form.senha_confirmar) {
        setErro("As senhas não conferem.");
        return;
      }
    }

    setSaving(true);
    try {
      await atualizarMe({
        nome_completo: form.nome_completo.trim(),
        username: form.username.trim(),
        ...(querTrocarSenha ? { senha_atual: form.senha_atual, senha_nova: form.senha_nova } : {}),
      });
      setForm((f) => ({ ...f, senha_atual: "", senha_nova: "", senha_confirmar: "" }));
      setSucesso(true);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.page}>
      <button className={styles.btnBack} onClick={() => navigate("/usuario/configuracoes")}>
        Voltar
      </button>

      <h1 className={styles.title}>Dados do Usuário</h1>

      <div className={styles.card}>
        <p className={styles.secLabel}>Conta</p>
        <div className={styles.grid2}>
          <label className={styles.field}>
            <span>Nome completo</span>
            <input
              className={styles.input}
              value={form.nome_completo}
              onChange={set("nome_completo")}
            />
          </label>
          <label className={styles.field}>
            <span>Login</span>
            <input className={styles.input} value={form.username} onChange={set("username")} />
          </label>
        </div>

        <p className={styles.secLabel} style={{ marginTop: "1.5rem" }}>
          Trocar senha
        </p>
        <div className={styles.grid2}>
          <label className={styles.field}>
            <span>Senha atual</span>
            <input
              type="password"
              className={styles.input}
              value={form.senha_atual}
              onChange={set("senha_atual")}
            />
          </label>
          <div />
          <label className={styles.field}>
            <span>Nova senha</span>
            <input
              type="password"
              className={styles.input}
              value={form.senha_nova}
              onChange={set("senha_nova")}
            />
          </label>
          <label className={styles.field}>
            <span>Confirmar nova senha</span>
            <input
              type="password"
              className={styles.input}
              value={form.senha_confirmar}
              onChange={set("senha_confirmar")}
            />
          </label>
        </div>

        {erro && <p className={styles.erro}>{erro}</p>}
        {sucesso && <p className={styles.sucesso}>Dados salvos com sucesso.</p>}

        <div className={styles.actions}>
          <button className={styles.btnNovo} onClick={handleSalvar} disabled={saving}>
            {saving ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}
