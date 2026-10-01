import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import styles from "./LoginPage.module.css";
import { useAuth } from "../auth/useAuth";
import { erroDaResposta } from "../services/api";
import { API_BASE } from "../services/config";
import appIcon from "../assets/android-chrome-512x512.png";

const AUTH_BASE = `${API_BASE}/api/v1/auth`;

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [checking, setChecking] = useState(true);
  const [primeiroAcesso, setPrimeiroAcesso] = useState(false);

  const [username, setUsername] = useState("");
  const [nomeCompleto, setNomeCompleto] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmarSenha, setConfirmarSenha] = useState("");
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    fetch(`${AUTH_BASE}/primeiro-acesso`)
      .then((res) => res.json())
      .then((json) => setPrimeiroAcesso(!!json.primeiro_acesso))
      .catch(() => setPrimeiroAcesso(false))
      .finally(() => setChecking(false));
  }, []);

  // Aviso de Caps Lock nos campos de senha (a senha diferencia maiúsculas).
  const detectarCapsLock = (e) => {
    if (e.getModifierState) setCapsLock(e.getModifierState("CapsLock"));
  };
  const capsLockProps = {
    onKeyDown: detectarCapsLock,
    onKeyUp: detectarCapsLock,
    onMouseDown: detectarCapsLock,
    onBlur: () => setCapsLock(false),
  };
  const avisoCapsLock = capsLock && <div className={styles.capsLock}>Caps Lock ativado</div>;

  const handleUsernameChange = (e) => {
    setUsername(e.target.value.toLowerCase().replace(/\s/g, ""));
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setErro("");
    if (!username || !senha) {
      setErro("Informe usuário e senha.");
      return;
    }
    setEnviando(true);
    try {
      await login(username, senha);
      navigate("/");
    } catch (err) {
      setErro(err.message || "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  };

  const handleSetupSubmit = async (e) => {
    e.preventDefault();
    setErro("");
    if (!username || !nomeCompleto || !senha) {
      setErro("Preencha todos os campos.");
      return;
    }
    if (senha !== confirmarSenha) {
      setErro("As senhas não coincidem.");
      return;
    }
    setEnviando(true);
    try {
      const res = await fetch(`${AUTH_BASE}/setup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, nome_completo: nomeCompleto, senha }),
      });
      const json = await res.json();
      if (!res.ok) {
        throw erroDaResposta(res, json);
      }
      await login(username, senha);
      navigate("/");
    } catch (err) {
      setErro(err.message || "Não foi possível criar o administrador.");
    } finally {
      setEnviando(false);
    }
  };

  if (checking) {
    return (
      <div className={styles.checkingWrap}>
        <div className={styles.spinner} />
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.leftPanel}>
        <div className={styles.circleLarge} />
        <div className={styles.circleSmall} />
        <div className={styles.leftContent}>
          <img src={appIcon} alt="SmartCut" className={styles.logoImg} />
          <div className={styles.brandName}>SmartCut</div>
        </div>
      </div>

      <div className={styles.rightPanel}>
        <div className={styles.formWrap}>
          <h1 className={styles.greeting}>Bem-vindo</h1>
          <p className={styles.greetingSub}>
            {primeiroAcesso
              ? "Configure o primeiro administrador do sistema"
              : "Faça login para continuar"}
          </p>

          {primeiroAcesso ? (
            <form onSubmit={handleSetupSubmit}>
              <div className={styles.field}>
                <label className={styles.label} htmlFor="setup-username">
                  Usuário
                </label>
                <input
                  id="setup-username"
                  className={styles.input}
                  value={username}
                  onChange={handleUsernameChange}
                  autoComplete="username"
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label} htmlFor="setup-nome">
                  Nome completo
                </label>
                <input
                  id="setup-nome"
                  className={`${styles.input} sc-upper`}
                  value={nomeCompleto}
                  onChange={(e) => setNomeCompleto(e.target.value.toUpperCase())}
                  autoComplete="name"
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label} htmlFor="setup-senha">
                  Senha
                </label>
                <div className={styles.passwordRow}>
                  <input
                    id="setup-senha"
                    type={mostrarSenha ? "text" : "password"}
                    className={styles.input}
                    value={senha}
                    onChange={(e) => setSenha(e.target.value)}
                    autoComplete="new-password"
                    {...capsLockProps}
                  />
                  <button
                    type="button"
                    className={styles.toggleBtn}
                    onClick={() => setMostrarSenha((v) => !v)}
                    tabIndex={-1}
                    aria-label={mostrarSenha ? "Ocultar senha" : "Mostrar senha"}
                  >
                    {mostrarSenha ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {avisoCapsLock}
              </div>
              <div className={styles.field}>
                <label className={styles.label} htmlFor="setup-confirmar">
                  Confirmar senha
                </label>
                <input
                  id="setup-confirmar"
                  type={mostrarSenha ? "text" : "password"}
                  className={styles.input}
                  value={confirmarSenha}
                  onChange={(e) => setConfirmarSenha(e.target.value)}
                  autoComplete="new-password"
                  {...capsLockProps}
                />
              </div>
              {erro && <div className={styles.error}>{erro}</div>}
              <button type="submit" className={styles.submitBtn} disabled={enviando}>
                {enviando ? "Criando..." : "Criar administrador"}
              </button>
            </form>
          ) : (
            <form onSubmit={handleLoginSubmit}>
              <div className={styles.field}>
                <label className={styles.label} htmlFor="login-username">
                  Usuário
                </label>
                <input
                  id="login-username"
                  className={styles.input}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  autoFocus
                />
              </div>
              <div className={styles.field}>
                <label className={styles.label} htmlFor="login-senha">
                  Senha
                </label>
                <div className={styles.passwordRow}>
                  <input
                    id="login-senha"
                    type={mostrarSenha ? "text" : "password"}
                    className={styles.input}
                    value={senha}
                    onChange={(e) => setSenha(e.target.value)}
                    autoComplete="current-password"
                    {...capsLockProps}
                  />
                  <button
                    type="button"
                    className={styles.toggleBtn}
                    onClick={() => setMostrarSenha((v) => !v)}
                    tabIndex={-1}
                    aria-label={mostrarSenha ? "Ocultar senha" : "Mostrar senha"}
                  >
                    {mostrarSenha ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {avisoCapsLock}
              </div>
              {erro && <div className={styles.error}>{erro}</div>}
              <button type="submit" className={styles.submitBtn} disabled={enviando}>
                {enviando ? "Entrando..." : "Entrar"}
              </button>
            </form>
          )}

          <div className={styles.footer}>SmartCut © 2026</div>
        </div>
      </div>
    </div>
  );
}
