import { useState, useEffect, useCallback } from "react";
import { usuariosApi } from "../api/usuarios";
import { useAuth } from "../auth/useAuth";
import styles from "./UsuariosPage.module.css";

// Módulos com acesso controlável — cobre todos os MODULOS_VALIDOS do
// backend (middleware/permissions.py). Cada item declara as ações que o
// módulo realmente verifica (ver/criar/editar/excluir e, em alguns casos,
// confirmar/gerar); módulos "compostos" como pedidos_criar, pedidos_editar,
// configuracoes_editar etc. já codificam a ação no próprio nome do módulo
// e por isso só têm "ver" na lista — é a única ação que o backend checa
// para eles (mesmo padrão de pedidos_ver).
const ACAO_LABEL = {
  ver: "Ver",
  criar: "Criar",
  editar: "Editar",
  excluir: "Excluir",
  confirmar: "Confirmar",
  gerar: "Gerar",
  executar: "Executar",
  cancelar: "Cancelar",
};

const CRUD = ["ver", "criar", "editar", "excluir"];

const GRUPOS = [
  { grupo: "Cadastros", itens: [
    { modulo: "cadastros_clientes", label: "Clientes", acoes: CRUD },
    { modulo: "cadastros_produtos", label: "Produtos", acoes: CRUD },
    { modulo: "cadastros_transportadoras", label: "Transportadoras", acoes: CRUD },
    { modulo: "cadastros_vendedores", label: "Vendedores", acoes: CRUD },
  ]},
  { grupo: "Produção", itens: [
    { modulo: "tecidos", label: "Tecidos", acoes: CRUD },
    { modulo: "moldes", label: "Moldes", acoes: CRUD },
    { modulo: "encaixes", label: "Encaixes", acoes: CRUD },
    { modulo: "encaixe_rapido", label: "Encaixe Rápido", acoes: ["ver", "criar"] },
  ]},
  { grupo: "Comercial", itens: [
    { modulo: "precificacao", label: "Precificação", acoes: CRUD },
    { modulo: "projecao", label: "Projeção", acoes: ["ver"] },
  ]},
  { grupo: "Pedidos", itens: [
    { modulo: "pedidos_ver", label: "Ver pedidos", acoes: ["ver"] },
    { modulo: "pedidos_criar", label: "Criar pedidos", acoes: ["ver"] },
    { modulo: "pedidos_editar", label: "Editar pedidos", acoes: ["ver"] },
    { modulo: "pedidos_excluir", label: "Excluir pedidos", acoes: ["ver"] },
    { modulo: "pedidos_emitir_nfe", label: "Emitir NF-e de pedidos", acoes: ["ver"] },
  ]},
  { grupo: "Financeiro", itens: [
    { modulo: "financeiro_painel", label: "Painel", acoes: ["ver"] },
    { modulo: "financeiro_fluxo", label: "Fluxo de Caixa", acoes: [...CRUD, "confirmar"] },
    { modulo: "financeiro_compras", label: "Compras", acoes: CRUD },
    { modulo: "financeiro_vendas", label: "Vendas", acoes: [...CRUD, "gerar"] },
    { modulo: "financeiro_contabilidade", label: "Contabilidade", acoes: ["ver", "gerar"] },
  ]},
  { grupo: "Fiscal", itens: [
    { modulo: "fiscal_nfe", label: "NF-e", acoes: CRUD },
    // Item 5.1: ações de execução em módulos próprios (o "ver" deixou de
    // autorizar transmitir/cancelar/CC-e — era o bug de permissão).
    { modulo: "fiscal_transmitir", label: "Transmitir NF-e", acoes: ["executar"] },
    { modulo: "fiscal_cancelar", label: "Cancelar NF-e", acoes: ["cancelar"] },
    { modulo: "fiscal_carta_correcao", label: "Carta de Correção", acoes: ["criar"] },
  ]},
  { grupo: "Configurações", itens: [
    { modulo: "configuracoes_ver", label: "Visualizar", acoes: ["ver"] },
    { modulo: "configuracoes_editar", label: "Editar", acoes: ["ver"] },
  ]},
  { grupo: "Usuários", itens: [
    { modulo: "usuarios_admin", label: "Administração de usuários", acoes: ["ver"] },
  ]},
];

const chave = (modulo, acao) => `${modulo}:${acao}`;

const FORM_VAZIO = { username: "", nome_completo: "", senha: "" };

export default function UsuariosPage() {
  const { usuario: usuarioLogado } = useAuth();
  const [usuarios, setUsuarios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selecionadoId, setSelecionadoId] = useState(null);
  const [detalhe, setDetalhe] = useState(null);
  const [tab, setTab] = useState("dados");
  const [showNovo, setShowNovo] = useState(false);
  const [toast, setToast] = useState(null);

  const carregarLista = useCallback(async () => {
    setLoading(true);
    try {
      const data = await usuariosApi.listar();
      setUsuarios(data || []);
    } catch (e) {
      setToast(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregarLista(); }, [carregarLista]);

  const showToast = (text) => {
    setToast(text);
    setTimeout(() => setToast(null), 4000);
  };

  const selecionar = async (id) => {
    setSelecionadoId(id);
    setTab("dados");
    try {
      const data = await usuariosApi.obter(id);
      setDetalhe(data);
    } catch (e) {
      showToast(e.message);
    }
  };

  const handleCriado = async (novo) => {
    setShowNovo(false);
    await carregarLista();
    if (novo?.id) selecionar(novo.id);
  };

  const handleAtualizado = async (atualizado) => {
    setDetalhe(atualizado);
    await carregarLista();
    showToast("Alterações salvas.");
  };

  return (
    <div className={styles.page}>
      <div className="sc-page-header">
        <h1>Usuários</h1>
      </div>

      <div className={styles.layout}>
      <div className={styles.listWrap}>
        <div className={styles.listHeader}>
          <span className={styles.listTitle}>Usuários do Sistema</span>
          <button className={styles.btnNovo} onClick={() => setShowNovo(true)}>+ Novo</button>
        </div>

        {toast && <div className={styles.msgErro} style={{ margin: "8px 10px" }}>{toast}</div>}

        {loading ? (
          <p className={styles.empty}>Carregando…</p>
        ) : usuarios.length === 0 ? (
          <p className={styles.empty}>Nenhum usuário cadastrado.</p>
        ) : (
          <ul className={styles.list}>
            {usuarios.map((u) => (
              <li
                key={u.id}
                className={`${styles.item} ${selecionadoId === u.id ? styles.itemSel : ""} ${!u.ativo ? styles.itemInativo : ""}`}
                onClick={() => selecionar(u.id)}
              >
                <div className={styles.itemInfo}>
                  <span className={styles.itemNome}>{u.nome_completo}</span>
                  <span className={styles.itemSub}>@{u.username}</span>
                </div>
                <div className={styles.itemBadges}>
                  {u.is_admin && <span className={styles.badgeAdmin}>Admin</span>}
                  {!u.ativo && <span className={styles.badgeInativo}>Inativo</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className={styles.drawer}>
        {!detalhe ? (
          <div className={styles.emptyRight}>
            <p>Selecione um usuário para ver os detalhes.</p>
          </div>
        ) : (
          <>
            <div className={styles.drawerHeader}>
              <div>
                <div className={styles.drawerNomeRow}>
                  <span className={styles.drawerNome}>{detalhe.nome_completo}</span>
                  {detalhe.is_admin && <span className={styles.badgeAdmin}>Admin</span>}
                </div>
                <span className={styles.drawerSub}>@{detalhe.username}</span>
              </div>
            </div>

            <div className={styles.tabBar}>
              <button
                className={`${styles.tabBtn} ${tab === "dados" ? styles.tabBtnActive : ""}`}
                onClick={() => setTab("dados")}
              >Dados</button>
              <button
                className={`${styles.tabBtn} ${tab === "permissoes" ? styles.tabBtnActive : ""}`}
                onClick={() => setTab("permissoes")}
                disabled={detalhe.is_admin}
                title={detalhe.is_admin ? "Administradores têm acesso total" : undefined}
              >Permissões</button>
            </div>

            <div className={styles.tabContent}>
              {tab === "dados" && (
                <PainelDados
                  detalhe={detalhe}
                  isProprio={usuarioLogado?.id === detalhe.id}
                  onSalvo={handleAtualizado}
                  onErro={showToast}
                />
              )}
              {tab === "permissoes" && !detalhe.is_admin && (
                <PainelPermissoes
                  detalhe={detalhe}
                  onSalvo={handleAtualizado}
                  onErro={showToast}
                />
              )}
            </div>
          </>
        )}
      </div>

      {showNovo && (
        <ModalNovoUsuario onClose={() => setShowNovo(false)} onCriado={handleCriado} onErro={showToast} />
      )}
      </div>
    </div>
  );
}

function PainelDados({ detalhe, isProprio, onSalvo, onErro }) {
  const [form, setForm] = useState({ nome_completo: detalhe.nome_completo, senha: "", ativo: detalhe.ativo });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setForm({ nome_completo: detalhe.nome_completo, senha: "", ativo: detalhe.ativo });
  }, [detalhe]);

  const handleSave = async () => {
    if (!form.nome_completo.trim()) { onErro("Informe o nome completo."); return; }
    setSaving(true);
    try {
      const payload = { nome_completo: form.nome_completo.trim(), ativo: form.ativo };
      if (form.senha) payload.senha = form.senha;
      const atualizado = await usuariosApi.atualizar(detalhe.id, payload);
      onSalvo(atualizado);
    } catch (e) {
      onErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.tabInner}>
      <label className={styles.field}>
        <span>Nome completo</span>
        <input
          className={styles.input}
          value={form.nome_completo}
          onChange={(e) => setForm((f) => ({ ...f, nome_completo: e.target.value }))}
        />
      </label>

      <label className={styles.field} style={{ marginTop: 10 }}>
        <span>Usuário</span>
        <input className={styles.input} value={detalhe.username} disabled />
      </label>

      <label className={styles.field} style={{ marginTop: 10 }}>
        <span>Nova senha (deixe em branco para manter a atual)</span>
        <input
          type="password"
          className={styles.input}
          value={form.senha}
          onChange={(e) => setForm((f) => ({ ...f, senha: e.target.value }))}
          autoComplete="new-password"
        />
      </label>

      <label className={styles.checkboxRow} style={{ marginTop: 14 }}>
        <input
          type="checkbox"
          checked={form.ativo}
          disabled={isProprio}
          onChange={(e) => setForm((f) => ({ ...f, ativo: e.target.checked }))}
        />
        Usuário ativo
        {isProprio && <span className={styles.hint}> — não é possível desativar o próprio usuário</span>}
      </label>

      <div className={styles.actions}>
        <button className={styles.btnPrimary} onClick={handleSave} disabled={saving}>
          {saving ? "Salvando…" : "Salvar"}
        </button>
      </div>
    </div>
  );
}

function PainelPermissoes({ detalhe, onSalvo, onErro }) {
  const [marcados, setMarcados] = useState(
    () => new Set((detalhe.permissoes || []).map((p) => chave(p.modulo, p.acao)))
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setMarcados(new Set((detalhe.permissoes || []).map((p) => chave(p.modulo, p.acao))));
  }, [detalhe]);

  const toggle = (modulo, acao) => {
    setMarcados((prev) => {
      const next = new Set(prev);
      const k = chave(modulo, acao);
      if (next.has(k)) next.delete(k); else next.add(k);
      return next;
    });
  };

  const chavesDoGrupo = (itens) =>
    itens.flatMap(({ modulo, acoes }) => acoes.map((acao) => chave(modulo, acao)));

  const grupoTotalmenteMarcado = (itens) =>
    chavesDoGrupo(itens).every((k) => marcados.has(k));

  const toggleGrupo = (itens) => {
    const chaves = chavesDoGrupo(itens);
    const todasMarcadas = chaves.every((k) => marcados.has(k));
    setMarcados((prev) => {
      const next = new Set(prev);
      chaves.forEach((k) => (todasMarcadas ? next.delete(k) : next.add(k)));
      return next;
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const permissoes = Array.from(marcados).map((k) => {
        const [modulo, acao] = k.split(":");
        return { modulo, acao };
      });
      const atualizado = await usuariosApi.substituirPermissoes(detalhe.id, permissoes);
      onSalvo(atualizado);
    } catch (e) {
      onErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.tabInner} style={{ maxWidth: 640 }}>
      <p className={styles.hint} style={{ marginBottom: 14 }}>
        Marque as ações que este usuário pode executar em cada módulo.
      </p>

      {GRUPOS.map(({ grupo, itens }) => (
        <div key={grupo} className={styles.permGrupo}>
          <div className={styles.permGrupoHeader}>
            <p className={styles.permGrupoTitulo}>{grupo}</p>
            <label className={styles.permSelecionarTudo}>
              <input
                type="checkbox"
                checked={grupoTotalmenteMarcado(itens)}
                onChange={() => toggleGrupo(itens)}
              />
              Selecionar tudo
            </label>
          </div>

          {itens.map(({ modulo, label, acoes }) => (
            <div key={modulo} className={styles.permRow}>
              <span className={styles.permModulo}>{label}</span>
              <div className={styles.permAcoes}>
                {acoes.map((acao) => (
                  <label key={acao} className={styles.permAcaoItem}>
                    <input
                      type="checkbox"
                      checked={marcados.has(chave(modulo, acao))}
                      onChange={() => toggle(modulo, acao)}
                    />
                    {ACAO_LABEL[acao]}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </div>
      ))}

      <div className={styles.actions}>
        <button className={styles.btnPrimary} onClick={handleSave} disabled={saving}>
          {saving ? "Salvando…" : "Salvar permissões"}
        </button>
      </div>
    </div>
  );
}

function ModalNovoUsuario({ onClose, onCriado, onErro }) {
  const [form, setForm] = useState(FORM_VAZIO);
  const [confirmarSenha, setConfirmarSenha] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);

  const handleUsernameChange = (e) => {
    setForm((f) => ({ ...f, username: e.target.value.toLowerCase().replace(/\s/g, "") }));
  };

  const handleSave = async () => {
    setErr(null);
    if (!form.username || !form.nome_completo || !form.senha) {
      setErr("Preencha todos os campos.");
      return;
    }
    if (form.senha !== confirmarSenha) {
      setErr("As senhas não coincidem.");
      return;
    }
    setSaving(true);
    try {
      const novo = await usuariosApi.criar({ ...form, permissoes: [] });
      onCriado(novo);
    } catch (e) {
      setErr(e.message);
      onErro?.(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.modalOverlay}>
      <div className={styles.modal}>
        <h3 className={styles.modalTitle}>Novo Usuário</h3>

        <label className={styles.field}>
          <span>Usuário</span>
          <input
            className={styles.input}
            value={form.username}
            onChange={handleUsernameChange}
            autoComplete="username"
            autoFocus
          />
        </label>

        <label className={styles.field} style={{ marginTop: 10 }}>
          <span>Nome completo</span>
          <input
            className={styles.input}
            value={form.nome_completo}
            onChange={(e) => setForm((f) => ({ ...f, nome_completo: e.target.value }))}
            autoComplete="name"
          />
        </label>

        <label className={styles.field} style={{ marginTop: 10 }}>
          <span>Senha</span>
          <input
            type="password"
            className={styles.input}
            value={form.senha}
            onChange={(e) => setForm((f) => ({ ...f, senha: e.target.value }))}
            autoComplete="new-password"
          />
        </label>

        <label className={styles.field} style={{ marginTop: 10 }}>
          <span>Confirmar senha</span>
          <input
            type="password"
            className={styles.input}
            value={confirmarSenha}
            onChange={(e) => setConfirmarSenha(e.target.value)}
            autoComplete="new-password"
          />
        </label>

        {err && <p className={styles.msgErro} style={{ marginTop: 10 }}>{err}</p>}

        <div className={styles.modalActions}>
          <button className={styles.btnSecondary} onClick={onClose}>Cancelar</button>
          <button className={styles.btnPrimary} onClick={handleSave} disabled={saving}>
            {saving ? "Criando…" : "Criar usuário"}
          </button>
        </div>
      </div>
    </div>
  );
}
