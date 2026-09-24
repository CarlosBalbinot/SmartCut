import { useState, useEffect, useRef } from "react";
import ReactDOM from "react-dom";
import { useParams, useNavigate } from "react-router-dom";
import {
  getPedidoVenda, updatePedidoVenda, updateStatusPedidoVenda,
  addItensBulkPedidoVenda, removeItemPedidoVenda,
  getPdfPedidoVenda, getPdfCortePedidoVenda, gerarEncaixePedidoVenda,
} from "../api/pedidos";
import { produtosApi } from "../api/produtos";
import { getVendedores } from "../api/vendedores";
import { listar as listarTes } from "../api/tes";
import { listar as listarCondicoesPagamento, simular as simularParcelas } from "../api/condicoesPagamento";
import { criar as criarNfe } from "../api/nfe";
import { transportadorasApi } from "../api/transportadoras";
import { aplicarTabelaPedidoVenda, updateItemPedidoVenda } from "../api/pedidos";
import { getTabelasPreco } from "../api/tabelasPreco";
import useResizableColumns from "../hooks/useResizableColumns";
import TesInput from "../components/TesInput/TesInput";
import ClienteInput from "../components/ClienteInput/ClienteInput";
import ClienteFormModal from "../components/ClienteFormModal/ClienteFormModal";
import ConfirmModal from "../components/ConfirmModal/ConfirmModal";
import { useAuth } from "../auth/useAuth";
import styles from "./PedidoVendaDetalhePage.module.css";

const MODULO_EDITAR = "pedidos_editar";
const MODULO_EXCLUIR = "pedidos_excluir";

const STATUS_LABELS = { Aberto: "Aberto", Fechado: "Fechado", Cancelado: "Cancelado" };
const STATUS_CLS = { Aberto: "stAberto", Fechado: "stFechado", Cancelado: "stCancelado" };

const INDICADOR_PRESENCA_OPCOES = [
  { value: "0", label: "0 – Não se aplica" },
  { value: "1", label: "1 – Operação presencial" },
  { value: "2", label: "2 – Operação não presencial, pela Internet" },
  { value: "3", label: "3 – Operação não presencial, Teleatendimento" },
  { value: "4", label: "4 – NFC-e em operação com entrega a domicílio" },
  { value: "5", label: "5 – Operação presencial, fora do estabelecimento" },
  { value: "9", label: "9 – Operação não presencial, outros" },
];
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

// ── Tabela de itens: colunas redimensionáveis + edição inline ────────────────
// descricao = null → coluna flexível (ocupa o que sobrar, mínimo 220px).
const ITENS_COLUNAS_CHAVE = "sc.pedido.itens.colunas";
const ITENS_COLUNAS_PADRAO = {
  ref: 150, descricao: null, qtde: 80, punit: 110, desc: 100, total: 120, tes: 130, acao: 40,
};
const ITENS_COLUNAS_MINIMOS = { descricao: 220 };
const ITENS_COLUNAS = [
  { key: "ref",       label: "REF" },
  { key: "descricao", label: "Descrição" },
  { key: "qtde",      label: "Qtde",     num: true },
  { key: "punit",     label: "P. Unit.", num: true },
  { key: "desc",      label: "Desc.",    num: true },
  { key: "total",     label: "Total",    num: true },
  { key: "tes",       label: "TES" },
  { key: "acao",      label: "" },
];

// Campo editável da coluna → campo do body do PATCH /itens/{item_id}.
const CAMPO_PATCH = { qtde: "quantidade", punit: "preco_unitario", desc: "desconto" };

const numeroBR = (v, casas) =>
  new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas })
    .format(Number(v) || 0);

// Comissão do pedido: % e origem vêm prontos do backend (snapshot gravado
// em venda_service.aplicar_comissao) — aqui só formata.
const pctBR = (v) => `${numeroBR(v, 2)}%`;

// Aceita "1.234,56", "1234,56", "1234.56" e "R$ 12,50". Vírgula presente →
// pontos são milhar; só ponto → decimal se tiver até 2 casas depois dele.
function parseNumeroBR(texto) {
  let t = String(texto ?? "").replace(/R\$/gi, "").replace(/\s/g, "");
  if (!t) return NaN;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  else if ((t.match(/\./g) || []).length > 1 || /\.\d{3,}$/.test(t)) t = t.replace(/\./g, "");
  return /^-?\d*\.?\d+$/.test(t) ? Number(t) : NaN;
}

/**
 * Célula numérica sempre em modo input. Fora do foco mostra o valor
 * formatado (com "R$" quando moeda); no foco, o número cru para edição.
 * Salva no blur ou Enter; Esc reverte. Erro da API mantém o texto digitado.
 */
function CelulaNumero({ valor, casas, moeda: ehMoeda, readOnly, onSalvar, onProximo, inputRef, marcador }) {
  const [focado, setFocado] = useState(false);
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState(null);
  const [salvando, setSalvando] = useState(false);
  const ignorarBlur = useRef(false);

  const formatado = ehMoeda ? moeda(valor) : numeroBR(valor, casas);
  const paraEdicao = () => numeroBR(valor, casas).replace(/\./g, "");
  const exibido = focado || erro ? texto : formatado;

  const salvar = async () => {
    const n = parseNumeroBR(texto);
    if (Number.isNaN(n)) { setErro("Valor inválido."); return false; }
    const arredondado = Number(n.toFixed(casas));
    if (arredondado === Number(valor || 0)) { setErro(null); return true; }
    setSalvando(true);
    try {
      await onSalvar(arredondado);
      setErro(null);
      return true;
    } catch (e) {
      setErro(e.message || "Erro ao salvar.");
      return false;
    } finally {
      setSalvando(false);
    }
  };

  const handleFocus = (e) => {
    if (!erro) setTexto(paraEdicao());
    setFocado(true);
    const el = e.target;
    requestAnimationFrame(() => el.select());
  };

  const handleBlur = () => {
    setFocado(false);
    if (ignorarBlur.current) { ignorarBlur.current = false; return; }
    if (!readOnly) salvar();
  };

  const handleKeyDown = async (e) => {
    if (readOnly || salvando) return;
    if (e.key === "Enter") {
      e.preventDefault();
      const ok = await salvar();
      if (ok) { ignorarBlur.current = true; onProximo?.(); }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setTexto(paraEdicao());
      setErro(null);
      ignorarBlur.current = true;
      e.currentTarget.blur();
    }
  };

  return (
    <div className={styles.celulaEdit}>
      {marcador}
      <input
        ref={inputRef}
        className={`${styles.inputCelula} ${erro ? styles.inputCelulaErro : ""}`}
        value={exibido}
        readOnly={readOnly || salvando}
        tabIndex={readOnly ? -1 : 0}
        inputMode="decimal"
        title={erro || formatado}
        onChange={(e) => setTexto(e.target.value.toUpperCase())}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
      />
      {erro && <div className={styles.celulaErro} title={erro}>{erro}</div>}
    </div>
  );
}

// Cliente do pedido no formato do ClienteInput — montado da cópia cliente_*
// gravada no pedido (dados completos ficam só no cadastro do cliente).
function clienteDoPedido(pedido) {
  if (!pedido.cliente_id && !pedido.cliente_razao_social) return null;
  return {
    id:           pedido.cliente_id ?? null,
    codigo:       pedido.cliente_codigo || "",
    razao_social: pedido.cliente_razao_social || "",
    cnpj:         pedido.cliente_cnpj || "",
    cidade:       pedido.cliente_cidade || "",
    uf:           pedido.cliente_uf || "",
  };
}

function headerFormFromPedido(pedido) {
  return {
    numero:               pedido.numero               || "",
    data_emissao:         pedido.data_emissao         || "",
    prazo_entrega_dias:   String(pedido.prazo_entrega_dias ?? ""),
    condicoes:            pedido.condicoes            || "avista",
    condicao_pagamento_id: pedido.condicao_pagamento_id ?? "",
    primeiro_vencimento:  pedido.primeiro_vencimento  || "",
    vendedor_id:          pedido.vendedor_id          || "",
    tabela_preco_id:      pedido.tabela_preco_id      || "",
    cliente:              clienteDoPedido(pedido),
    tes_id:               pedido.tes_id ?? "",
    indicador_presenca:   pedido.indicador_presenca   || "1",
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

// ── Modal "Adicionar Item" — 3 passos: busca (pai/avulso) → grade do pai
// → linha simples do avulso. Ver PART 2a do fluxo de itens.
const ITEM_MODAL_VAZIO = {
  step: 1,
  searchQuery: "", searchResults: [], searching: false,
  produtoPai: null, grade: null, gradeLoading: false, gradeQtds: {},
  avulso: null, avulsoForm: null,
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
  const [condicoesPagamento, setCondicoesPagamento] = useState([]);
  const [loading, setLoading]           = useState(true);

  const [previewParcelas, setPreviewParcelas] = useState(null);
  const [previewParcelasErro, setPreviewParcelasErro] = useState(null);
  const [previewParcelasLoading, setPreviewParcelasLoading] = useState(false);
  const previewParcelasTimer = useRef(null);

  const [aba, setAba]                   = useState("dados");
  const [headerForm, setHeaderForm]     = useState(null);
  const [savingHeader, setSavingHeader] = useState(false);
  const [erroHeader, setErroHeader]     = useState(null);
  // Troca de tabela de preço com itens: { id, nome } aguardando confirmação.
  const [confirmTabela, setConfirmTabela] = useState(null);
  const [confirmCliente, setConfirmCliente] = useState(null);
  // id do cliente aberto no modal de cadastro ("Ver cadastro"), ou null.
  const [cadastroClienteId, setCadastroClienteId] = useState(null);
  const [aplicandoTabela, setAplicandoTabela] = useState(false);
  // Referências que mantiveram o preço anterior (sem preço na tabela nova).
  const [semPrecoTabela, setSemPrecoTabela] = useState(null);
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
      getTabelasPreco(),
      listarTes().catch(() => []),
      transportadorasApi.listar().catch(() => []),
      listarCondicoesPagamento({ situacao: "Ativa" }).catch(() => []),
    ]).then(([v, t, tes, transp, condicoes]) => {
      setVendedores((v || []).filter((x) => x.ativo !== false));
      // Lista completa — o filtro de ativas fica só no select (tabelasSelecionaveis).
      setTabelas(t || []);
      setTesList((tes || []).filter((x) => x.tipo === "Saída" && x.situacao === "Ativo"));
      setTransportadoras((transp || []).filter((x) => !x.bloqueado));
      setCondicoesPagamento(condicoes || []);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // ── Cabeçalho (Dados / Transporte / Outros) ───────────────────────────────────
  const setH = (key) => (e) => setHeaderForm((f) => ({ ...f, [key]: e.target.value }));
  const setHUpper = (key) => (e) => setHeaderForm((f) => ({ ...f, [key]: e.target.value.toUpperCase() }));

  const handleSalvarHeader = async () => {
    if (!headerForm.cliente?.razao_social) {
      setErroHeader("Informe o cliente do pedido.");
      setAba("dados");
      return;
    }
    setSavingHeader(true); setErroHeader(null); setHeaderSalvo(false);
    try {
      const updated = await updatePedidoVenda(id, {
        prazo_entrega_dias:   Number(headerForm.prazo_entrega_dias) || 0,
        condicoes:            headerForm.condicoes,
        condicao_pagamento_id: headerForm.condicao_pagamento_id ? Number(headerForm.condicao_pagamento_id) : null,
        primeiro_vencimento:  headerForm.primeiro_vencimento || null,
        vendedor_id:          headerForm.vendedor_id     || null,
        tabela_preco_id:      headerForm.tabela_preco_id || null,
        // Só o vínculo: a cópia cliente_* é preenchida pelo backend a partir
        // do cadastro (e ignorada se vier daqui). Pedido de cliente não
        // cadastrado (sem id) não manda nada e mantém a cópia atual.
        ...(headerForm.cliente?.id ? { cliente_id: headerForm.cliente.id } : {}),
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

  // Campo do backend é "ativa". A tabela já gravada no pedido continua
  // no select mesmo se tiver sido inativada depois.
  const tabelasSelecionaveis = tabelas.filter(
    (t) => t.ativa || t.id === headerForm?.tabela_preco_id,
  );
  const condicaoPagamentoSel = headerForm?.condicao_pagamento_id
    ? condicoesPagamento.find((c) => String(c.id) === String(headerForm.condicao_pagamento_id))
    : null;

  // ── Preview de parcelas (Aba Dados) — debounce 600ms ──────────────────────
  useEffect(() => {
    if (!headerForm || !pedido) return;
    clearTimeout(previewParcelasTimer.current);

    if (!condicaoPagamentoSel || !(parseFloat(pedido.total_pedido) > 0)) {
      setPreviewParcelas(null);
      setPreviewParcelasErro(null);
      return;
    }
    const dataBase = condicaoPagamentoSel.tipo === "intervalo"
      ? headerForm.primeiro_vencimento
      : pedido.data_emissao;
    if (!dataBase) {
      setPreviewParcelas(null);
      setPreviewParcelasErro(null);
      return;
    }

    previewParcelasTimer.current = setTimeout(async () => {
      setPreviewParcelasLoading(true);
      setPreviewParcelasErro(null);
      try {
        const resp = await simularParcelas({
          condicao_id: Number(headerForm.condicao_pagamento_id),
          valor: pedido.total_pedido,
          data_emissao: dataBase,
        });
        setPreviewParcelas(resp.parcelas || []);
      } catch (e) {
        setPreviewParcelas(null);
        setPreviewParcelasErro(e.message);
      } finally {
        setPreviewParcelasLoading(false);
      }
    }, 600);
    return () => clearTimeout(previewParcelasTimer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [headerForm?.condicao_pagamento_id, headerForm?.primeiro_vencimento, pedido?.total_pedido, pedido?.data_emissao]);

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
  const abrirItemModal = () => {
    setItemModal({ ...ITEM_MODAL_VAZIO });
    setErroItem(null);
  };

  const handleSearchChange = (query) => {
    setItemModal((m) => ({ ...m, searchQuery: query, searchResults: [] }));
    if (searchInputRef.current) {
      const rect = searchInputRef.current.getBoundingClientRect();
      setAcPos({ top: rect.bottom + 2, left: rect.left, width: rect.width });
    }
    clearTimeout(searchTimer.current);
    if (query.trim().length < 1) return;
    searchTimer.current = setTimeout(async () => {
      setItemModal((m) => ({ ...m, searching: true }));
      try {
        const results = await produtosApi.buscaPedido(query);
        setItemModal((m) => ({ ...m, searchResults: results || [], searching: false }));
      } catch {
        setItemModal((m) => ({ ...m, searching: false }));
      }
    }, 400);
  };

  // Passo 1 → Passo 2 (produto pai, carrega a grade) ou Passo 3 (avulso).
  const selecionarResultadoBusca = async (resultado) => {
    if (resultado.tipo === "avulso") {
      setItemModal((m) => ({
        ...m,
        step: 3,
        searchResults: [],
        avulso: resultado,
        avulsoForm: {
          quantidade: "1",
          precoUnit: resultado.preco_venda != null ? String(resultado.preco_venda) : "",
          tesId: headerForm?.tes_id || "",
          descontoPct: "0",
        },
      }));
      return;
    }
    setItemModal((m) => ({
      ...m, step: 2, searchResults: [], produtoPai: resultado, gradeLoading: true, gradeQtds: {},
    }));
    try {
      const grade = await produtosApi.gradePedido(resultado.id);
      setItemModal((m) => ({ ...m, grade, gradeLoading: false }));
    } catch (e) {
      setErroItem(e.message);
      setItemModal((m) => ({ ...m, gradeLoading: false }));
    }
  };

  const voltarParaBusca = () => {
    setErroItem(null);
    setItemModal((m) => ({ ...ITEM_MODAL_VAZIO, searchQuery: m.searchQuery }));
  };

  // ── Passo 2 — grade do produto pai ────────────────────────────────────────
  const skuNaCelula = (linhaId, colunaId) =>
    itemModal?.grade?.skus.find((s) => s.linha_item_id === linhaId && s.coluna_item_id === colunaId);

  const setGradeQtd = (linhaId, colunaId, valor) => {
    const key = `${linhaId}-${colunaId}`;
    setItemModal((m) => ({ ...m, gradeQtds: { ...m.gradeQtds, [key]: valor } }));
  };

  const gradeTotais = (() => {
    if (!itemModal?.grade) return { pecas: 0, valor: 0, temSemPreco: false };
    let pecas = 0, valor = 0, temSemPreco = false;
    for (const [key, qtdStr] of Object.entries(itemModal.gradeQtds)) {
      const qtd = parseInt(qtdStr) || 0;
      if (qtd <= 0) continue;
      const [linhaId, colunaId] = key.split("-").map((v) => (v === "null" ? null : Number(v)));
      const sku = skuNaCelula(linhaId, colunaId);
      if (!sku) continue;
      pecas += qtd;
      if (sku.preco_origem === "sem_preco") temSemPreco = true;
      else valor += qtd * (parseFloat(sku.preco_venda) || 0);
    }
    return { pecas, valor, temSemPreco };
  })();

  const handleAdicionarGrade = async () => {
    const itensBulk = [];
    for (const [key, qtdStr] of Object.entries(itemModal.gradeQtds)) {
      const qtd = parseInt(qtdStr) || 0;
      if (qtd <= 0) continue;
      const [linhaId, colunaId] = key.split("-").map((v) => (v === "null" ? null : Number(v)));
      const sku = skuNaCelula(linhaId, colunaId);
      if (!sku || sku.situacao !== "Ativo") continue;
      itensBulk.push({
        produto_id: itemModal.produtoPai.id,
        sku_id: sku.id,
        quantidade: qtd,
        preco_unitario: sku.preco_venda ?? 0,
        tes_id: headerForm?.tes_id ? Number(headerForm.tes_id) : null,
        desconto_pct: 0,
      });
    }
    if (itensBulk.length === 0) { setErroItem("Informe ao menos uma quantidade na grade."); return; }
    setSaving(true); setErroItem(null);
    try {
      await addItensBulkPedidoVenda(id, itensBulk);
      await carregar();
      setItemModal(null);
    } catch (e) {
      setErroItem(e.message);
    } finally {
      setSaving(false);
    }
  };

  // ── Passo 3 — produto avulso ───────────────────────────────────────────────
  const setAvulsoForm = (key) => (e) =>
    setItemModal((m) => ({ ...m, avulsoForm: { ...m.avulsoForm, [key]: e.target.value } }));

  const totalAvulso = (() => {
    if (!itemModal?.avulsoForm) return 0;
    const qtd = parseInt(itemModal.avulsoForm.quantidade) || 0;
    const preco = parseFloat(itemModal.avulsoForm.precoUnit) || 0;
    const desconto = parseFloat(itemModal.avulsoForm.descontoPct) || 0;
    return qtd * preco * (1 - desconto / 100);
  })();

  const handleAdicionarAvulso = async () => {
    const { quantidade, precoUnit, tesId, descontoPct } = itemModal.avulsoForm;
    if (!parseInt(quantidade) || parseInt(quantidade) <= 0) {
      setErroItem("Informe uma quantidade válida.");
      return;
    }
    setSaving(true); setErroItem(null);
    try {
      await addItensBulkPedidoVenda(id, [{
        produto_id: itemModal.avulso.id,
        sku_id: null,
        quantidade: parseInt(quantidade),
        preco_unitario: parseFloat(precoUnit) || 0,
        tes_id: tesId ? Number(tesId) : null,
        desconto_pct: parseFloat(descontoPct) || 0,
      }]);
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

  const itens = pedido?.itens || [];

  // ── Tabela de itens: edição inline ────────────────────────────────────────────
  const itensEditaveis = podeEditar && pedido?.status === "Aberto";
  const { larguras, arrastando, iniciarArrasto, restaurar } = useResizableColumns(
    ITENS_COLUNAS_CHAVE, ITENS_COLUNAS_PADRAO, ITENS_COLUNAS_MINIMOS,
  );
  const camposItemRef = useRef(new Map());

  // Item legado de corte (grupo_id) tem quantidade por tamanho — o PATCH
  // recusa "quantidade" para ele, então Qtde fica só leitura.
  const camposEditaveisItem = (item) => {
    if (!itensEditaveis) return [];
    return item.grupo_id ? ["punit", "desc"] : ["qtde", "punit", "desc"];
  };

  // Ordem de navegação do Enter: campos editáveis da linha, depois a
  // primeira coluna editável da linha seguinte.
  const focarProximoCampo = (chaveAtual) => {
    const ordem = itens.flatMap((item) => camposEditaveisItem(item).map((c) => `${item.id}:${c}`));
    const proximo = ordem[ordem.indexOf(chaveAtual) + 1];
    if (proximo) camposItemRef.current.get(proximo)?.focus();
    else camposItemRef.current.get(chaveAtual)?.blur();
  };

  const aplicarRespostaItem = (resp) =>
    setPedido((p) => ({
      ...p,
      total_pedido: resp.totais.total,
      itens: p.itens.map((i) => (i.id === resp.item.id ? { ...i, ...resp.item } : i)),
    }));

  const salvarCampoItem = async (item, coluna, valor) => {
    aplicarRespostaItem(await updateItemPedidoVenda(id, item.id, { [CAMPO_PATCH[coluna]]: valor }));
  };

  // TesInput já validou o código; o PATCH revalida pelo tes_codigo.
  const salvarTesItem = async (item, tes) => {
    aplicarRespostaItem(await updateItemPedidoVenda(id, item.id, { tes_codigo: tes.codigo }));
  };

  // ── Troca de cliente ──────────────────────────────────────────────────────────
  // Só no formulário — vai para o backend com "Salvar Alterações". Com itens
  // no pedido, pede confirmação antes.
  const handleTrocarCliente = (novo) => {
    if (itens.length > 0) {
      setConfirmCliente(novo);
      return;
    }
    setHeaderForm((f) => ({ ...f, cliente: novo }));
  };

  // "Ver cadastro": abre o cadastro em modal por cima do pedido — sem sair
  // da página, então alterações não salvas do pedido continuam no form.
  const verCadastroCliente = (c) => setCadastroClienteId(c.id);

  const cadastroClienteSalvo = async (salvo) => {
    setCadastroClienteId(null);
    const doCampo = headerForm.cliente?.id === salvo.id;
    // O backend já recopiou o cadastro para este pedido (Aberto, sem NF-e,
    // cliente gravado = o editado): busca a cópia nova sem descartar o
    // resto do formulário.
    if (salvo.pedidos_sincronizados > 0 && pedido.cliente_id === salvo.id) {
      try {
        const p = await getPedidoVenda(id);
        setPedido(p);
        if (doCampo) setHeaderForm((f) => ({ ...f, cliente: clienteDoPedido(p) }));
        return;
      } catch { /* segue para o ajuste local abaixo */ }
    }
    // Cliente escolhido e ainda não salvo no pedido (ou pedido que não
    // sincroniza): só o campo mostra o cadastro novo; a cópia do pedido vem
    // no próximo "Salvar Alterações".
    if (doCampo && pedido.status === "Aberto") {
      setHeaderForm((f) => ({
        ...f,
        cliente: {
          id: salvo.id,
          codigo: salvo.codigo || "",
          razao_social: salvo.razao_social || "",
          cnpj: salvo.cnpj || salvo.cpf || "",
          cidade: salvo.cidade || "",
          uf: salvo.estado || "",
        },
      }));
    }
  };

  // ── Troca de tabela de preço ──────────────────────────────────────────────────
  // Com itens no pedido, escolher outra tabela reprecifica tudo (inclusive
  // preço manual) após confirmação. Esvaziar o campo não mexe em preço —
  // só entra no PATCH do cabeçalho ao salvar.
  const handleTrocarTabela = (e) => {
    const novaId = e.target.value;
    if (!novaId || itens.length === 0 || novaId === pedido.tabela_preco_id) {
      setHeaderForm((f) => ({ ...f, tabela_preco_id: novaId }));
      return;
    }
    const tabela = tabelas.find((t) => t.id === novaId);
    setConfirmTabela({ id: novaId, nome: tabela?.nome || "" });
  };

  const confirmarAplicarTabela = async () => {
    const { id: tabelaId } = confirmTabela;
    setAplicandoTabela(true);
    try {
      const resp = await aplicarTabelaPedidoVenda(id, tabelaId);
      setPedido(resp.pedido);
      setHeaderForm((f) => ({ ...f, tabela_preco_id: tabelaId }));
      setSemPrecoTabela(resp.sem_preco?.length ? resp.sem_preco : null);
      setErroHeader(null);
    } catch (err) {
      setErroHeader(err.message);
    } finally {
      setAplicandoTabela(false);
      setConfirmTabela(null);
    }
  };

  const valorTotalItem = (item) =>
    (parseFloat(item.preco_total) || 0) - (parseFloat(item.desconto_valor) || 0) + (parseFloat(item.acrescimo_valor) || 0);

  const somaLargurasFixas = Object.values(larguras).reduce((acc, w) => acc + (w || 0), 0);
  const estiloTabelaItens = larguras.descricao != null
    ? { width: somaLargurasFixas }
    : { width: "100%", minWidth: somaLargurasFixas + ITENS_COLUNAS_MINIMOS.descricao };

  // Sem vendedor não há comissão — nem quadro na aba Dados, nem linha nos totais.
  const tabelaAtual    = tabelas.find((t) => t.id === pedido?.tabela_preco_id);
  const comissaoPctStr = pedido?.vendedor_id ? pctBR(pedido.comissao_pct) : null;
  const comissaoOrigemTexto = !pedido?.vendedor_id ? "Pedido sem vendedor" : ({
    VINCULO:         `Comissão do vendedor na tabela ${tabelaAtual?.nome || ""}`.trim(),
    PADRAO_VENDEDOR: "Comissão padrão do vendedor",
    NENHUMA:         "Vendedor sem comissão para esta tabela",
  }[pedido.comissao_origem] || "");
  // Vendedor/tabela alterados no formulário e ainda não salvos: o campo
  // continua mostrando a comissão gravada até o PATCH devolver a nova.
  const comissaoPendente = !!pedido && !!headerForm && pedido.status === "Aberto" && (
    (headerForm.vendedor_id || null) !== (pedido.vendedor_id || null)
    || (headerForm.tabela_preco_id || null) !== (pedido.tabela_preco_id || null)
  );
  const comissaoTooltip = [comissaoOrigemTexto, comissaoPendente && "Salve o pedido para recalcular."]
    .filter(Boolean).join(" — ");

  const subtotalItens = itens.reduce(
    (acc, i) => acc + (parseFloat(i.preco_total) || 0) - (parseFloat(i.desconto_valor) || 0) + (parseFloat(i.acrescimo_valor) || 0),
    0
  );

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

      {/* ── Cabeçalho: título + status + cliente à esquerda, ações à direita.
          Em tela estreita as ações quebram para a linha de baixo. ── */}
      <div className={styles.cabecalho}>
        <div className={styles.cabecalhoTitulo}>
          <div className={styles.tituloLinha}>
            <h1 className={styles.titulo}>Pedido {pedido.numero}</h1>
            <span className={`${styles.statusBadge} ${styles[STATUS_CLS[pedido.status] || "stAberto"]}`}>
              {STATUS_LABELS[pedido.status] || pedido.status}
            </span>
          </div>
          {/* Cliente gravado — atualiza depois de trocar e salvar. */}
          {pedido.cliente_razao_social && (
            <p className={styles.clienteLinha} title={pedido.cliente_razao_social}>
              {pedido.cliente_razao_social}
            </p>
          )}
        </div>

        <div className={styles.actionBar}>
          <button
            className={styles.btnHeaderSecondary}
            onClick={() => downloadBlob(() => getPdfCortePedidoVenda(id), `corte-${pedido.numero}.pdf`)}
          >
            Formulário de Corte PDF
          </button>
          <button
            className={styles.btnHeaderSecondary}
            onClick={() => downloadBlob(() => getPdfPedidoVenda(id), `pedido-${pedido.numero}.pdf`)}
          >
            Formulário de Pedido PDF
          </button>

          {((podeExcluir && pedido.status === "Aberto") ||
            (podeEditar && pedido.status === "Fechado" && pedido.nfe_id == null) ||
            (podeEditar && pedido.status === "Aberto")) && (
            <span className={styles.actionBarSeparator} />
          )}

          {podeExcluir && pedido.status === "Aberto" && (
            <button className={styles.btnHeaderCancelar} onClick={() => setCancelarConfirm(true)} disabled={statusLoading}>
              Cancelar Pedido
            </button>
          )}
          {podeEditar && pedido.status === "Fechado" && pedido.nfe_id == null && (
            <button className={styles.btnHeaderSecondary} onClick={() => handleMudarStatus("Aberto")} disabled={statusLoading}>
              Reabrir Pedido
            </button>
          )}
          {podeEditar && pedido.status === "Fechado" && pedido.nfe_id == null && (
            <button className={styles.btnHeaderFechar} onClick={abrirNfeModal}>
              Emitir Nota Fiscal
            </button>
          )}
          {podeEditar && pedido.status === "Aberto" && (
            <button className={styles.btnHeaderFechar} onClick={() => handleMudarStatus("Fechado")} disabled={statusLoading}>
              Fechar Pedido
            </button>
          )}
        </div>
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

      {semPrecoTabela && (
        <div
          className={styles.avisoWarn}
          style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "0.75rem", marginBottom: "0.75rem" }}
        >
          <span>
            Sem preço na tabela aplicada — mantiveram o preço anterior:{" "}
            <strong>{semPrecoTabela.join(", ")}</strong>
          </span>
          <button className={styles.btnClose} onClick={() => setSemPrecoTabela(null)} aria-label="Fechar aviso">×</button>
        </div>
      )}

      {cadastroClienteId != null && (
        <ClienteFormModal
          clienteId={cadastroClienteId}
          onClose={() => setCadastroClienteId(null)}
          onSaved={cadastroClienteSalvo}
        />
      )}

      <ConfirmModal
        isOpen={!!confirmCliente}
        titulo="Trocar cliente"
        mensagem={`Trocar o cliente do pedido para ${confirmCliente?.razao_social || ""}?`}
        labelConfirmar="Trocar"
        variante="neutro"
        onConfirmar={() => {
          const novo = confirmCliente;
          setConfirmCliente(null);
          setHeaderForm((f) => ({ ...f, cliente: novo }));
        }}
        onCancelar={() => setConfirmCliente(null)}
      />

      <ConfirmModal
        isOpen={!!confirmTabela}
        titulo="Aplicar tabela de preço"
        mensagem={`Aplicar a tabela ${confirmTabela?.nome || ""}? Todos os preços dos itens serão substituídos, inclusive os alterados manualmente.`}
        labelConfirmar={aplicandoTabela ? "Aplicando…" : "Aplicar"}
        variante="neutro"
        onConfirmar={() => { if (!aplicandoTabela) confirmarAplicarTabela(); }}
        onCancelar={() => { if (!aplicandoTabela) setConfirmTabela(null); }}
      />

      {/* ══ ABA DADOS ══ */}
      {aba === "dados" && (
        <div className={`${styles.tabPanel} ${styles.compactoCampos}`}>
          <div className={styles.grid3Compacto}>
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

            {/* div, não label: o campo tem dois inputs e botões */}
            <div className={`${styles.field} ${styles.colSpan3}`}>
              <span>Cliente</span>
              <ClienteInput
                cliente={headerForm.cliente}
                readOnly={!podeEditar || pedido.status !== "Aberto"}
                onChange={handleTrocarCliente}
                onVerCadastro={hasPermission("cadastros_clientes", "ver") ? verCadastroCliente : null}
              />
            </div>

            <label className={`${styles.field} ${styles.colSpan2}`}>
              <span>Condição de Pagamento</span>
              <select
                className={styles.input}
                disabled={!podeEditar}
                value={headerForm.condicao_pagamento_id}
                onChange={(e) => setHeaderForm((f) => ({ ...f, condicao_pagamento_id: e.target.value }))}
              >
                <option value="">Nenhuma</option>
                {condicoesPagamento.map((c) => (
                  <option key={c.id} value={c.id}>{c.codigo} — {c.descricao}</option>
                ))}
              </select>
            </label>
            <label className={styles.field}>
              <span>Primeiro Vencimento</span>
              <input type="date" className={styles.input}
                disabled={!podeEditar || condicaoPagamentoSel?.tipo !== "intervalo"}
                value={headerForm.primeiro_vencimento} onChange={setH("primeiro_vencimento")} />
            </label>

            <label className={styles.field}>
              <span>Vendedor</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.vendedor_id}
                onChange={(e) => {
                  const vid = e.target.value;
                  setHeaderForm((f) => ({ ...f, vendedor_id: vid }));
                }}>
                <option value="">Sem vendedor</option>
                {vendedores.map((v) => <option key={v.id} value={v.id}>{v.nome}</option>)}
              </select>
            </label>
            <label className={styles.field}>
              <span>Tabela de preço</span>
              <select className={styles.input} disabled={!podeEditar || aplicandoTabela} value={headerForm.tabela_preco_id} onChange={handleTrocarTabela}>
                <option value="">Nenhuma</option>
                {tabelasSelecionaveis.map((t) => (
                  <option key={t.id} value={t.id}>{t.nome}</option>
                ))}
              </select>
            </label>
            <label className={styles.field}>
              {/* Renomeado de "Condição de pagamento" para não confundir com o
                  select de Condição de Pagamento (parcelas) acima — este aqui só
                  decide preço à vista/a prazo na tabela de preço, ver
                  services/venda_service.get_preco. */}
              <span>Preço da tabela</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.condicoes} onChange={setH("condicoes")}>
                <option value="avista">À Vista</option>
                <option value="aprazo">A Prazo</option>
              </select>
            </label>

            <label className={styles.field}>
              <span>Comissão (%)</span>
              <input
                className={`${styles.input} ${styles.inputSomenteLeitura} ${pedido.vendedor_id && pedido.comissao_origem === "NENHUMA" ? styles.inputAlerta : ""}`}
                value={comissaoPctStr || "—"}
                title={comissaoTooltip}
                readOnly
                tabIndex={-1}
              />
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
                {INDICADOR_PRESENCA_OPCOES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>

            {condicaoPagamentoSel && (
              <div className={`${styles.parcelasPreview} ${styles.colSpan3}`}>
                <p className={styles.parcelasPreviewTitulo}>Parcelas que serão geradas:</p>
                {previewParcelasLoading ? (
                  <p className={styles.parcelasPreviewMsg}>Calculando…</p>
                ) : previewParcelasErro ? (
                  <p className={styles.parcelasPreviewMsg}>{previewParcelasErro}</p>
                ) : previewParcelas ? (
                  <ul className={styles.parcelasPreviewLista}>
                    {previewParcelas.map((p) => (
                      <li key={p.parcela}>
                        {p.descricao} — {moeda(p.valor)} — {dataLocal(p.vencimento)}
                      </li>
                    ))}
                  </ul>
                ) : condicaoPagamentoSel.tipo === "intervalo" ? (
                  <p className={styles.parcelasPreviewMsg}>Informe o primeiro vencimento para ver o preview.</p>
                ) : (
                  <p className={styles.parcelasPreviewMsg}>Salve o total do pedido para ver o preview.</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══ ABA ITENS ══ */}
      {aba === "itens" && (
        <div className={styles.tabPanel}>
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>Itens do pedido</h2>
            <div className={styles.sectionHeadRight}>
              <div className={styles.descontoHeader}>
                <span className={styles.descontoHeaderLabel}>DESCONTO GERAL:</span>
                <input
                  type="number" step="0.01" min="0" max="100"
                  className={styles.descontoInputSm}
                  disabled={!podeEditar}
                  title="Desconto (%)"
                  value={headerForm.desconto_geral_pct}
                  onChange={(e) => {
                    const pct = e.target.value;
                    const valor = subtotalItens > 0 ? (subtotalItens * (parseFloat(pct) || 0)) / 100 : 0;
                    setHeaderForm((f) => ({ ...f, desconto_geral_pct: pct, desconto_geral_valor: valor.toFixed(2) }));
                  }}
                />
                <span className={styles.descontoUnit}>%</span>
                <span className={styles.descontoUnit}>R$</span>
                <input
                  type="number" step="0.01" min="0"
                  className={styles.descontoInputSm}
                  disabled={!podeEditar}
                  title="Desconto (R$)"
                  value={headerForm.desconto_geral_valor}
                  onChange={(e) => {
                    const valor = e.target.value;
                    const pct = subtotalItens > 0 ? ((parseFloat(valor) || 0) / subtotalItens) * 100 : 0;
                    setHeaderForm((f) => ({ ...f, desconto_geral_valor: valor, desconto_geral_pct: pct.toFixed(2) }));
                  }}
                />
                {podeEditar && (
                  <button className={styles.btnAplicar} onClick={handleSalvarHeader} disabled={savingHeader}>
                    {savingHeader ? "Salvando…" : "Aplicar"}
                  </button>
                )}
              </div>
              {podeEditar && (
                <>
                  <span className={styles.headSeparator}>|</span>
                  <button className={styles.btnPrimary} onClick={abrirItemModal}>+ Adicionar Item</button>
                </>
              )}
            </div>
          </div>

          <div className={`sc-card ${styles.tableCard}`}>
            <div className={styles.tableWrap}>
              <table className={styles.table} style={estiloTabelaItens}>
                <colgroup>
                  {ITENS_COLUNAS.map((col) => (
                    <col
                      key={col.key}
                      style={larguras[col.key] != null ? { width: larguras[col.key] } : undefined}
                    />
                  ))}
                </colgroup>
                <thead>
                  <tr>
                    {ITENS_COLUNAS.map((col) => (
                      <th key={col.key} className={col.num ? styles.thNum : ""} title={col.label}>
                        {col.label}
                        <span
                          className={`${styles.resizeHandle} ${arrastando === col.key ? styles.resizeHandleAtivo : ""}`}
                          onMouseDown={iniciarArrasto(col.key)}
                          onDoubleClick={() => restaurar(col.key)}
                          title="Arraste para redimensionar. Duplo clique restaura."
                        />
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {itens.map((item) => {
                    const editaveis = camposEditaveisItem(item);
                    const celula = (coluna, props) => {
                      const chave = `${item.id}:${coluna}`;
                      return (
                        <CelulaNumero
                          {...props}
                          readOnly={!editaveis.includes(coluna)}
                          onSalvar={(valor) => salvarCampoItem(item, coluna, valor)}
                          onProximo={() => focarProximoCampo(chave)}
                          inputRef={(el) => {
                            if (el) camposItemRef.current.set(chave, el);
                            else camposItemRef.current.delete(chave);
                          }}
                        />
                      );
                    };
                    const totalItem = valorTotalItem(item);
                    return (
                      <tr key={item.id}>
                        <td className={styles.tdRef} title={item.ref_codigo || ""}>
                          <code>{item.ref_codigo || ""}</code>
                        </td>
                        <td className={styles.tdNome} title={item.descricao_completa || ""}>
                          {item.descricao_completa || ""}
                        </td>
                        <td className={styles.tdEdit}>
                          {celula("qtde", { valor: item.quantidade_total, casas: 0 })}
                        </td>
                        <td className={styles.tdEdit}>
                          {celula("punit", {
                            valor: item.preco_unitario, casas: 2, moeda: true,
                            marcador: item.preco_manual ? (
                              <span className={styles.marcadorManual} title="Preço alterado manualmente" />
                            ) : null,
                          })}
                        </td>
                        <td className={styles.tdEdit}>
                          {celula("desc", { valor: item.desconto_valor, casas: 2, moeda: true })}
                        </td>
                        <td className={styles.tdTotal} title={moeda(totalItem)}>{moeda(totalItem)}</td>
                        <td className={styles.tdTes}>
                          <TesInput
                            tesId={item.tes_id}
                            tesList={tesList}
                            readOnly={!itensEditaveis}
                            onChange={(tes) => salvarTesItem(item, tes)}
                          />
                        </td>
                        <td className={styles.tdAcao}>
                          {itensEditaveis && (
                            <button
                              className={styles.btnExcluir}
                              onClick={() => removerItem(item.id)}
                              title="Remover"
                            >×</button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {itens.length === 0 && (
                    <tr>
                      <td colSpan={ITENS_COLUNAS.length} className={styles.empty}>
                        Nenhum item adicionado.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
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
        <div className={`${styles.tabPanel} ${styles.compactoCampos}`}>
          <div className={styles.grid3Compacto}>
            <label className={`${styles.field} ${styles.colSpan3}`}>
              <span>Tipo de Frete</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.tipo_frete} onChange={setH("tipo_frete")}>
                <option value="">Selecionar</option>
                {TIPO_FRETE_OPCOES.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
            <label className={`${styles.field} ${styles.colSpan3}`}>
              <span>Transportadora</span>
              <select className={styles.input} disabled={!podeEditar} value={headerForm.transportadora_id} onChange={setH("transportadora_id")}>
                <option value="">Nenhuma</option>
                {transportadoras.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
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
              <span>Peso Bruto (kg)</span>
              <input type="number" step="0.001" min="0" className={styles.input} disabled={!podeEditar}
                value={headerForm.peso_bruto} onChange={setH("peso_bruto")} />
            </label>
            <label className={styles.field}>
              <span>Peso Líquido (kg)</span>
              <input type="number" step="0.001" min="0" className={styles.input} disabled={!podeEditar}
                value={headerForm.peso_liquido} onChange={setH("peso_liquido")} />
            </label>
            <label className={styles.field}>
              <span>Quantidade de Volumes</span>
              <input type="number" step="1" min="0" className={styles.input} disabled={!podeEditar}
                value={headerForm.qtd_volumes} onChange={setH("qtd_volumes")} />
            </label>

            <label className={styles.field}>
              <span>Espécie dos Volumes</span>
              <input className={styles.input} disabled={!podeEditar}
                value={headerForm.especie_volumes} onChange={setHUpper("especie_volumes")} placeholder="Ex: Caixa, Fardo…" />
            </label>
            <label className={styles.field}>
              <span>Placa do Veículo</span>
              <input className={styles.input} disabled={!podeEditar}
                value={headerForm.placa_veiculo} onChange={setHUpper("placa_veiculo")} maxLength={10} />
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
        <div className={`${styles.tabPanel} ${styles.compactoCampos}`}>
          <div className={styles.grid3Compacto}>
            <label className={`${styles.field} ${styles.colSpan3}`}>
              <span>Informações Adicionais da Nota</span>
              <textarea
                className={`${styles.input} ${styles.textarea}`}
                disabled={!podeEditar}
                rows={3}
                value={headerForm.informacoes_adicionais}
                onChange={setHUpper("informacoes_adicionais")}
                placeholder="Vai para o XML da NF-e"
              />
            </label>
            <label className={`${styles.field} ${styles.colSpan3}`}>
              <span>Observações Internas</span>
              <textarea
                className={`${styles.input} ${styles.textarea}`}
                disabled={!podeEditar}
                rows={3}
                value={headerForm.observacoes_internas}
                onChange={setHUpper("observacoes_internas")}
                placeholder="Uso interno — não vai para a NF-e"
              />
            </label>
          </div>
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

      {/* ══ MODAL — Adicionar item (3 passos: busca → grade do pai / avulso) ══ */}
      {itemModal && (
        <div className={styles.overlay} onClick={() => { setItemModal(null); setErroItem(null); }}>
          <div
            className={`${styles.modalMd} ${
              itemModal.step === 2 ? styles.modalGrade : itemModal.step === 3 ? styles.modalAvulso : styles.modalBusca
            }`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>
                {itemModal.step === 1 ? (
                  "Adicionar Item"
                ) : (
                  <>
                    <button className={styles.btnVoltarModal} onClick={voltarParaBusca} title="Voltar">←</button>
                    {itemModal.step === 2 ? itemModal.produtoPai?.descricao : itemModal.avulso?.descricao}
                  </>
                )}
              </h2>
              <button className={styles.btnClose}
                onClick={() => { setItemModal(null); setErroItem(null); }}>×</button>
            </div>

            <div className={styles.modalBody}>
              {/* ── Passo 1 — busca ── */}
              {itemModal.step === 1 && (
                <div className={styles.searchWrap}>
                  <label className={styles.field}>
                    <span>Buscar produto</span>
                    <input
                      ref={searchInputRef}
                      className={styles.input}
                      placeholder="Buscar produto por código ou nome..."
                      value={itemModal.searchQuery}
                      onChange={(e) => handleSearchChange(e.target.value)}
                      onBlur={() => setTimeout(() => setItemModal((m) => m ? { ...m, searchResults: [] } : m), 200)}
                      autoComplete="off"
                      autoFocus
                    />
                  </label>
                  {itemModal.searching && <small className={styles.precoHint}>Buscando…</small>}
                  {itemModal.searchResults.length > 0 && ReactDOM.createPortal(
                    <ul className={styles.autocomplete} style={{ top: acPos.top, left: acPos.left, width: acPos.width }}>
                      {itemModal.searchResults.map((r) => (
                        <li key={`${r.tipo}-${r.id}`} className={styles.acItem} onClick={() => selecionarResultadoBusca(r)}>
                          <span className={styles.acIcone} title={r.tipo === "pai" ? "Produto com grade" : "Produto avulso"}>
                            {r.tipo === "pai" ? "⊞" : "□"}
                          </span>
                          <code className={styles.acCod}>{r.codigo || "?"}</code>
                          <span className={styles.acNomeCol}>
                            <span className={styles.acNome}>{r.descricao}</span>
                            {r.grupo && <span className={styles.acGrupo}>{r.grupo}</span>}
                          </span>
                        </li>
                      ))}
                    </ul>,
                    document.body
                  )}
                </div>
              )}

              {/* ── Passo 2 — grade do produto pai ── */}
              {itemModal.step === 2 && (
                <>
                  {itemModal.gradeLoading ? (
                    <p className={styles.precoHint}>Carregando grade…</p>
                  ) : itemModal.grade ? (
                    <>
                      {gradeTotais.temSemPreco && (
                        <div className={styles.avisoWarn}>
                          Alguns produtos não têm preço definido. Informe uma tabela de preço no
                          pedido, cadastre o preço no produto pai, ou preencha o preço manualmente
                          após adicionar.
                        </div>
                      )}
                      <div className={styles.gradeWrap}>
                        <table className={styles.gradeTable}>
                          <thead>
                            <tr>
                              <th></th>
                              {itemModal.grade.coluna_grade.itens.map((col) => (
                                <th key={col.id}>{col.codigo_curto}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {itemModal.grade.linha_grade.itens.map((linha) => (
                              <tr key={linha.id}>
                                <th>{linha.codigo_curto}</th>
                                {itemModal.grade.coluna_grade.itens.map((col) => {
                                  const sku = skuNaCelula(linha.id, col.id);
                                  const disabled = !sku || sku.situacao !== "Ativo";
                                  const key = `${linha.id}-${col.id}`;
                                  return (
                                    <td key={col.id}>
                                      <input
                                        type="number" min="0"
                                        className={styles.gradeCell}
                                        disabled={disabled}
                                        value={itemModal.gradeQtds[key] || ""}
                                        onChange={(e) => setGradeQtd(linha.id, col.id, e.target.value)}
                                      />
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <table className={styles.gradePrecoTable}>
                          <thead><tr><th>Preço Unit.</th></tr></thead>
                          <tbody>
                            {itemModal.grade.linha_grade.itens.map((linha) => {
                              // Uma referência de preço por linha — usa a primeira coluna com
                              // SKU (o preço, salvo edição manual do SKU, é igual em toda a linha).
                              const skuRef = itemModal.grade.coluna_grade.itens
                                .map((col) => skuNaCelula(linha.id, col.id))
                                .find(Boolean);
                              return (
                                <tr key={linha.id}>
                                  <td
                                    className={skuRef?.preco_origem === "sem_preco" ? styles.gradePrecoSemPreco : ""}
                                  >
                                    {skuRef?.preco_origem === "sem_preco" ? "—" : moeda(skuRef?.preco_venda)}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      <div className={styles.itemTotal}>
                        Total de peças: <strong>{gradeTotais.pecas}</strong> | Total: <strong>{moeda(gradeTotais.valor)}</strong>
                      </div>
                    </>
                  ) : null}
                </>
              )}

              {/* ── Passo 3 — produto avulso ── */}
              {itemModal.step === 3 && itemModal.avulsoForm && (
                <>
                  <label className={styles.field}>
                    <span>Código</span>
                    <input className={styles.input} value={itemModal.avulso.codigo} disabled />
                  </label>
                  <label className={styles.field}>
                    <span>Descrição</span>
                    <input className={styles.input} value={itemModal.avulso.descricao} disabled />
                  </label>
                  <div className={styles.grid2}>
                    <label className={styles.field}>
                      <span>Quantidade *</span>
                      <input type="number" min="1" className={styles.input}
                        value={itemModal.avulsoForm.quantidade} onChange={setAvulsoForm("quantidade")} />
                    </label>
                    <label className={styles.field}>
                      <span>Preço unitário (R$) *</span>
                      <input type="number" step="0.01" className={styles.input}
                        value={itemModal.avulsoForm.precoUnit} onChange={setAvulsoForm("precoUnit")} />
                    </label>
                  </div>
                  <div className={styles.grid2}>
                    <label className={styles.field}>
                      <span>TES</span>
                      <select className={styles.input} value={itemModal.avulsoForm.tesId} onChange={setAvulsoForm("tesId")}>
                        <option value="">Nenhum</option>
                        {tesList.map((t) => <option key={t.id} value={t.id}>{t.codigo} — {t.descricao}</option>)}
                      </select>
                    </label>
                    <label className={styles.field}>
                      <span>Desconto (%)</span>
                      <input type="number" step="0.01" min="0" max="100" className={styles.input}
                        value={itemModal.avulsoForm.descontoPct} onChange={setAvulsoForm("descontoPct")} />
                    </label>
                  </div>
                  <div className={styles.itemTotal}>
                    Total: <strong>{moeda(totalAvulso)}</strong>
                  </div>
                </>
              )}

              {erroItem && <p className={styles.erro}>{erroItem}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary}
                onClick={() => { setItemModal(null); setErroItem(null); }}>Cancelar</button>
              {itemModal.step === 2 && (
                <button
                  className={styles.btnPrimary}
                  onClick={handleAdicionarGrade}
                  disabled={saving || gradeTotais.pecas === 0}
                >
                  {saving ? "Adicionando…" : "Adicionar à grade →"}
                </button>
              )}
              {itemModal.step === 3 && (
                <button className={styles.btnPrimary} onClick={handleAdicionarAvulso} disabled={saving}>
                  {saving ? "Adicionando…" : "Adicionar item"}
                </button>
              )}
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
