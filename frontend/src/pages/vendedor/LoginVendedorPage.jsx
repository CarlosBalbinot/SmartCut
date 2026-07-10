import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import styles from "./LoginVendedorPage.module.css";
import { API_BASE } from "../../services/config";

export default function LoginVendedorPage() {
  const [username, setUsername] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [loading, setLoading] = useState(false);
  const [logoUrl, setLogoUrl] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/configuracao-empresa/`)
      .then((r) => r.json())
      .then((j) => {
        const d = j.data ?? j;
        if (d?.logo_url) setLogoUrl(d.logo_url);
      })
      .catch(() => {});
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setErro("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/vendedor/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, senha }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || json.detail || "Credenciais inválidas");
      localStorage.setItem("smartcut_vendedor_token", json.data.token);
      localStorage.setItem("smartcut_vendedor_info", JSON.stringify(json.data.vendedor || {}));
      navigate("/vendedor/dashboard");
    } catch (err) {
      setErro(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.logoBox}>
        {logoUrl ? (
          <img src={logoUrl} alt="Logo" className={styles.logoImg} />
        ) : (
          <span className={styles.logoFallback}>Vaidosa Fitness</span>
        )}
      </div>
      <div className={styles.card}>
        <h1 className={styles.titulo}>Área do Vendedor</h1>
        <form onSubmit={handleSubmit} className={styles.form}>
          <input
            className={styles.input}
            type="text"
            placeholder="Usuário"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <input
            className={styles.input}
            type="password"
            placeholder="Senha"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            autoComplete="current-password"
            required
          />
          {erro && <p className={styles.erro}>{erro}</p>}
          <button className={styles.botao} type="submit" disabled={loading}>
            {loading ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
