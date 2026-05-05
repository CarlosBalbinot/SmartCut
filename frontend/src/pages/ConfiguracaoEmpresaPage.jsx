import { useState, useEffect, useRef } from "react";
import { configuracaoEmpresaApi } from "../services/api";
import styles from "./ConfiguracaoEmpresaPage.module.css";

const CAMPOS = [
  { name: "razao_social", label: "Razão Social" },
  { name: "cnpj",         label: "CNPJ"         },
  { name: "ie",           label: "Inscrição Estadual" },
  { name: "endereco",     label: "Endereço"      },
  { name: "cidade",       label: "Cidade"        },
  { name: "cep",          label: "CEP"           },
  { name: "tel1",         label: "Telefone 1"    },
  { name: "tel2",         label: "Telefone 2"    },
  { name: "email",        label: "E-mail"        },
  { name: "site",         label: "Site"          },
];

const VAZIO = { razao_social: "", cnpj: "", ie: "", endereco: "", cidade: "", cep: "", tel1: "", tel2: "", email: "", site: "" };

export default function ConfiguracaoEmpresaPage() {
  const [form, setForm]       = useState(VAZIO);
  const [logoUrl, setLogoUrl] = useState(null);
  const [saving, setSaving]   = useState(false);
  const [msg, setMsg]         = useState(null);
  const fileRef               = useRef();

  useEffect(() => {
    configuracaoEmpresaApi.get().then((d) => {
      if (!d) return;
      setForm({
        razao_social: d.razao_social || "",
        cnpj:         d.cnpj         || "",
        ie:           d.ie           || "",
        endereco:     d.endereco     || "",
        cidade:       d.cidade       || "",
        cep:          d.cep          || "",
        tel1:         d.tel1         || "",
        tel2:         d.tel2         || "",
        email:        d.email        || "",
        site:         d.site         || "",
      });
      if (d.logo_url) setLogoUrl(d.logo_url);
    }).catch(() => {});
  }, []);

  const handleChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const handleSave = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await configuracaoEmpresaApi.update(form);
      setMsg({ type: "success", text: "Dados salvos com sucesso." });
    } catch (e) {
      setMsg({ type: "error", text: e.message });
    } finally {
      setSaving(false);
    }
  };

  const handleLogoChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("logo", file);
    try {
      const d = await configuracaoEmpresaApi.uploadLogo(fd);
      if (d?.logo_url) setLogoUrl(d.logo_url);
    } catch (e) {
      setMsg({ type: "error", text: e.message });
    }
  };

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Configuração da Empresa</h1>

      <div className={styles.card}>
        {/* Logo */}
        <div className={styles.logoRow}>
          <div className={styles.logoPreview}>
            {logoUrl
              ? <img src={logoUrl} alt="Logo da empresa" className={styles.logoImg} />
              : <span className={styles.logoPlaceholder}>Sem logo</span>}
          </div>
          <div className={styles.logoInfo}>
            <p className={styles.logoLabel}>Logo da empresa</p>
            <button className={styles.btnSecondary} onClick={() => fileRef.current?.click()}>
              Escolher logo
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className={styles.hidden}
              onChange={handleLogoChange}
            />
            <p className={styles.logoHint}>PNG ou JPG — recomendado 300 × 120 px</p>
          </div>
        </div>

        {/* Grid de campos */}
        <div className={styles.grid}>
          {CAMPOS.map(({ name, label }) => (
            <label key={name} className={styles.field}>
              <span className={styles.fieldLabel}>{label}</span>
              <input
                name={name}
                value={form[name]}
                onChange={handleChange}
                className={styles.input}
              />
            </label>
          ))}
        </div>

        {msg && (
          <p className={msg.type === "success" ? styles.msgSuccess : styles.msgError}>
            {msg.text}
          </p>
        )}

        <div className={styles.footer}>
          <button className={styles.btnPrimary} onClick={handleSave} disabled={saving}>
            {saving ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}
