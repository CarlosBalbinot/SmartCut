import { useState, useEffect, useCallback } from "react";
import { catalogosApi, leadsApi, tabelasPrecoApi } from "../services/api";
import {
  getVendedores, createVendedor, updateVendedor,
  getCredenciaisVendedor, setCredenciaisVendedor, getMetasVendedor, updateMetasVendedor,
} from "../api/vendedores";
import { useAuth } from "../auth/useAuth";
import styles from "./VendedoresPage.module.css";

const MODULO = "cadastros_vendedores";

const TABS_DADOS = [
  { id: "dados", label: "Dados" },
  { id: "endereco", label: "Endereço" },
  { id: "fiscal", label: "Fiscal / Contato" },
];

const TABS_GESTAO = [
  { id: "acesso", label: "Acesso" },
  { id: "metas", label: "Metas" },
  { id: "catalogos", label: "Catálogos" },
  { id: "leads", label: "Leads" },
];

const formatCpfCnpj = (v) => {
  const d = v.replace(/\D/g, "");
  if (d.length <= 11) {
    const c = d.slice(0, 11);
    if (c.length <= 3) return c;
    if (c.length <= 6) return `${c.slice(0, 3)}.${c.slice(3)}`;
    if (c.length <= 9) return `${c.slice(0, 3)}.${c.slice(3, 6)}.${c.slice(6)}`;
    return `${c.slice(0, 3)}.${c.slice(3, 6)}.${c.slice(6, 9)}-${c.slice(9)}`;
  }
  const c = d.slice(0, 14);
  if (c.length <= 2) return c;
  if (c.length <= 5) return `${c.slice(0, 2)}.${c.slice(2)}`;
  if (c.length <= 8) return `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5)}`;
  if (c.length <= 12) return `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8)}`;
  return `${c.slice(0, 2)}.${c.slice(2, 5)}.${c.slice(5, 8)}/${c.slice(8, 12)}-${c.slice(12)}`;
};

const formatCep = (v) => {
  const d = v.replace(/\D/g, "").slice(0, 8);
  if (d.length <= 5) return d;
  return `${d.slice(0, 5)}-${d.slice(5)}`;
};

const stripDigits = (v) => (v || "").replace(/\D/g, "");

const VAZIO = {
  tipo_pessoa: "fisica",
  nome: "",
  nome_fantasia: "",
  descricao: "",
  endereco: "",
  numero: "",
  complemento: "",
  bairro: "",
  municipio: "",
  estado: "",
  cep: "",
  telefone: "",
  celular: "",
  fax: "",
  cpf_cnpj: "",
  rg_ie: "",
  inscricao_municipal: "",
  comissao_pct: "0",
  dia_pagto: "0",
  pct_pago_emissao: "100",
  pct_pago_baixa: "0",
  email: "",
  email_nfe: "",
  status: "ativo",
};

const money2 = (v) => Number(v || 0).toFixed(2);

export default function VendedoresPage() {
  const { hasPermission } = useAuth();
  const [vendedores, setVendedores] = useState([]);
  const [busca, setBusca]           = useState("");
  const [filtroStatus, setFiltroStatus] = useState("");
  const [loading, setLoading]       = useState(true);
  const [modal, setModal]           = useState(null);
  const [aba, setAba]               = useState("dados");
  const [abaErro, setAbaErro]       = useState(null);
  const [saving, setSaving]         = useState(false);
  const [erro, setErro]             = useState(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      setVendedores((await getVendedores(busca, filtroStatus)) || []);
    } catch {
      setVendedores([]);
    } finally {
      setLoading(false);
    }
  }, [busca, filtroStatus]);

  useEffect(() => { carregar(); }, [carregar]);

  const abrirNovo = () => { setModal({ ...VAZIO }); setAba("dados"); setAbaErro(null); setErro(null); };

  const abrirEditar = (v) => {
    setModal({
      id: v.id,
      codigo: v.codigo || "",
      tipo_pessoa: v.tipo_pessoa || "fisica",
      nome: v.nome || "",
      nome_fantasia: v.nome_fantasia || "",
      descricao: v.descricao || "",
      endereco: v.endereco || "",
      numero: v.numero || "",
      complemento: v.complemento || "",
      bairro: v.bairro || "",
      municipio: v.municipio || "",
      estado: v.estado || "",
      cep: formatCep(v.cep || ""),
      telefone: v.telefone || "",
      celular: v.celular || "",
      fax: v.fax || "",
      cpf_cnpj: formatCpfCnpj(v.cpf_cnpj || ""),
      rg_ie: v.rg_ie || "",
      inscricao_municipal: v.inscricao_municipal || "",
      comissao_pct: money2(v.comissao_pct),
      dia_pagto: String(v.dia_pagto ?? 0),
      pct_pago_emissao: money2(v.pct_pago_emissao),
      pct_pago_baixa: money2(v.pct_pago_baixa),
      email: v.email || "",
      email_nfe: v.email_nfe || "",
      status: v.status || "ativo",
      data_cadastro: v.data_cadastro,
    });
    setAba("dados");
    setAbaErro(null);
    setErro(null);
  };

  const fecharModal = () => { setModal(null); setErro(null); };
  const setF = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.value }));

  const handleSalvar = async () => {
    setAbaErro(null);
    if (!modal.nome.trim()) {
      setErro("Nome é obrigatório.");
      setAbaErro("dados");
      setAba("dados");
      return;
    }
    setSaving(true); setErro(null);
    try {
      const payload = {
        tipo_pessoa: modal.tipo_pessoa || null,
        nome: modal.nome.trim(),
        nome_fantasia: modal.nome_fantasia.trim() || null,
        descricao: modal.descricao.trim() || null,
        endereco: modal.endereco.trim() || null,
        numero: modal.numero.trim() || null,
        complemento: modal.complemento.trim() || null,
        bairro: modal.bairro.trim() || null,
        municipio: modal.municipio.trim() || null,
        estado: modal.estado.trim().toUpperCase() || null,
        cep: stripDigits(modal.cep) || null,
        telefone: modal.telefone.trim() || null,
        celular: modal.celular.trim() || null,
        fax: modal.fax.trim() || null,
        cpf_cnpj: stripDigits(modal.cpf_cnpj) || null,
        rg_ie: modal.rg_ie.trim() || null,
        inscricao_municipal: modal.inscricao_municipal.trim() || null,
        comissao_pct: Number(modal.comissao_pct) || 0,
        dia_pagto: parseInt(modal.dia_pagto, 10) || 0,
        pct_pago_emissao: Number(modal.pct_pago_emissao) || 0,
        pct_pago_baixa: Number(modal.pct_pago_baixa) || 0,
        email: modal.email.trim() || null,
        email_nfe: modal.email_nfe.trim() || null,
        status: modal.status,
      };
      if (modal.id) {
        await updateVendedor(modal.id, payload);
      } else {
        await createVendedor(payload);
      }
      await carregar();
      fecharModal();
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleInativar = async (v) => {
    const novoStatus = v.status === "ativo" ? "inativo" : "ativo";
    if (!window.confirm(`Deseja marcar este vendedor como ${novoStatus}?`)) return;
    try { await updateVendedor(v.id, { status: novoStatus }); await carregar(); } catch (e) { alert(e.message); }
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Vendedores</h1>
        {hasPermission(MODULO, "criar") && (
          <button className={styles.btnNovo} onClick={abrirNovo}>+ Novo Vendedor</button>
        )}
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <input
            className={styles.busca}
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por nome ou CPF/CNPJ…"
          />
        </div>
        <select className={styles.select} value={filtroStatus} onChange={(e) => setFiltroStatus(e.target.value)}>
          <option value="">Todos</option>
          <option value="ativo">Ativo</option>
          <option value="inativo">Inativo</option>
        </select>
      </div>

      <div className={`sc-card ${styles.tableCard}`}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Código</th>
              <th>Nome</th>
              <th>CPF/CNPJ</th>
              <th>Comissão (%)</th>
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className={styles.empty}>Carregando…</td></tr>
            ) : vendedores.length === 0 ? (
              <tr><td colSpan={6} className={styles.empty}>Nenhum vendedor cadastrado.</td></tr>
            ) : vendedores.map((v) => (
              <tr key={v.id}>
                <td className={styles.tdMono}>{v.codigo || "—"}</td>
                <td>{v.nome}</td>
                <td className={styles.tdMono}>{formatCpfCnpj(v.cpf_cnpj || "") || "—"}</td>
                <td className={styles.tdMono}>{money2(v.comissao_pct)}%</td>
                <td>
                  <span className={`${styles.badge} ${v.status === "ativo" ? styles.badgeAtivo : styles.badgeInativo}`}>
                    {v.status === "ativo" ? "Ativo" : "Inativo"}
                  </span>
                </td>
                <td>
                  <div className={styles.actions}>
                    {hasPermission(MODULO, "editar") && (
                      <button className={styles.btnLink} onClick={() => abrirEditar(v)}>Editar</button>
                    )}
                    {hasPermission(MODULO, "excluir") && (
                      <button className={`${styles.btnLink} ${styles.btnDanger}`} onClick={() => handleInativar(v)}>
                        {v.status === "ativo" ? "Inativar" : "Ativar"}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className={styles.overlay} onClick={fecharModal}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>{modal.id ? "Editar Vendedor" : "Novo Vendedor"}</h2>
              <button className={styles.btnClose} onClick={fecharModal}>×</button>
            </div>

            <div className={styles.tabs}>
              {TABS_DADOS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`${styles.tab} ${aba === t.id ? styles.tabActive : ""} ${abaErro === t.id ? styles.tabErro : ""}`}
                  onClick={() => setAba(t.id)}
                >
                  {t.label}
                </button>
              ))}
              {modal.id && TABS_GESTAO.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`${styles.tab} ${aba === t.id ? styles.tabActive : ""}`}
                  onClick={() => setAba(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {aba === "dados" && (
              <div className={styles.modalBody}>
                <div className={styles.fieldGrid}>
                  <label className={styles.field}>
                    <span>Código</span>
                    <input className={styles.input} value={modal.codigo || "Gerado automaticamente"} readOnly />
                  </label>

                  <label className={styles.field}>
                    <span>Tipo Pessoa</span>
                    <select className={styles.input} value={modal.tipo_pessoa} onChange={setF("tipo_pessoa")}>
                      <option value="fisica">Física</option>
                      <option value="juridica">Jurídica</option>
                    </select>
                  </label>

                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Nome *</span>
                    <input className={styles.input} value={modal.nome} onChange={setF("nome")} />
                  </label>

                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Nome Fantasia</span>
                    <input className={styles.input} value={modal.nome_fantasia} onChange={setF("nome_fantasia")} />
                  </label>

                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Descrição</span>
                    <textarea className={`${styles.input} ${styles.textarea}`} rows={2} value={modal.descricao} onChange={setF("descricao")} />
                  </label>

                  <label className={styles.field}>
                    <span>Comissão (%)</span>
                    <input type="number" step="0.01" className={styles.input} value={modal.comissao_pct} onChange={setF("comissao_pct")} />
                  </label>

                  <label className={styles.field}>
                    <span>Dia Pagto</span>
                    <input type="number" step="1" min="0" max="31" className={styles.input} value={modal.dia_pagto} onChange={setF("dia_pagto")} />
                  </label>

                  <label className={styles.field}>
                    <span>% Pago Emissão</span>
                    <input type="number" step="0.01" className={styles.input} value={modal.pct_pago_emissao} onChange={setF("pct_pago_emissao")} />
                  </label>

                  <label className={styles.field}>
                    <span>% Pago Baixa</span>
                    <input type="number" step="0.01" className={styles.input} value={modal.pct_pago_baixa} onChange={setF("pct_pago_baixa")} />
                  </label>

                  <label className={styles.field}>
                    <span>Data Cadastro</span>
                    <input
                      className={styles.input}
                      value={modal.data_cadastro ? new Date(modal.data_cadastro).toLocaleDateString("pt-BR") : "Hoje"}
                      readOnly
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Status</span>
                    <select className={styles.input} value={modal.status} onChange={setF("status")}>
                      <option value="ativo">Ativo</option>
                      <option value="inativo">Inativo</option>
                    </select>
                  </label>
                </div>

                {erro && <p className={styles.erro}>{erro}</p>}
              </div>
            )}

            {aba === "endereco" && (
              <div className={styles.modalBody}>
                <div className={styles.fieldGrid}>
                  <label className={styles.field}>
                    <span>CEP</span>
                    <input
                      className={styles.input}
                      value={modal.cep}
                      onChange={(e) => setModal((m) => ({ ...m, cep: formatCep(e.target.value) }))}
                      placeholder="00000-000"
                      maxLength={9}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Estado (UF)</span>
                    <input className={styles.input} value={modal.estado} onChange={setF("estado")} placeholder="SP" maxLength={2} />
                  </label>

                  <div className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Endereço / Número</span>
                    <div className={styles.endRow}>
                      <input className={styles.input} value={modal.endereco} onChange={setF("endereco")} placeholder="Rua, Av…" />
                      <input className={`${styles.input} ${styles.inputNumero}`} value={modal.numero} onChange={setF("numero")} placeholder="Nº" />
                    </div>
                  </div>

                  <label className={styles.field}>
                    <span>Complemento</span>
                    <input className={styles.input} value={modal.complemento} onChange={setF("complemento")} />
                  </label>

                  <label className={styles.field}>
                    <span>Bairro</span>
                    <input className={styles.input} value={modal.bairro} onChange={setF("bairro")} />
                  </label>

                  <label className={styles.field}>
                    <span>Município</span>
                    <input className={styles.input} value={modal.municipio} onChange={setF("municipio")} />
                  </label>
                </div>
              </div>
            )}

            {aba === "fiscal" && (
              <div className={styles.modalBody}>
                <div className={styles.fieldGrid}>
                  <label className={styles.field}>
                    <span>CPF/CNPJ</span>
                    <input
                      className={styles.input}
                      value={modal.cpf_cnpj}
                      onChange={(e) => setModal((m) => ({ ...m, cpf_cnpj: formatCpfCnpj(e.target.value) }))}
                      maxLength={18}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>RG/IE</span>
                    <input className={styles.input} value={modal.rg_ie} onChange={setF("rg_ie")} />
                  </label>

                  <label className={styles.field}>
                    <span>Inscrição Municipal</span>
                    <input className={styles.input} value={modal.inscricao_municipal} onChange={setF("inscricao_municipal")} />
                  </label>

                  <label className={styles.field}>
                    <span>Telefone</span>
                    <input className={styles.input} value={modal.telefone} onChange={setF("telefone")} placeholder="(00) 0000-0000" />
                  </label>

                  <label className={styles.field}>
                    <span>Celular</span>
                    <input className={styles.input} value={modal.celular} onChange={setF("celular")} placeholder="(00) 00000-0000" />
                  </label>

                  <label className={styles.field}>
                    <span>Fax</span>
                    <input className={styles.input} value={modal.fax} onChange={setF("fax")} />
                  </label>

                  <label className={styles.field}>
                    <span>E-mail</span>
                    <input type="email" className={styles.input} value={modal.email} onChange={setF("email")} />
                  </label>

                  <label className={styles.field}>
                    <span>E-mail NF-e</span>
                    <input type="email" className={styles.input} value={modal.email_nfe} onChange={setF("email_nfe")} />
                  </label>
                </div>
              </div>
            )}

            {aba === "acesso"    && modal.id && <TabAcesso vendedorId={modal.id} />}
            {aba === "metas"     && modal.id && <TabMetas vendedorId={modal.id} />}
            {aba === "catalogos" && modal.id && <TabCatalogos vendedorId={modal.id} />}
            {aba === "leads"     && modal.id && <TabLeads vendedorId={modal.id} />}

            {["dados", "endereco", "fiscal"].includes(aba) ? (
              <div className={styles.modalActions}>
                <button className={styles.btnSecondary} onClick={fecharModal} disabled={saving}>Cancelar</button>
                <button className={styles.btnPrimary} onClick={handleSalvar} disabled={saving}>
                  {saving ? "Salvando…" : "Salvar"}
                </button>
              </div>
            ) : (
              <div className={styles.modalActions}>
                <button className={styles.btnSecondary} onClick={fecharModal}>Fechar</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Aba: Acesso ─────────────────────────────────────────────────────────

function TabAcesso({ vendedorId }) {
  const [creds, setCreds]   = useState(null);
  const [form, setForm]     = useState({ username: "", senha: "" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg]       = useState(null);

  useEffect(() => {
    getCredenciaisVendedor(vendedorId).then(setCreds).catch(() => {});
  }, [vendedorId]);

  const handleSave = async () => {
    if (!form.username.trim() || !form.senha.trim()) {
      setMsg({ ok: false, text: "Preencha username e senha." }); return;
    }
    setSaving(true); setMsg(null);
    try {
      const d = await setCredenciaisVendedor(vendedorId, form);
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

// ── Aba: Metas ───────────────────────────────────────────────────────────

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
    getMetasVendedor(vendedorId).then((d) => {
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
      await updateMetasVendedor(vendedorId, payload);
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

// ── Aba: Catálogos ──────────────────────────────────────────────────────

function TabCatalogos({ vendedorId }) {
  const { hasPermission } = useAuth();
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

  if (loading) return <p className={styles.tabInner} style={{ color: "var(--sc-text-muted)", fontSize: 13 }}>Carregando…</p>;

  return (
    <div className={styles.tabInner}>
      {hasPermission(MODULO, "criar") && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
          <button className={styles.btnPill} onClick={() => { setShowUpload(true); setErrUp(null); setUpForm({ nome: "", tabela_preco_id: "" }); setUpFile(null); }}>
            + Upload Catálogo
          </button>
        </div>
      )}

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

// ── Aba: Leads ───────────────────────────────────────────────────────────

const LEAD_CAMPOS = [
  { label: "Nome *", key: "nome" },
  { label: "Segmento", key: "segmento" },
  { label: "Endereço", key: "endereco" },
  { label: "Cidade", key: "cidade" },
  { label: "Telefone", key: "telefone" },
];

const LEAD_VAZIO = { nome: "", segmento: "", endereco: "", cidade: "", telefone: "", observacao: "" };

function TabLeads({ vendedorId }) {
  const { hasPermission } = useAuth();
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
      {hasPermission(MODULO, "criar") && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
          <button className={styles.btnPill} onClick={() => { setShowNovo(true); setErr(null); setForm(LEAD_VAZIO); }}>
            + Novo Lead
          </button>
        </div>
      )}

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
                {hasPermission(MODULO, "excluir") && (
                  <button
                    style={{ background: "none", border: "none", cursor: "pointer", color: "var(--sc-danger-text)", fontSize: 16, lineHeight: 1, padding: "2px 4px" }}
                    onClick={() => handleDelete(lead.id)}
                  >×</button>
                )}
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

// ── Msg helper ───────────────────────────────────────────────────────────

function Msg({ msg }) {
  if (!msg) return null;
  return <p className={msg.ok ? styles.msgOk : styles.msgErro}>{msg.text}</p>;
}
