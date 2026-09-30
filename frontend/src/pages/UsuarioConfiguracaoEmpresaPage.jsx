import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  getConfiguracaoEmpresa,
  updateConfiguracaoEmpresa,
  uploadLogoEmpresa,
} from "../api/configuracaoEmpresa";
import { atualizarConfigProducao } from "../api/encaixes";
import { getConfigProducao } from "../api/ordensCorte";
import { urlAbsoluta } from "../services/config";
import { buscarEnderecoPorCep } from "../utils/cepIbge";
import { useAuth } from "../auth/useAuth";
import styles from "./UsuarioConfiguracaoEmpresaPage.module.css";

const MODULO = "configuracoes_editar";

const CAMPOS_EMPRESA = [
  { name: "razao_social", label: "Razão Social", full: true, upper: true },
  { name: "cnpj", label: "CNPJ" },
  { name: "ie", label: "Inscrição Estadual", upper: true },
];

const CAMPOS_CONTATO = [
  { name: "telefone1", label: "Telefone 1" },
  { name: "telefone2", label: "Telefone 2" },
  { name: "email", label: "E-mail", type: "email" },
  { name: "site", label: "Site", type: "url" },
];

const EMPRESA_VAZIO = {
  razao_social: "",
  cnpj: "",
  ie: "",
  endereco: "",
  endereco_numero: "",
  endereco_bairro: "",
  codigo_ibge_municipio: "",
  cidade: "",
  cep: "",
  telefone1: "",
  telefone2: "",
  email: "",
  site: "",
};

// Configurações > Produção — ver ordens_corte.configuracao-producao.
const PRODUCAO_PADRAO = {
  comprimento_max_mesa_cm: "200",
  alerta_economia_pct: "5",
  tempo_maximo_oc_s: "300",
};
const MESA_MIN = 50;
const MESA_MAX = 2000;
const TEMPO_MIN = 30;
const TEMPO_MAX = 7200;

const stripDigits = (v) => (v || "").replace(/\D/g, "");
const formatCep = (v) => {
  const d = stripDigits(v).slice(0, 8);
  return d.length <= 5 ? d : `${d.slice(0, 5)}-${d.slice(5)}`;
};

export default function UsuarioConfiguracaoEmpresaPage() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const podeEditar = hasPermission(MODULO, "ver");
  const [form, setForm] = useState(EMPRESA_VAZIO);
  const [logoUrl, setLogoUrl] = useState(null);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState(null);
  const [sucesso, setSucesso] = useState(false);
  const [cepStatus, setCepStatus] = useState(null);
  const fileRef = useRef();
  const [producao, setProducao] = useState(PRODUCAO_PADRAO);
  const [salvandoProd, setSalvandoProd] = useState(false);
  const [erroProd, setErroProd] = useState(null);
  const [sucessoProd, setSucessoProd] = useState(false);

  useEffect(() => {
    getConfiguracaoEmpresa()
      .then((d) => {
        if (!d) return;
        setForm({
          razao_social: d.razao_social || "",
          cnpj: d.cnpj || "",
          ie: d.ie || "",
          endereco: d.endereco || "",
          endereco_numero: d.endereco_numero || "",
          endereco_bairro: d.endereco_bairro || "",
          codigo_ibge_municipio: d.codigo_ibge_municipio || "",
          cidade: d.cidade || "",
          cep: formatCep(d.cep || ""),
          telefone1: d.telefone1 || "",
          telefone2: d.telefone2 || "",
          email: d.email || "",
          site: d.site || "",
        });
        if (d.logo_url) setLogoUrl(urlAbsoluta(d.logo_url));
      })
      .catch(() => {});
    getConfigProducao()
      .then((c) =>
        setProducao({
          comprimento_max_mesa_cm: String(c.comprimento_max_mesa_cm),
          alerta_economia_pct: String(c.alerta_economia_pct),
          tempo_maximo_oc_s: String(c.tempo_maximo_oc_s),
        })
      )
      .catch((e) => setErroProd(e.message));
  }, []);

  const salvarProducao = async () => {
    const mesa = Number(producao.comprimento_max_mesa_cm);
    const pct = Number(String(producao.alerta_economia_pct).replace(",", "."));
    if (!Number.isInteger(mesa) || mesa < MESA_MIN || mesa > MESA_MAX) {
      setErroProd(`O comprimento da mesa deve ser um inteiro entre ${MESA_MIN} e ${MESA_MAX} cm.`);
      return;
    }
    if (!Number.isFinite(pct) || pct < 0 || pct > 100) {
      setErroProd("A economia mínima deve estar entre 0 e 100%.");
      return;
    }
    const tempo = Number(producao.tempo_maximo_oc_s);
    if (!Number.isInteger(tempo) || tempo < TEMPO_MIN || tempo > TEMPO_MAX) {
      setErroProd(`O tempo limite deve ser um inteiro entre ${TEMPO_MIN} e ${TEMPO_MAX} segundos.`);
      return;
    }
    setSalvandoProd(true);
    setErroProd(null);
    setSucessoProd(false);
    try {
      const c = await atualizarConfigProducao({
        comprimento_max_mesa_cm: mesa,
        alerta_economia_pct: pct,
        tempo_maximo_oc_s: tempo,
      });
      setProducao({
        comprimento_max_mesa_cm: String(c.comprimento_max_mesa_cm),
        alerta_economia_pct: String(c.alerta_economia_pct),
        tempo_maximo_oc_s: String(c.tempo_maximo_oc_s),
      });
      setSucessoProd(true);
    } catch (e) {
      setErroProd(e.message);
    } finally {
      setSalvandoProd(false);
    }
  };

  const mudarProducao = (campo) => (e) => {
    setProducao((p) => ({ ...p, [campo]: e.target.value }));
    setSucessoProd(false);
  };

  const consultarCep = async () => {
    const digits = stripDigits(form.cep);
    if (digits.length !== 8) {
      setCepStatus("invalido");
      return;
    }

    setCepStatus("consultando");
    try {
      const r = await buscarEnderecoPorCep(digits);
      if (!r.logradouro && !r.bairro && !r.cidade) {
        setCepStatus("nao_encontrado");
        return;
      }

      setForm((f) => ({
        ...f,
        endereco: r.logradouro || f.endereco,
        endereco_bairro: r.bairro || f.endereco_bairro,
        cidade: r.cidade || f.cidade,
        codigo_ibge_municipio: r.codigo_ibge || f.codigo_ibge_municipio,
      }));
      setCepStatus("preenchido");
    } catch {
      setCepStatus("erro");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setErro(null);
    setSucesso(false);
    try {
      await updateConfiguracaoEmpresa({ ...form, cep: stripDigits(form.cep) || null });
      setSucesso(true);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleLogo = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("logo", file);
    try {
      const d = await uploadLogoEmpresa(fd);
      if (d?.logo_url) setLogoUrl(urlAbsoluta(d.logo_url));
    } catch (e) {
      setErro(e.message);
    }
  };

  const renderCampo = ({ name, label, upper, type }) => (
    <label key={name} className={styles.field}>
      <span>{label}</span>
      <input
        className={upper ? `${styles.input} sc-upper` : styles.input}
        type={type}
        name={name}
        value={form[name]}
        disabled={!podeEditar}
        onChange={(e) =>
          setForm((f) => ({ ...f, [name]: upper ? e.target.value.toUpperCase() : e.target.value }))
        }
      />
    </label>
  );

  return (
    <div className={styles.page}>
      <button className={styles.btnBack} onClick={() => navigate("/usuario/configuracoes")}>
        Voltar
      </button>

      <h1 className={styles.title}>Dados da Empresa</h1>

      <div className={styles.card}>
        <p className={styles.secLabel}>Empresa</p>
        {renderCampo(CAMPOS_EMPRESA[0])}
        <div className={styles.grid2}>
          {renderCampo(CAMPOS_EMPRESA[1])}
          {renderCampo(CAMPOS_EMPRESA[2])}
        </div>

        <p className={styles.secLabel} style={{ marginTop: "1.5rem" }}>
          Endereço
        </p>
        <div className={styles.cepRow}>
          <label className={styles.field} style={{ flex: 1 }}>
            <span>CEP</span>
            <input
              className={styles.input}
              value={form.cep}
              disabled={!podeEditar}
              onChange={(e) => {
                setForm((f) => ({ ...f, cep: formatCep(e.target.value) }));
                setCepStatus(null);
              }}
              placeholder="00000-000"
              maxLength={9}
            />
          </label>
          {podeEditar && (
            <button
              type="button"
              className={styles.btnSecondary}
              onClick={consultarCep}
              disabled={cepStatus === "consultando"}
            >
              {cepStatus === "consultando" ? "Consultando…" : "Buscar CEP"}
            </button>
          )}
        </div>
        {cepStatus === "invalido" && (
          <p className={styles.erro}>CEP inválido — informe 8 dígitos numéricos.</p>
        )}
        {cepStatus === "nao_encontrado" && (
          <p className={styles.erro}>CEP não encontrado. Preencha o endereço manualmente.</p>
        )}
        {cepStatus === "erro" && <p className={styles.erro}>Erro ao consultar o CEP.</p>}
        {cepStatus === "preenchido" && (
          <p className={styles.sucesso}>Endereço preenchido. Revise antes de salvar.</p>
        )}

        {renderCampo({ name: "endereco", label: "Endereço", upper: true })}
        <div className={styles.grid2}>
          {renderCampo({ name: "endereco_numero", label: "Número", upper: true })}
          {renderCampo({ name: "endereco_bairro", label: "Bairro", upper: true })}
        </div>
        <div className={styles.grid2}>
          {renderCampo({ name: "cidade", label: "Cidade", upper: true })}
        </div>

        <p className={styles.secLabel} style={{ marginTop: "1.5rem" }}>
          Contato
        </p>
        <div className={styles.grid2}>{CAMPOS_CONTATO.map(renderCampo)}</div>

        <p className={styles.secLabel} style={{ marginTop: "1.5rem" }}>
          Logo
        </p>
        <div className={styles.logoRow}>
          <div className={styles.logoBox}>
            {logoUrl ? (
              <img src={logoUrl} alt="Logo" className={styles.logoImg} />
            ) : (
              <span className={styles.logoVazio}>Sem logo</span>
            )}
          </div>
          <div className={styles.logoInfo}>
            <p className={styles.logoLabel}>Logo da empresa</p>
            {podeEditar && (
              <button className={styles.btnSecondary} onClick={() => fileRef.current?.click()}>
                Escolher logo
              </button>
            )}
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className={styles.hidden}
              onChange={handleLogo}
            />
            <p className={styles.hint}>PNG ou JPG — recomendado 300 × 120 px</p>
          </div>
        </div>

        {erro && <p className={styles.erro}>{erro}</p>}
        {sucesso && <p className={styles.sucesso}>Dados salvos com sucesso.</p>}

        {podeEditar && (
          <div className={styles.actions}>
            <button className={styles.btnNovo} onClick={handleSave} disabled={saving}>
              {saving ? "Salvando…" : "Salvar"}
            </button>
          </div>
        )}
      </div>

      {/* ── Produção: alerta de mesa maior ── */}
      <div className={styles.card} style={{ marginTop: "1.25rem" }}>
        <p className={styles.secLabel}>Produção</p>
        <div className={styles.grid2}>
          <label className={styles.field}>
            <span>Comprimento máximo da mesa (cm)</span>
            <input
              className={styles.input}
              type="number"
              inputMode="numeric"
              min={MESA_MIN}
              max={MESA_MAX}
              step={1}
              value={producao.comprimento_max_mesa_cm}
              disabled={!podeEditar}
              onChange={mudarProducao("comprimento_max_mesa_cm")}
            />
            <span className={styles.hint}>
              Usado para sugerir enfestos maiores quando economizam tecido
            </span>
          </label>
          <label className={styles.field}>
            <span>Alertar economia a partir de (%)</span>
            <input
              className={styles.input}
              type="number"
              inputMode="decimal"
              min={0}
              max={100}
              step={0.5}
              value={producao.alerta_economia_pct}
              disabled={!podeEditar}
              onChange={mudarProducao("alerta_economia_pct")}
            />
          </label>
          <label className={styles.field}>
            <span>Tempo limite da ordem de corte (s)</span>
            <input
              className={styles.input}
              type="number"
              inputMode="numeric"
              min={TEMPO_MIN}
              max={TEMPO_MAX}
              step={30}
              value={producao.tempo_maximo_oc_s}
              disabled={!podeEditar}
              onChange={mudarProducao("tempo_maximo_oc_s")}
            />
            <span className={styles.hint}>
              Orçamento da qualidade Automático: cada risco começa no perfil Rápido e sobe um
              degrau (Equilibrado, Máximo) enquanto sobrar tempo. Mais tempo, mais qualidade de
              encaixe. O limite vale para a ordem inteira — a comparação de enfestos já consome
              parte dele. Se nem o perfil mais barato couber no que sobrar, a tela avisa que a
              geração vai passar do prazo.
            </span>
          </label>
        </div>

        {erroProd && <p className={styles.erro}>{erroProd}</p>}
        {sucessoProd && <p className={styles.sucesso}>Configurações de produção salvas.</p>}

        {podeEditar && (
          <div className={styles.actions}>
            <button className={styles.btnNovo} onClick={salvarProducao} disabled={salvandoProd}>
              {salvandoProd ? "Salvando…" : "Salvar produção"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
