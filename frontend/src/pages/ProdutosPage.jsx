import { useState, useEffect, useCallback, useMemo } from "react";
import { produtosApi, gruposProdutoApi } from "../api/produtos";
import * as tabelasGradeApi from "../api/tabelasGrade";
import { atualizarSku, excluirSku } from "../api/gradeProdutos";
import { useAuth } from "../auth/useAuth";
import styles from "./ProdutosPage.module.css";

const MODULO = "cadastros_produtos";

const TAMANHOS_DISPONIVEIS = ["PP", "P", "M", "G", "GG", "XGG"];

const VAZIO_PRODUTO = {
  grupo_id: "",
  descricao: "",
  tipo: "",
  almoxarifado: "01",
  unidade: "",
  segunda_unidade: "",
  tipo_conversao: "",
  fator_conversao: "",
  classe: "",
  marca: "",
  comissao_pct: "0",
  custo: "0",
  margem_lucro_pct: "0",
  preco_venda: "0",
  ultimo_preco_compra: "0",
  tipo_cod_barras: "",
  cod_barras: "",
  peso_gramas: "",
  peso_kg: "",
  linha_grade_id: "",
  coluna_grade_id: "",
  status: "ativo",
  tamanhos_disponiveis: [],
  // Impostos
  ncm: "",
  cest: "",
  origem: "0",
  icms_incidencia: "normal",
  aliquota_ipi_pct: "0",
  codigo_iss: "",
  cod_trib_iss: "",
  cod_cnae: "",
  base_icms_st_ret: "0",
  valor_icms_st_ret: "0",
  base_fcp_st_ret: "0",
  aliq_fcp_st_ret_pct: "0",
  valor_fcp_st_ret: "0",
  nat_receita: "",
  codigo_anp: "",
  conta_contabil: "",
  cod_fci: "",
  valor_importacao: "0",
  inf_adicionais: "",
  inventario_sped: "sim",
  fcp: "nao",
  um_faturamento: "primeira_um",
};

const VAZIO_GRUPO = { nome: "", prefixo: "", situacao: "ativo" };

const num = (v) => (v === "" || v === null || v === undefined ? undefined : Number(v));
const txtOuNull = (v) => {
  const t = (v || "").trim();
  return t || null;
};

function produtoParaForm(p) {
  return {
    grupo_id: p.grupo_id || "",
    descricao: p.descricao || "",
    tipo: p.tipo || "",
    almoxarifado: p.almoxarifado || "01",
    unidade: p.unidade || "",
    segunda_unidade: p.segunda_unidade || "",
    tipo_conversao: p.tipo_conversao || "",
    fator_conversao: p.fator_conversao ?? "",
    classe: p.classe || "",
    marca: p.marca || "",
    comissao_pct: p.comissao_pct ?? "0",
    custo: p.custo ?? "0",
    margem_lucro_pct: p.margem_lucro_pct ?? "0",
    preco_venda: p.preco_venda ?? "0",
    ultimo_preco_compra: p.ultimo_preco_compra ?? "0",
    tipo_cod_barras: p.tipo_cod_barras || "",
    cod_barras: p.cod_barras || "",
    peso_gramas: p.peso_gramas ?? "",
    peso_kg: p.peso_kg ?? "",
    linha_grade_id: p.linha_grade_id || "",
    coluna_grade_id: p.coluna_grade_id || "",
    linha_grade_nome: p.linha_grade_nome || "",
    coluna_grade_nome: p.coluna_grade_nome || "",
    status: p.status || "ativo",
    tamanhos_disponiveis: p.tamanhos_disponiveis || [],
    ncm: p.ncm || "",
    cest: p.cest || "",
    origem: String(p.origem ?? 0),
    icms_incidencia: p.icms_incidencia || "normal",
    aliquota_ipi_pct: p.aliquota_ipi_pct ?? "0",
    codigo_iss: p.codigo_iss || "",
    cod_trib_iss: p.cod_trib_iss || "",
    cod_cnae: p.cod_cnae || "",
    base_icms_st_ret: p.base_icms_st_ret ?? "0",
    valor_icms_st_ret: p.valor_icms_st_ret ?? "0",
    base_fcp_st_ret: p.base_fcp_st_ret ?? "0",
    aliq_fcp_st_ret_pct: p.aliq_fcp_st_ret_pct ?? "0",
    valor_fcp_st_ret: p.valor_fcp_st_ret ?? "0",
    nat_receita: p.nat_receita || "",
    codigo_anp: p.codigo_anp || "",
    conta_contabil: p.conta_contabil || "",
    cod_fci: p.cod_fci || "",
    valor_importacao: p.valor_importacao ?? "0",
    inf_adicionais: p.inf_adicionais || "",
    inventario_sped: p.inventario_sped ? "sim" : "nao",
    fcp: p.fcp ? "sim" : "nao",
    um_faturamento: p.um_faturamento || "primeira_um",
  };
}

function formParaPayload(f) {
  return {
    grupo_id: f.grupo_id,
    descricao: f.descricao.trim(),
    tipo: txtOuNull(f.tipo),
    almoxarifado: f.almoxarifado.trim() || "01",
    unidade: f.unidade.trim(),
    segunda_unidade: txtOuNull(f.segunda_unidade),
    tipo_conversao: txtOuNull(f.tipo_conversao),
    fator_conversao: num(f.fator_conversao),
    classe: txtOuNull(f.classe),
    marca: txtOuNull(f.marca),
    comissao_pct: num(f.comissao_pct),
    custo: num(f.custo),
    margem_lucro_pct: num(f.margem_lucro_pct),
    preco_venda: num(f.preco_venda),
    ultimo_preco_compra: num(f.ultimo_preco_compra),
    tipo_cod_barras: txtOuNull(f.tipo_cod_barras),
    cod_barras: txtOuNull(f.cod_barras),
    peso_gramas: num(f.peso_gramas),
    peso_kg: num(f.peso_kg),
    linha_grade_id: f.linha_grade_id ? Number(f.linha_grade_id) : null,
    coluna_grade_id: f.coluna_grade_id ? Number(f.coluna_grade_id) : null,
    status: f.status,
    tamanhos_disponiveis:
      f.tamanhos_disponiveis && f.tamanhos_disponiveis.length > 0 ? f.tamanhos_disponiveis : null,
    ncm: txtOuNull(f.ncm),
    cest: txtOuNull(f.cest),
    origem: parseInt(f.origem, 10) || 0,
    icms_incidencia: f.icms_incidencia,
    aliquota_ipi_pct: num(f.aliquota_ipi_pct),
    codigo_iss: txtOuNull(f.codigo_iss),
    cod_trib_iss: txtOuNull(f.cod_trib_iss),
    cod_cnae: txtOuNull(f.cod_cnae),
    base_icms_st_ret: num(f.base_icms_st_ret),
    valor_icms_st_ret: num(f.valor_icms_st_ret),
    base_fcp_st_ret: num(f.base_fcp_st_ret),
    aliq_fcp_st_ret_pct: num(f.aliq_fcp_st_ret_pct),
    valor_fcp_st_ret: num(f.valor_fcp_st_ret),
    nat_receita: txtOuNull(f.nat_receita),
    codigo_anp: txtOuNull(f.codigo_anp),
    conta_contabil: txtOuNull(f.conta_contabil),
    cod_fci: txtOuNull(f.cod_fci),
    valor_importacao: num(f.valor_importacao),
    inf_adicionais: txtOuNull(f.inf_adicionais),
    inventario_sped: f.inventario_sped === "sim",
    fcp: f.fcp === "sim",
    um_faturamento: f.um_faturamento,
  };
}

const money = (v) => Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export default function ProdutosPage() {
  const { hasPermission } = useAuth();
  const [produtos, setProdutos] = useState([]);
  const [grupos, setGrupos] = useState([]);
  const [tabelasGrade, setTabelasGrade] = useState([]);
  const [loading, setLoading] = useState(true);

  const [busca, setBusca] = useState("");
  const [filtroGrupo, setFiltroGrupo] = useState("");
  const [filtroStatus, setFiltroStatus] = useState("");

  const [modal, setModal] = useState(null); // form do produto
  const [aba, setAba] = useState("dados");
  const [abaErro, setAbaErro] = useState(null);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState(null);

  const [modalGrupos, setModalGrupos] = useState(false);

  const [modalSku, setModalSku] = useState(null);
  const [savingSku, setSavingSku] = useState(false);
  const [erroSku, setErroSku] = useState(null);

  const carregarListas = useCallback(async () => {
    const [g, t] = await Promise.all([
      gruposProdutoApi.listar().catch(() => []),
      tabelasGradeApi.listar().catch(() => []),
    ]);
    setGrupos(g || []);
    setTabelasGrade(t || []);
  }, []);

  const carregarProdutos = useCallback(async () => {
    setLoading(true);
    try {
      const filtros = { excluirPais: true };
      if (filtroStatus) filtros.status = filtroStatus;
      if (filtroGrupo) filtros.grupoId = filtroGrupo;
      setProdutos((await produtosApi.listar(filtros)) || []);
    } catch {
      setProdutos([]);
    } finally {
      setLoading(false);
    }
  }, [filtroStatus, filtroGrupo]);

  useEffect(() => {
    carregarListas();
  }, [carregarListas]);
  useEffect(() => {
    carregarProdutos();
  }, [carregarProdutos]);

  const gruposAtivos = useMemo(() => grupos.filter((g) => g.situacao === "ativo"), [grupos]);
  const tabelasGradeAtivas = useMemo(
    () => tabelasGrade.filter((t) => t.situacao === "Ativa"),
    [tabelasGrade]
  );

  const gruposPorId = useMemo(() => {
    const map = {};
    grupos.forEach((g) => {
      map[g.id] = g;
    });
    return map;
  }, [grupos]);

  const produtosFiltrados = useMemo(() => {
    if (!busca.trim()) return produtos;
    const termo = busca.trim().toLowerCase();
    return produtos.filter(
      (p) =>
        p.codigo.toLowerCase().includes(termo) ||
        (p.descricao_completa || p.descricao).toLowerCase().includes(termo)
    );
  }, [produtos, busca]);

  const abrirNovo = () => {
    setModal({ ...VAZIO_PRODUTO });
    setAba("dados");
    setAbaErro(null);
    setErro(null);
  };

  const abrirEditar = async (p) => {
    // A listagem (excluir_pais=true) devolve uma forma reduzida — busca o
    // produto completo antes de abrir o modal com todos os campos.
    try {
      const full = await produtosApi.obter(p.id);
      setModal({
        id: full.id,
        codigo: full.codigo,
        data_cadastro: full.data_cadastro,
        ...produtoParaForm(full),
      });
      setAba("dados");
      setAbaErro(null);
      setErro(null);
    } catch (e) {
      alert(e.message);
    }
  };

  const fecharModal = () => {
    setModal(null);
    setErro(null);
  };
  const setF = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.value }));
  const setFUpper = (k) => (e) => setModal((m) => ({ ...m, [k]: e.target.value.toUpperCase() }));

  const toggleTamanho = (t) => {
    setModal((m) => {
      const sel = m.tamanhos_disponiveis || [];
      const novo = sel.includes(t) ? sel.filter((x) => x !== t) : [...sel, t];
      return { ...m, tamanhos_disponiveis: TAMANHOS_DISPONIVEIS.filter((x) => novo.includes(x)) };
    });
  };

  const handleSalvar = async () => {
    setAbaErro(null);
    if (!modal.grupo_id) {
      setErro("Selecione um grupo.");
      setAbaErro("dados");
      setAba("dados");
      return;
    }
    if (!modal.descricao.trim()) {
      setErro("Descrição é obrigatória.");
      setAbaErro("dados");
      setAba("dados");
      return;
    }
    if (!modal.unidade.trim()) {
      setErro("Unidade é obrigatória.");
      setAbaErro("dados");
      setAba("dados");
      return;
    }

    setSaving(true);
    setErro(null);
    try {
      const payload = formParaPayload(modal);
      if (modal.id) {
        await produtosApi.atualizar(modal.id, payload);
      } else {
        await produtosApi.criar(payload);
      }
      await carregarProdutos();
      fecharModal();
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleExcluir = async (p) => {
    if (p.is_sku) {
      if (!window.confirm(`Excluir o SKU "${p.codigo}"?`)) return;
      try {
        await excluirSku(p.produto_pai_id, p.sku_id);
        await carregarProdutos();
      } catch (e) {
        alert(e.message);
      }
      return;
    }
    if (!window.confirm("Deseja excluir este produto?")) return;
    try {
      await produtosApi.deletar(p.id);
      await carregarProdutos();
    } catch (e) {
      alert(e.message);
    }
  };

  const abrirEditarSku = (p) => {
    setModalSku({
      produtoPaiId: p.produto_pai_id,
      skuId: p.sku_id,
      codigo: p.codigo,
      preco_venda: String(p.preco_venda ?? ""),
      status: p.status,
    });
    setErroSku(null);
  };

  const fecharModalSku = () => {
    setModalSku(null);
    setErroSku(null);
  };

  const handleSalvarSku = async () => {
    if (!modalSku.codigo.trim()) {
      setErroSku("Código é obrigatório.");
      return;
    }
    setSavingSku(true);
    setErroSku(null);
    try {
      await atualizarSku(modalSku.produtoPaiId, modalSku.skuId, {
        codigo: modalSku.codigo.trim(),
        preco_venda: modalSku.preco_venda === "" ? null : Number(modalSku.preco_venda),
        situacao: modalSku.status === "ativo" ? "Ativo" : "Inativo",
      });
      await carregarProdutos();
      fecharModalSku();
    } catch (e) {
      setErroSku(e.message);
    } finally {
      setSavingSku(false);
    }
  };

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Produtos</h1>
        {hasPermission(MODULO, "criar") && (
          <button className={styles.btnNovo} onClick={abrirNovo}>
            + Novo Produto
          </button>
        )}
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <input
            className={styles.busca}
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por código ou descrição…"
          />
        </div>
        <select
          className={styles.select}
          value={filtroGrupo}
          onChange={(e) => setFiltroGrupo(e.target.value)}
        >
          <option value="">Todos os grupos</option>
          {grupos.map((g) => (
            <option key={g.id} value={g.id}>
              {g.nome}
            </option>
          ))}
        </select>
        <select
          className={styles.select}
          value={filtroStatus}
          onChange={(e) => setFiltroStatus(e.target.value)}
        >
          <option value="">Todos os status</option>
          <option value="ativo">Ativo</option>
          <option value="inativo">Inativo</option>
        </select>
        <button className={styles.btnSecondary} onClick={() => setModalGrupos(true)}>
          Grupos de Produto
        </button>
      </div>

      <div className={`sc-card ${styles.tableCard}`}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Código</th>
              <th>Descrição</th>
              <th>Grupo</th>
              <th>Unidade</th>
              <th>Preço Venda</th>
              <th>Status</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className={styles.empty}>
                  Carregando…
                </td>
              </tr>
            ) : produtosFiltrados.length === 0 ? (
              <tr>
                <td colSpan={7} className={styles.empty}>
                  Nenhum produto cadastrado.
                </td>
              </tr>
            ) : (
              produtosFiltrados.map((p) => (
                <tr key={p.id}>
                  <td className={styles.tdMono}>{p.codigo}</td>
                  <td>{p.descricao_completa || p.descricao}</td>
                  <td>{gruposPorId[p.grupo_id]?.nome || "—"}</td>
                  <td>{p.unidade}</td>
                  <td className={styles.tdMono}>{money(p.preco_venda)}</td>
                  <td>
                    <span
                      className={`${styles.badge} ${p.status === "ativo" ? styles.badgeAtivo : styles.badgeInativo}`}
                    >
                      {p.status === "ativo" ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td>
                    <div className={styles.actions}>
                      {hasPermission(MODULO, "editar") && (
                        <button
                          className={styles.btnLink}
                          onClick={() => (p.is_sku ? abrirEditarSku(p) : abrirEditar(p))}
                        >
                          Editar
                        </button>
                      )}
                      {hasPermission(MODULO, "excluir") && (
                        <button
                          className={`${styles.btnLink} ${styles.btnDanger}`}
                          onClick={() => handleExcluir(p)}
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
              <h2 className={styles.modalTitle}>{modal.id ? "Editar Produto" : "Novo Produto"}</h2>
              <button className={styles.btnClose} onClick={fecharModal}>
                ×
              </button>
            </div>

            <div className={styles.tabs}>
              <button
                type="button"
                className={`${styles.tab} ${aba === "dados" ? styles.tabActive : ""} ${abaErro === "dados" ? styles.tabErro : ""}`}
                onClick={() => setAba("dados")}
              >
                Dados
              </button>
              <button
                type="button"
                className={`${styles.tab} ${aba === "impostos" ? styles.tabActive : ""}`}
                onClick={() => setAba("impostos")}
              >
                Impostos / Faturamento
              </button>
            </div>

            <div className={styles.modalBody}>
              {aba === "dados" && (
                <div className={styles.fieldGrid}>
                  <label className={styles.field}>
                    <span>Grupo *</span>
                    <select
                      className={styles.input}
                      value={modal.grupo_id}
                      onChange={setF("grupo_id")}
                    >
                      <option value="">Selecione…</option>
                      {gruposAtivos.map((g) => (
                        <option key={g.id} value={g.id}>
                          {g.nome} ({g.prefixo})
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className={styles.field}>
                    <span>Código</span>
                    <input
                      className={styles.input}
                      value={modal.codigo || "Gerado automaticamente"}
                      readOnly
                    />
                  </label>

                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Descrição *</span>
                    <input
                      className={styles.input}
                      value={modal.descricao}
                      onChange={setFUpper("descricao")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Tipo</span>
                    <input className={styles.input} value={modal.tipo} onChange={setF("tipo")} />
                  </label>

                  <label className={styles.field}>
                    <span>Almoxarifado</span>
                    <input
                      className={styles.input}
                      value={modal.almoxarifado}
                      onChange={setF("almoxarifado")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Unidade *</span>
                    <input
                      className={styles.input}
                      value={modal.unidade}
                      onChange={setF("unidade")}
                      placeholder="PC, UN…"
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Segunda Unidade</span>
                    <input
                      className={styles.input}
                      value={modal.segunda_unidade}
                      onChange={setF("segunda_unidade")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Tipo Conversão</span>
                    <input
                      className={styles.input}
                      value={modal.tipo_conversao}
                      onChange={setF("tipo_conversao")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Fator Conversão</span>
                    <input
                      type="number"
                      step="0.0001"
                      className={styles.input}
                      value={modal.fator_conversao}
                      onChange={setF("fator_conversao")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Classe</span>
                    <input
                      className={styles.input}
                      value={modal.classe}
                      onChange={setFUpper("classe")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Marca</span>
                    <input
                      className={styles.input}
                      value={modal.marca}
                      onChange={setFUpper("marca")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Comissão (%)</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.comissao_pct}
                      onChange={setF("comissao_pct")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Custo</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.custo}
                      onChange={setF("custo")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Margem Lucro (%)</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.margem_lucro_pct}
                      onChange={setF("margem_lucro_pct")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Preço Venda</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.preco_venda}
                      onChange={setF("preco_venda")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Último Preço Compra</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.ultimo_preco_compra}
                      onChange={setF("ultimo_preco_compra")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Tipo Código de Barras</span>
                    <input
                      className={styles.input}
                      value={modal.tipo_cod_barras}
                      onChange={setF("tipo_cod_barras")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Código de Barras</span>
                    <input
                      className={styles.input}
                      value={modal.cod_barras}
                      onChange={setF("cod_barras")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Peso Gramas</span>
                    <input
                      type="number"
                      step="0.001"
                      className={styles.input}
                      value={modal.peso_gramas}
                      onChange={setF("peso_gramas")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Peso (Kg)</span>
                    <input
                      type="number"
                      step="0.001"
                      className={styles.input}
                      value={modal.peso_kg}
                      onChange={setF("peso_kg")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Linha Grade</span>
                    <select
                      className={styles.input}
                      value={modal.linha_grade_id}
                      onChange={setF("linha_grade_id")}
                    >
                      <option value="">Nenhuma</option>
                      {tabelasGradeAtivas.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.codigo} - {t.descricao}
                        </option>
                      ))}
                    </select>
                    {modal.linha_grade_nome && (
                      <span className={styles.hint}>Atual: {modal.linha_grade_nome}</span>
                    )}
                  </label>

                  <label className={styles.field}>
                    <span>Coluna Grade</span>
                    <select
                      className={styles.input}
                      value={modal.coluna_grade_id}
                      onChange={setF("coluna_grade_id")}
                    >
                      <option value="">Nenhuma</option>
                      {tabelasGradeAtivas.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.codigo} - {t.descricao}
                        </option>
                      ))}
                    </select>
                    {modal.coluna_grade_nome && (
                      <span className={styles.hint}>Atual: {modal.coluna_grade_nome}</span>
                    )}
                  </label>

                  <label className={styles.field}>
                    <span>Data Cadastro</span>
                    <input
                      className={styles.input}
                      value={modal.data_cadastro || "Hoje"}
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

                  <div className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Tamanhos disponíveis</span>
                    <div className={styles.tamanhosRow}>
                      {TAMANHOS_DISPONIVEIS.map((t) => (
                        <button
                          key={t}
                          type="button"
                          className={`${styles.tamanhoPill} ${
                            (modal.tamanhos_disponiveis || []).includes(t)
                              ? styles.tamanhoPillAtivo
                              : ""
                          }`}
                          onClick={() => toggleTamanho(t)}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {aba === "impostos" && (
                <div className={styles.fieldGrid}>
                  <label className={styles.field}>
                    <span>NCM</span>
                    <input
                      className={styles.input}
                      value={modal.ncm}
                      onChange={setF("ncm")}
                      maxLength={8}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>CEST</span>
                    <input className={styles.input} value={modal.cest} onChange={setF("cest")} />
                  </label>

                  <label className={styles.field}>
                    <span>Origem</span>
                    <select className={styles.input} value={modal.origem} onChange={setF("origem")}>
                      {Array.from({ length: 9 }, (_, i) => (
                        <option key={i} value={i}>
                          {i}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className={styles.field}>
                    <span>ICMS Incidência</span>
                    <select
                      className={styles.input}
                      value={modal.icms_incidencia}
                      onChange={setF("icms_incidencia")}
                    >
                      <option value="normal">Normal</option>
                      <option value="st">Substituição Tributária</option>
                      <option value="isento">Isento</option>
                      <option value="outros">Outros</option>
                    </select>
                  </label>

                  <label className={styles.field}>
                    <span>Alíquota IPI (%)</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.aliquota_ipi_pct}
                      onChange={setF("aliquota_ipi_pct")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Código ISS</span>
                    <input
                      className={styles.input}
                      value={modal.codigo_iss}
                      onChange={setF("codigo_iss")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Cód. Tributário ISS</span>
                    <input
                      className={styles.input}
                      value={modal.cod_trib_iss}
                      onChange={setF("cod_trib_iss")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Cód. CNAE</span>
                    <input
                      className={styles.input}
                      value={modal.cod_cnae}
                      onChange={setF("cod_cnae")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Base ICMS ST Ret.</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.base_icms_st_ret}
                      onChange={setF("base_icms_st_ret")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Valor ICMS ST Ret.</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.valor_icms_st_ret}
                      onChange={setF("valor_icms_st_ret")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Base FCP ST Ret.</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.base_fcp_st_ret}
                      onChange={setF("base_fcp_st_ret")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Alíq. FCP ST Ret. (%)</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.aliq_fcp_st_ret_pct}
                      onChange={setF("aliq_fcp_st_ret_pct")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Valor FCP ST Ret.</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.valor_fcp_st_ret}
                      onChange={setF("valor_fcp_st_ret")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Natureza Receita</span>
                    <input
                      className={styles.input}
                      value={modal.nat_receita}
                      onChange={setF("nat_receita")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>TES Entrada</span>
                    <select className={styles.input} disabled>
                      <option>Disponível na Fase 2</option>
                    </select>
                  </label>

                  <label className={styles.field}>
                    <span>TES Saída</span>
                    <select className={styles.input} disabled>
                      <option>Disponível na Fase 2</option>
                    </select>
                  </label>

                  <label className={styles.field}>
                    <span>Código ANP</span>
                    <input
                      className={styles.input}
                      value={modal.codigo_anp}
                      onChange={setF("codigo_anp")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Conta Contábil</span>
                    <input
                      className={styles.input}
                      value={modal.conta_contabil}
                      onChange={setF("conta_contabil")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Cód. FCI</span>
                    <input
                      className={styles.input}
                      value={modal.cod_fci}
                      onChange={setF("cod_fci")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Valor Importação</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={modal.valor_importacao}
                      onChange={setF("valor_importacao")}
                    />
                  </label>

                  <label className={styles.field}>
                    <span>Inventário SPED</span>
                    <select
                      className={styles.input}
                      value={modal.inventario_sped}
                      onChange={setF("inventario_sped")}
                    >
                      <option value="sim">Sim</option>
                      <option value="nao">Não</option>
                    </select>
                  </label>

                  <label className={styles.field}>
                    <span>F.C.P.</span>
                    <select className={styles.input} value={modal.fcp} onChange={setF("fcp")}>
                      <option value="sim">Sim</option>
                      <option value="nao">Não</option>
                    </select>
                  </label>

                  <label className={styles.field}>
                    <span>UM Faturamento</span>
                    <select
                      className={styles.input}
                      value={modal.um_faturamento}
                      onChange={setF("um_faturamento")}
                    >
                      <option value="primeira_um">Primeira UM</option>
                      <option value="segunda_um">Segunda UM</option>
                    </select>
                  </label>

                  <label className={`${styles.field} ${styles.fieldFull}`}>
                    <span>Informações Adicionais</span>
                    <textarea
                      className={`${styles.input} ${styles.textarea}`}
                      rows={3}
                      value={modal.inf_adicionais}
                      onChange={setF("inf_adicionais")}
                    />
                  </label>
                </div>
              )}

              {erro && <p className={styles.erro}>{erro}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharModal} disabled={saving}>
                Cancelar
              </button>
              <button className={styles.btnPrimary} onClick={handleSalvar} disabled={saving}>
                {saving ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {modalSku && (
        <div className={styles.overlay} onClick={fecharModalSku}>
          <div className={`${styles.modal} ${styles.modalSm}`} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Editar SKU</h2>
              <button className={styles.btnClose} onClick={fecharModalSku}>
                ×
              </button>
            </div>

            <div className={styles.modalBody}>
              <div className={styles.fieldGrid}>
                <label className={styles.field}>
                  <span>Código</span>
                  <input
                    className={styles.input}
                    value={modalSku.codigo}
                    onChange={(e) => setModalSku((m) => ({ ...m, codigo: e.target.value }))}
                  />
                </label>
                <label className={styles.field}>
                  <span>Situação</span>
                  <select
                    className={styles.input}
                    value={modalSku.status}
                    onChange={(e) => setModalSku((m) => ({ ...m, status: e.target.value }))}
                  >
                    <option value="ativo">Ativo</option>
                    <option value="inativo">Inativo</option>
                  </select>
                </label>
                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Preço Venda</span>
                  <input
                    type="number"
                    step="0.01"
                    className={styles.input}
                    value={modalSku.preco_venda}
                    placeholder="Herdado do produto pai"
                    onChange={(e) => setModalSku((m) => ({ ...m, preco_venda: e.target.value }))}
                  />
                </label>
              </div>
              {erroSku && <p className={styles.erro}>{erroSku}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharModalSku} disabled={savingSku}>
                Cancelar
              </button>
              <button className={styles.btnPrimary} onClick={handleSalvarSku} disabled={savingSku}>
                {savingSku ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {modalGrupos && (
        <ModalGruposProduto
          grupos={grupos}
          onFechar={() => setModalGrupos(false)}
          onAtualizado={carregarListas}
        />
      )}
    </div>
  );
}

function ModalGruposProduto({ grupos, onFechar, onAtualizado }) {
  const { hasPermission } = useAuth();
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState(null);

  const setF = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const abrirNovo = () => {
    setForm({ ...VAZIO_GRUPO });
    setErro(null);
  };
  const abrirEditar = (g) => {
    setForm({ id: g.id, nome: g.nome, prefixo: g.prefixo, situacao: g.situacao });
    setErro(null);
  };
  const cancelarForm = () => {
    setForm(null);
    setErro(null);
  };

  const salvar = async () => {
    if (!form.nome.trim()) {
      setErro("Nome é obrigatório.");
      return;
    }
    if (!form.prefixo.trim()) {
      setErro("Prefixo é obrigatório.");
      return;
    }
    setSaving(true);
    setErro(null);
    try {
      const payload = {
        nome: form.nome.trim(),
        prefixo: form.prefixo.trim().toUpperCase().slice(0, 4),
        situacao: form.situacao,
      };
      if (form.id) {
        await gruposProdutoApi.atualizar(form.id, payload);
      } else {
        await gruposProdutoApi.criar(payload);
      }
      await onAtualizado();
      setForm(null);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  const excluir = async (id) => {
    if (!window.confirm("Deseja excluir este grupo?")) return;
    try {
      await gruposProdutoApi.deletar(id);
      await onAtualizado();
    } catch (e) {
      alert(e.message);
    }
  };

  return (
    <div className={styles.overlay} onClick={onFechar}>
      <div className={`${styles.modal} ${styles.modalSm}`} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHead}>
          <h2 className={styles.modalTitle}>Grupos de Produto</h2>
          <button className={styles.btnClose} onClick={onFechar}>
            ×
          </button>
        </div>

        <div className={styles.modalBody}>
          {form ? (
            <>
              <p className={styles.sectionLabel}>{form.id ? "Editar Grupo" : "Novo Grupo"}</p>
              <div className={styles.grupoFormRow}>
                <label className={styles.field}>
                  <span>Nome</span>
                  <input
                    className={styles.input}
                    value={form.nome}
                    onChange={setF("nome")}
                    placeholder="Ex: Legging"
                  />
                </label>
                <label className={styles.field}>
                  <span>Prefixo</span>
                  <input
                    className={styles.input}
                    value={form.prefixo}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, prefixo: e.target.value.toUpperCase().slice(0, 4) }))
                    }
                    placeholder="LEG"
                    maxLength={4}
                  />
                </label>
                <label className={styles.field}>
                  <span>Situação</span>
                  <select
                    className={styles.input}
                    value={form.situacao}
                    onChange={setF("situacao")}
                  >
                    <option value="ativo">Ativo</option>
                    <option value="inativo">Inativo</option>
                  </select>
                </label>
                <button className={styles.btnSecondary} onClick={cancelarForm} disabled={saving}>
                  Cancelar
                </button>
                <button className={styles.btnPrimary} onClick={salvar} disabled={saving}>
                  {saving ? "Salvando…" : "Salvar"}
                </button>
              </div>
              {erro && <p className={styles.erro}>{erro}</p>}
            </>
          ) : hasPermission(MODULO, "criar") ? (
            <div className={styles.actions} style={{ marginBottom: "1rem" }}>
              <button className={styles.btnPrimary} onClick={abrirNovo}>
                + Novo Grupo
              </button>
            </div>
          ) : null}

          <table className={styles.table}>
            <thead>
              <tr>
                <th>Código</th>
                <th>Nome</th>
                <th>Prefixo</th>
                <th>Situação</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {grupos.length === 0 ? (
                <tr>
                  <td colSpan={5} className={styles.empty}>
                    Nenhum grupo cadastrado.
                  </td>
                </tr>
              ) : (
                grupos.map((g) => (
                  <tr key={g.id}>
                    <td className={styles.tdMono}>{g.codigo}</td>
                    <td>{g.nome}</td>
                    <td>{g.prefixo}</td>
                    <td>
                      <span
                        className={`${styles.badge} ${g.situacao === "ativo" ? styles.badgeAtivo : styles.badgeInativo}`}
                      >
                        {g.situacao === "ativo" ? "Ativo" : "Inativo"}
                      </span>
                    </td>
                    <td>
                      <div className={styles.actions}>
                        {hasPermission(MODULO, "editar") && (
                          <button className={styles.btnLink} onClick={() => abrirEditar(g)}>
                            Editar
                          </button>
                        )}
                        {hasPermission(MODULO, "excluir") && (
                          <button
                            className={`${styles.btnLink} ${styles.btnDanger}`}
                            onClick={() => excluir(g.id)}
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

        <div className={styles.modalActions}>
          <button className={styles.btnSecondary} onClick={onFechar}>
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
