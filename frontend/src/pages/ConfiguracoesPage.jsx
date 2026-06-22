import { useState, useEffect, useRef } from "react";
import {
  catalogosApi, configuracaoEmpresaApi, gruposApi, leadsApi,
  precificacoesApi, tabelasPrecoApi, vendedoresApi,
} from "../services/api";
import styles from "./ConfiguracoesPage.module.css";

// ── Menu interno ──────────────────────────────────────────────────────────────

const MENU = [
  { id: "empresa",    label: "Dados da Empresa"     },
  { id: "geral",      label: "Configurações Gerais"  },
  { id: "tabelas",    label: "Tabelas de Preço"      },
  { id: "vendedores", label: "Vendedores"             },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

const n = (v) => parseFloat(v) || 0;

const fmtUnit = (v) =>
  v > 0
    ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 4 }).format(v)
    : "—";

const fmtMoeda = (v) =>
  v > 0
    ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v)
    : "—";

const fmtR = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(parseFloat(v) || 0);

const fmtPct = (v) => `${(parseFloat(v) * 100).toFixed(0)}%`;

// ── Inline style constants ────────────────────────────────────────────────────

const MODAL_OVERLAY = {
  position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
  display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
};
const MODAL_BOX = {
  background: "var(--sc-surface)", borderRadius: 10, padding: 24,
  width: 380, maxWidth: "90vw", boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
};
const TABLE_STYLE = { width: "100%", borderCollapse: "collapse", fontSize: 14 };
const TH_STYLE = {
  textAlign: "left", padding: "8px 10px", fontWeight: 600, fontSize: 12,
  borderBottom: "2px solid var(--sc-border)", color: "var(--sc-text-muted)",
  textTransform: "uppercase", letterSpacing: "0.04em",
};
const TD_STYLE = {
  padding: "8px 10px", borderBottom: "1px solid var(--sc-border)", verticalAlign: "middle",
};
const BTN_LINK = {
  background: "none", border: "none", cursor: "pointer",
  color: "var(--sc-text-secondary)", textDecoration: "underline", padding: 0, fontSize: 13,
};
const BTN_LINK_DANGER = {
  background: "none", border: "none", cursor: "pointer",
  color: "#c0392b", textDecoration: "underline", padding: 0, fontSize: 13,
};
const BTN_DANGER_SM = {
  background: "#c0392b", color: "#fff", border: "none", borderRadius: 4,
  padding: "2px 8px", cursor: "pointer", fontSize: 12,
};
const DROPDOWN_STYLE = {
  position: "absolute", top: "100%", left: 0, right: 0,
  background: "var(--sc-surface)",
  border: "1px solid var(--sc-border)", borderRadius: 6,
  boxShadow: "0 4px 16px rgba(0,0,0,0.1)", zIndex: 10,
  listStyle: "none", margin: 0, padding: 0, maxHeight: 240, overflowY: "auto",
};
const DROPDOWN_ITEM_STYLE = {
  padding: "10px 12px", cursor: "pointer",
  borderBottom: "1px solid var(--sc-border)", fontSize: 14,
};

// ── Custos estado inicial ─────────────────────────────────────────────────────

const CUSTOS_VAZIO = {
  custo_rolo_overlock: "", metros_rolo_overlock: "",
  custo_rolo_reta: "", metros_rolo_reta: "",
  custo_saquinho_lote: "", unidades_saquinho_lote: "",
  custo_caixa: "", pecas_por_caixa: "",
  distancia_costureira_km: "", num_viagens: "",
  consumo_veiculo_km_l: "", preco_combustivel: "",
};

// ── Componente raiz ───────────────────────────────────────────────────────────

export default function ConfiguracoesPage() {
  const [active, setActive] = useState("empresa");

  return (
    <div className={styles.page}>
      <nav className={styles.sidebar}>
        <p className={styles.sidebarTitle}>Configurações</p>
        {MENU.map(({ id, label }) => (
          <button
            key={id}
            className={`${styles.menuItem} ${active === id ? styles.menuItemActive : ""}`}
            onClick={() => setActive(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className={styles.panel}>
        {active === "empresa"    && <PanelEmpresa />}
        {active === "geral"      && <PanelGeral />}
        {active === "tabelas"    && <PanelTabelasPreco />}
        {active === "vendedores" && <PanelVendedores />}
      </div>
    </div>
  );
}

// ── Painel: Dados da Empresa ──────────────────────────────────────────────────

const CAMPOS_EMPRESA = [
  { name: "razao_social", label: "Razão Social"       },
  { name: "cnpj",         label: "CNPJ"               },
  { name: "ie",           label: "Inscrição Estadual"  },
  { name: "endereco",     label: "Endereço"            },
  { name: "cidade",       label: "Cidade"              },
  { name: "cep",          label: "CEP"                 },
  { name: "tel1",         label: "Telefone 1"          },
  { name: "tel2",         label: "Telefone 2"          },
  { name: "email",        label: "E-mail"              },
  { name: "site",         label: "Site"                },
];

const EMPRESA_VAZIO = {
  razao_social: "", cnpj: "", ie: "", endereco: "",
  cidade: "", cep: "", tel1: "", tel2: "", email: "", site: "",
};

function PanelEmpresa() {
  const [form, setForm]       = useState(EMPRESA_VAZIO);
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

  const handleSave = async () => {
    setSaving(true); setMsg(null);
    try {
      await configuracaoEmpresaApi.update(form);
      setMsg({ ok: true, text: "Dados salvos com sucesso." });
    } catch (e) {
      setMsg({ ok: false, text: e.message });
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
      const d = await configuracaoEmpresaApi.uploadLogo(fd);
      if (d?.logo_url) setLogoUrl(d.logo_url);
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    }
  };

  return (
    <div className={styles.panelContent}>
      <h2 className={styles.panelTitle}>Dados da Empresa</h2>

      <div className={styles.logoRow}>
        <div className={styles.logoBox}>
          {logoUrl
            ? <img src={logoUrl} alt="Logo" className={styles.logoImg} />
            : <span className={styles.logoVazio}>Sem logo</span>}
        </div>
        <div className={styles.logoInfo}>
          <p className={styles.logoLabel}>Logo da empresa</p>
          <button className={styles.btnSecondary} onClick={() => fileRef.current?.click()}>
            Escolher logo
          </button>
          <input ref={fileRef} type="file" accept="image/*" className={styles.hidden} onChange={handleLogo} />
          <p className={styles.hint}>PNG ou JPG — recomendado 300 × 120 px</p>
        </div>
      </div>

      <div className={styles.grid2}>
        {CAMPOS_EMPRESA.map(({ name, label }) => (
          <label key={name} className={styles.field}>
            <span>{label}</span>
            <input
              className={styles.input}
              name={name}
              value={form[name]}
              onChange={(e) => setForm((f) => ({ ...f, [name]: e.target.value }))}
            />
          </label>
        ))}
      </div>

      <Msg msg={msg} />

      <div className={styles.actions}>
        <button className={styles.btnPrimary} onClick={handleSave} disabled={saving}>
          {saving ? "Salvando…" : "Salvar"}
        </button>
      </div>
    </div>
  );
}

// ── Painel: Configurações Gerais (impostos + insumos + logística) ─────────────

function PanelGeral() {
  const [form, setForm]     = useState({ aliquota_simples: "", custo_etiqueta: "", ...CUSTOS_VAZIO });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg]       = useState(null);

  useEffect(() => {
    Promise.all([
      configuracaoEmpresaApi.get(),
      precificacoesApi.getCustos(),
    ]).then(([emp, custos]) => {
      setForm((prev) => {
        const next = { ...prev };
        if (emp) {
          next.aliquota_simples = emp.aliquota_simples ?? "";
          next.custo_etiqueta   = emp.custo_etiqueta   ?? "";
        }
        if (custos) {
          Object.keys(CUSTOS_VAZIO).forEach((k) => {
            if (custos[k] !== undefined && custos[k] !== null) next[k] = custos[k];
          });
        }
        return next;
      });
    }).catch(() => {});
  }, []);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSave = async () => {
    setSaving(true); setMsg(null);
    try {
      await Promise.all([
        configuracaoEmpresaApi.update({
          aliquota_simples: n(form.aliquota_simples),
          custo_etiqueta:   n(form.custo_etiqueta),
        }),
        precificacoesApi.updateCustos(
          Object.fromEntries(Object.keys(CUSTOS_VAZIO).map((k) => [k, n(form[k])]))
        ),
      ]);
      setMsg({ ok: true, text: "Configurações salvas." });
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    } finally {
      setSaving(false);
    }
  };

  const custoOverlock  = n(form.metros_rolo_overlock)        ? n(form.custo_rolo_overlock) / n(form.metros_rolo_overlock)        : 0;
  const custoLinhaReta = n(form.metros_rolo_reta)            ? n(form.custo_rolo_reta)     / n(form.metros_rolo_reta)            : 0;
  const custoSaquinho  = n(form.unidades_saquinho_lote)      ? n(form.custo_saquinho_lote) / n(form.unidades_saquinho_lote)      : 0;
  const custoCaixa     = n(form.pecas_por_caixa)             ? n(form.custo_caixa)         / n(form.pecas_por_caixa)             : 0;
  const custoGasolina  = n(form.distancia_costureira_km) > 0 && n(form.consumo_veiculo_km_l) > 0
    ? (n(form.distancia_costureira_km) / n(form.consumo_veiculo_km_l)) *
      n(form.preco_combustivel) * n(form.num_viagens)
    : 0;

  return (
    <div className={styles.panelContent}>
      <h2 className={styles.panelTitle}>Configurações Gerais</h2>

      {/* IMPOSTOS */}
      <ConfigSecao titulo="IMPOSTOS">
        <div className={styles.grid2}>
          <label className={styles.field}>
            <span>Alíquota Simples Nacional (%)</span>
            <input type="number" step="0.01" min="0" max="100"
              className={styles.input} value={form.aliquota_simples} onChange={set("aliquota_simples")} />
          </label>
        </div>
      </ConfigSecao>

      {/* INSUMOS */}
      <ConfigSecao titulo="INSUMOS">
        <div className={styles.custoRow} style={{ marginBottom: "1rem" }}>
          <label className={styles.field} style={{ flex: 1 }}>
            <span>Etiqueta (R$)</span>
            <input type="number" step="0.01" min="0"
              className={styles.input} value={form.custo_etiqueta} onChange={set("custo_etiqueta")} />
          </label>
        </div>
        <CustoRow
          campos={[
            { label: "Saquinho — preço do pacote (R$)", key: "custo_saquinho_lote",    step: "0.01" },
            { label: "Unidades por pacote",             key: "unidades_saquinho_lote", step: "1"    },
          ]}
          form={form} set={set} resultLabel="R$/unidade" resultado={fmtUnit(custoSaquinho)}
          style={{ marginBottom: "1rem" }}
        />
        <CustoRow
          campos={[
            { label: "Caixa — custo (R$)", key: "custo_caixa",    step: "0.01" },
            { label: "Peças por caixa",    key: "pecas_por_caixa", step: "1"    },
          ]}
          form={form} set={set} resultLabel="R$/peça" resultado={fmtUnit(custoCaixa)}
        />
      </ConfigSecao>

      {/* LOGÍSTICA */}
      <ConfigSecao titulo="LOGÍSTICA" last>
        <CustoRow
          campos={[
            { label: "Linha overlock — custo do rolo (R$)", key: "custo_rolo_overlock",  step: "0.01" },
            { label: "Metros por rolo",                     key: "metros_rolo_overlock", step: "1"    },
          ]}
          form={form} set={set} resultLabel="R$/metro" resultado={fmtUnit(custoOverlock)}
          style={{ marginBottom: "1rem" }}
        />
        <CustoRow
          campos={[
            { label: "Linha reta — custo do rolo (R$)", key: "custo_rolo_reta",  step: "0.01" },
            { label: "Metros por rolo",                 key: "metros_rolo_reta", step: "1"    },
          ]}
          form={form} set={set} resultLabel="R$/metro" resultado={fmtUnit(custoLinhaReta)}
          style={{ marginBottom: "1rem" }}
        />

        <p className={styles.custoSubtitulo}>Gasolina</p>
        <div className={styles.gasGrid}>
          {[
            { label: "Distância (km)",           key: "distancia_costureira_km", step: "0.1"  },
            { label: "Nº de viagens",            key: "num_viagens",             step: "1"    },
            { label: "Consumo (km/l)",           key: "consumo_veiculo_km_l",    step: "0.1"  },
            { label: "Preço combustível (R$/l)", key: "preco_combustivel",       step: "0.01" },
          ].map(({ label, key, step }) => (
            <label key={key} className={styles.field}>
              <span>{label}</span>
              <input type="number" step={step} min="0" className={styles.input}
                value={form[key]} onChange={set(key)} />
            </label>
          ))}
        </div>
        <div className={styles.gasTotal}>
          <span>Custo total estimado</span>
          <strong>{fmtMoeda(custoGasolina)}</strong>
        </div>
      </ConfigSecao>

      <Msg msg={msg} />

      <div className={styles.actions}>
        <button className={styles.btnPrimary} onClick={handleSave} disabled={saving}>
          {saving ? "Salvando…" : "Salvar"}
        </button>
      </div>
    </div>
  );
}

function ConfigSecao({ titulo, children, last = false }) {
  return (
    <div className={`${styles.configSecao} ${last ? styles.configSecaoLast : ""}`}>
      <p className={styles.configSecaoTitulo}>{titulo}</p>
      {children}
    </div>
  );
}

// ── Painel: Tabelas de Preço ──────────────────────────────────────────────────

function PanelTabelasPreco() {
  const [tabelas, setTabelas]             = useState([]);
  const [grupos, setGrupos]               = useState([]);
  const [loading, setLoading]             = useState(true);
  const [selectedId, setSelectedId]       = useState(null);
  const [tabItens, setTabItens]           = useState({});
  const [showNova, setShowNova]           = useState(false);
  const [showAdd, setShowAdd]             = useState(null);
  const [editTabela, setEditTabela]       = useState(null);
  const [editForm, setEditForm]           = useState({ nome: "", comissao: "" });
  const [savingEdit, setSavingEdit]       = useState(false);
  const [errEdit, setErrEdit]             = useState(null);
  const [inativaOpen, setInativaOpen]     = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(null);
  const [toast, setToast]                 = useState(null);

  useEffect(() => {
    loadTabelas(true);
    gruposApi.listar().then((d) => setGrupos(d || [])).catch(() => {});
  }, []);

  const loadTabelas = async (autoSelect = false) => {
    setLoading(true);
    try {
      const data = await tabelasPrecoApi.list() || [];
      setTabelas(data);
      if (autoSelect) {
        const first = data.find((t) => t.ativo !== false);
        if (first) {
          setSelectedId(first.id);
          const itens = await tabelasPrecoApi.listItens(first.id).catch(() => []);
          setTabItens((prev) => ({ ...prev, [first.id]: itens }));
        }
      }
    } catch {}
    finally { setLoading(false); }
  };

  const showToast = (text) => {
    setToast(text);
    setTimeout(() => setToast(null), 4000);
  };

  const handleSelect = async (tab) => {
    setSelectedId(tab.id);
    if (!tabItens[tab.id]) {
      try {
        const data = await tabelasPrecoApi.listItens(tab.id);
        setTabItens((prev) => ({ ...prev, [tab.id]: data || [] }));
      } catch {
        setTabItens((prev) => ({ ...prev, [tab.id]: [] }));
      }
    }
  };

  const reloadItens = async (tabelaId) => {
    try {
      const data = await tabelasPrecoApi.listItens(tabelaId);
      setTabItens((prev) => ({ ...prev, [tabelaId]: data || [] }));
    } catch {}
  };

  const handleInativar = async (tab) => {
    try {
      await tabelasPrecoApi.update(tab.id, { ativo: false });
      if (selectedId === tab.id) setSelectedId(null);
      await loadTabelas();
    } catch (e) { showToast(e.message); }
  };

  const handleAtivar = async (tab) => {
    try {
      await tabelasPrecoApi.update(tab.id, { ativo: true });
      await loadTabelas();
    } catch (e) { showToast(e.message); }
  };

  const handleDelete = async (tab) => {
    if ((tab.num_itens ?? 0) > 0) {
      showToast("Remova os produtos antes de excluir esta tabela.");
      return;
    }
    try {
      await tabelasPrecoApi.remove(tab.id);
      if (selectedId === tab.id) setSelectedId(null);
      await loadTabelas();
    } catch (e) { showToast(e.message); }
  };

  const abrirEdit = (tab) => {
    setEditForm({ nome: tab.nome, comissao: String((parseFloat(tab.comissao_pct) * 100).toFixed(2)) });
    setEditTabela(tab);
    setErrEdit(null);
  };

  const handleSaveEdit = async () => {
    if (!editTabela) return;
    setSavingEdit(true); setErrEdit(null);
    try {
      await tabelasPrecoApi.update(editTabela.id, {
        nome: editForm.nome,
        comissao_pct: parseFloat(editForm.comissao) / 100,
      });
      await loadTabelas();
      setEditTabela(null);
    } catch (e) {
      setErrEdit(e.message);
    } finally {
      setSavingEdit(false);
    }
  };

  const handleRemoveItem = async (tabelaId, grupoId) => {
    try {
      await tabelasPrecoApi.removeItem(tabelaId, grupoId);
      setConfirmRemove(null);
      await reloadItens(tabelaId);
      await loadTabelas();
    } catch {}
  };

  const ativas      = tabelas.filter((t) => t.ativo !== false);
  const inativas    = tabelas.filter((t) => t.ativo === false);
  const selectedTab = tabelas.find((t) => t.id === selectedId) ?? null;
  const itens       = selectedId ? (tabItens[selectedId] ?? []) : [];

  return (
    <div className={styles.tabelasLayout}>

      {/* ── Left column — card list ── */}
      <div className={styles.tabelasLeft}>
        <div className={styles.tabelasLeftHeader}>
          <span className={styles.tabelasLeftTitle}>Tabelas</span>
          <button className={styles.btnPill} onClick={() => setShowNova(true)}>+ Nova</button>
        </div>

        {toast && (
          <div className={styles.msgErro} style={{ margin: "8px 10px", fontSize: 12 }}>{toast}</div>
        )}

        {loading ? (
          <p className={styles.tabelasEmptyLeft}>Carregando…</p>
        ) : ativas.length === 0 ? (
          <p className={styles.tabelasEmptyLeft}>Nenhuma tabela ativa.</p>
        ) : (
          ativas.map((tab) => (
            <div
              key={tab.id}
              className={`${styles.tabelaCard} ${selectedId === tab.id ? styles.tabelaCardSel : ""}`}
              onClick={() => handleSelect(tab)}
            >
              <div className={styles.tabelaCardHead}>
                <span className={styles.tabelaCardNome}>{tab.nome}</span>
                <div className={styles.tabelaCardActions}>
                  <button
                    className={styles.tabelaCardActionBtn}
                    title="Editar"
                    onClick={(e) => { e.stopPropagation(); abrirEdit(tab); }}
                  >✏</button>
                  <button
                    className={`${styles.tabelaCardActionBtn} ${styles.tabelaCardActionBtnDanger}`}
                    title="Excluir"
                    onClick={(e) => { e.stopPropagation(); handleDelete(tab); }}
                  >×</button>
                </div>
              </div>
              <div className={styles.tabelaCardMeta}>
                <span className={styles.tabelaCardComissao}>{fmtPct(tab.comissao_pct)} comissão</span>
                <span className={styles.tabelaBadgeAtiva}>Ativa</span>
              </div>
              <span className={styles.tabelaCardCount}>
                {tab.num_itens ?? 0} produto{(tab.num_itens ?? 0) !== 1 ? "s" : ""}
              </span>
            </div>
          ))
        )}

        {inativas.length > 0 && (
          <>
            <button
              className={styles.inativasToggle}
              onClick={() => setInativaOpen(!inativaOpen)}
            >
              {inativaOpen ? "▴" : "▾"} Inativas ({inativas.length})
            </button>
            {inativaOpen && inativas.map((tab) => (
              <div
                key={tab.id}
                className={`${styles.tabelaCard} ${styles.inativaCard} ${selectedId === tab.id ? styles.tabelaCardSel : ""}`}
                onClick={() => handleSelect(tab)}
              >
                <div className={styles.tabelaCardHead}>
                  <span className={styles.tabelaCardNome}>{tab.nome}</span>
                  <div className={styles.tabelaCardActions}>
                    <button
                      className={styles.tabelaCardActionBtn}
                      title="Ativar"
                      onClick={(e) => { e.stopPropagation(); handleAtivar(tab); }}
                    >↑</button>
                  </div>
                </div>
                <div className={styles.tabelaCardMeta}>
                  <span className={styles.tabelaCardComissao}>{fmtPct(tab.comissao_pct)}</span>
                  <span className={styles.tabelaBadgeInativa}>Inativa</span>
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      {/* ── Right panel — detail ── */}
      <div className={styles.tabelasRight}>
        {!selectedTab ? (
          <div className={styles.tabelasEmptyRight}>
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <rect x="6" y="6" width="28" height="28" rx="6"
                stroke="var(--sc-border-strong)" strokeWidth="2"/>
              <path d="M13 14h14M13 20h10M13 26h7"
                stroke="var(--sc-border-strong)" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            <p>Selecione uma tabela de preço</p>
          </div>
        ) : (
          <>
            <div className={styles.tabelasRightHeader}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                  <h3 className={styles.tabelasRightNome}>{selectedTab.nome}</h3>
                  <span className={selectedTab.ativo !== false ? styles.tabelaBadgeAtiva : styles.tabelaBadgeInativa}>
                    {selectedTab.ativo !== false ? "Ativa" : "Inativa"}
                  </span>
                </div>
                <p className={styles.tabelasRightComissao}>
                  Comissão: {fmtPct(selectedTab.comissao_pct)} sobre o valor do pedido
                </p>
              </div>
              <div className={styles.tabelasRightBtns}>
                <button className={styles.btnSecondary} onClick={() => abrirEdit(selectedTab)}>
                  Editar
                </button>
                {selectedTab.ativo !== false
                  ? <button className={styles.btnSecondary} onClick={() => handleInativar(selectedTab)}>
                      Inativar
                    </button>
                  : <button className={styles.btnSecondary} onClick={() => handleAtivar(selectedTab)}>
                      Ativar
                    </button>
                }
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--sc-text-primary)" }}>
                Produtos ({itens.length})
              </span>
              {selectedTab.ativo !== false && (
                <button className={styles.btnSecondary} onClick={() => setShowAdd(selectedId)}>
                  + Adicionar produto
                </button>
              )}
            </div>

            {itens.length === 0 ? (
              <div className={styles.tabelasEmptyRight} style={{ minHeight: 180 }}>
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                  <circle cx="16" cy="16" r="13" stroke="var(--sc-border-strong)" strokeWidth="2"/>
                  <path d="M10 16h12M16 10v12"
                    stroke="var(--sc-border-strong)" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                <p>Nenhum produto nesta tabela.</p>
                {selectedTab.ativo !== false && (
                  <button className={styles.btnSecondary} style={{ marginTop: 8 }}
                    onClick={() => setShowAdd(selectedId)}>
                    + Adicionar produto
                  </button>
                )}
              </div>
            ) : (
              <table className={styles.prodTable}>
                <thead>
                  <tr>
                    <th className={styles.prodTh}>Ref</th>
                    <th className={styles.prodTh}>Produto</th>
                    <th className={styles.prodTh}>À vista</th>
                    <th className={styles.prodTh}>A prazo</th>
                    <th className={styles.prodTh} style={{ width: 40 }} />
                  </tr>
                </thead>
                <tbody>
                  {itens.map((item) => (
                    <tr key={item.grupo_id} className={styles.prodTr}>
                      <td className={styles.prodTd}>
                        <span className={styles.refBadge}>{item.codigo || "—"}</span>
                      </td>
                      <td className={styles.prodTd}>{item.nome}</td>
                      <td className={styles.prodTd}>
                        <span className={styles.priceValue}>{fmtR(item.preco_avista)}</span>
                      </td>
                      <td className={styles.prodTd}>
                        <span className={styles.priceValue}>{fmtR(item.preco_aprazo)}</span>
                      </td>
                      <td className={styles.prodTd} style={{ textAlign: "right" }}>
                        {confirmRemove === `${selectedId}-${item.grupo_id}` ? (
                          <span style={{ display: "inline-flex", gap: 4 }}>
                            <button
                              style={{ background: "var(--sc-danger-text)", color: "#fff", border: "none", borderRadius: 4, padding: "2px 7px", cursor: "pointer", fontSize: 11 }}
                              onClick={() => handleRemoveItem(selectedId, item.grupo_id)}
                            >Sim</button>
                            <button
                              style={{ background: "none", border: "none", cursor: "pointer", fontSize: 11, color: "var(--sc-text-secondary)" }}
                              onClick={() => setConfirmRemove(null)}
                            >Não</button>
                          </span>
                        ) : (
                          <button
                            className={styles.prodRemoveBtn}
                            onClick={() => setConfirmRemove(`${selectedId}-${item.grupo_id}`)}
                          >×</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>

      {/* Modals */}
      {showNova && (
        <ModalNovaTabela
          onClose={() => setShowNova(false)}
          onCreated={async () => { setShowNova(false); await loadTabelas(); }}
        />
      )}

      {showAdd && (
        <ModalAddItem
          tabelaId={showAdd}
          grupos={grupos}
          onClose={() => setShowAdd(null)}
          onAdded={async () => {
            const id = showAdd;
            setShowAdd(null);
            await reloadItens(id);
            await loadTabelas();
          }}
        />
      )}

      {editTabela && (
        <div className={styles.modalPillOverlay}>
          <div className={styles.modalPill}>
            <h3 className={styles.modalPillTitle}>Editar Tabela</h3>
            <label className={styles.field}>
              <span>Nome</span>
              <input className={styles.input} value={editForm.nome}
                onChange={(e) => setEditForm((f) => ({ ...f, nome: e.target.value }))} />
            </label>
            <label className={styles.field} style={{ marginTop: 10 }}>
              <span>Comissão (%)</span>
              <input type="number" step="0.01" min="0" className={styles.input}
                value={editForm.comissao}
                onChange={(e) => setEditForm((f) => ({ ...f, comissao: e.target.value }))} />
            </label>
            {errEdit && <p className={styles.msgErro} style={{ marginTop: 10 }}>{errEdit}</p>}
            <div className={styles.modalPillActions}>
              <button className={styles.btnPillSecondary} onClick={() => setEditTabela(null)}>Cancelar</button>
              <button className={styles.btnPillPrimary} onClick={handleSaveEdit} disabled={savingEdit}>
                {savingEdit ? "…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ModalNovaTabela({ onClose, onCreated }) {
  const [form, setForm]     = useState({ nome: "", comissao: "" });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState(null);

  const handleSave = async () => {
    if (!form.nome.trim() || !form.comissao) { setErr("Preencha todos os campos."); return; }
    setSaving(true); setErr(null);
    try {
      await tabelasPrecoApi.create({
        nome:         form.nome.trim(),
        comissao_pct: parseFloat(form.comissao) / 100,
      });
      onCreated();
    } catch (e) {
      setErr(e.message);
      setSaving(false);
    }
  };

  return (
    <div className={styles.modalPillOverlay}>
      <div className={styles.modalPill}>
        <h3 className={styles.modalPillTitle}>Nova Tabela de Preço</h3>
        <label className={styles.field}>
          <span>Nome</span>
          <input className={styles.input} value={form.nome}
            onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
            placeholder="Ex.: Atacado Sul"
            autoFocus />
        </label>
        <label className={styles.field} style={{ marginTop: 10 }}>
          <span>Comissão (%)</span>
          <input type="number" step="0.01" min="0" className={styles.input}
            value={form.comissao}
            onChange={(e) => setForm((f) => ({ ...f, comissao: e.target.value }))}
            placeholder="Ex.: 10" />
        </label>
        {err && <p className={styles.msgErro} style={{ marginTop: 10 }}>{err}</p>}
        <div className={styles.modalPillActions}>
          <button className={styles.btnPillSecondary} onClick={onClose}>Cancelar</button>
          <button className={styles.btnPillPrimary} onClick={handleSave} disabled={saving}>
            {saving ? "Criando…" : "Criar Tabela"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ModalAddItem({ tabelaId, grupos, onClose, onAdded }) {
  const [search, setSearch]     = useState("");
  const [grupoSel, setGrupoSel] = useState(null);
  const [form, setForm]         = useState({ preco_avista: "", preco_aprazo: "" });
  const [saving, setSaving]     = useState(false);
  const [err, setErr]           = useState(null);

  const filtered = search.trim().length >= 1
    ? grupos.filter((g) =>
        (g.codigo && g.codigo.toLowerCase().includes(search.toLowerCase())) ||
        g.nome.toLowerCase().includes(search.toLowerCase())
      ).slice(0, 10)
    : [];

  const handleSave = async () => {
    if (!grupoSel)                                { setErr("Selecione um produto."); return; }
    if (!form.preco_avista || !form.preco_aprazo)  { setErr("Informe os preços."); return; }
    setSaving(true); setErr(null);
    try {
      await tabelasPrecoApi.addItem(tabelaId, {
        grupo_id:     grupoSel.id,
        preco_avista: parseFloat(form.preco_avista),
        preco_aprazo: parseFloat(form.preco_aprazo),
      });
      onAdded();
    } catch (e) {
      setErr(e.message);
      setSaving(false);
    }
  };

  return (
    <div className={styles.modalPillOverlay}>
      <div className={`${styles.modalPill} ${styles.modalPillWide}`}>
        <h3 className={styles.modalPillTitle}>Adicionar Produto</h3>

        {grupoSel ? (
          <div style={{ marginBottom: 16, padding: "10px 14px", background: "var(--sc-bg-secondary)", borderRadius: 10, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              {grupoSel.codigo && (
                <span className={styles.refBadge} style={{ display: "inline-block", marginBottom: 4 }}>
                  {grupoSel.codigo}
                </span>
              )}
              <div style={{ fontWeight: 600, fontSize: 14 }}>{grupoSel.nome}</div>
            </div>
            <button
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--sc-text-secondary)", textDecoration: "underline", fontSize: 13, padding: 0 }}
              onClick={() => { setGrupoSel(null); setSearch(""); }}
            >Trocar</button>
          </div>
        ) : (
          <div style={{ position: "relative", marginBottom: 16 }}>
            <label className={styles.field}>
              <span>Buscar por código ou nome</span>
              <input className={styles.input} value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Digite para buscar…" autoFocus />
            </label>
            {filtered.length > 0 && (
              <ul style={DROPDOWN_STYLE}>
                {filtered.map((g) => (
                  <li key={g.id} style={DROPDOWN_ITEM_STYLE}
                    onMouseDown={(e) => { e.preventDefault(); setGrupoSel(g); setSearch(""); }}>
                    {g.codigo ? <strong>{g.codigo}</strong> : null}
                    {g.codigo ? " · " : null}
                    {g.nome}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div style={{ display: "flex", gap: 12 }}>
          <label className={styles.field} style={{ flex: 1 }}>
            <span>Preço à vista (R$)</span>
            <input type="number" step="0.01" min="0" className={styles.input}
              value={form.preco_avista}
              onChange={(e) => setForm((f) => ({ ...f, preco_avista: e.target.value }))} />
          </label>
          <label className={styles.field} style={{ flex: 1 }}>
            <span>Preço a prazo (R$)</span>
            <input type="number" step="0.01" min="0" className={styles.input}
              value={form.preco_aprazo}
              onChange={(e) => setForm((f) => ({ ...f, preco_aprazo: e.target.value }))} />
          </label>
        </div>

        {err && <p className={styles.msgErro} style={{ marginTop: 10 }}>{err}</p>}

        <div className={styles.modalPillActions}>
          <button className={styles.btnPillSecondary} onClick={onClose}>Cancelar</button>
          <button className={styles.btnPillPrimary} onClick={handleSave} disabled={saving || !grupoSel}>
            {saving ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Painel: Vendedores ────────────────────────────────────────────────────────

function PanelVendedores() {
  const [vendedores, setVendedores]   = useState([]);
  const [loading, setLoading]         = useState(true);
  const [selected, setSelected]       = useState(null);
  const [activeTab, setActiveTab]     = useState("dados");
  const [modalCreate, setModalCreate] = useState(false);
  const [formCreate, setFormCreate]   = useState({ nome: "", telefone: "", email: "" });
  const [savingCreate, setSavingCreate] = useState(false);
  const [errCreate, setErrCreate]     = useState(null);

  const load = async () => {
    setLoading(true);
    try { setVendedores(await vendedoresApi.list() || []); }
    catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleGerenciar = (v) => { setSelected(v); setActiveTab("dados"); };

  const handleCriar = async () => {
    if (!formCreate.nome.trim()) { setErrCreate("Nome é obrigatório."); return; }
    setSavingCreate(true); setErrCreate(null);
    try {
      await vendedoresApi.create(formCreate);
      await load();
      setModalCreate(false);
    } catch (e) {
      setErrCreate(e.message);
    } finally {
      setSavingCreate(false);
    }
  };

  const TAB_LABELS = { dados: "Dados", acesso: "Acesso", metas: "Metas", catalogos: "Catálogos", leads: "Leads" };

  const ativos   = vendedores.filter((v) => v.ativo !== false);
  const inativos = vendedores.filter((v) => v.ativo === false);

  return (
    <div className={styles.vendedoresLayout}>
      {/* ── Lista ── */}
      <div className={styles.vendedoresListWrap}>
        <div className={styles.vendedoresListHeader}>
          <span className={styles.tabelasLeftTitle}>Vendedores</span>
          <button className={styles.btnPill} onClick={() => { setModalCreate(true); setErrCreate(null); setFormCreate({ nome: "", telefone: "", email: "" }); }}>
            + Novo
          </button>
        </div>

        {loading ? (
          <p className={styles.tabelasEmptyLeft}>Carregando…</p>
        ) : (
          <ul className={styles.vendedoresList}>
            {ativos.map((v) => (
              <li
                key={v.id}
                className={`${styles.vendedorItem} ${selected?.id === v.id ? styles.vendedorItemSel : ""}`}
              >
                <div className={styles.vendedorItemInfo}>
                  <span className={styles.vendedorItemNome}>{v.nome}</span>
                  <span className={styles.vendedorItemSub}>{v.email || v.telefone || "Sem contato"}</span>
                </div>
                <button className={styles.btnPill} onClick={() => handleGerenciar(v)}>Gerenciar</button>
              </li>
            ))}
            {ativos.length === 0 && (
              <li className={styles.vendedorEmpty}>Nenhum vendedor ativo.</li>
            )}
            {inativos.length > 0 && (
              <>
                <li className={styles.vendedorInativoLabel}>Inativos ({inativos.length})</li>
                {inativos.map((v) => (
                  <li key={v.id} className={`${styles.vendedorItem} ${styles.vendedorItemInativo}`}>
                    <div className={styles.vendedorItemInfo}>
                      <span className={styles.vendedorItemNome}>{v.nome}</span>
                      <span className={styles.vendedorItemSub}>{v.email || v.telefone || "—"}</span>
                    </div>
                  </li>
                ))}
              </>
            )}
          </ul>
        )}
      </div>

      {/* ── Drawer lateral ── */}
      {selected ? (
        <div className={styles.vendedoresDrawer}>
          <div className={styles.drawerHeader}>
            <span className={styles.drawerNome}>{selected.nome}</span>
            <button className={styles.drawerClose} onClick={() => setSelected(null)}>×</button>
          </div>
          <div className={styles.tabBar}>
            {Object.entries(TAB_LABELS).map(([tab, label]) => (
              <button
                key={tab}
                className={`${styles.tabBtn} ${activeTab === tab ? styles.tabBtnActive : ""}`}
                onClick={() => setActiveTab(tab)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className={styles.tabContent}>
            {activeTab === "dados"     && (
              <TabDados
                vendedor={selected}
                onSaved={(v) => { if (v === null) { setSelected(null); } else { setSelected(v); } load(); }}
              />
            )}
            {activeTab === "acesso"    && <TabAcesso vendedorId={selected.id} />}
            {activeTab === "metas"     && <TabMetas vendedorId={selected.id} />}
            {activeTab === "catalogos" && <TabCatalogos vendedorId={selected.id} />}
            {activeTab === "leads"     && <TabLeads vendedorId={selected.id} />}
          </div>
        </div>
      ) : (
        <div className={styles.tabelasEmptyRight}>
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
            <circle cx="20" cy="14" r="6" stroke="var(--sc-border-strong)" strokeWidth="2"/>
            <path d="M8 34c0-6.627 5.373-12 12-12s12 5.373 12 12"
              stroke="var(--sc-border-strong)" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          <p>Selecione um vendedor para gerenciar</p>
        </div>
      )}

      {/* ── Modal criar ── */}
      {modalCreate && (
        <div className={styles.modalPillOverlay}>
          <div className={styles.modalPill}>
            <h3 className={styles.modalPillTitle}>Novo Vendedor</h3>
            <label className={styles.field}>
              <span>Nome *</span>
              <input className={styles.input} value={formCreate.nome} autoFocus
                onChange={(e) => setFormCreate((f) => ({ ...f, nome: e.target.value }))} />
            </label>
            <label className={styles.field} style={{ marginTop: 10 }}>
              <span>Telefone</span>
              <input className={styles.input} value={formCreate.telefone}
                onChange={(e) => setFormCreate((f) => ({ ...f, telefone: e.target.value }))} />
            </label>
            <label className={styles.field} style={{ marginTop: 10 }}>
              <span>E-mail</span>
              <input className={styles.input} value={formCreate.email}
                onChange={(e) => setFormCreate((f) => ({ ...f, email: e.target.value }))} />
            </label>
            {errCreate && <p className={styles.msgErro} style={{ marginTop: 10 }}>{errCreate}</p>}
            <div className={styles.modalPillActions}>
              <button className={styles.btnPillSecondary} onClick={() => setModalCreate(false)}>Cancelar</button>
              <button className={styles.btnPillPrimary} onClick={handleCriar} disabled={savingCreate}>
                {savingCreate ? "Criando…" : "Criar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Aba: Dados ────────────────────────────────────────────────────────────────

function TabDados({ vendedor, onSaved }) {
  const [form, setForm]     = useState({ nome: vendedor.nome || "", telefone: vendedor.telefone || "", email: vendedor.email || "" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg]       = useState(null);

  const handleSave = async () => {
    if (!form.nome.trim()) { setMsg({ ok: false, text: "Nome é obrigatório." }); return; }
    setSaving(true); setMsg(null);
    try {
      const updated = await vendedoresApi.update(vendedor.id, form);
      setMsg({ ok: true, text: "Dados salvos." });
      onSaved(updated || { ...vendedor, ...form });
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    } finally {
      setSaving(false);
    }
  };

  const handleInativar = async () => {
    try { await vendedoresApi.remove(vendedor.id); onSaved(null); } catch {}
  };

  return (
    <div className={styles.tabInner}>
      <label className={styles.field}>
        <span>Nome *</span>
        <input className={styles.input} value={form.nome}
          onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))} />
      </label>
      <label className={styles.field} style={{ marginTop: 10 }}>
        <span>Telefone</span>
        <input className={styles.input} value={form.telefone}
          onChange={(e) => setForm((f) => ({ ...f, telefone: e.target.value }))} />
      </label>
      <label className={styles.field} style={{ marginTop: 10 }}>
        <span>E-mail</span>
        <input className={styles.input} value={form.email}
          onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
      </label>
      <Msg msg={msg} />
      <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <button style={BTN_LINK_DANGER} onClick={handleInativar}>Inativar vendedor</button>
        <button className={styles.btnPrimary} onClick={handleSave} disabled={saving}>
          {saving ? "Salvando…" : "Salvar"}
        </button>
      </div>
    </div>
  );
}

// ── Aba: Acesso ───────────────────────────────────────────────────────────────

function TabAcesso({ vendedorId }) {
  const [creds, setCreds]   = useState(null);
  const [form, setForm]     = useState({ username: "", senha: "" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg]       = useState(null);

  useEffect(() => {
    vendedoresApi.getCredenciais(vendedorId).then(setCreds).catch(() => {});
  }, [vendedorId]);

  const handleSave = async () => {
    if (!form.username.trim() || !form.senha.trim()) {
      setMsg({ ok: false, text: "Preencha username e senha." }); return;
    }
    setSaving(true); setMsg(null);
    try {
      const d = await vendedoresApi.setCredenciais(vendedorId, form);
      setCreds(d);
      setForm((f) => ({ ...f, senha: "" }));
      setMsg({ ok: true, text: "Credenciais salvas com sucesso." });
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.tabInner}>
      {creds?.username && (
        <div className={styles.credInfo}>
          <span className={styles.credLabel}>Username atual</span>
          <code className={styles.credValue}>{creds.username}</code>
        </div>
      )}
      <label className={styles.field} style={{ marginTop: creds?.username ? 10 : 0 }}>
        <span>{creds?.username ? "Novo username" : "Username"}</span>
        <input className={styles.input} value={form.username}
          onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
          placeholder="ex.: joao.silva" />
      </label>
      <label className={styles.field} style={{ marginTop: 10 }}>
        <span>Nova senha</span>
        <input type="password" className={styles.input} value={form.senha}
          onChange={(e) => setForm((f) => ({ ...f, senha: e.target.value }))} />
      </label>
      <Msg msg={msg} />
      <button className={styles.btnPrimary} style={{ marginTop: 14 }} onClick={handleSave} disabled={saving}>
        {saving ? "Salvando…" : "Salvar credenciais"}
      </button>
      <p className={styles.hint} style={{ marginTop: 12 }}>
        Compartilhe este usuário e senha com o vendedor para que ele possa acessar o painel.
      </p>
    </div>
  );
}

// ── Aba: Metas ────────────────────────────────────────────────────────────────

const METAS_CAMPOS = [
  { label: "Meta de ativação mensal (R$)", key: "meta_ativacao",       step: "0.01", tipo: "float" },
  { label: "Bônus logística (R$)",         key: "bonus_logistica",     step: "0.01", tipo: "float" },
  { label: "Meta novos clientes (nº)",     key: "meta_novos_clientes", step: "1",    tipo: "int"   },
  { label: "Bônus expansão (R$)",          key: "bonus_expansao",      step: "0.01", tipo: "float" },
  { label: "Pedido mínimo (R$)",           key: "pedido_minimo",       step: "0.01", tipo: "float" },
];

function TabMetas({ vendedorId }) {
  const [form, setForm]     = useState({ meta_ativacao: "", bonus_logistica: "", meta_novos_clientes: "", bonus_expansao: "", pedido_minimo: "" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg]       = useState(null);

  useEffect(() => {
    vendedoresApi.getMetas(vendedorId).then((d) => {
      if (d) setForm({
        meta_ativacao:       d.meta_ativacao       ?? "",
        bonus_logistica:     d.bonus_logistica     ?? "",
        meta_novos_clientes: d.meta_novos_clientes ?? "",
        bonus_expansao:      d.bonus_expansao      ?? "",
        pedido_minimo:       d.pedido_minimo       ?? "",
      });
    }).catch(() => {});
  }, [vendedorId]);

  const handleSave = async () => {
    setSaving(true); setMsg(null);
    try {
      const payload = {};
      METAS_CAMPOS.forEach(({ key, tipo }) => {
        payload[key] = tipo === "int" ? parseInt(form[key]) || 0 : parseFloat(form[key]) || 0;
      });
      await vendedoresApi.updateMetas(vendedorId, payload);
      setMsg({ ok: true, text: "Metas salvas." });
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.tabInner}>
      {METAS_CAMPOS.map(({ label, key, step }, i) => (
        <label key={key} className={styles.field} style={{ marginBottom: i < METAS_CAMPOS.length - 1 ? 10 : 0 }}>
          <span>{label}</span>
          <input type="number" step={step} min="0" className={styles.input}
            value={form[key]} onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} />
        </label>
      ))}
      <Msg msg={msg} />
      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 4 }}>
        <button className={styles.btnPrimary} onClick={handleSave} disabled={saving}>
          {saving ? "Salvando…" : "Salvar metas"}
        </button>
      </div>
    </div>
  );
}

// ── Aba: Catálogos ────────────────────────────────────────────────────────────

function TabCatalogos({ vendedorId }) {
  const [catalogos, setCatalogos]   = useState([]);
  const [acessos, setAcessos]       = useState([]);
  const [tabelas, setTabelas]       = useState([]);
  const [loading, setLoading]       = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [upForm, setUpForm]         = useState({ nome: "", tabela_preco_id: "" });
  const [upFile, setUpFile]         = useState(null);
  const [uploading, setUploading]   = useState(false);
  const [errUp, setErrUp]           = useState(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [cats, tabs] = await Promise.all([catalogosApi.list(), tabelasPrecoApi.list()]);
      const catList = cats || [];
      setCatalogos(catList);
      setTabelas(tabs || []);
      const acessosArr = await Promise.all(
        catList.map((cat) => catalogosApi.listVendedores(cat.id).catch(() => []))
      );
      const comAcesso = catList
        .filter((_, i) => (acessosArr[i] || []).includes(String(vendedorId)))
        .map((cat) => cat.id);
      setAcessos(comAcesso);
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { loadAll(); }, [vendedorId]);

  const toggleAcesso = async (catId, temAcesso) => {
    try {
      if (temAcesso) {
        await catalogosApi.removeVendedor(catId, vendedorId);
        setAcessos((prev) => prev.filter((id) => id !== catId));
      } else {
        await catalogosApi.addVendedor(catId, vendedorId);
        setAcessos((prev) => [...prev, catId]);
      }
    } catch {}
  };

  const handleUpload = async () => {
    if (!upForm.nome.trim() || !upFile) { setErrUp("Nome e arquivo são obrigatórios."); return; }
    setUploading(true); setErrUp(null);
    try {
      const fd = new FormData();
      fd.append("nome", upForm.nome);
      if (upForm.tabela_preco_id) fd.append("tabela_preco_id", upForm.tabela_preco_id);
      fd.append("arquivo", upFile);
      await catalogosApi.create(fd);
      setShowUpload(false);
      setUpForm({ nome: "", tabela_preco_id: "" });
      setUpFile(null);
      await loadAll();
    } catch (e) {
      setErrUp(e.message);
    } finally {
      setUploading(false);
    }
  };

  if (loading) return <p style={{ padding: "1rem", color: "var(--sc-text-muted)", fontSize: 13 }}>Carregando…</p>;

  return (
    <div className={styles.tabInner}>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
        <button className={styles.btnPill} onClick={() => { setShowUpload(true); setErrUp(null); setUpForm({ nome: "", tabela_preco_id: "" }); setUpFile(null); }}>
          + Upload Catálogo
        </button>
      </div>

      {catalogos.length === 0 ? (
        <p style={{ color: "var(--sc-text-muted)", fontSize: 13 }}>Nenhum catálogo cadastrado.</p>
      ) : (
        <ul className={styles.catalogosList}>
          {catalogos.map((cat) => {
            const temAcesso = acessos.includes(cat.id);
            return (
              <li key={cat.id} className={styles.catalogoItem}>
                <input
                  type="checkbox" id={`cat-${cat.id}`}
                  checked={temAcesso}
                  onChange={() => toggleAcesso(cat.id, temAcesso)}
                />
                <label htmlFor={`cat-${cat.id}`} className={styles.catalogoLabel}>
                  <span className={styles.catalogoNome}>{cat.nome}</span>
                  {cat.tabela_preco_nome && (
                    <span className={styles.catalogoTabela}>{cat.tabela_preco_nome}</span>
                  )}
                </label>
              </li>
            );
          })}
        </ul>
      )}

      {showUpload && (
        <div className={styles.modalPillOverlay}>
          <div className={styles.modalPill}>
            <h3 className={styles.modalPillTitle}>Upload de Catálogo</h3>
            <label className={styles.field}>
              <span>Nome *</span>
              <input className={styles.input} value={upForm.nome} autoFocus
                onChange={(e) => setUpForm((f) => ({ ...f, nome: e.target.value }))} />
            </label>
            <label className={styles.field} style={{ marginTop: 10 }}>
              <span>Tabela de preço</span>
              <select className={styles.input} value={upForm.tabela_preco_id}
                onChange={(e) => setUpForm((f) => ({ ...f, tabela_preco_id: e.target.value }))}>
                <option value="">— Nenhuma —</option>
                {tabelas.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
              </select>
            </label>
            <label className={styles.field} style={{ marginTop: 10 }}>
              <span>Arquivo PDF *</span>
              <input type="file" accept=".pdf" className={styles.input}
                onChange={(e) => setUpFile(e.target.files[0] || null)} />
            </label>
            {errUp && <p className={styles.msgErro} style={{ marginTop: 10 }}>{errUp}</p>}
            <div className={styles.modalPillActions}>
              <button className={styles.btnPillSecondary} onClick={() => setShowUpload(false)}>Cancelar</button>
              <button className={styles.btnPillPrimary} onClick={handleUpload} disabled={uploading}>
                {uploading ? "Enviando…" : "Upload"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Aba: Leads ────────────────────────────────────────────────────────────────

const LEAD_CAMPOS = [
  { label: "Nome *", key: "nome" },
  { label: "Segmento", key: "segmento" },
  { label: "Endereço", key: "endereco" },
  { label: "Cidade", key: "cidade" },
  { label: "Telefone", key: "telefone" },
];

const LEAD_VAZIO = { nome: "", segmento: "", endereco: "", cidade: "", telefone: "", observacao: "" };

function TabLeads({ vendedorId }) {
  const [leads, setLeads]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [showNovo, setShowNovo] = useState(false);
  const [form, setForm]         = useState(LEAD_VAZIO);
  const [saving, setSaving]     = useState(false);
  const [err, setErr]           = useState(null);

  const loadLeads = async () => {
    setLoading(true);
    try {
      const all = await leadsApi.list();
      setLeads((all || []).filter((l) => l.vendedor_id === String(vendedorId)));
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { loadLeads(); }, [vendedorId]);

  const handleCriar = async () => {
    if (!form.nome.trim()) { setErr("Nome é obrigatório."); return; }
    setSaving(true); setErr(null);
    try {
      await leadsApi.create({ ...form, vendedor_id: vendedorId });
      setShowNovo(false);
      setForm(LEAD_VAZIO);
      await loadLeads();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (leadId) => {
    try { await leadsApi.remove(leadId); await loadLeads(); } catch {}
  };

  return (
    <div className={styles.tabInner}>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
        <button className={styles.btnPill} onClick={() => { setShowNovo(true); setErr(null); setForm(LEAD_VAZIO); }}>
          + Novo Lead
        </button>
      </div>

      {loading ? (
        <p style={{ color: "var(--sc-text-muted)", fontSize: 13 }}>Carregando…</p>
      ) : leads.length === 0 ? (
        <p style={{ color: "var(--sc-text-muted)", fontSize: 13 }}>Nenhum lead atribuído.</p>
      ) : (
        <ul className={styles.leadsList}>
          {leads.map((lead) => (
            <li key={lead.id} className={styles.leadItem}>
              <div className={styles.leadInfo}>
                <span className={styles.leadNome}>{lead.nome}</span>
                {lead.cidade && <span className={styles.leadSub}>{lead.cidade}</span>}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                <span className={styles.leadStatus}>{lead.status}</span>
                <button style={BTN_DANGER_SM} onClick={() => handleDelete(lead.id)}>×</button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {showNovo && (
        <div className={styles.modalPillOverlay}>
          <div className={styles.modalPill}>
            <h3 className={styles.modalPillTitle}>Novo Lead</h3>
            {LEAD_CAMPOS.map(({ label, key }, i) => (
              <label key={key} className={styles.field} style={{ marginTop: i > 0 ? 10 : 0 }}>
                <span>{label}</span>
                <input className={styles.input} value={form[key]} autoFocus={i === 0}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))} />
              </label>
            ))}
            <label className={styles.field} style={{ marginTop: 10 }}>
              <span>Observação</span>
              <textarea className={styles.input} rows={3} value={form.observacao}
                onChange={(e) => setForm((f) => ({ ...f, observacao: e.target.value }))}
                style={{ resize: "vertical" }} />
            </label>
            {err && <p className={styles.msgErro} style={{ marginTop: 10 }}>{err}</p>}
            <div className={styles.modalPillActions}>
              <button className={styles.btnPillSecondary} onClick={() => setShowNovo(false)}>Cancelar</button>
              <button className={styles.btnPillPrimary} onClick={handleCriar} disabled={saving}>
                {saving ? "Criando…" : "Criar Lead"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Sub-componentes helpers ───────────────────────────────────────────────────

function CustoRow({ campos, form, set, resultLabel, resultado, style }) {
  return (
    <div className={styles.custoRow} style={style}>
      {campos.map(({ label, key, step }) => (
        <label key={key} className={styles.field}>
          <span>{label}</span>
          <input type="number" step={step} min="0" className={styles.input}
            value={form[key]} onChange={set(key)} />
        </label>
      ))}
      <div className={styles.custoCalc}>
        <span>{resultLabel}</span>
        <strong>{resultado}</strong>
      </div>
    </div>
  );
}

// ── Msg helper ────────────────────────────────────────────────────────────────

function Msg({ msg }) {
  if (!msg) return null;
  return <p className={msg.ok ? styles.msgOk : styles.msgErro}>{msg.text}</p>;
}
