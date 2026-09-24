import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { getFiscal, updateFiscal, testarCertificado } from "../api/configuracaoFiscal";
import styles from "./UsuarioConfiguracoesFiscaisPage.module.css";

// Item 4.1: no desktop o usuário escolhe o .pfx com o diálogo nativo do
// sistema (Electron). No navegador o campo de caminho continua manual.
const electron = typeof window !== "undefined" ? window.electronAPI : undefined;

const UFS = [
  "AC",
  "AL",
  "AP",
  "AM",
  "BA",
  "CE",
  "DF",
  "ES",
  "GO",
  "MA",
  "MT",
  "MS",
  "MG",
  "PA",
  "PB",
  "PR",
  "PE",
  "PI",
  "RJ",
  "RN",
  "RS",
  "RO",
  "RR",
  "SC",
  "SP",
  "SE",
  "TO",
];

const VAZIO = {
  regime_tributario: "Simples Nacional",
  uf_emitente: "RS",
  ambiente_sefaz: "Homologacao",
  certificado_path: "",
  certificado_senha: "",
  nfe_serie_padrao: "001",
  nfe_numero_atual: 0,
  nfce_serie_padrao: "002",
  nfce_numero_atual: 0,
};

export default function UsuarioConfiguracoesFiscaisPage() {
  const navigate = useNavigate();

  const [form, setForm] = useState(VAZIO);
  const [temSenhaSalva, setTemSenhaSalva] = useState(false);
  const [certificadoValido, setCertificadoValido] = useState(false);
  const [mostrarSenha, setMostrarSenha] = useState(false);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState(null);
  const [sucesso, setSucesso] = useState(false);
  const [testando, setTestando] = useState(false);
  const [resultadoTeste, setResultadoTeste] = useState(null);

  useEffect(() => {
    getFiscal()
      .then((data) => {
        if (!data) return;
        setForm({
          regime_tributario: data.regime_tributario,
          uf_emitente: data.uf_emitente,
          ambiente_sefaz: data.ambiente_sefaz,
          certificado_path: data.certificado_path || "",
          certificado_senha: "",
          nfe_serie_padrao: data.nfe_serie_padrao,
          nfe_numero_atual: data.nfe_numero_atual,
          nfce_serie_padrao: data.nfce_serie_padrao,
          nfce_numero_atual: data.nfce_numero_atual,
        });
        setTemSenhaSalva(Boolean(data.certificado_senha));
        setCertificadoValido(Boolean(data.certificado_valido));
      })
      .catch(() => {});
  }, []);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  // Item 4.1: preenche o caminho com o arquivo escolhido no diálogo nativo.
  const handleSelecionarCertificado = async () => {
    const caminho = await electron.selecionarCertificado();
    if (caminho) setForm((f) => ({ ...f, certificado_path: caminho }));
  };

  const handleSalvar = async () => {
    setErro(null);
    setSucesso(false);
    setSaving(true);
    try {
      const payload = {
        regime_tributario: form.regime_tributario,
        uf_emitente: form.uf_emitente,
        ambiente_sefaz: form.ambiente_sefaz,
        certificado_path: form.certificado_path,
        nfe_serie_padrao: form.nfe_serie_padrao,
        nfe_numero_atual: parseInt(form.nfe_numero_atual, 10) || 0,
        nfce_serie_padrao: form.nfce_serie_padrao,
        nfce_numero_atual: parseInt(form.nfce_numero_atual, 10) || 0,
      };
      if (form.certificado_senha) payload.certificado_senha = form.certificado_senha;

      const data = await updateFiscal(payload);
      setTemSenhaSalva(Boolean(data.certificado_senha));
      setCertificadoValido(Boolean(data.certificado_valido));
      setForm((f) => ({ ...f, certificado_senha: "" }));
      setSucesso(true);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleTestar = async () => {
    setResultadoTeste(null);
    setTestando(true);
    try {
      const r = await testarCertificado(form.certificado_path, form.certificado_senha);
      setResultadoTeste(r);
    } catch (e) {
      setResultadoTeste({ valido: false, erro: e.message });
    } finally {
      setTestando(false);
    }
  };

  const podeTestar = form.certificado_path.trim() && form.certificado_senha.trim() && !testando;

  return (
    <div className={styles.page}>
      <button className={styles.btnBack} onClick={() => navigate("/usuario/configuracoes")}>
        Voltar
      </button>

      <h1 className={styles.title}>Configurações Fiscais</h1>

      <div className={styles.card}>
        {/* EMPRESA */}
        <div className={styles.secao}>
          <p className={styles.secLabel}>Empresa</p>
          <div className={styles.grid2}>
            <label className={styles.field}>
              <span>Regime Tributário</span>
              <select
                className={styles.select}
                value={form.regime_tributario}
                onChange={set("regime_tributario")}
              >
                <option value="Simples Nacional">Simples Nacional</option>
                <option value="Lucro Presumido">Lucro Presumido</option>
                <option value="Lucro Real">Lucro Real</option>
              </select>
            </label>
            <label className={styles.field}>
              <span>UF Emitente</span>
              <select
                className={styles.select}
                value={form.uf_emitente}
                onChange={set("uf_emitente")}
              >
                {UFS.map((uf) => (
                  <option key={uf} value={uf}>
                    {uf}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.field}>
              <span>Ambiente SEFAZ</span>
              <select
                className={styles.select}
                value={form.ambiente_sefaz}
                onChange={set("ambiente_sefaz")}
              >
                <option value="Homologacao">Homologação</option>
                <option value="Producao">Produção</option>
              </select>
              {form.ambiente_sefaz === "Producao" && (
                <span className={styles.badgeWarning}>
                  Atenção: em produção as notas têm valor fiscal real
                </span>
              )}
            </label>
          </div>
        </div>

        {/* CERTIFICADO DIGITAL A1 */}
        <div className={styles.secao}>
          <p className={styles.secLabel}>Certificado Digital A1</p>
          <div className={styles.grid2}>
            <label className={styles.field}>
              <span>Caminho do arquivo .pfx</span>
              <input
                className={styles.input}
                placeholder="C:\Certificados\empresa.pfx"
                value={form.certificado_path}
                onChange={set("certificado_path")}
              />
              {electron?.selecionarCertificado && (
                <button
                  type="button"
                  className={styles.btnSecondary}
                  onClick={handleSelecionarCertificado}
                  style={{ marginTop: 8 }}
                >
                  Selecionar arquivo…
                </button>
              )}
              <p className={styles.hint}>
                Escolha o arquivo do certificado digital no computador (fora da pasta do projeto)
              </p>
            </label>
            <label className={styles.field}>
              <span>Senha do certificado</span>
              <div className={styles.passwordWrap}>
                <input
                  type={mostrarSenha ? "text" : "password"}
                  className={styles.input}
                  placeholder={temSenhaSalva ? "••••••••" : ""}
                  value={form.certificado_senha}
                  onChange={set("certificado_senha")}
                />
                <button
                  type="button"
                  className={styles.btnEye}
                  onClick={() => setMostrarSenha((v) => !v)}
                  aria-label={mostrarSenha ? "Ocultar senha" : "Mostrar senha"}
                >
                  {mostrarSenha ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </label>
          </div>

          <div className={styles.statusRow}>
            {!form.certificado_path.trim() ? (
              <span className={`${styles.badge} ${styles.badgeNeutral}`}>
                Nenhum certificado configurado
              </span>
            ) : certificadoValido ? (
              <span className={`${styles.badge} ${styles.badgeSuccess}`}>
                Certificado encontrado
              </span>
            ) : (
              <span className={`${styles.badge} ${styles.badgeDanger}`}>
                Arquivo não encontrado
              </span>
            )}
          </div>

          <button
            type="button"
            className={styles.btnSecondary}
            disabled={!podeTestar}
            onClick={handleTestar}
          >
            {testando ? "Testando…" : "Testar Certificado"}
          </button>

          {resultadoTeste && (
            <p
              className={`${styles.testeResultado} ${resultadoTeste.valido ? styles.testeSucesso : styles.testeErro}`}
            >
              {resultadoTeste.valido
                ? `Válido — Titular: ${resultadoTeste.titular || "—"} | Vence: ${resultadoTeste.validade || "—"}`
                : resultadoTeste.erro}
            </p>
          )}
        </div>

        {/* NUMERAÇÃO NF-e */}
        <div className={`${styles.secao} ${styles.secaoLast}`}>
          <p className={styles.secLabel}>Numeração NF-e</p>
          <div className={styles.grid2}>
            <label className={styles.field}>
              <span>Série NF-e padrão</span>
              <input
                className={styles.input}
                value={form.nfe_serie_padrao}
                onChange={set("nfe_serie_padrao")}
              />
            </label>
            <label className={styles.field}>
              <span>Número atual NF-e</span>
              <input
                type="number"
                min="0"
                className={styles.input}
                value={form.nfe_numero_atual}
                onChange={set("nfe_numero_atual")}
              />
              <p className={styles.hint}>
                O próximo número emitido será {(parseInt(form.nfe_numero_atual, 10) || 0) + 1}
              </p>
            </label>
            <label className={styles.field}>
              <span>Série NFC-e padrão</span>
              <input
                className={styles.input}
                value={form.nfce_serie_padrao}
                onChange={set("nfce_serie_padrao")}
              />
            </label>
            <label className={styles.field}>
              <span>Número atual NFC-e</span>
              <input
                type="number"
                min="0"
                className={styles.input}
                value={form.nfce_numero_atual}
                onChange={set("nfce_numero_atual")}
              />
              <p className={styles.hint}>
                O próximo número emitido será {(parseInt(form.nfce_numero_atual, 10) || 0) + 1}
              </p>
            </label>
          </div>
        </div>

        {erro && <p className={styles.erro}>{erro}</p>}
        {sucesso && <p className={styles.sucesso}>Configurações fiscais salvas.</p>}

        <div className={styles.actions}>
          <button className={styles.btnNovo} onClick={handleSalvar} disabled={saving}>
            {saving ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}
