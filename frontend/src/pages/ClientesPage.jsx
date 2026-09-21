import { useState, useEffect, useCallback } from "react";
import { getClientes, createCliente, updateCliente, deleteCliente, getClienteByCnpj } from "../api/clientes";
import { buscarEnderecoPorCep } from "../utils/cepIbge";
import { useAuth } from "../auth/useAuth";
import styles from "./ClientesPage.module.css";

const MODULO = "cadastros_clientes";

const formatCnpj = (v) => {
  const d = v.replace(/\D/g, "").slice(0, 14);
  if (d.length <= 2) return d;
  if (d.length <= 5) return `${d.slice(0, 2)}.${d.slice(2)}`;
  if (d.length <= 8) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5)}`;
  if (d.length <= 12) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8)}`;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
};

const displayCnpj = (raw) => {
  if (!raw) return null;
  const d = raw.replace(/\D/g, "");
  if (d.length !== 14) return raw;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
};

const formatCep = (v) => {
  const d = v.replace(/\D/g, "").slice(0, 8);
  if (d.length <= 5) return d;
  return `${d.slice(0, 5)}-${d.slice(5)}`;
};

const stripDigits = (v) => (v || "").replace(/\D/g, "");

const TIPO_REGISTRO_LABEL = { cliente: "Cliente", fornecedor: "Fornecedor", ambos: "Ambos" };

const TABS = [
  { id: "dados", label: "Dados" },
  { id: "fiscal", label: "Fiscal" },
  { id: "endereco", label: "Endereço" },
  { id: "contato", label: "Contato" },
];

const VAZIO = {
  tipo_registro: "cliente",
  tipo_pessoa: "juridica",
  razao_social: "",
  nome_fantasia: "",
  cnpj: "",
  cpf: "",
  ie: "",
  inscricao_municipal: "",
  rg: "",
  id_estrangeiro: "",
  tipo_fiscal: "consumidor_final",
  email: "",
  email_nfe: "",
  telefone: "",
  telefone2: "",
  celular: "",
  whatsapp: "",
  fax: "",
  contato: "",
  endereco: "",
  numero: "",
  complemento: "",
  bairro: "",
  cidade: "",
  estado: "",
  cep: "",
  pais: "Brasil",
  codigo_ibge_municipio: "",
  caixa_postal: "",
  atividade: "",
  nascimento: "",
  homepage: "",
  instagram: "",
  grupo: "",
  situacao: "ativo",
  observacoes: "",
};

export default function ClientesPage() {
  const { hasPermission } = useAuth();
  const [clientes, setClientes]       = useState([]);
  const [busca, setBusca]             = useState("");
  const [filtroTipo, setFiltroTipo]   = useState("");
  const [loading, setLoading]         = useState(true);
  const [modal, setModal]             = useState(null);
  const [aba, setAba]                 = useState("dados");
  const [abaErro, setAbaErro]         = useState(null);
  const [saving, setSaving]           = useState(false);
  const [erro, setErro]               = useState(null);
  const [cnpjStatus, setCnpjStatus]   = useState(null);
  const [clienteExistente, setClienteExistente] = useState(null);
  const [cepStatus, setCepStatus]     = useState(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      setClientes((await getClientes(busca, filtroTipo)) || []);
    } catch {
      setClientes([]);
    } finally {
      setLoading(false);
    }
  }, [busca, filtroTipo]);

  useEffect(() => { carregar(); }, [carregar]);

  const resetModal = (base = VAZIO) => {
    setModal(base);
    setAba("dados");
    setAbaErro(null);
    setCnpjStatus(null);
    setCepStatus(null);
    setClienteExistente(null);
    setErro(null);
  };

  const abrirNovo     = ()  => resetModal({ ...VAZIO });
  const abrirEditar   = (c) => resetModal({
    id: c.id,
    codigo: c.codigo || "",
    tipo_registro: c.tipo_registro || "cliente",
    tipo_pessoa: c.tipo_pessoa || "juridica",
    razao_social: c.razao_social || "",
    nome_fantasia: c.nome_fantasia || "",
    cnpj:  formatCnpj(c.cnpj || ""),
    cpf:   c.cpf  || "",
    ie:    c.ie   || "",
    inscricao_municipal: c.inscricao_municipal || "",
    rg: c.rg || "",
    id_estrangeiro: c.id_estrangeiro || "",
    tipo_fiscal: c.tipo_fiscal || "consumidor_final",
    email: c.email || "",
    email_nfe: c.email_nfe || "",
    telefone: c.telefone || "",
    telefone2: c.telefone2 || "",
    celular: c.celular || "",
    whatsapp: c.whatsapp || "",
    fax: c.fax || "",
    contato:  c.contato  || "",
    endereco: c.endereco || "",
    numero:   c.numero   || "",
    complemento: c.complemento || "",
    bairro:   c.bairro   || "",
    cidade:   c.cidade   || "",
    estado:   c.estado   || "",
    cep:      formatCep(c.cep || ""),
    pais: c.pais || "Brasil",
    codigo_ibge_municipio: c.codigo_ibge_municipio || "",
    caixa_postal: c.caixa_postal || "",
    atividade: c.atividade || "",
    nascimento: c.nascimento || "",
    homepage: c.homepage || "",
    instagram: c.instagram || "",
    grupo: c.grupo || "",
    situacao: c.situacao || "ativo",
    observacoes: c.observacoes || "",
    data_cadastro: c.created_at,
  });

  const fecharModal = () => { setModal(null); setErro(null); setCnpjStatus(null); setCepStatus(null); setClienteExistente(null); };
  const setF = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.value }));

  const handleSalvar = async () => {
    setAbaErro(null);
    if (!modal.razao_social.trim()) {
      setErro("Razão Social é obrigatória.");
      setAbaErro("dados");
      setAba("dados");
      return;
    }
    setSaving(true); setErro(null);
    try {
      const payload = {
        tipo_registro: modal.tipo_registro,
        tipo_pessoa: modal.tipo_pessoa || null,
        razao_social: modal.razao_social.trim(),
        nome_fantasia: modal.nome_fantasia.trim() || null,
        cnpj:  stripDigits(modal.cnpj) || null,
        cpf:   stripDigits(modal.cpf)  || null,
        ie:    modal.ie.trim()         || null,
        inscricao_municipal: modal.inscricao_municipal.trim() || null,
        rg: modal.rg.trim() || null,
        id_estrangeiro: modal.id_estrangeiro.trim() || null,
        tipo_fiscal: modal.tipo_fiscal || null,
        email: modal.email.trim()      || null,
        email_nfe: modal.email_nfe.trim() || null,
        telefone: modal.telefone.trim() || null,
        telefone2: modal.telefone2.trim() || null,
        celular: modal.celular.trim() || null,
        whatsapp: modal.whatsapp.trim() || null,
        fax: modal.fax.trim() || null,
        contato:  modal.contato.trim()  || null,
        endereco: modal.endereco.trim() || null,
        numero:   modal.numero.trim()   || null,
        complemento: modal.complemento.trim() || null,
        bairro:   modal.bairro.trim()   || null,
        cidade:   modal.cidade.trim()   || null,
        estado:   modal.estado.trim().toUpperCase() || null,
        cep:      stripDigits(modal.cep) || null,
        pais: modal.pais.trim() || null,
        codigo_ibge_municipio: modal.codigo_ibge_municipio || null,
        caixa_postal: modal.caixa_postal.trim() || null,
        atividade: modal.atividade.trim() || null,
        nascimento: modal.nascimento || null,
        homepage: modal.homepage.trim() || null,
        instagram: modal.instagram.trim() || null,
        grupo: modal.grupo.trim() || null,
        situacao: modal.situacao,
        observacoes: modal.observacoes.trim() || null,
      };
      if (modal.id) {
        await updateCliente(modal.id, payload);
      } else {
        await createCliente(payload);
      }
      await carregar();
      fecharModal();
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleExcluir = async (id) => {
    if (!window.confirm("Deseja excluir este cadastro?")) return;
    try { await deleteCliente(id); await carregar(); } catch {}
  };

  const consultarCnpj = async (forcarBrasilApi = false) => {
    const digits = stripDigits(modal.cnpj);
    if (digits.length !== 14) { setCnpjStatus("invalido"); return; }

    setCnpjStatus("consultando");
    setClienteExistente(null);

    try {
      if (!forcarBrasilApi) {
        const existente = await getClienteByCnpj(digits);
        if (existente) {
          setClienteExistente(existente);
          setCnpjStatus("ja_cadastrado");
          return;
        }
      }

      const res = await fetch(`https://brasilapi.com.br/api/cnpj/v1/${digits}`);
      if (res.status === 404) { setCnpjStatus("nao_encontrado"); return; }
      if (!res.ok)            { setCnpjStatus("erro");           return; }

      const d = await res.json();
      const tel = (d.ddd_telefone_1 || "").trim();
      const logradouro  = d.logradouro  || "";
      const complemento = d.complemento || "";
      const cepRaw = (d.cep || "").replace(/\D/g, "");
      const cep = cepRaw.length === 8 ? `${cepRaw.slice(0, 5)}-${cepRaw.slice(5)}` : cepRaw;

      setModal((m) => ({
        ...m,
        razao_social: d.razao_social || m.razao_social,
        nome_fantasia: d.nome_fantasia || m.nome_fantasia,
        email:    d.email    || m.email,
        telefone: tel        || m.telefone,
        cep,
        endereco: logradouro  || m.endereco,
        complemento: complemento || m.complemento,
        numero:   d.numero   || m.numero,
        bairro:   d.bairro   || m.bairro,
        cidade:   d.municipio || m.cidade,
        estado:   d.uf        || m.estado,
      }));
      setCnpjStatus("preenchido");
    } catch {
      setCnpjStatus("erro");
    }
  };

  const consultarCep = async () => {
    const digits = stripDigits(modal.cep);
    if (digits.length !== 8) { setCepStatus("invalido"); return; }

    setCepStatus("consultando");
    try {
      const r = await buscarEnderecoPorCep(digits);
      if (!r.logradouro && !r.bairro && !r.cidade) { setCepStatus("nao_encontrado"); return; }

      setModal((m) => ({
        ...m,
        endereco: r.logradouro || m.endereco,
        bairro:   r.bairro     || m.bairro,
        cidade:   r.cidade     || m.cidade,
        estado:   r.uf         || m.estado,
        complemento: r.complemento || m.complemento,
        codigo_ibge_municipio: r.codigo_ibge || m.codigo_ibge_municipio,
      }));
      setCepStatus("preenchido");
    } catch {
      setCepStatus("erro");
    }
  };

  const carregarExistente = () => {
    if (!clienteExistente) return;
    abrirEditar(clienteExistente);
    setCnpjStatus("preenchido");
    setClienteExistente(null);
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Clientes</h1>
        {hasPermission(MODULO, "criar") && (
          <button className={styles.btnNovo} onClick={abrirNovo}>+ Novo Cadastro</button>
        )}
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <input
            className={styles.busca}
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por nome, CNPJ ou CPF…"
          />
        </div>
        <select className={styles.select} value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
          <option value="">Todos</option>
          <option value="cliente">Clientes</option>
          <option value="fornecedor">Fornecedores</option>
        </select>
      </div>

      <div className={`sc-card ${styles.tableCard}`}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Código</th>
              <th>Razão Social</th>
              <th>Tipo</th>
              <th>CNPJ / CPF</th>
              <th>Cidade / UF</th>
              <th>Telefone</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className={styles.empty}>Carregando…</td></tr>
            ) : clientes.length === 0 ? (
              <tr><td colSpan={7} className={styles.empty}>Nenhum cadastro encontrado.</td></tr>
            ) : clientes.map((c) => (
              <tr key={c.id}>
                <td className={styles.tdMono}>{c.codigo || "—"}</td>
                <td>{c.razao_social}</td>
                <td>
                  <span className={`${styles.badge} ${styles["badge_" + (c.tipo_registro || "cliente")]}`}>
                    {TIPO_REGISTRO_LABEL[c.tipo_registro] || "Cliente"}
                  </span>
                </td>
                <td className={styles.tdMono}>{displayCnpj(c.cnpj) || c.cpf || "—"}</td>
                <td>{c.cidade && c.estado ? `${c.cidade} / ${c.estado}` : c.cidade || "—"}</td>
                <td>{c.telefone || "—"}</td>
                <td>
                  <div className={styles.actions}>
                    {hasPermission(MODULO, "editar") && (
                      <button className={styles.btnLink} onClick={() => abrirEditar(c)}>Editar</button>
                    )}
                    {hasPermission(MODULO, "excluir") && (
                      <button className={`${styles.btnLink} ${styles.btnDanger}`} onClick={() => handleExcluir(c.id)}>
                        Excluir
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
              <h2 className={styles.modalTitle}>{modal.id ? "Editar Cadastro" : "Novo Cadastro"}</h2>
              <button className={styles.btnClose} onClick={fecharModal}>×</button>
            </div>

            <div className={styles.tabs}>
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`${styles.tab} ${aba === t.id ? styles.tabActive : ""} ${abaErro === t.id ? styles.tabErro : ""}`}
                  onClick={() => setAba(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div className={styles.modalBody}>
              {aba === "dados" && (
                <div className={styles.fieldGrid}>
                  <label className={styles.field}>
                    <span>Tipo Registro</span>
                    <select className={styles.input} value={modal.tipo_registro} onChange={setF("tipo_registro")}>
                      <option value="cliente">Cliente</option>
                      <option value="fornecedor">Fornecedor</option>
                      <option value="ambos">Ambos</option>
                    </select>
                  </label>

                  <label className={styles.field}>
                    <span>Tipo Pessoa</span>
                    <select className={styles.input} value={modal.tipo_pessoa} onChange={setF("tipo_pessoa")}>
                      <option value="juridica">Jurídica</option>
                      <option value="fisica">Física</option>
                    </select>
                  </label>

                  <label className={styles.field}>
                    <span>Código</span>
                    <input className={styles.input} value={modal.codigo || "Gerado automaticamente"} readOnly />
                  </label>

                  <label className={styles.field}>
                    <span>Situação</span>
                    <select className={styles.input} value={modal.situacao} onChange={setF("situacao")}>
                      <option value="ativo">Ativo</option>
                      <option value="inativo">Inativo</option>
                    </select>
                  </label>

                  <label className={styles.field}>
                    <span>Grupo</span>
                    <input className={styles.input} value={modal.grupo} onChange={setF("grupo")} placeholder="Opcional" />
                  </label>

                  <label className={styles.field}>
                    <span>Data Cadastro</span>
                    <input
                      className={styles.input}
                      value={modal.data_cadastro ? new Date(modal.data_cadastro).toLocaleDateString("pt-BR") : "Hoje"}
                      readOnly
                    />
                  </label>

                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Razão Social *</span>
                    <input className={styles.input} value={modal.razao_social} onChange={setF("razao_social")} placeholder="Nome ou razão social" />
                  </label>

                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Nome Fantasia</span>
                    <input className={styles.input} value={modal.nome_fantasia} onChange={setF("nome_fantasia")} />
                  </label>

                  <label className={styles.field}>
                    <span>Tipo Fiscal</span>
                    <select className={styles.input} value={modal.tipo_fiscal} onChange={setF("tipo_fiscal")}>
                      <option value="consumidor_final">Consumidor Final</option>
                      <option value="contribuinte">Contribuinte</option>
                      <option value="nao_contribuinte">Não Contribuinte</option>
                    </select>
                  </label>
                </div>
              )}

              {aba === "fiscal" && (
                <div className={styles.fieldGrid}>
                  {/* CNPJ + Consultar */}
                  <div className={`${styles.field} ${styles.fieldFull}`}>
                    <span>CNPJ</span>
                    <div className={styles.cnpjRow}>
                      <input
                        className={styles.input}
                        value={modal.cnpj}
                        onChange={(e) => {
                          setModal((m) => ({ ...m, cnpj: formatCnpj(e.target.value) }));
                          setCnpjStatus(null);
                          setClienteExistente(null);
                        }}
                        placeholder="00.000.000/0000-00"
                        maxLength={18}
                      />
                      <button
                        className={styles.btnConsultar}
                        onClick={() => consultarCnpj(false)}
                        disabled={cnpjStatus === "consultando"}
                      >
                        {cnpjStatus === "consultando" ? "Consultando…" : "Consultar Receita Federal"}
                      </button>
                    </div>
                  </div>

                  {/* Banners de status CNPJ */}
                  {cnpjStatus === "invalido" && (
                    <div className={`${styles.banner} ${styles.bannerErro} ${styles.fieldFull}`}>
                      CNPJ inválido — informe 14 dígitos numéricos.
                    </div>
                  )}
                  {cnpjStatus === "preenchido" && (
                    <div className={`${styles.banner} ${styles.bannerSucesso} ${styles.fieldFull}`}>
                      Dados preenchidos pela Receita Federal. Revise antes de salvar.
                    </div>
                  )}
                  {cnpjStatus === "nao_encontrado" && (
                    <div className={`${styles.banner} ${styles.bannerAviso} ${styles.fieldFull}`}>
                      CNPJ não encontrado na Receita Federal. Preencha manualmente.
                    </div>
                  )}
                  {cnpjStatus === "erro" && (
                    <div className={`${styles.banner} ${styles.bannerErro} ${styles.fieldFull}`}>
                      Erro ao consultar. Verifique sua conexão ou preencha manualmente.
                    </div>
                  )}
                  {cnpjStatus === "ja_cadastrado" && clienteExistente && (
                    <div className={`${styles.banner} ${styles.bannerInfo} ${styles.fieldFull}`}>
                      <span>
                        <strong>Cadastro já existente:</strong> {clienteExistente.razao_social}
                      </span>
                      <div className={styles.bannerBtns}>
                        <button className={styles.btnBannerPrimary} onClick={carregarExistente}>
                          Carregar dados cadastrados
                        </button>
                        <button className={styles.btnBannerSecondary} onClick={() => consultarCnpj(true)}>
                          Continuar consultando
                        </button>
                      </div>
                    </div>
                  )}

                  <label className={styles.field}>
                    <span>CPF</span>
                    <input className={styles.input} value={modal.cpf} onChange={setF("cpf")} placeholder="000.000.000-00" />
                  </label>

                  <label className={styles.field}>
                    <span>Inscrição Estadual (IE)</span>
                    <input className={styles.input} value={modal.ie} onChange={setF("ie")} />
                  </label>

                  <label className={styles.field}>
                    <span>Inscrição Municipal</span>
                    <input className={styles.input} value={modal.inscricao_municipal} onChange={setF("inscricao_municipal")} />
                  </label>

                  <label className={styles.field}>
                    <span>RG</span>
                    <input className={styles.input} value={modal.rg} onChange={setF("rg")} />
                  </label>

                  <label className={styles.field}>
                    <span>ID Estrangeiro</span>
                    <input className={styles.input} value={modal.id_estrangeiro} onChange={setF("id_estrangeiro")} />
                  </label>
                </div>
              )}

              {aba === "endereco" && (
                <div className={styles.fieldGrid}>
                  <div className={styles.field}>
                    <span>CEP</span>
                    <div className={styles.cnpjRow}>
                      <input
                        className={styles.input}
                        value={modal.cep}
                        onChange={(e) => { setModal((m) => ({ ...m, cep: formatCep(e.target.value) })); setCepStatus(null); }}
                        placeholder="00000-000"
                        maxLength={9}
                      />
                      <button className={styles.btnConsultar} onClick={consultarCep} disabled={cepStatus === "consultando"}>
                        {cepStatus === "consultando" ? "Consultando…" : "Buscar CEP"}
                      </button>
                    </div>
                  </div>

                  <label className={styles.field}>
                    <span>Estado (UF)</span>
                    <input className={styles.input} value={modal.estado} onChange={setF("estado")} placeholder="SP" maxLength={2} />
                  </label>

                  {cepStatus === "invalido" && (
                    <div className={`${styles.banner} ${styles.bannerErro} ${styles.fieldFull}`}>
                      CEP inválido — informe 8 dígitos numéricos.
                    </div>
                  )}
                  {cepStatus === "nao_encontrado" && (
                    <div className={`${styles.banner} ${styles.bannerAviso} ${styles.fieldFull}`}>
                      CEP não encontrado. Preencha o endereço manualmente.
                    </div>
                  )}
                  {cepStatus === "erro" && (
                    <div className={`${styles.banner} ${styles.bannerErro} ${styles.fieldFull}`}>
                      Erro ao consultar o CEP. Verifique sua conexão.
                    </div>
                  )}
                  {cepStatus === "preenchido" && (
                    <div className={`${styles.banner} ${styles.bannerSucesso} ${styles.fieldFull}`}>
                      Endereço preenchido pelo ViaCEP. Revise antes de salvar.
                    </div>
                  )}

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
                    <input className={styles.input} value={modal.bairro} onChange={setF("bairro")} placeholder="Bairro" />
                  </label>

                  <label className={styles.field}>
                    <span>Município</span>
                    <input className={styles.input} value={modal.cidade} onChange={setF("cidade")} placeholder="Cidade" />
                  </label>

                  <label className={styles.field}>
                    <span>País</span>
                    <input className={styles.input} value={modal.pais} onChange={setF("pais")} />
                  </label>
                </div>
              )}

              {aba === "contato" && (
                <div className={styles.fieldGrid}>
                  <label className={styles.field}>
                    <span>Telefone 1</span>
                    <input className={styles.input} value={modal.telefone} onChange={setF("telefone")} placeholder="(00) 0000-0000" />
                  </label>

                  <label className={styles.field}>
                    <span>Telefone 2</span>
                    <input className={styles.input} value={modal.telefone2} onChange={setF("telefone2")} />
                  </label>

                  <label className={styles.field}>
                    <span>Celular</span>
                    <input className={styles.input} value={modal.celular} onChange={setF("celular")} placeholder="(00) 00000-0000" />
                  </label>

                  <label className={styles.field}>
                    <span>WhatsApp</span>
                    <input className={styles.input} value={modal.whatsapp} onChange={setF("whatsapp")} />
                  </label>

                  <label className={styles.field}>
                    <span>Fax</span>
                    <input className={styles.input} value={modal.fax} onChange={setF("fax")} />
                  </label>

                  <label className={styles.field}>
                    <span>Contato</span>
                    <input className={styles.input} value={modal.contato} onChange={setF("contato")} placeholder="Nome do contato" />
                  </label>

                  <label className={styles.field}>
                    <span>E-mail</span>
                    <input type="email" className={styles.input} value={modal.email} onChange={setF("email")} placeholder="email@empresa.com" />
                  </label>

                  <label className={styles.field}>
                    <span>E-mail NF-e</span>
                    <input type="email" className={styles.input} value={modal.email_nfe} onChange={setF("email_nfe")} />
                  </label>

                  <label className={styles.field}>
                    <span>Home-Page</span>
                    <input className={styles.input} value={modal.homepage} onChange={setF("homepage")} placeholder="https://…" />
                  </label>

                  <label className={styles.field}>
                    <span>Instagram</span>
                    <input className={styles.input} value={modal.instagram} onChange={setF("instagram")} placeholder="@usuario" />
                  </label>

                  <label className={styles.field}>
                    <span>Atividade</span>
                    <input className={styles.input} value={modal.atividade} onChange={setF("atividade")} placeholder="Ramo de atividade" />
                  </label>

                  <label className={styles.field}>
                    <span>Caixa Postal</span>
                    <input className={styles.input} value={modal.caixa_postal} onChange={setF("caixa_postal")} />
                  </label>

                  <label className={styles.field}>
                    <span>Nascimento</span>
                    <input type="date" className={styles.input} value={modal.nascimento || ""} onChange={setF("nascimento")} />
                  </label>

                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Observações</span>
                    <textarea className={`${styles.input} ${styles.textarea}`} value={modal.observacoes} onChange={setF("observacoes")} rows={2} placeholder="Observações opcionais" />
                  </label>
                </div>
              )}

              {erro && <p className={styles.erro}>{erro}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharModal} disabled={saving}>Cancelar</button>
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
