import { useState, useEffect, useCallback } from "react";
import { transportadorasApi } from "../api/transportadoras";
import { useAuth } from "../auth/useAuth";
import styles from "./TransportadorasPage.module.css";

const MODULO = "cadastros_transportadoras";

const formatCpfCnpj = (v) => {
  const d = v.replace(/\D/g, "");
  if (d.length <= 11) {
    // CPF
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

const TABS = [
  { id: "dados", label: "Dados" },
  { id: "endereco", label: "Endereço" },
  { id: "fiscal", label: "Fiscal / Contato" },
];

const VAZIO = {
  tipo_pessoa: "juridica",
  nome: "",
  nome_fantasia: "",
  endereco: "",
  numero: "",
  complemento: "",
  bairro: "",
  municipio: "",
  estado: "",
  cep: "",
  placa: "",
  telefone: "",
  fax: "",
  cpf_cnpj: "",
  rg_ie: "",
  email: "",
  email_nfe: "",
  homepage: "",
  contato: "",
  bloqueado: false,
};

export default function TransportadorasPage() {
  const { hasPermission } = useAuth();
  const [transportadoras, setTransportadoras] = useState([]);
  const [busca, setBusca] = useState("");
  const [filtroBloqueado, setFiltroBloqueado] = useState("");
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null);
  const [aba, setAba] = useState("dados");
  const [abaErro, setAbaErro] = useState(null);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState(null);
  const [cnpjStatus, setCnpjStatus] = useState(null);
  const [cepStatus, setCepStatus] = useState(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      setTransportadoras((await transportadorasApi.listar(busca, filtroBloqueado)) || []);
    } catch {
      setTransportadoras([]);
    } finally {
      setLoading(false);
    }
  }, [busca, filtroBloqueado]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const resetModal = (base) => {
    setModal(base);
    setAba("dados");
    setAbaErro(null);
    setCnpjStatus(null);
    setCepStatus(null);
    setErro(null);
  };

  const abrirNovo = () => resetModal({ ...VAZIO });

  const abrirEditar = (t) =>
    resetModal({
      id: t.id,
      codigo: t.codigo || "",
      tipo_pessoa: t.tipo_pessoa || "juridica",
      nome: t.nome || "",
      nome_fantasia: t.nome_fantasia || "",
      endereco: t.endereco || "",
      numero: t.numero || "",
      complemento: t.complemento || "",
      bairro: t.bairro || "",
      municipio: t.municipio || "",
      estado: t.estado || "",
      cep: formatCep(t.cep || ""),
      placa: t.placa || "",
      telefone: t.telefone || "",
      fax: t.fax || "",
      cpf_cnpj: formatCpfCnpj(t.cpf_cnpj || ""),
      rg_ie: t.rg_ie || "",
      email: t.email || "",
      email_nfe: t.email_nfe || "",
      homepage: t.homepage || "",
      contato: t.contato || "",
      bloqueado: !!t.bloqueado,
      data_cadastro: t.data_cadastro,
    });

  const fecharModal = () => {
    setModal(null);
    setErro(null);
    setCnpjStatus(null);
    setCepStatus(null);
  };
  const setF = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.value }));
  const setFUpper = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.value.toUpperCase() }));

  const handleSalvar = async () => {
    setAbaErro(null);
    if (!modal.nome.trim()) {
      setErro("Nome é obrigatório.");
      setAbaErro("dados");
      setAba("dados");
      return;
    }
    setSaving(true);
    setErro(null);
    try {
      const payload = {
        tipo_pessoa: modal.tipo_pessoa || null,
        nome: modal.nome.trim(),
        nome_fantasia: modal.nome_fantasia.trim() || null,
        endereco: modal.endereco.trim() || null,
        numero: modal.numero.trim() || null,
        complemento: modal.complemento.trim() || null,
        bairro: modal.bairro.trim() || null,
        municipio: modal.municipio.trim() || null,
        estado: modal.estado.trim().toUpperCase() || null,
        cep: stripDigits(modal.cep) || null,
        placa: modal.placa.trim().toUpperCase() || null,
        telefone: modal.telefone.trim() || null,
        fax: modal.fax.trim() || null,
        cpf_cnpj: stripDigits(modal.cpf_cnpj) || null,
        rg_ie: modal.rg_ie.trim() || null,
        email: modal.email.trim() || null,
        email_nfe: modal.email_nfe.trim() || null,
        homepage: modal.homepage.trim() || null,
        contato: modal.contato.trim() || null,
        bloqueado: modal.bloqueado,
      };
      if (modal.id) {
        await transportadorasApi.atualizar(modal.id, payload);
      } else {
        await transportadorasApi.criar(payload);
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
    if (!window.confirm("Deseja excluir esta transportadora?")) return;
    try {
      await transportadorasApi.deletar(id);
      await carregar();
    } catch (e) {
      alert(e.message);
    }
  };

  const consultarCnpj = async () => {
    const digits = stripDigits(modal.cpf_cnpj);
    if (digits.length !== 14) {
      setCnpjStatus("invalido");
      return;
    }

    setCnpjStatus("consultando");
    try {
      const res = await fetch(`https://brasilapi.com.br/api/cnpj/v1/${digits}`);
      if (res.status === 404) {
        setCnpjStatus("nao_encontrado");
        return;
      }
      if (!res.ok) {
        setCnpjStatus("erro");
        return;
      }

      const d = await res.json();
      const tel = (d.ddd_telefone_1 || "").trim();
      const logradouro = d.logradouro || "";
      const complemento = d.complemento || "";
      const cepRaw = (d.cep || "").replace(/\D/g, "");
      const cep = cepRaw.length === 8 ? `${cepRaw.slice(0, 5)}-${cepRaw.slice(5)}` : cepRaw;

      setModal((m) => ({
        ...m,
        nome: d.razao_social || m.nome,
        nome_fantasia: d.nome_fantasia || m.nome_fantasia,
        email: d.email || m.email,
        telefone: tel || m.telefone,
        cep,
        endereco: logradouro || m.endereco,
        complemento: complemento || m.complemento,
        numero: d.numero || m.numero,
        bairro: d.bairro || m.bairro,
        municipio: d.municipio || m.municipio,
        estado: d.uf || m.estado,
      }));
      setCnpjStatus("preenchido");
    } catch {
      setCnpjStatus("erro");
    }
  };

  const consultarCep = async () => {
    const digits = stripDigits(modal.cep);
    if (digits.length !== 8) {
      setCepStatus("invalido");
      return;
    }

    setCepStatus("consultando");
    try {
      const res = await fetch(`https://viacep.com.br/ws/${digits}/json/`);
      if (!res.ok) {
        setCepStatus("erro");
        return;
      }
      const d = await res.json();
      if (d.erro) {
        setCepStatus("nao_encontrado");
        return;
      }

      setModal((m) => ({
        ...m,
        endereco: d.logradouro || m.endereco,
        bairro: d.bairro || m.bairro,
        municipio: d.localidade || m.municipio,
        estado: d.uf || m.estado,
        complemento: d.complemento || m.complemento,
      }));
      setCepStatus("preenchido");
    } catch {
      setCepStatus("erro");
    }
  };

  const consultarSefaz = () => {
    alert("Consulta SEFAZ ainda não implementada — funcionalidade futura.");
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Transportadoras</h1>
        {hasPermission(MODULO, "criar") && (
          <button className={styles.btnNovo} onClick={abrirNovo}>
            + Nova Transportadora
          </button>
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
        <select
          className={styles.select}
          value={filtroBloqueado}
          onChange={(e) => setFiltroBloqueado(e.target.value)}
        >
          <option value="">Todos</option>
          <option value="false">Não bloqueadas</option>
          <option value="true">Bloqueadas</option>
        </select>
      </div>

      <div className={`sc-card ${styles.tableCard}`}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Código</th>
              <th>Nome</th>
              <th>CPF/CNPJ</th>
              <th>Telefone</th>
              <th>Bloqueado</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className={styles.empty}>
                  Carregando…
                </td>
              </tr>
            ) : transportadoras.length === 0 ? (
              <tr>
                <td colSpan={6} className={styles.empty}>
                  Nenhuma transportadora cadastrada.
                </td>
              </tr>
            ) : (
              transportadoras.map((t) => (
                <tr key={t.id}>
                  <td className={styles.tdMono}>{t.codigo || "—"}</td>
                  <td>{t.nome}</td>
                  <td className={styles.tdMono}>{formatCpfCnpj(t.cpf_cnpj || "") || "—"}</td>
                  <td>{t.telefone || "—"}</td>
                  <td>
                    <span
                      className={`${styles.badge} ${t.bloqueado ? styles.badgeBloqueado : styles.badgeOk}`}
                    >
                      {t.bloqueado ? "Sim" : "Não"}
                    </span>
                  </td>
                  <td>
                    <div className={styles.actions}>
                      {hasPermission(MODULO, "editar") && (
                        <button className={styles.btnLink} onClick={() => abrirEditar(t)}>
                          Editar
                        </button>
                      )}
                      {hasPermission(MODULO, "excluir") && (
                        <button
                          className={`${styles.btnLink} ${styles.btnDanger}`}
                          onClick={() => handleExcluir(t.id)}
                        >
                          Excluir
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className={styles.overlay} onClick={fecharModal}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>
                {modal.id ? "Editar Transportadora" : "Nova Transportadora"}
              </h2>
              <button className={styles.btnClose} onClick={fecharModal}>
                ×
              </button>
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
                    <span>Código</span>
                    <input
                      className={styles.input}
                      value={modal.codigo || "Gerado automaticamente"}
                      readOnly
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Tipo Pessoa</span>
                    <select
                      className={styles.input}
                      value={modal.tipo_pessoa}
                      onChange={setF("tipo_pessoa")}
                    >
                      <option value="juridica">Jurídica</option>
                      <option value="fisica">Física</option>
                    </select>
                  </label>

                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Nome *</span>
                    <input
                      className={styles.input}
                      value={modal.nome}
                      onChange={setFUpper("nome")}
                      placeholder="Razão social ou nome"
                    />
                  </label>

                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Nome Fantasia</span>
                    <input
                      className={styles.input}
                      value={modal.nome_fantasia}
                      onChange={setFUpper("nome_fantasia")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Placa</span>
                    <input
                      className={styles.input}
                      value={modal.placa}
                      onChange={(e) =>
                        setModal((m) => ({ ...m, placa: e.target.value.toUpperCase() }))
                      }
                      placeholder="ABC1D23"
                      maxLength={10}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Data Cadastro</span>
                    <input
                      className={styles.input}
                      value={
                        modal.data_cadastro
                          ? new Date(modal.data_cadastro).toLocaleDateString("pt-BR")
                          : "Hoje"
                      }
                      readOnly
                    />
                  </label>

                  <label className={styles.checkboxField}>
                    <input
                      type="checkbox"
                      checked={modal.bloqueado}
                      onChange={(e) => setModal((m) => ({ ...m, bloqueado: e.target.checked }))}
                    />
                    <span>Bloqueado</span>
                  </label>
                </div>
              )}

              {aba === "endereco" && (
                <div className={styles.fieldGrid}>
                  <div className={styles.field}>
                    <span>CEP</span>
                    <div className={styles.consultaRow}>
                      <input
                        className={styles.input}
                        value={modal.cep}
                        onChange={(e) => {
                          setModal((m) => ({ ...m, cep: formatCep(e.target.value) }));
                          setCepStatus(null);
                        }}
                        placeholder="00000-000"
                        maxLength={9}
                      />
                      <button
                        className={styles.btnConsultar}
                        onClick={consultarCep}
                        disabled={cepStatus === "consultando"}
                      >
                        {cepStatus === "consultando" ? "Consultando…" : "Buscar CEP"}
                      </button>
                    </div>
                  </div>

                  <label className={styles.field}>
                    <span>Estado (UF)</span>
                    <input
                      className={styles.input}
                      value={modal.estado}
                      onChange={setF("estado")}
                      placeholder="SP"
                      maxLength={2}
                    />
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
                      <input
                        className={styles.input}
                        value={modal.endereco}
                        onChange={setFUpper("endereco")}
                        placeholder="Rua, Av…"
                      />
                      <input
                        className={`${styles.input} ${styles.inputNumero}`}
                        value={modal.numero}
                        onChange={setFUpper("numero")}
                        placeholder="Nº"
                      />
                    </div>
                  </div>

                  <label className={styles.field}>
                    <span>Complemento</span>
                    <input
                      className={styles.input}
                      value={modal.complemento}
                      onChange={setFUpper("complemento")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Bairro</span>
                    <input
                      className={styles.input}
                      value={modal.bairro}
                      onChange={setFUpper("bairro")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Município</span>
                    <input
                      className={styles.input}
                      value={modal.municipio}
                      onChange={setFUpper("municipio")}
                    />
                  </label>
                </div>
              )}

              {aba === "fiscal" && (
                <div className={styles.fieldGrid}>
                  {/* CPF/CNPJ + Consultar */}
                  <div className={`${styles.field} ${styles.fieldFull}`}>
                    <span>CPF/CNPJ</span>
                    <div className={styles.consultaRow}>
                      <input
                        className={styles.input}
                        value={modal.cpf_cnpj}
                        onChange={(e) => {
                          setModal((m) => ({ ...m, cpf_cnpj: formatCpfCnpj(e.target.value) }));
                          setCnpjStatus(null);
                        }}
                        placeholder="00.000.000/0000-00"
                        maxLength={18}
                      />
                      <button
                        className={styles.btnConsultar}
                        onClick={consultarCnpj}
                        disabled={cnpjStatus === "consultando"}
                      >
                        {cnpjStatus === "consultando"
                          ? "Consultando…"
                          : "Consultar Receita Federal"}
                      </button>
                    </div>
                  </div>

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

                  <label className={styles.field}>
                    <span>RG/IE</span>
                    <input className={styles.input} value={modal.rg_ie} onChange={setF("rg_ie")} />
                  </label>

                  <label className={styles.field}>
                    <span>Telefone</span>
                    <input
                      className={styles.input}
                      value={modal.telefone}
                      onChange={setF("telefone")}
                      placeholder="(00) 0000-0000"
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Fax</span>
                    <input className={styles.input} value={modal.fax} onChange={setF("fax")} />
                  </label>

                  <label className={styles.field}>
                    <span>E-mail</span>
                    <input
                      type="email"
                      className={styles.input}
                      value={modal.email}
                      onChange={setF("email")}
                      placeholder="email@empresa.com"
                    />
                  </label>

                  <label className={styles.field}>
                    <span>E-mail NF-e</span>
                    <input
                      type="email"
                      className={styles.input}
                      value={modal.email_nfe}
                      onChange={setF("email_nfe")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Home-Page</span>
                    <input
                      className={`${styles.input} no-uppercase`}
                      value={modal.homepage}
                      onChange={setF("homepage")}
                      placeholder="https://…"
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Contato</span>
                    <input
                      className={styles.input}
                      value={modal.contato}
                      onChange={setFUpper("contato")}
                      placeholder="Nome do contato"
                    />
                  </label>
                </div>
              )}

              {erro && <p className={styles.erro}>{erro}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSefaz} onClick={consultarSefaz}>
                Consultar SEFAZ
              </button>
              <div className={styles.modalActionsRight}>
                <button className={styles.btnSecondary} onClick={fecharModal} disabled={saving}>
                  Cancelar
                </button>
                <button className={styles.btnPrimary} onClick={handleSalvar} disabled={saving}>
                  {saving ? "Salvando…" : "Salvar"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
