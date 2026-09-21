import { useState, useEffect, useRef } from "react";
import ReactDOM from "react-dom";
import { useParams, useNavigate } from "react-router-dom";
import {
  getPedidoVenda, updatePedidoVenda, updateStatusPedidoVenda,
  addItemPedidoVenda, updateItemPedidoVenda, removeItemPedidoVenda,
  getPdfPedidoVenda, getPdfCortePedidoVenda, gerarEncaixePedidoVenda,
} from "../api/pedidos";
import { getVendedores } from "../api/vendedores";
import { listar as listarTes } from "../api/tes";
import { criar as criarNfe } from "../api/nfe";
import { transportadorasApi } from "../api/transportadoras";
import { tabelasPrecoApi, modelosApi, coresApi, gruposApi } from "../services/api";
import { useAuth } from "../auth/useAuth";
import styles from "./PedidoVendaDetalhePage.module.css";

const MODULO_EDITAR = "pedidos_editar";
const MODULO_EXCLUIR = "pedidos_excluir";

const TAMANHOS_BASE = ["P", "M", "G", "GG"];
const TAMANHOS_PLUS = ["P", "M", "G", "GG", "G1", "G2", "G3"];
const TAM_KEY = { P: "qtd_p", M: "qtd_m", G: "qtd_g", GG: "qtd_gg", G1: "qtd_g1", G2: "qtd_g2", G3: "qtd_g3" };
const QTD_KEYS = ["qtd_p", "qtd_m", "qtd_g", "qtd_gg", "qtd_g1", "qtd_g2", "qtd_g3"];

const CONDICOES_LABEL = { avista: "À Vista", aprazo: "A Prazo" };

const STATUS_LABELS = { Aberto: "Aberto", Fechado: "Fechado", Cancelado: "Cancelado" };
const STATUS_CLS = { Aberto: "stAberto", Fechado: "stFechado", Cancelado: "stCancelado" };

const INDICADOR_PRESENCA_OPCOES = ["Presencial", "Internet", "Teleatendimento", "Outros"];
const TIPO_FRETE_OPCOES = ["Sem Frete", "CIF", "FOB", "Por conta de terceiros", "Próprio", "Sem Ocorrência"];
const SERIE_NFE_OPCOES = [
  { value: "001", label: "001 - NF-e" },
  { value: "002", label: "002 - NFC-e" },
  { value: "ORC", label: "ORC - Orçamento" },
];

const ABAS = [
  { id: "dados", label: "Dados" },
  { id: "itens", label: "Itens" },
  { id: "transporte", label: "Transporte" },
  { id: "outros", label: "Outros" },
];

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const dataLocal = (iso) =>
  iso ? new Date(iso).toLocaleDateString("pt-BR") : "";

const hojeISO = () => new Date().toISOString().split("T")[0];
const agoraHora = () => new Date().toTimeString().slice(0, 5);

async function downloadBlob(promiseFn, filename) {
  const blob = await promiseFn();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

const CAMPOS_CLIENTE = [
  { k: "cliente_razao_social", l: "Razão Social *"    },
  { k: "cliente_cnpj",         l: "CNPJ"              },
  { k: "cliente_ie",           l: "Inscrição Estadual" },
  { k: "cliente_endereco",     l: "Endereço"           },
  { k: "cliente_cidade",       l: "Cidade"             },
  { k: "cliente_cep",          l: "CEP"                },
  { k: "cliente_telefone",     l: "Telefone"           },
  { k: "cliente_email",        l: "E-mail"             },
];

function headerFormFromPedido(pedido) {
  return {
    numero:               pedido.numero               || "",
    data_emissao:         pedido.data_emissao         || "",
    prazo_entrega_dias:   String(pedido.prazo_entrega_dias ?? ""),
    condicoes:            pedido.condicoes            || "avista",
    vendedor_id:          pedido.vendedor_id          || "",
    tabela_preco_id:      pedido.tabela_preco_id      || "",
    cliente_razao_social: pedido.cliente_razao_social || "",
    cliente_cnpj:         pedido.cliente_cnpj         || "",
    cliente_ie:           pedido.cliente_ie           || "",
    cliente_endereco:     pedido.cliente_endereco     || "",
    cliente_cidade:       pedido.cliente_cidade       || "",
    cliente_cep:          pedido.cliente_cep          || "",
    cliente_telefone:     pedido.cliente_telefone     || "",
    cliente_email:        pedido.cliente_email        || "",
    representante:        pedido.representante        || "",
    tes_id:               pedido.tes_id ?? "",
    indicador_presenca:   pedido.indicador_presenca   || "Presencial",
    desconto_geral_pct:   String(pedido.desconto_geral_pct ?? 0),
    desconto_geral_valor: String(pedido.desconto_geral_valor ?? 0),
    acrescimo_pct:        String(pedido.acrescimo_pct ?? 0),
    acrescimo_valor:      String(pedido.acrescimo_valor ?? 0),
    transportadora_id:    pedido.transportadora_id ?? "",
    tipo_frete:           pedido.tipo_frete || "",
    valor_frete:          String(pedido.valor_frete ?? 0),
    valor_seguro:         String(pedido.valor_seguro ?? 0),
    valor_despesas:       String(pedido.valor_despesas ?? 0),
    peso_liquido:         String(pedido.peso_liquido ?? 0),
    peso_bruto:           String(pedido.peso_bruto ?? 0),
    qtd_volumes:          String(pedido.qtd_volumes ?? 0),
    especie_volumes:      pedido.especie_volumes || "",
    placa_veiculo:        pedido.placa_veiculo || "",
    uf_veiculo:           pedido.uf_veiculo || "",
    informacoes_adicionais: pedido.informacoes_adicionais || "",
    observacoes_internas:  pedido.observacoes_internas || "",
  };
}

const ITEM_VAZIO = {
  searchQuery: "", searchResults: [], selectedGrupo: null,
  modelo_id: "", cor_id: "", lote_id: "",
  cores: [], lotes: [],
  cor: "", qtd_p: "", qtd_m: "", qtd_g: "", qtd_gg: "",
  qtd_g1: "", qtd_g2: "", qtd_g3: "",
  precoUnit: "", loadingPreco: false,
  precoAutoFilled: false, precoSemTabela: false,
  tes_id: "", desconto_pct: "0", desconto_valor: "0",
};

export default function PedidoVendaDetalhePage() {
  const { id }   = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const podeEditar = hasPermission(MODULO_EDITAR, "ver");
  const podeExcluir = hasPermission(MODULO_EXCLUIR, "ver");

  const [pedido, setPedido]             = useState(null);
  const [vendedores, setVendedores]     = useState([]);
  const [tabelas, setTabelas]           = useState([]);
  const [tesList, setTesList]           = useState([]);
  const [transportadoras, setTransportadoras] = useState([]);
  const [modelos, setModelos]           = useState([]);
  const [loading, setLoading]           = useState(true);

  const [aba, setAba]                   = useState("dados");
  const [headerForm, setHeaderForm]     = useState(null);
  const [savingHeader, setSavingHeader] = useState(false);
  const [erroHeader, setErroHeader]     = useState(null);
  const [headerSalvo, setHeaderSalvo]   = useState(false);

  const [itemModal, setItemModal]       = useState(null);
  const [saving, setSaving]             = useState(false);
  const [erroItem, setErroItem]         = useState(null);

  const [statusLoading, setStatusLoading] = useState(false);
  const [statusErro, setStatusErro]       = useState(null);
  const [cancelarConfirm, setCancelarConfirm] = useState(false);

  const [nfeModal, setNfeModal]         = useState(null);
  const [nfeMsg, setNfeMsg]             = useState(null);
  const [nfeSaving, setNfeSaving]       = useState(false);
  const [nfeResultado, setNfeResultado] = useState(null);

  const searchTimer                     = useRef(null);
  const searchInputRef                  = useRef(null);
  const [acPos, setAcPos]               = useState({ top: 0, left: 0, width: 200 });

  const carregar = async () => {
    setLoading(true);
    try {
      const p = await getPedidoVenda(id);
      setPedido(p);
      setHeaderForm(headerFormFromPedido(p));
    } catch {
      setPedido(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregar();
    Promise.all([
      getVendedores(),
      tabelasPrecoApi.list(),
      listarTes().catch(() => []),
      transportadorasApi.listar().catch(() => []),
    ]).then(([v, t, tes, transp]) => {
      setVendedores((v || []).filter((x) => x.ativo !== false));
      setTabelas((t || []).filter((x) => x.ativo));
      setTesList((tes || []).filter((x) => x.tipo === "Saída" && x.situacao === "Ativo"));
      setTransportadoras((transp || []).filter((x) => !x.bloqueado));
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // ── Cabeçalho (Dados / Transporte / Outros) ───────────────────────────────────
  const setH = (key) => (e) => setHeaderForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSalvarHeader = async () => {
    if (!headerForm.cliente_razao_social.trim()) {
      setErroHeader("Razão social é obrigatória.");
      setAba("dados");
      return;
    }
    setSavingHeader(true); setErroHeader(null); setHeaderSalvo(false);
    try {
      const updated = await updatePedidoVenda(id, {
        prazo_entrega_dias:   Number(headerForm.prazo_entrega_dias) || 0,
        condicoes:            headerForm.condicoes,
        vendedor_id:          headerForm.vendedor_id     || null,
        tabela_preco_id:      headerForm.tabela_preco_id || null,
        cliente_razao_social: headerForm.cliente_razao_social.trim(),
        cliente_cnpj:         headerForm.cliente_cnpj,
        cliente_ie:           headerForm.cliente_ie,
        cliente_endereco:     headerForm.cliente_endereco,
        cliente_cidade:       headerForm.cliente_cidade,
        cliente_cep:          headerForm.cliente_cep,
        cliente_telefone:     headerForm.cliente_telefone,
        cliente_email:        headerForm.cliente_email,
        representante:        headerForm.representante,
        tes_id:               headerForm.tes_id || null,
        indicador_presenca:   headerForm.indicador_presenca,
        desconto_geral_pct:   Number(headerForm.desconto_geral_pct) || 0,
        desconto_geral_valor: Number(headerForm.desconto_geral_valor) || 0,
        acrescimo_pct:        Number(headerForm.acrescimo_pct) || 0,
        acrescimo_valor:      Number(headerForm.acrescimo_valor) || 0,
        transportadora_id:    headerForm.transportadora_id || null,
        tipo_frete:           headerForm.tipo_frete || null,
        valor_frete:          Number(headerForm.valor_frete) || 0,
        valor_seguro:         Number(headerForm.valor_seguro) || 0,
        valor_despesas:       Number(headerForm.valor_despesas) || 0,
        peso_liquido:         Number(headerForm.peso_liquido) || 0,
        peso_bruto:           Number(headerForm.peso_bruto) || 0,
        qtd_volumes:          Number(headerForm.qtd_volumes) || 0,
        especie_volumes:      headerForm.especie_volumes || null,
        placa_veiculo:        headerForm.placa_veiculo || null,
        uf_veiculo:           headerForm.uf_veiculo || null,
        informacoes_adicionais: headerForm.informacoes_adicionais || null,
        observacoes_internas:  headerForm.observacoes_internas || null,
      });
      setPedido(updated);
      setHeaderForm(headerFormFromPedido(updated));
      setHeaderSalvo(true);
      setTimeout(() => setHeaderSalvo(false), 3000);
    } catch (e) {
      setErroHeader(e.message);
    } finally {
      setSavingHeader(false);
    }
  };

  const tabelaSel = headerForm?.tabela_preco_id
    ? tabelas.find((t) => t.id === headerForm.tabela_preco_id)
    : null;

  // ── Status / ações ────────────────────────────────────────────────────────────
  const handleMudarStatus = async (novoStatus) => {
    setStatusLoading(true); setStatusErro(null);
    try {
      const updated = await updateStatusPedidoVenda(id, novoStatus);
      setPedido(updated);
      setCancelarConfirm(false);
    } catch (e) {
      setStatusErro(e.message || "Erro ao mudar status.");
    } finally {
      setStatusLoading(false);
    }
  };

  // ── Item modal ────────────────────────────────────────────────────────────────
  const abrirItemModal = async () => {
    setItemModal({ ...ITEM_VAZIO, tes_id: headerForm?.tes_id || "" });
    setErroItem(null);
    try { const ms = await modelosApi.listar(); setModelos(ms || []); } catch {}
  };

  const handleSearchChange = (query) => {
    setItemModal((m) => ({ ...m, searchQuery: query, selectedGrupo: null, searchResults: [] }));
    if (searchInputRef.current) {
      const rect = searchInputRef.current.getBoundingClientRect();
      setAcPos({ top: rect.bottom + 2, left: rect.left, width: rect.width });
    }
    clearTimeout(searchTimer.current);
    if (query.trim().length < 2) return;
    searchTimer.current = setTimeout(async () => {
      try {
        const results = await gruposApi.buscar(query);
        setItemModal((m) => ({ ...m, searchResults: (results || []).slice(0, 10) }));
      } catch {}
    }, 300);
  };

  const selecionarGrupo = async (grupo) => {
    setItemModal((m) => ({
      ...m,
      searchQuery:     `${grupo.codigo ? grupo.codigo + " — " : ""}${grupo.nome}`,
      searchResults:   [],
      selectedGrupo:   grupo,
      qtd_p: "", qtd_m: "", qtd_g: "", qtd_gg: "",
      qtd_g1: "", qtd_g2: "", qtd_g3: "",
      precoUnit:       "",
      loadingPreco:    !!pedido?.tabela_preco_id,
      precoAutoFilled: false,
      precoSemTabela:  false,
    }));

    if (!pedido?.tabela_preco_id) return;

    try {
      const itensTabela = await tabelasPrecoApi.listItens(pedido.tabela_preco_id);
      const precoItem   = (itensTabela || []).find((it) => it.grupo_id === grupo.id);
      if (precoItem) {
        const val = pedido.condicoes === "avista" ? precoItem.preco_avista : precoItem.preco_aprazo;
        setItemModal((m) => ({ ...m, precoUnit: String(val ?? ""), loadingPreco: false, precoAutoFilled: true }));
        return;
      }
    } catch {}
    setItemModal((m) => ({ ...m, loadingPreco: false, precoSemTabela: true }));
  };

  const handleModeloChange = async (modelo_id) => {
    setItemModal((m) => ({ ...m, modelo_id, cor_id: "", lote_id: "", cor: "", cores: [], lotes: [] }));
    if (!modelo_id) return;
    try {
      const cores = await modelosApi.listarCores(modelo_id);
      setItemModal((m) => ({ ...m, cores: cores || [] }));
    } catch {}
  };

  const handleCorChange = async (cor_id) => {
    setItemModal((m) => ({ ...m, cor_id, lote_id: "", cor: "", lotes: [] }));
    if (!cor_id) return;
    try {
      const lotes = await coresApi.listarLotes(cor_id);
      const lotesAtivos = (lotes || []).filter(
        (l) => !l.status || l.status === "aberto" || l.status === "intacto"
      );
      setItemModal((m) => ({ ...m, lotes: lotesAtivos }));
    } catch {}
  };

  const handleLoteChange = (lote_id) => {
    const corSel = itemModal.cores.find((c) => String(c.id) === String(itemModal.cor_id));
    setItemModal((m) => ({ ...m, lote_id, cor: corSel?.nome || "" }));
  };

  const loteLabelFn = (l) => {
    const cod = l.codigo || l.nome || String(l.id).slice(0, 8);
    const qtd = l.quantidade_disponivel ?? l.qtd_disponivel ?? l.metros ?? null;
    return qtd != null ? `${cod} — ${qtd}kg disp.` : cod;
  };

  const totalItemBruto = (() => {
    if (!itemModal) return 0;
    const qtd = QTD_KEYS.reduce((s, k) => s + (parseInt(itemModal[k]) || 0), 0);
    return qtd * (parseFloat(itemModal.precoUnit) || 0);
  })();

  const totalItemLiquido = totalItemBruto - (parseFloat(itemModal?.desconto_valor) || 0);

  // Desconto do item: editar % recalcula R$, editar R$ recalcula % — cada um
  // usa o total bruto do momento, então se a quantidade/preço mudar depois,
  // o par pct/valor pode ficar defasado até o usuário reeditar um dos dois.
  const setDescontoPct = (e) => {
    const pct = e.target.value;
    const valor = totalItemBruto > 0 ? (totalItemBruto * (parseFloat(pct) || 0)) / 100 : 0;
    setItemModal((m) => ({ ...m, desconto_pct: pct, desconto_valor: valor.toFixed(2) }));
  };

  const setDescontoValor = (e) => {
    const valor = e.target.value;
    const pct = totalItemBruto > 0 ? ((parseFloat(valor) || 0) / totalItemBruto) * 100 : 0;
    setItemModal((m) => ({ ...m, desconto_valor: valor, desconto_pct: pct.toFixed(2) }));
  };

  const handleSalvarItem = async () => {
    if (!itemModal.selectedGrupo) { setErroItem("Selecione uma referência."); return; }
    const qtdTotal = QTD_KEYS.reduce((s, k) => s + (parseInt(itemModal[k]) || 0), 0);
    if (qtdTotal === 0) { setErroItem("Informe ao menos uma quantidade."); return; }
    setSaving(true); setErroItem(null);
    try {
      await addItemPedidoVenda(id, {
        grupo_id:       itemModal.selectedGrupo.id,
        cor:            itemModal.cor,
        lote_id:        itemModal.lote_id || null,
        qtd_p:          parseInt(itemModal.qtd_p)  || 0,
        qtd_m:          parseInt(itemModal.qtd_m)  || 0,
        qtd_g:          parseInt(itemModal.qtd_g)  || 0,
        qtd_gg:         parseInt(itemModal.qtd_gg) || 0,
        qtd_g1:         parseInt(itemModal.qtd_g1) || 0,
        qtd_g2:         parseInt(itemModal.qtd_g2) || 0,
        qtd_g3:         parseInt(itemModal.qtd_g3) || 0,
        preco_unitario: parseFloat(itemModal.precoUnit) || 0,
        tes_id:         itemModal.tes_id || null,
        desconto_pct:   parseFloat(itemModal.desconto_pct) || 0,
        desconto_valor: parseFloat(itemModal.desconto_valor) || 0,
      });
      await carregar();
      setItemModal(null);
    } catch (e) {
      setErroItem(e.message);
    } finally {
      setSaving(false);
    }
  };

  const removerItem = async (itemId) => {
    try { await removeItemPedidoVenda(id, itemId); await carregar(); } catch {}
  };

  const alterarTesItem = async (item, novoTesId) => {
    try {
      await updateItemPedidoVenda(id, item.id, { tes_id: novoTesId ? Number(novoTesId) : null });
      await carregar();
    } catch {}
  };

  // ── Table grouping ──────────────────────────────────────────────────────────
  const itens       = pedido?.itens || [];
  const temPlus     = itens.some((i) => (i.qtd_g1 || 0) + (i.qtd_g2 || 0) + (i.qtd_g3 || 0) > 0);
  const tamCols     = temPlus ? TAMANHOS_PLUS : TAMANHOS_BASE;
  const gruposOrdem = [];
  const grupoMap    = {};
  itens.forEach((item) => {
    if (!grupoMap[item.grupo_id]) { grupoMap[item.grupo_id] = []; gruposOrdem.push(item.grupo_id); }
    grupoMap[item.grupo_id].push(item);
  });

  const tabelaAtual    = tabelas.find((t) => t.id === pedido?.tabela_preco_id);
  const comissaoPctStr = tabelaAtual
    ? `${((tabelaAtual.comissao_pct || 0) * 100).toFixed(1)}%`
    : null;

  const subtotalItens = itens.reduce(
    (acc, i) => acc + (parseFloat(i.preco_total) || 0) - (parseFloat(i.desconto_valor) || 0) + (parseFloat(i.acrescimo_valor) || 0),
    0
  );

  const isPlus  = itemModal?.selectedGrupo?.tem_plus;
  const tamForm = isPlus ? TAMANHOS_PLUS : TAMANHOS_BASE;

  // ── NF-e ──────────────────────────────────────────────────────────────────────
  const abrirNfeModal = () => {
    setNfeModal({ serie: "001", data_emissao: hojeISO(), data_saida: hojeISO(), hora_saida: agoraHora() });
    setNfeMsg(null);
    setNfeResultado(null);
  };

  const handleConfirmarNfe = async () => {
    setNfeSaving(true);
    setNfeMsg(null);
    try {
      const resp = await criarNfe({
        pedido_id: pedido.id,
        serie: nfeModal.serie,
        data_emissao: nfeModal.data_emissao,
        data_saida: nfeModal.data_saida,
        hora_saida: nfeModal.hora_saida,
      });
      setNfeResultado(resp);
      await carregar();
    } catch (e) {
      setNfeMsg(e.message);
    } finally {
      setNfeSaving(false);
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  if (loading) return <div className="sc-page"><p className={styles.stateMsg}>Carregando…</p></div>;
  if (!pedido || !headerForm) return (
    <div className="sc-page">
      <button className={styles.btnBack} onClick={() => navigate("/vendas/pedidos")}>Voltar</button>
      <p className={styles.stateMsg}>Pedido não encontrado.</p>
    </div>
  );

  return (
    <div className="sc-page">
      <button className={styles.btnBack} onClick={() => navigate("/vendas/pedidos")}>
        Voltar
      </button>

      {/* ── Cabeçalho ── */}
      <div className="sc-page-header">
        <div>
          <h1>Pedido {pedido.numero}</h1>
          <div className={styles.statusLine}>
            <span className={`${styles.statusBadge} ${styles[STATUS_CLS[pedido.status] || "stAberto"]}`}>
              {STATUS_LABELS[pedido.status] || pedido.status}
            </span>
          </div>
        </div>

        <div className={styles.headerActions}>
          {podeEditar && pedido.status === "Aberto" && (
            <button className={styles.btnNovo} onClick={() => handleMudarStatus("Fechado")} disabled={statusLoading}>
              Fechar Pedido
            </button>
          )}
          {podeEditar && pedido.status === "Fechado" && pedido.nfe_id == null && (
            <button className={styles.btnSecondary} onClick={() => handleMudarStatus("Aberto")} disabled={statusLoading}>
              Reabrir Pedido
            </button>
          )}
          {podeExcluir && pedido.status === "Aberto" && (
            <button className={styles.btnDanger} onClick={() => setCancelarConfirm(true)} disabled={statusLoading}>
              Cancelar Pedido
            </button>
          )}
          {podeEditar && pedido.status === "Fechado" && pedido.nfe_id == null && (
            <button className={styles.btnNovo} onClick={abrirNfeModal}>
              Emitir Nota Fiscal
            </button>
          )}
          <button
            className={styles.btnDownload}
            onClick={() => downloadBlob(() => getPdfPedidoVenda(id), `pedido-${pedido.numero}.pdf`)}
          >
            Formulário de Pedido PDF
          </button>
          <button
            className={styles.btnDownload}
            onClick={() => downloadBlob(() => getPdfCortePedidoVenda(id), `corte-${pedido.numero}.pdf`)}
          >
            Formulário de Corte PDF
          </button>
        </div>
      </div>

      <div className={styles.infoGrid}>
        {[
          { label: "Cliente",  valor: pedido.cliente_razao_social || "" },
          { label: "Data",     valor: dataLocal(pedido.data_emissao) },
          { label: "Prazo",    valor: `${pedido.prazo_entrega_dias ?? 0} dias` },
          { label: "Vendedor", valor: pedido.vendedor_nome || "" },
          { label: "Tabela",   valor: pedido.tabela_nome || "" },
          { label: "Condição", valor: CONDICOES_LABEL[pedido.condicoes] || pedido.condicoes || "" },
        ].map((c) => (
          <div key={c.label} className={styles.infoCard}>
            <span className={styles.infoLabel}>{c.label}</span>
            <span className={styles.infoValor}>{c.valor}</span>
          </div>
        ))}
      </div>

      {statusErro && <p className={styles.erroInline}>{statusErro}</p>}

      {/* ── Abas ── */}
      <div className={styles.tabBar}>
        {ABAS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`${styles.tabBtn} ${aba === t.id ? styles.tabBtnActive : ""}`}
            onClick={() => setAba(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ══ ABA DADOS ══ */}
      {aba === "dados" && (
        <div className={styles.tabPanel}>
          <div className={styles.grid2}>
            <label className={styles.field}>
              <span>Nº Pedido</span>
              <input className={styles.input} value={headerForm.numero} disabled />
            </label>
            <label className={styles.field}>
              <span>Data de emissão</span>
              <input className={styles.input} value={dataLocal(headerForm.data_emissao)} disabled />
            </label>
            <label className={styles.field}>
              <span>Prazo de entrega (dias)</span>
              <input type="number" min="0" className={styles.input} disabled={!podeEditar}
                value={headerForm.prazo_entrega_dias} onChange={setH("prazo_entrega_dias")} />
            </label>
            <label className={styles.field}>
              <span>Condição de pagamento</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.condicoes} onChange={setH("condicoes")}>
                <option value="avista">À Vista</option>
                <option value="aprazo">A Prazo</option>
              </select>
            </label>
            <label className={styles.field}>
              <span>Vendedor</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.vendedor_id}
                onChange={(e) => {
                  const vid  = e.target.value;
                  const vend = vendedores.find((v) => String(v.id) === String(vid));
                  setHeaderForm((f) => ({ ...f, vendedor_id: vid, representante: vend?.nome || f.representante }));
                }}>
                <option value="">Nenhum</option>
                {vendedores.map((v) => <option key={v.id} value={v.id}>{v.nome}</option>)}
              </select>
            </label>
            <label className={styles.field}>
              <span>Tabela de preço</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.tabela_preco_id} onChange={setH("tabela_preco_id")}>
                <option value="">Nenhuma</option>
                {tabelas.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nome} ({((t.comissao_pct || 0) * 100).toFixed(0)}% comissão)
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.field}>
              <span>TES padrão do pedido</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.tes_id} onChange={setH("tes_id")}>
                <option value="">Nenhum</option>
                {tesList.map((t) => (
                  <option key={t.id} value={t.id}>{t.codigo} — {t.descricao}</option>
                ))}
              </select>
            </label>
            <label className={styles.field}>
              <span>Indicador de Presença</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.indicador_presenca} onChange={setH("indicador_presenca")}>
                {INDICADOR_PRESENCA_OPCOES.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
          </div>

          {tabelaSel && (
            <div className={styles.aviso}>
              Comissão: <strong>{((tabelaSel.comissao_pct || 0) * 100).toFixed(1)}%</strong> sobre preço{" "}
              {headerForm.condicoes === "avista" ? "à vista" : "a prazo"}
            </div>
          )}

          <p className={styles.secLabel} style={{ marginTop: "1.5rem" }}>Cliente</p>
          <div className={styles.grid2}>
            {CAMPOS_CLIENTE.map(({ k, l }) => (
              <label key={k} className={styles.field}>
                <span>{l}</span>
                <input className={styles.input} disabled={!podeEditar} value={headerForm[k]} onChange={setH(k)} />
              </label>
            ))}
            <label className={styles.field}>
              <span>Representante</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.representante} onChange={setH("representante")}>
                <option value="">Nenhum</option>
                {vendedores.map((v) => <option key={v.id} value={v.nome}>{v.nome}</option>)}
              </select>
            </label>
          </div>
        </div>
      )}

      {/* ══ ABA ITENS ══ */}
      {aba === "itens" && (
        <div className={styles.tabPanel}>
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>Itens do pedido</h2>
            {podeEditar && (
              <button className={styles.btnPrimary} onClick={abrirItemModal}>+ Adicionar item</button>
            )}
          </div>

          <div className={`sc-card ${styles.tableCard}`}>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>REF</th>
                    <th>Nome</th>
                    <th>Cor</th>
                    {tamCols.map((t) => <th key={t} className={styles.thQty}>{t}</th>)}
                    <th className={styles.thPreco}>P. Unit.</th>
                    <th className={styles.thPreco}>Desconto</th>
                    <th className={styles.thPreco}>Total</th>
                    <th>TES</th>
                    <th style={{ width: 36 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {gruposOrdem.map((gid) => {
                    const grupo_itens = grupoMap[gid];
                    return grupo_itens.map((item, idx) => (
                      <tr key={item.id} className={idx === 0 ? styles.trFirst : styles.trCont}>
                        {idx === 0 && (
                          <>
                            <td rowSpan={grupo_itens.length} className={styles.tdRef}>
                              <code>{item.grupo_codigo || ""}</code>
                            </td>
                            <td rowSpan={grupo_itens.length} className={styles.tdNome}>
                              {item.grupo_nome || ""}
                            </td>
                          </>
                        )}
                        <td>{item.cor || ""}</td>
                        {tamCols.map((t) => (
                          <td key={t} className={styles.tdQty}>
                            {(item[TAM_KEY[t]] || 0) > 0 ? item[TAM_KEY[t]] : ""}
                          </td>
                        ))}
                        <td className={styles.tdPreco}>{moeda(item.preco_unitario)}</td>
                        <td className={styles.tdPreco}>
                          {parseFloat(item.desconto_valor) > 0 ? moeda(item.desconto_valor) : ""}
                        </td>
                        <td className={styles.tdTotal}>
                          {moeda((parseFloat(item.preco_total) || 0) - (parseFloat(item.desconto_valor) || 0) + (parseFloat(item.acrescimo_valor) || 0))}
                        </td>
                        <td>
                          <select
                            className={styles.tesSelectInline}
                            value={item.tes_id ?? ""}
                            disabled={!podeEditar}
                            onChange={(e) => alterarTesItem(item, e.target.value)}
                          >
                            <option value="">Nenhum</option>
                            {tesList.map((t) => <option key={t.id} value={t.id}>{t.codigo}</option>)}
                          </select>
                        </td>
                        <td>
                          {podeEditar && (
                            <button
                              className={styles.btnExcluir}
                              onClick={() => removerItem(item.id)}
                              title="Remover"
                            >×</button>
                          )}
                        </td>
                      </tr>
                    ));
                  })}
                  {itens.length === 0 && (
                    <tr>
                      <td colSpan={6 + tamCols.length} className={styles.empty}>
                        Nenhum item adicionado.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className={styles.descontoGeralRow}>
              <span className={styles.secLabel} style={{ margin: 0 }}>Desconto geral</span>
              <label className={styles.field} style={{ maxWidth: 140 }}>
                <span>Desconto (%)</span>
                <input type="number" step="0.01" min="0" max="100" className={styles.input} disabled={!podeEditar}
                  value={headerForm.desconto_geral_pct}
                  onChange={(e) => {
                    const pct = e.target.value;
                    const valor = subtotalItens > 0 ? (subtotalItens * (parseFloat(pct) || 0)) / 100 : 0;
                    setHeaderForm((f) => ({ ...f, desconto_geral_pct: pct, desconto_geral_valor: valor.toFixed(2) }));
                  }} />
              </label>
              <label className={styles.field} style={{ maxWidth: 140 }}>
                <span>Desconto (R$)</span>
                <input type="number" step="0.01" min="0" className={styles.input} disabled={!podeEditar}
                  value={headerForm.desconto_geral_valor}
                  onChange={(e) => {
                    const valor = e.target.value;
                    const pct = subtotalItens > 0 ? ((parseFloat(valor) || 0) / subtotalItens) * 100 : 0;
                    setHeaderForm((f) => ({ ...f, desconto_geral_valor: valor, desconto_geral_pct: pct.toFixed(2) }));
                  }} />
              </label>
              {podeEditar && (
                <button className={styles.btnSecondary} onClick={handleSalvarHeader} disabled={savingHeader}>
                  {savingHeader ? "Salvando…" : "Salvar desconto"}
                </button>
              )}
            </div>

            {itens.length > 0 && (
              <div className={styles.totais}>
                <div className={styles.totaisLinha}>
                  <span>Subtotal itens</span>
                  <span>{moeda(subtotalItens)}</span>
                </div>
                {parseFloat(pedido.desconto_geral_valor) > 0 && (
                  <div className={styles.totaisLinha}>
                    <span>Desconto geral</span>
                    <span>- {moeda(pedido.desconto_geral_valor)}</span>
                  </div>
                )}
                {parseFloat(pedido.acrescimo_valor) > 0 && (
                  <div className={styles.totaisLinha}>
                    <span>Acréscimo</span>
                    <span>{moeda(pedido.acrescimo_valor)}</span>
                  </div>
                )}
                {parseFloat(pedido.valor_frete) > 0 && (
                  <div className={styles.totaisLinha}>
                    <span>Frete</span>
                    <span>{moeda(pedido.valor_frete)}</span>
                  </div>
                )}
                {parseFloat(pedido.valor_seguro) > 0 && (
                  <div className={styles.totaisLinha}>
                    <span>Seguro</span>
                    <span>{moeda(pedido.valor_seguro)}</span>
                  </div>
                )}
                {parseFloat(pedido.valor_despesas) > 0 && (
                  <div className={styles.totaisLinha}>
                    <span>Despesas</span>
                    <span>{moeda(pedido.valor_despesas)}</span>
                  </div>
                )}
                {comissaoPctStr && (
                  <div className={styles.totaisLinha}>
                    <span>Comissão ({comissaoPctStr})</span>
                    <span>{moeda(pedido.comissao_valor)}</span>
                  </div>
                )}
                <div className={`${styles.totaisLinha} ${styles.totaisTotal}`}>
                  <span>Total</span>
                  <strong>{moeda(pedido.total_pedido)}</strong>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══ ABA TRANSPORTE ══ */}
      {aba === "transporte" && (
        <div className={styles.tabPanel}>
          <div className={styles.grid2}>
            <label className={styles.field}>
              <span>Transportadora</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.transportadora_id} onChange={setH("transportadora_id")}>
                <option value="">Nenhuma</option>
                {transportadoras.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
              </select>
            </label>
            <label className={styles.field}>
              <span>Tipo de Frete</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.tipo_frete} onChange={setH("tipo_frete")}>
                <option value="">Selecionar</option>
                {TIPO_FRETE_OPCOES.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
            <label className={styles.field}>
              <span>Valor Frete (R$)</span>
              <input type="number" step="0.01" min="0" className={styles.input} disabled={!podeEditar}
                value={headerForm.valor_frete} onChange={setH("valor_frete")} />
            </label>
            <label className={styles.field}>
              <span>Valor Seguro (R$)</span>
              <input type="number" step="0.01" min="0" className={styles.input} disabled={!podeEditar}
                value={headerForm.valor_seguro} onChange={setH("valor_seguro")} />
            </label>
            <label className={styles.field}>
              <span>Valor Despesas (R$)</span>
              <input type="number" step="0.01" min="0" className={styles.input} disabled={!podeEditar}
                value={headerForm.valor_despesas} onChange={setH("valor_despesas")} />
            </label>
            <label className={styles.field}>
              <span>Peso Líquido (kg)</span>
              <input type="number" step="0.001" min="0" className={styles.input} disabled={!podeEditar}
                value={headerForm.peso_liquido} onChange={setH("peso_liquido")} />
            </label>
            <label className={styles.field}>
              <span>Peso Bruto (kg)</span>
              <input type="number" step="0.001" min="0" className={styles.input} disabled={!podeEditar}
                value={headerForm.peso_bruto} onChange={setH("peso_bruto")} />
            </label>
            <label className={styles.field}>
              <span>Quantidade de Volumes</span>
              <input type="number" step="1" min="0" className={styles.input} disabled={!podeEditar}
                value={headerForm.qtd_volumes} onChange={setH("qtd_volumes")} />
            </label>
            <label className={styles.field}>
              <span>Espécie dos Volumes</span>
              <input className={styles.input} disabled={!podeEditar}
                value={headerForm.especie_volumes} onChange={setH("especie_volumes")} placeholder="Ex: Caixa, Fardo…" />
            </label>
            <label className={styles.field}>
              <span>Placa do Veículo</span>
              <input className={styles.input} disabled={!podeEditar}
                value={headerForm.placa_veiculo} onChange={setH("placa_veiculo")} maxLength={10} />
            </label>
            <label className={styles.field}>
              <span>UF do Veículo</span>
              <input className={styles.input} disabled={!podeEditar}
                value={headerForm.uf_veiculo} onChange={setH("uf_veiculo")} maxLength={2} />
            </label>
          </div>
        </div>
      )}

      {/* ══ ABA OUTROS ══ */}
      {aba === "outros" && (
        <div className={styles.tabPanel}>
          <label className={styles.field}>
            <span>Observações Internas</span>
            <textarea
              className={`${styles.input} ${styles.textarea}`}
              disabled={!podeEditar}
              rows={4}
              value={headerForm.observacoes_internas}
              onChange={setH("observacoes_internas")}
              placeholder="Uso interno — não vai para a NF-e"
            />
          </label>
          <label className={styles.field} style={{ marginTop: "1rem" }}>
            <span>Informações Adicionais da Nota</span>
            <textarea
              className={`${styles.input} ${styles.textarea}`}
              disabled={!podeEditar}
              rows={4}
              value={headerForm.informacoes_adicionais}
              onChange={setH("informacoes_adicionais")}
              placeholder="Vai para o XML da NF-e"
            />
          </label>
        </div>
      )}

      {/* ── Salvar cabeçalho (Dados/Transporte/Outros) ── */}
      {podeEditar && aba !== "itens" && (
        <div className={styles.headerSaveBar}>
          {erroHeader && <p className={styles.erro} style={{ margin: 0 }}>{erroHeader}</p>}
          {headerSalvo && <span className={styles.msgSalvo}>Alterações salvas.</span>}
          <button className={styles.btnPrimary} onClick={handleSalvarHeader} disabled={savingHeader}>
            {savingHeader ? "Salvando…" : "Salvar Alterações"}
          </button>
        </div>
      )}

      {/* ══ MODAL — Adicionar item ══ */}
      {itemModal && (
        <div className={styles.overlay} onClick={() => { setItemModal(null); setErroItem(null); }}>
          <div className={styles.modalMd} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Adicionar item</h2>
              <button className={styles.btnClose}
                onClick={() => { setItemModal(null); setErroItem(null); }}>×</button>
            </div>

            <div className={styles.modalBody}>
              <div className={styles.searchWrap}>
                <label className={styles.field}>
                  <span>Referência — código ou nome</span>
                  <input
                    ref={searchInputRef}
                    className={styles.input}
                    placeholder="Digite para buscar…"
                    value={itemModal.searchQuery}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    onBlur={() => setTimeout(() => setItemModal((m) => m ? { ...m, searchResults: [] } : m), 200)}
                    autoComplete="off"
                  />
                </label>
                {itemModal.searchResults.length > 0 && ReactDOM.createPortal(
                  <ul className={styles.autocomplete} style={{ top: acPos.top, left: acPos.left, width: acPos.width }}>
                    {itemModal.searchResults.map((g) => (
                      <li key={g.id} className={styles.acItem} onClick={() => selecionarGrupo(g)}>
                        <code className={styles.acCod}>{g.codigo || "?"}</code>
                        <span className={styles.acNome}>{g.nome}</span>
                        {g.tem_plus && <span className={styles.acPlus}>Plus</span>}
                      </li>
                    ))}
                  </ul>,
                  document.body
                )}
              </div>

              {itemModal.selectedGrupo && (
                <>
                  <div className={styles.grupoInfo}>
                    <span className={styles.grupoNome}>{itemModal.selectedGrupo.nome}</span>
                    <code className={styles.grupoCod}>{itemModal.selectedGrupo.codigo}</code>
                    {itemModal.selectedGrupo.tem_plus && (
                      <span className={styles.badgePlus}>Plus</span>
                    )}
                  </div>

                  <div className={styles.tecidoSection}>
                    <label className={styles.field}>
                      <span>Modelo de Tecido</span>
                      <select className={styles.input} value={itemModal.modelo_id}
                        onChange={(e) => handleModeloChange(e.target.value)}>
                        <option value="">Selecionar modelo</option>
                        {modelos.map((mo) => <option key={mo.id} value={mo.id}>{mo.nome}</option>)}
                      </select>
                    </label>
                    {itemModal.modelo_id && (
                      <label className={styles.field}>
                        <span>Cor</span>
                        <select className={styles.input} value={itemModal.cor_id}
                          onChange={(e) => handleCorChange(e.target.value)}>
                          <option value="">Selecionar cor</option>
                          {itemModal.cores.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
                        </select>
                      </label>
                    )}
                    {itemModal.cor_id && (
                      <label className={styles.field}>
                        <span>Lote</span>
                        <select className={styles.input} value={itemModal.lote_id}
                          onChange={(e) => handleLoteChange(e.target.value)}>
                          <option value="">Selecionar lote</option>
                          {itemModal.lotes.map((l) => (
                            <option key={l.id} value={l.id}>{loteLabelFn(l)}</option>
                          ))}
                        </select>
                      </label>
                    )}
                    {itemModal.cor && (
                      <p className={styles.corExtraida}>
                        Cor selecionada: <strong>{itemModal.cor}</strong>
                      </p>
                    )}
                  </div>

                  <div className={styles.tamSection}>
                    <p className={styles.tamLabel}>Quantidades por tamanho</p>
                    <div className={styles.tamGrid}>
                      {tamForm.map((tam) => (
                        <label key={tam} className={styles.tamItem}>
                          <span>{tam}</span>
                          <input
                            type="number"
                            min="0"
                            className={styles.tamInput}
                            value={itemModal[TAM_KEY[tam]]}
                            onChange={(e) =>
                              setItemModal((m) => ({ ...m, [TAM_KEY[tam]]: e.target.value }))
                            }
                          />
                        </label>
                      ))}
                    </div>
                  </div>

                  <label className={styles.field}>
                    <span>Preço unitário (R$)</span>
                    <input
                      type="number"
                      step="0.01"
                      className={styles.input}
                      value={itemModal.precoUnit}
                      disabled={itemModal.loadingPreco}
                      onChange={(e) => setItemModal((m) => ({ ...m, precoUnit: e.target.value }))}
                    />
                    {pedido.tabela_nome && (
                      <small className={`${styles.precoHint}${itemModal.precoSemTabela ? " " + styles.precoHintWarn : ""}`}>
                        {itemModal.loadingPreco
                          ? "Buscando preço…"
                          : itemModal.precoSemTabela
                          ? "Produto sem preço nesta tabela"
                          : `Tabela ${pedido.tabela_nome} — ${CONDICOES_LABEL[pedido.condicoes] || pedido.condicoes}${itemModal.precoAutoFilled ? " — valor automático" : ""}`}
                      </small>
                    )}
                  </label>

                  <div className={styles.grid2}>
                    <label className={styles.field}>
                      <span>Desconto (%)</span>
                      <input type="number" step="0.01" min="0" max="100" className={styles.input}
                        value={itemModal.desconto_pct} onChange={setDescontoPct} />
                    </label>
                    <label className={styles.field}>
                      <span>Desconto (R$)</span>
                      <input type="number" step="0.01" min="0" className={styles.input}
                        value={itemModal.desconto_valor} onChange={setDescontoValor} />
                    </label>
                  </div>

                  <label className={styles.field}>
                    <span>TES do item</span>
                    <select className={styles.input} value={itemModal.tes_id}
                      onChange={(e) => setItemModal((m) => ({ ...m, tes_id: e.target.value }))}>
                      <option value="">Nenhum</option>
                      {tesList.map((t) => <option key={t.id} value={t.id}>{t.codigo} — {t.descricao}</option>)}
                    </select>
                    <small className={styles.precoHint}>
                      Preenchido a partir do TES padrão do pedido — pode ser trocado aqui.
                    </small>
                  </label>

                  <div className={styles.itemTotal}>
                    Total do item: <strong>{moeda(totalItemLiquido)}</strong>
                  </div>
                </>
              )}

              {erroItem && <p className={styles.erro}>{erroItem}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary}
                onClick={() => { setItemModal(null); setErroItem(null); }}>Cancelar</button>
              <button
                className={styles.btnPrimary}
                onClick={handleSalvarItem}
                disabled={saving || !itemModal.selectedGrupo}
              >
                {saving ? "Adicionando…" : "Adicionar item"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Cancelar pedido ══ */}
      {cancelarConfirm && (
        <div className={styles.overlay} onClick={() => setCancelarConfirm(false)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle} style={{ marginBottom: "0.75rem" }}>
              Cancelar pedido?
            </h2>
            <p className={styles.confirmText}>
              O pedido <strong>{pedido.numero}</strong> será marcado como Cancelado.
              Esta ação não pode ser desfeita.
            </p>
            {statusErro && <p className={styles.erro}>{statusErro}</p>}
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setCancelarConfirm(false)}>
                Voltar
              </button>
              <button className={styles.btnDanger} onClick={() => handleMudarStatus("Cancelado")} disabled={statusLoading}>
                {statusLoading ? "Cancelando…" : "Cancelar Pedido"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Emitir Nota Fiscal ══ */}
      {nfeModal && (
        <div className={styles.overlay} onClick={() => setNfeModal(null)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle} style={{ marginBottom: "1rem" }}>
              Emitir Nota Fiscal
            </h2>

            {nfeResultado ? (
              <>
                <p className={styles.aviso}>NF-e emitida com sucesso.</p>
                <p style={{ fontSize: "0.8rem", wordBreak: "break-all", color: "var(--sc-text-secondary)" }}>
                  Chave de acesso: {nfeResultado.chave_acesso}
                </p>
                <div className={styles.modalActions}>
                  <button className={styles.btnSecondary} onClick={() => setNfeModal(null)}>Fechar</button>
                  <button className={styles.btnPrimary} onClick={() => navigate("/vendas/nfe")}>Ver NF-e</button>
                </div>
              </>
            ) : (
              <>
                <label className={styles.field}>
                  <span>Série</span>
                  <select className={styles.input} value={nfeModal.serie}
                    onChange={(e) => setNfeModal((m) => ({ ...m, serie: e.target.value }))}>
                    {SERIE_NFE_OPCOES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </label>
                <label className={styles.field} style={{ marginTop: "0.75rem" }}>
                  <span>Data de Emissão</span>
                  <input type="date" className={styles.input} value={nfeModal.data_emissao}
                    onChange={(e) => setNfeModal((m) => ({ ...m, data_emissao: e.target.value }))} />
                </label>
                <label className={styles.field} style={{ marginTop: "0.75rem" }}>
                  <span>Data de Saída</span>
                  <input type="date" className={styles.input} value={nfeModal.data_saida}
                    onChange={(e) => setNfeModal((m) => ({ ...m, data_saida: e.target.value }))} />
                </label>
                <label className={styles.field} style={{ marginTop: "0.75rem" }}>
                  <span>Hora de Saída</span>
                  <input type="time" className={styles.input} value={nfeModal.hora_saida}
                    onChange={(e) => setNfeModal((m) => ({ ...m, hora_saida: e.target.value }))} />
                </label>
                {nfeMsg && <p className={styles.erro} style={{ marginTop: "1rem" }}>{nfeMsg}</p>}
                <div className={styles.modalActions}>
                  <button className={styles.btnSecondary} onClick={() => setNfeModal(null)} disabled={nfeSaving}>Cancelar</button>
                  <button className={styles.btnPrimary} onClick={handleConfirmarNfe} disabled={nfeSaving}>
                    {nfeSaving ? "Emitindo…" : "Confirmar"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
