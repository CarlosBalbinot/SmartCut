import { useState, useEffect, useCallback } from "react";
import { clientesApi } from "../services/api";
import { API_BASE } from "../services/config";
import styles from "./ClientesPage.module.css";

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

const stripDigits = (v) => (v || "").replace(/\D/g, "");

const VAZIO = {
  razao_social: "",
  cnpj: "",
  cpf: "",
  ie: "",
  email: "",
  telefone: "",
  contato: "",
  endereco: "",
  numero: "",
  bairro: "",
  cidade: "",
  estado: "",
  cep: "",
  observacoes: "",
};

export default function ClientesPage() {
  const [clientes, setClientes]       = useState([]);
  const [busca, setBusca]             = useState("");
  const [loading, setLoading]         = useState(true);
  const [modal, setModal]             = useState(null);
  const [saving, setSaving]           = useState(false);
  const [erro, setErro]               = useState(null);
  const [cnpjStatus, setCnpjStatus]   = useState(null);
  const [clienteExistente, setClienteExistente] = useState(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      setClientes((await clientesApi.listar(busca)) || []);
    } catch {
      setClientes([]);
    } finally {
      setLoading(false);
    }
  }, [busca]);

  useEffect(() => { carregar(); }, [carregar]);

  const resetModal = (base = VAZIO) => {
    setModal(base);
    setCnpjStatus(null);
    setClienteExistente(null);
    setErro(null);
  };

  const abrirNovo     = ()  => resetModal({ ...VAZIO });
  const abrirEditar   = (c) => resetModal({
    id: c.id,
    razao_social: c.razao_social || "",
    cnpj:  formatCnpj(c.cnpj || ""),
    cpf:   c.cpf  || "",
    ie:    c.ie   || "",
    email: c.email || "",
    telefone: c.telefone || "",
    contato:  c.contato  || "",
    endereco: c.endereco || "",
    numero:   c.numero   || "",
    bairro:   c.bairro   || "",
    cidade:   c.cidade   || "",
    estado:   c.estado   || "",
    cep:      c.cep      || "",
    observacoes: c.observacoes || "",
  });

  const fecharModal = () => { setModal(null); setErro(null); setCnpjStatus(null); setClienteExistente(null); };
  const setF = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.value }));

  const handleSalvar = async () => {
    if (!modal.razao_social.trim()) { setErro("Razão Social é obrigatória."); return; }
    setSaving(true); setErro(null);
    try {
      const payload = {
        razao_social: modal.razao_social.trim(),
        cnpj:  stripDigits(modal.cnpj) || null,
        cpf:   stripDigits(modal.cpf)  || null,
        ie:    modal.ie.trim()         || null,
        email: modal.email.trim()      || null,
        telefone: modal.telefone.trim() || null,
        contato:  modal.contato.trim()  || null,
        endereco: modal.endereco.trim() || null,
        numero:   modal.numero.trim()   || null,
        bairro:   modal.bairro.trim()   || null,
        cidade:   modal.cidade.trim()   || null,
        estado:   modal.estado.trim().toUpperCase() || null,
        cep:      stripDigits(modal.cep) || null,
        observacoes: modal.observacoes.trim() || null,
      };
      if (modal.id) {
        await clientesApi.atualizar(modal.id, payload);
      } else {
        await clientesApi.criar(payload);
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
    if (!window.confirm("Deseja excluir este cliente?")) return;
    try { await clientesApi.deletar(id); await carregar(); } catch {}
  };

  const consultarCnpj = async (forcarBrasilApi = false) => {
    const digits = stripDigits(modal.cnpj);
    if (digits.length !== 14) { setCnpjStatus("invalido"); return; }

    setCnpjStatus("consultando");
    setClienteExistente(null);

    try {
      if (!forcarBrasilApi) {
        const existente = await clientesApi.buscarCnpj(digits);
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
      const end = [logradouro, complemento].filter(Boolean).join(", ");
      const cepRaw = (d.cep || "").replace(/\D/g, "");
      const cep = cepRaw.length === 8 ? `${cepRaw.slice(0, 5)}-${cepRaw.slice(5)}` : cepRaw;

      setModal((m) => ({
        ...m,
        razao_social: d.razao_social || m.razao_social,
        email:    d.email    || m.email,
        telefone: tel        || m.telefone,
        cep,
        endereco: end        || m.endereco,
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

  const carregarExistente = () => {
    if (!clienteExistente) return;
    setModal((m) => ({
      ...m,
      razao_social: clienteExistente.razao_social || "",
      cnpj:  formatCnpj(clienteExistente.cnpj || ""),
      cpf:   clienteExistente.cpf       || "",
      ie:    clienteExistente.ie        || "",
      email: clienteExistente.email     || "",
      telefone: clienteExistente.telefone  || "",
      contato:  clienteExistente.contato   || "",
      endereco: clienteExistente.endereco  || "",
      numero:   clienteExistente.numero    || "",
      bairro:   clienteExistente.bairro    || "",
      cidade:   clienteExistente.cidade    || "",
      estado:   clienteExistente.estado    || "",
      cep:      clienteExistente.cep       || "",
      observacoes: clienteExistente.observacoes || "",
    }));
    setCnpjStatus("preenchido");
    setClienteExistente(null);
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Clientes</h1>
        <div className={styles.headerRight}>
          <input
            className={styles.busca}
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por nome ou CNPJ…"
          />
          <button className={styles.btnPrimary} onClick={abrirNovo}>+ Novo Cliente</button>
        </div>
      </div>

      <div className={styles.card}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Razão Social</th>
              <th>CNPJ / CPF</th>
              <th>Cidade / UF</th>
              <th>Telefone</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className={styles.empty}>Carregando…</td></tr>
            ) : clientes.length === 0 ? (
              <tr><td colSpan={5} className={styles.empty}>Nenhum cliente cadastrado.</td></tr>
            ) : clientes.map((c) => (
              <tr key={c.id}>
                <td>{c.razao_social}</td>
                <td className={styles.tdMono}>{displayCnpj(c.cnpj) || c.cpf || "—"}</td>
                <td>{c.cidade && c.estado ? `${c.cidade} / ${c.estado}` : c.cidade || "—"}</td>
                <td>{c.telefone || "—"}</td>
                <td>
                  <div className={styles.actions}>
                    <button className={styles.btnLink} onClick={() => abrirEditar(c)}>Editar</button>
                    <button className={`${styles.btnLink} ${styles.btnDanger}`} onClick={() => handleExcluir(c.id)}>
                      Excluir
                    </button>
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
              <h2 className={styles.modalTitle}>{modal.id ? "Editar Cliente" : "Novo Cliente"}</h2>
              <button className={styles.btnClose} onClick={fecharModal}>×</button>
            </div>

            <div className={styles.modalBody}>
              {/* ── Dados Fiscais ── */}
              <p className={styles.sectionLabel}>Dados Fiscais</p>
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

                {/* Banners de status */}
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
                      <strong>Cliente já cadastrado:</strong> {clienteExistente.razao_social}
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
                  <input className={styles.input} value={modal.ie} onChange={setF("ie")} placeholder="Preencha manualmente" />
                </label>

                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Razão Social *</span>
                  <input className={styles.input} value={modal.razao_social} onChange={setF("razao_social")} placeholder="Nome ou razão social" />
                </label>

                <label className={styles.field}>
                  <span>E-mail</span>
                  <input type="email" className={styles.input} value={modal.email} onChange={setF("email")} placeholder="email@empresa.com" />
                </label>

                <label className={styles.field}>
                  <span>Telefone</span>
                  <input className={styles.input} value={modal.telefone} onChange={setF("telefone")} placeholder="(00) 00000-0000" />
                </label>

                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Contato</span>
                  <input className={styles.input} value={modal.contato} onChange={setF("contato")} placeholder="Nome do contato" />
                </label>
              </div>

              {/* ── Endereço ── */}
              <p className={`${styles.sectionLabel} ${styles.sectionLabelMt}`}>Endereço</p>
              <div className={styles.fieldGrid}>
                <label className={styles.field}>
                  <span>CEP</span>
                  <input className={styles.input} value={modal.cep} onChange={setF("cep")} placeholder="00000-000" maxLength={9} />
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
                  <span>Bairro</span>
                  <input className={styles.input} value={modal.bairro} onChange={setF("bairro")} placeholder="Bairro" />
                </label>

                <label className={styles.field}>
                  <span>Cidade</span>
                  <input className={styles.input} value={modal.cidade} onChange={setF("cidade")} placeholder="Cidade" />
                </label>

                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Observações</span>
                  <textarea className={`${styles.input} ${styles.textarea}`} value={modal.observacoes} onChange={setF("observacoes")} rows={2} placeholder="Observações opcionais" />
                </label>
              </div>

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
