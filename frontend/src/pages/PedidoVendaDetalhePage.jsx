import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import {
  getPedidoVenda,
  salvarPedidoVenda,
  updateStatusPedidoVenda,
  getParcelasPreviewPedidoVenda,
} from "../api/pedidos";
import { getVendedores } from "../api/vendedores";
import { listar as listarTes } from "../api/tes";
import { listar as listarCondicoesPagamento } from "../api/condicoesPagamento";
import { criar as criarNfe } from "../api/nfe";
import { transportadorasApi } from "../api/transportadoras";
import { aplicarTabelaPedidoVenda } from "../api/pedidos";
import { getTabelasPreco } from "../api/tabelasPreco";
import ItensPedidoCard, {
  PENDENTES_VAZIO,
  contarPendencias,
  linhasEfetivas,
  mapearErrosItens,
  montarLoteItens,
  subtotalItensPedido,
} from "../components/ItensPedidoCard/ItensPedidoCard";
import ClienteInput from "../components/ClienteInput/ClienteInput";
import TesInput from "../components/TesInput/TesInput";
import ClienteFormModal from "../components/ClienteFormModal/ClienteFormModal";
import ConfirmModal from "../components/ConfirmModal/ConfirmModal";
import MenuDropdown from "../components/MenuDropdown/MenuDropdown";
import OrdemCorteAssistente from "../components/OrdemCorteAssistente/OrdemCorteAssistente";
import { criarOrdemCorte, getOrdemCorteDoPedido } from "../api/ordensCorte";
import { useAuth } from "../auth/useAuth";
import {
  RELATORIO_FORMULARIO_CORTE,
  RELATORIO_PEDIDO_VENDA,
  imprimirRelatorio,
  listarVariantes,
} from "../api/relatorios";
import styles from "./PedidoVendaDetalhePage.module.css";
import useOverlayDismiss from "../hooks/useOverlayDismiss";

const MODULO_EDITAR = "pedidos_editar";
const MODULO_EXCLUIR = "pedidos_excluir";

const STATUS_LABELS = { Aberto: "Aberto", Fechado: "Fechado", Cancelado: "Cancelado" };
const STATUS_CLS = { Aberto: "stAberto", Fechado: "stFechado", Cancelado: "stCancelado" };

// Indicador de presença (NF-e, tag indPres): label curto cabe no campo
// (3 colunas do grid); o texto completo vai no tooltip.
const INDICADOR_PRESENCA_OPCOES = [
  { value: "0", label: "0 – Não se aplica", completo: "0 – Não se aplica" },
  { value: "1", label: "1 – Presencial", completo: "1 – Operação presencial" },
  {
    value: "2",
    label: "2 – Não presencial, internet",
    completo: "2 – Operação não presencial, pela Internet",
  },
  {
    value: "3",
    label: "3 – Não presencial, teleatendimento",
    completo: "3 – Operação não presencial, Teleatendimento",
  },
  {
    value: "4",
    label: "4 – NFC-e, entrega a domicílio",
    completo: "4 – NFC-e em operação com entrega a domicílio",
  },
  {
    value: "5",
    label: "5 – Presencial, fora do estab.",
    completo: "5 – Operação presencial, fora do estabelecimento",
  },
  {
    value: "9",
    label: "9 – Não presencial, outros",
    completo: "9 – Operação não presencial, outros",
  },
];
const TIPO_FRETE_OPCOES = [
  "Sem Frete",
  "CIF",
  "FOB",
  "Por conta de terceiros",
  "Próprio",
  "Sem Ocorrência",
];
const SERIE_NFE_OPCOES = [
  { value: "001", label: "001 - NF-e" },
  { value: "002", label: "002 - NFC-e" },
  { value: "ORC", label: "ORC - Orçamento" },
];

const ABAS = [
  { id: "dados", label: "Dados" },
  { id: "transporte", label: "Transporte" },
  { id: "outros", label: "Outros" },
];

// Ícones da barra do topo (SVG, cor do texto do botão).
const IconeChevron = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
    <path
      d="M2 3.5 5 6.5 8 3.5"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);
const IconeMais = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
    <circle cx="3" cy="8" r="1.4" />
    <circle cx="8" cy="8" r="1.4" />
    <circle cx="13" cy="8" r="1.4" />
  </svg>
);

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

// Datas sem hora ("YYYY-MM-DD") são tratadas como texto, sem Date: new
// Date("2026-11-25") é meia-noite UTC e no Brasil vira 24/11 às 21h.
const dataBR = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
};

// Hoje no fuso local (toISOString é UTC: depois das 21h já seria amanhã).
const hojeISO = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
const agoraHora = () => new Date().toTimeString().slice(0, 5);

const numeroBR = (v, casas) =>
  new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(Number(v) || 0);

// Comissão do pedido: % e origem vêm prontos do backend (snapshot gravado
// em venda_service.aplicar_comissao) — aqui só formata.
const pctBR = (v) => `${numeroBR(v, 2)}%`;

// Cliente do pedido no formato do ClienteInput — montado da cópia cliente_*
// gravada no pedido (dados completos ficam só no cadastro do cliente).
// "1.234,56", "1234,56", "1234.56", "R$ 12,50", "10%" → número (NaN se
// inválido). Com vírgula, pontos são milhar; sem vírgula, ponto é decimal.
function parseNumeroBR(texto) {
  let t = String(texto ?? "").replace(/R\$|%|\s/gi, "");
  if (!t) return NaN;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  return /^-?\d*\.?\d+$/.test(t) ? Number(t) : NaN;
}

/**
 * Input numérico com formato BR fora do foco ("0,00" ou "R$ 0,00") e o
 * número cru no foco. Confirma no blur/Enter (onConfirmar(numero)); Esc ou
 * valor inválido volta ao anterior.
 */
function CampoNumero({ valor, casas = 2, prefixo = "", className, disabled, onConfirmar }) {
  const [texto, setTexto] = useState(null); // null = fora de edição
  const descartar = useRef(false);
  return (
    <input
      className={className}
      inputMode="decimal"
      disabled={disabled}
      value={texto ?? `${prefixo}${numeroBR(valor, casas)}`}
      onFocus={(e) => {
        setTexto(numeroBR(valor, casas).replace(/\./g, ""));
        const el = e.target;
        requestAnimationFrame(() => el.select());
      }}
      onChange={(e) => setTexto(e.target.value)}
      onBlur={() => {
        const n = parseNumeroBR(texto);
        setTexto(null);
        if (descartar.current) descartar.current = false;
        else if (!Number.isNaN(n)) onConfirmar(n);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        else if (e.key === "Escape") {
          descartar.current = true;
          e.currentTarget.blur();
        }
      }}
    />
  );
}

function clienteDoPedido(pedido) {
  if (!pedido.cliente_id && !pedido.cliente_razao_social) return null;
  return {
    id: pedido.cliente_id ?? null,
    codigo: pedido.cliente_codigo || "",
    razao_social: pedido.cliente_razao_social || "",
    cnpj: pedido.cliente_cnpj || "",
    cidade: pedido.cliente_cidade || "",
    uf: pedido.cliente_uf || "",
  };
}

const MSG_SAIR_SEM_SALVAR = "Há alterações não salvas neste pedido. Sair mesmo assim?";
const MSG_SALVE_ANTES = "Salve as alterações antes de continuar.";

// Forma comparável do formulário do cabeçalho: cliente pelo id (o objeto do
// ClienteInput tem outros campos) e números como número ("0" == "0.00").
function assinaturaHeader(form) {
  const norm = {};
  for (const [k, v] of Object.entries(form)) {
    if (k === "cliente") norm[k] = v?.id ?? v?.razao_social ?? null;
    else if (typeof v === "string" && /^-?\d+(\.\d+)?$/.test(v.trim())) norm[k] = Number(v);
    else norm[k] = v ?? "";
  }
  return JSON.stringify(norm);
}

// Corpo do cabeçalho no PUT /pedidos-venda/{id}.
function payloadHeader(headerForm) {
  return {
    prazo_entrega_dias: Number(headerForm.prazo_entrega_dias) || 0,
    condicoes: headerForm.condicoes,
    condicao_pagamento_id: headerForm.condicao_pagamento_id
      ? Number(headerForm.condicao_pagamento_id)
      : null,
    // Sempre enviado: data apagada → null explícito (o backend limpa; campo
    // omitido é que não alteraria).
    primeiro_vencimento: headerForm.primeiro_vencimento || null,
    vendedor_id: headerForm.vendedor_id || null,
    tabela_preco_id: headerForm.tabela_preco_id || null,
    // Só o vínculo: a cópia cliente_* é preenchida pelo backend a partir
    // do cadastro (e ignorada se vier daqui). Pedido de cliente não
    // cadastrado (sem id) não manda nada e mantém a cópia atual.
    ...(headerForm.cliente?.id ? { cliente_id: headerForm.cliente.id } : {}),
    tes_id: headerForm.tes_id || null,
    indicador_presenca: headerForm.indicador_presenca,
    desconto_geral_pct: Number(headerForm.desconto_geral_pct) || 0,
    desconto_geral_valor: Number(headerForm.desconto_geral_valor) || 0,
    acrescimo_pct: Number(headerForm.acrescimo_pct) || 0,
    acrescimo_valor: Number(headerForm.acrescimo_valor) || 0,
    transportadora_id: headerForm.transportadora_id || null,
    tipo_frete: headerForm.tipo_frete || null,
    valor_frete: Number(headerForm.valor_frete) || 0,
    valor_seguro: Number(headerForm.valor_seguro) || 0,
    valor_despesas: Number(headerForm.valor_despesas) || 0,
    peso_liquido: Number(headerForm.peso_liquido) || 0,
    peso_bruto: Number(headerForm.peso_bruto) || 0,
    qtd_volumes: Number(headerForm.qtd_volumes) || 0,
    especie_volumes: headerForm.especie_volumes || null,
    placa_veiculo: headerForm.placa_veiculo || null,
    uf_veiculo: headerForm.uf_veiculo || null,
    informacoes_adicionais: headerForm.informacoes_adicionais || null,
    observacoes_internas: headerForm.observacoes_internas || null,
  };
}

function headerFormFromPedido(pedido) {
  return {
    numero: pedido.numero || "",
    data_emissao: pedido.data_emissao || "",
    prazo_entrega_dias: String(pedido.prazo_entrega_dias ?? ""),
    condicoes: pedido.condicoes || "avista",
    condicao_pagamento_id: pedido.condicao_pagamento_id ?? "",
    primeiro_vencimento: pedido.primeiro_vencimento || "",
    vendedor_id: pedido.vendedor_id || "",
    tabela_preco_id: pedido.tabela_preco_id || "",
    cliente: clienteDoPedido(pedido),
    tes_id: pedido.tes_id ?? "",
    indicador_presenca: pedido.indicador_presenca || "1",
    desconto_geral_pct: String(pedido.desconto_geral_pct ?? 0),
    desconto_geral_valor: String(pedido.desconto_geral_valor ?? 0),
    acrescimo_pct: String(pedido.acrescimo_pct ?? 0),
    acrescimo_valor: String(pedido.acrescimo_valor ?? 0),
    transportadora_id: pedido.transportadora_id ?? "",
    tipo_frete: pedido.tipo_frete || "",
    valor_frete: String(pedido.valor_frete ?? 0),
    valor_seguro: String(pedido.valor_seguro ?? 0),
    valor_despesas: String(pedido.valor_despesas ?? 0),
    peso_liquido: String(pedido.peso_liquido ?? 0),
    peso_bruto: String(pedido.peso_bruto ?? 0),
    qtd_volumes: String(pedido.qtd_volumes ?? 0),
    especie_volumes: pedido.especie_volumes || "",
    placa_veiculo: pedido.placa_veiculo || "",
    uf_veiculo: pedido.uf_veiculo || "",
    informacoes_adicionais: pedido.informacoes_adicionais || "",
    observacoes_internas: pedido.observacoes_internas || "",
  };
}

export default function PedidoVendaDetalhePage() {
  const seletorModelosOverlay = useOverlayDismiss(() => setSeletorModelos(false));
  const cancelarConfirmOverlay = useOverlayDismiss(() => setCancelarConfirm(false));
  const nfeModalOverlay = useOverlayDismiss(() => setNfeModal(null));

  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  // ?modo=visualizar (duplo clique / "Visualizar" na lista): tudo só leitura
  // até o "Editar" do topo, que tira o parâmetro sem recarregar.
  const [searchParams, setSearchParams] = useSearchParams();
  const modoVisualizar = searchParams.get("modo") === "visualizar";
  const podeEditar = hasPermission(MODULO_EDITAR, "ver");
  const podeExcluir = hasPermission(MODULO_EXCLUIR, "ver");
  // Ordem de Corte usa as permissões do módulo de encaixes (backend idem).
  const podeVerOC = hasPermission("encaixes", "ver");
  const podeCriarOC = hasPermission("encaixes", "criar");

  const [pedido, setPedido] = useState(null);
  const [vendedores, setVendedores] = useState([]);
  const [tabelas, setTabelas] = useState([]);
  const [tesList, setTesList] = useState([]);
  const [transportadoras, setTransportadoras] = useState([]);
  const [condicoesPagamento, setCondicoesPagamento] = useState([]);
  const [loading, setLoading] = useState(true);

  const [previewParcelas, setPreviewParcelas] = useState(null);
  const [previewParcelasErro, setPreviewParcelasErro] = useState(null);
  const [previewParcelasLoading, setPreviewParcelasLoading] = useState(false);
  const previewParcelasTimer = useRef(null);

  const [aba, setAba] = useState("dados");
  const [headerForm, setHeaderForm] = useState(null);
  const [savingHeader, setSavingHeader] = useState(false);
  const [erroHeader, setErroHeader] = useState(null);
  // Troca de tabela de preço com itens: { id, nome } aguardando confirmação.
  const [confirmTabela, setConfirmTabela] = useState(null);
  const [confirmCliente, setConfirmCliente] = useState(null);
  // id do cliente aberto no modal de cadastro ("Ver cadastro"), ou null.
  const [cadastroClienteId, setCadastroClienteId] = useState(null);
  // Cadastro aberto pela lupa com o pedido fora de Aberto: só consulta.
  const [cadastroSomenteLeitura, setCadastroSomenteLeitura] = useState(false);
  const [aplicandoTabela, setAplicandoTabela] = useState(false);
  // Referências que mantiveram o preço anterior (sem preço na tabela nova).
  const [semPrecoTabela, setSemPrecoTabela] = useState(null);
  const [headerSalvo, setHeaderSalvo] = useState(false);

  // Itens: edições pendentes até "Salvar Itens" (card) ou "Salvar Pedido".
  const [pendentes, setPendentes] = useState(PENDENTES_VAZIO);
  const [errosItens, setErrosItens] = useState({});
  const [confirmSair, setConfirmSair] = useState(false);
  const paginaRef = useRef(null);

  const [statusLoading, setStatusLoading] = useState(false);
  const [statusErro, setStatusErro] = useState(null);
  const [cancelarConfirm, setCancelarConfirm] = useState(false);

  // Modelos do Formulário de Pedido (GET /variantes): [{ arquivo, padrao }].
  const [modelosPedido, setModelosPedido] = useState([]);
  const [seletorModelos, setSeletorModelos] = useState(false);
  const [gerandoRelatorio, setGerandoRelatorio] = useState(false);

  const [nfeModal, setNfeModal] = useState(null);
  const [nfeMsg, setNfeMsg] = useState(null);
  const [nfeSaving, setNfeSaving] = useState(false);
  const [nfeResultado, setNfeResultado] = useState(null);
  // OC ativa do pedido (null = nenhuma) e o assistente aberto (id da OC).
  const [ordemCorte, setOrdemCorte] = useState(null);
  const [assistenteOcId, setAssistenteOcId] = useState(null);
  const [gerandoOC, setGerandoOC] = useState(false);

  const carregar = async () => {
    setLoading(true);
    try {
      const p = await getPedidoVenda(id);
      setPedido(p);
      setHeaderForm(headerFormFromPedido(p));
      setPendentes(PENDENTES_VAZIO);
      setErrosItens({});
    } catch {
      setPedido(null);
    } finally {
      setLoading(false);
    }
  };

  // Só o pedido gravado (itens/totais) — sem tela de carregando, sem mexer no
  // formulário do cabeçalho nem nas pendências dos itens.
  const recarregarPedido = async () => setPedido(await getPedidoVenda(id));

  useEffect(() => {
    carregar();
    Promise.all([
      getVendedores(),
      getTabelasPreco(),
      listarTes().catch(() => []),
      transportadorasApi.listar().catch(() => []),
      listarCondicoesPagamento({ situacao: "Ativa" }).catch(() => []),
    ])
      .then(([v, t, tes, transp, condicoes]) => {
        setVendedores((v || []).filter((x) => x.ativo !== false));
        // Lista completa — o filtro de ativas fica só no select (tabelasSelecionaveis).
        setTabelas(t || []);
        setTesList((tes || []).filter((x) => x.tipo === "Saída" && x.situacao === "Ativo"));
        setTransportadoras((transp || []).filter((x) => !x.bloqueado));
        setCondicoesPagamento(condicoes || []);
      })
      .catch(() => {});
    listarVariantes(RELATORIO_PEDIDO_VENDA).then(setModelosPedido);
    recarregarOrdemCorte();
  }, [id]);

  const recarregarOrdemCorte = () => {
    if (!podeVerOC) return;
    getOrdemCorteDoPedido(id)
      .then(setOrdemCorte)
      .catch(() => setOrdemCorte(null));
  };

  // ── Cabeçalho (Dados / Transporte / Outros) ───────────────────────────────────
  const setH = (key) => (e) => setHeaderForm((f) => ({ ...f, [key]: e.target.value }));
  const setHUpper = (key) => (e) =>
    setHeaderForm((f) => ({ ...f, [key]: e.target.value.toUpperCase() }));

  // "Salvar Pedido": cabeçalho + itens pendentes numa transação só (PUT).
  // Item inválido → 422: marca os campos no card e nada é gravado.
  const handleSalvarPedido = async () => {
    if (!headerForm.cliente?.razao_social) {
      setErroHeader("Informe o cliente do pedido.");
      setAba("dados");
      return;
    }
    setSavingHeader(true);
    setErroHeader(null);
    setHeaderSalvo(false);
    try {
      const updated = await salvarPedidoVenda(id, {
        ...payloadHeader(headerForm),
        ...(contarPendencias(pendentes) ? { itens: montarLoteItens(pendentes) } : {}),
      });
      setPedido(updated);
      setHeaderForm(headerFormFromPedido(updated));
      setPendentes(PENDENTES_VAZIO);
      setErrosItens({});
      setHeaderSalvo(true);
      setTimeout(() => setHeaderSalvo(false), 3000);
    } catch (e) {
      if (e.erros) setErrosItens(mapearErrosItens(e.erros));
      setErroHeader(e.message);
    } finally {
      setSavingHeader(false);
    }
  };

  // Lote salvo pelo card: pedido novo, pendências dos itens zeradas. O
  // formulário do cabeçalho (e suas pendências) fica como está.
  const handleItensSalvos = (updated) => {
    setPedido(updated);
    setPendentes(PENDENTES_VAZIO);
  };

  // Campo do backend é "ativa". A tabela já gravada no pedido continua
  // no select mesmo se tiver sido inativada depois.
  const tabelasSelecionaveis = tabelas.filter(
    (t) => t.ativa || t.id === headerForm?.tabela_preco_id
  );
  const condicaoPagamentoSel = headerForm?.condicao_pagamento_id
    ? condicoesPagamento.find((c) => String(c.id) === String(headerForm.condicao_pagamento_id))
    : null;

  // ── Status / ações ────────────────────────────────────────────────────────────
  const handleMudarStatus = async (novoStatus) => {
    setStatusLoading(true);
    setStatusErro(null);
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

  const itens = pedido?.itens || [];

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
  const verCadastroCliente = (c, { somenteLeitura = false } = {}) => {
    setCadastroSomenteLeitura(somenteLeitura);
    setCadastroClienteId(c.id);
  };

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
      } catch {
        /* segue para o ajuste local abaixo */
      }
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
    // aplicar-tabela grava na hora e reprecifica os itens gravados — com
    // itens pendentes, salvar ou descartar primeiro.
    if (novaId && novaId !== pedido.tabela_preco_id && itensSujos) {
      setStatusErro("Salve ou descarte as alterações dos itens antes de trocar a tabela de preço.");
      return;
    }
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

  // Sem vendedor não há comissão — nem quadro na aba Dados, nem linha nos totais.
  const tabelaAtual = tabelas.find((t) => t.id === pedido?.tabela_preco_id);
  const comissaoPctStr = pedido?.vendedor_id ? pctBR(pedido.comissao_pct) : null;
  const comissaoOrigemTexto = !pedido?.vendedor_id
    ? "Pedido sem vendedor"
    : {
        VINCULO: `Comissão do vendedor na tabela ${tabelaAtual?.nome || ""}`.trim(),
        PADRAO_VENDEDOR: "Comissão padrão do vendedor",
        NENHUMA: "Vendedor sem comissão para esta tabela",
      }[pedido.comissao_origem] || "";
  // Vendedor/tabela alterados no formulário e ainda não salvos: o campo
  // continua mostrando a comissão gravada até o PATCH devolver a nova.
  const comissaoPendente =
    !!pedido &&
    !!headerForm &&
    pedido.status === "Aberto" &&
    ((headerForm.vendedor_id || null) !== (pedido.vendedor_id || null) ||
      (headerForm.tabela_preco_id || null) !== (pedido.tabela_preco_id || null));
  const comissaoTooltip = [
    comissaoOrigemTexto,
    comissaoPendente && "Salve o pedido para recalcular.",
  ]
    .filter(Boolean)
    .join(" — ");

  const linhasAtuais = linhasEfetivas(itens, pendentes);
  const subtotalItens = subtotalItensPedido(linhasAtuais);

  // ── Pendências e proteções ────────────────────────────────────────────────────
  // Regra única de só leitura: modo visualização ou fora de Aberto (sem
  // salvar, então não há pendência).
  const somenteLeitura = modoVisualizar || pedido?.status !== "Aberto";
  const editavel = podeEditar && !somenteLeitura;
  const sairVisualizacao = () =>
    setSearchParams(
      (sp) => {
        sp.delete("modo");
        return sp;
      },
      { replace: true }
    );
  const itensSujos = contarPendencias(pendentes) > 0;
  const headerSujo =
    !!pedido &&
    !!headerForm &&
    assinaturaHeader(headerForm) !== assinaturaHeader(headerFormFromPedido(pedido));
  const temPendencias = editavel && (itensSujos || headerSujo);

  // Fechar a janela/aba do navegador. No Electron um beforeunload que
  // cancela bloqueia o fechamento sem mostrar diálogo (precisa de
  // will-prevent-unload no processo principal), então lá não registra.
  useEffect(() => {
    if (!temPendencias || window.electronAPI) return;
    const aoSair = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", aoSair);
    return () => window.removeEventListener("beforeunload", aoSair);
  }, [temPendencias]);

  // Menu lateral: o app usa HashRouter (sem useBlocker), então intercepta o
  // clique na fase de captura, antes do NavLink/onClick navegar. Pega
  // links/botões da <nav> (menos o recolher/expandir) e os links do popover
  // do menu recolhido. Cancelou → o clique não chega ao React.
  useEffect(() => {
    if (!temPendencias) return;
    const aoClicar = (e) => {
      const alvo = e.target.closest?.("a, button, [role='button']");
      if (!alvo || paginaRef.current?.contains(alvo)) return;
      const noMenu =
        (alvo.closest("nav") && !/menu/i.test(alvo.getAttribute("aria-label") || "")) ||
        (alvo.tagName === "A" && alvo.closest("[class*='tooltipMenu']"));
      if (!noMenu) return;
      if (!window.confirm(MSG_SAIR_SEM_SALVAR)) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    document.addEventListener("click", aoClicar, true);
    return () => document.removeEventListener("click", aoClicar, true);
  }, [temPendencias]);

  // ── Totais do cabeçalho ───────────────────────────────────────────────────────
  // Sem pendência: os calculados no backend (pedido.totais, S1). Com
  // pendência: prévia local com as linhas pendentes e o formulário (mesma
  // conta do recalcular_pedido) — o definitivo volta ao salvar.
  const totaisCabecalho = (() => {
    if (!pedido) return null;
    if (!temPendencias && pedido.totais) return { ...pedido.totais, previa: false };
    const n = (v) => Number(v) || 0;
    const ativas = linhasAtuais.filter((l) => !l.removido);
    return {
      qtd_total: ativas.reduce((acc, l) => acc + n(l.quantidade), 0),
      valor_mercadoria: ativas.reduce((acc, l) => acc + n(l.quantidade) * n(l.preco_unitario), 0),
      comissao_valor: (subtotalItens * n(pedido.comissao_pct)) / 100,
      valor_total:
        subtotalItens -
        n(headerForm?.desconto_geral_valor) +
        n(headerForm?.acrescimo_valor) +
        n(headerForm?.valor_frete) +
        n(headerForm?.valor_seguro) +
        n(headerForm?.valor_despesas),
      previa: true,
    };
  })();

  // ── Prévia de parcelas — cálculo só no backend, debounce 300ms ────────────
  // Manda o que ainda não foi salvo: condição e 1º vencimento do formulário
  // e, com pendências, o total local (para a prévia bater com a tela).
  // Total que a tela mostra agora (com pendências) — decide se há valor.
  const totalAtual = Math.round((Number(totaisCabecalho?.valor_total) || 0) * 100) / 100;
  const totalPrevia = totaisCabecalho?.previa ? totalAtual : null;
  const seqPreviewParcelas = useRef(0);
  useEffect(() => {
    if (!headerForm || !pedido) return;
    clearTimeout(previewParcelasTimer.current);
    const seq = ++seqPreviewParcelas.current;

    if (!condicaoPagamentoSel || !(totalAtual > 0)) {
      setPreviewParcelas(null);
      setPreviewParcelasErro(null);
      setPreviewParcelasLoading(false);
      return;
    }

    setPreviewParcelasLoading(true);
    previewParcelasTimer.current = setTimeout(async () => {
      try {
        const lista = await getParcelasPreviewPedidoVenda(pedido.id, {
          primeiroVencimento: headerForm.primeiro_vencimento || "",
          total: totalPrevia,
          condicaoPagamentoId: headerForm.condicao_pagamento_id,
        });
        if (seq !== seqPreviewParcelas.current) return;
        setPreviewParcelas(lista || []);
        setPreviewParcelasErro(null);
      } catch (e) {
        if (seq !== seqPreviewParcelas.current) return;
        console.error("Prévia de parcelas:", e);
        setPreviewParcelas(null);
        setPreviewParcelasErro(e.message || "Erro ao calcular as parcelas.");
      } finally {
        if (seq === seqPreviewParcelas.current) setPreviewParcelasLoading(false);
      }
    }, 300);
    return () => clearTimeout(previewParcelasTimer.current);
    // condicaoPagamentoSel?.id: a lista de condições pode chegar depois do
    // pedido — sem ela aqui a prévia não rodava de novo e ficava vazia.
  }, [
    pedido?.id,
    headerForm?.condicao_pagamento_id,
    condicaoPagamentoSel?.id,
    headerForm?.primeiro_vencimento,
    totalAtual,
    totalPrevia,
    pedido?.data_emissao,
  ]);

  // Popover "N parcelas" (abaixo do VALOR TOTAL): fecha no clique fora ou Esc.
  const [parcelasAbertas, setParcelasAbertas] = useState(false);
  const parcelasRef = useRef(null);
  useEffect(() => {
    if (!parcelasAbertas) return;
    const fora = (e) => {
      if (!parcelasRef.current?.contains(e.target)) setParcelasAbertas(false);
    };
    const esc = (e) => e.key === "Escape" && setParcelasAbertas(false);
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", fora);
      document.removeEventListener("keydown", esc);
    };
  }, [parcelasAbertas]);

  // Desconto geral: o campo digitado manda; no blur/Enter recalcula o par
  // % ↔ R$ sobre o subtotal dos itens (com as pendências). Fica pendente
  // até "Salvar Pedido" — mesma regra de antes, sem o botão Aplicar.
  const aplicarDescontoGeral = (origem, numero) =>
    setHeaderForm((f) => {
      if (origem === "pct") {
        const pct = Math.min(Math.max(numero, 0), 100);
        const valor = subtotalItens > 0 ? (subtotalItens * pct) / 100 : 0;
        return { ...f, desconto_geral_pct: pct.toFixed(2), desconto_geral_valor: valor.toFixed(2) };
      }
      const valor = Math.max(numero, 0);
      const pct = subtotalItens > 0 ? (valor / subtotalItens) * 100 : 0;
      return { ...f, desconto_geral_valor: valor.toFixed(2), desconto_geral_pct: pct.toFixed(2) };
    });

  // Parcelas (abaixo do VALOR TOTAL): textos curtos, sem corte. Com lista,
  // link "N parcelas" que abre o popover; senão o estado em texto muted
  // (o erro vai no tooltip). "Sem valor" usa o total atual (com pendências).
  const parcelasInfo = !condicaoPagamentoSel
    ? { texto: "Sem condição" }
    : !(totalAtual > 0)
      ? { texto: "Sem valor" }
      : previewParcelasErro
        ? { texto: "Parcelas indisponíveis", tooltip: previewParcelasErro }
        : previewParcelas?.length
          ? {
              lista: previewParcelas,
              texto:
                previewParcelas.length === 1 ? "1 parcela" : `${previewParcelas.length} parcelas`,
            }
          : previewParcelasLoading || previewParcelas === null
            ? { texto: "Calculando…" }
            : { texto: "Sem valor" };

  const voltar = () => {
    if (temPendencias) setConfirmSair(true);
    else navigate("/vendas/pedidos");
  };

  // Fechar Pedido / PDFs usam o que está gravado — com pendências, bloqueia.
  const semPendencias = (acao) => () => {
    if (temPendencias) {
      setStatusErro(MSG_SALVE_ANTES);
      return;
    }
    setStatusErro(null);
    acao();
  };

  // ── Formulário de Pedido (relVen001) ──────────────────────────────────────────
  // Impressão via api/relatorios (Electron: PDF; navegador: aba + print).
  // Sem variante, o backend usa o padrão do config.json.
  const imprimirPedido = async (variante = null) => {
    if (gerandoRelatorio) return;
    setGerandoRelatorio(true);
    setStatusErro(null);
    try {
      await imprimirRelatorio(RELATORIO_PEDIDO_VENDA, id, variante);
    } catch (e) {
      setStatusErro(e.message);
    } finally {
      setGerandoRelatorio(false);
    }
  };

  // ── NF-e ──────────────────────────────────────────────────────────────────────
  const abrirNfeModal = () => {
    setNfeModal({
      serie: "001",
      data_emissao: hojeISO(),
      data_saida: hojeISO(),
      hora_saida: agoraHora(),
    });
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

  // ── Ordem de Corte ──────────────────────────────────────────────────────────
  // Corte sempre por pedido: sem OC ativa → gera e abre o assistente; com OC
  // → leva à tela da OC (RASCUNHO também pode continuar no assistente).
  const gerarOrdemCorte = async () => {
    if (gerandoOC) return;
    setGerandoOC(true);
    try {
      const oc = await criarOrdemCorte(id);
      setOrdemCorte(oc);
      setAssistenteOcId(oc.id);
    } catch (e) {
      setStatusErro(e.message);
      if (e.status === 409) recarregarOrdemCorte();
    } finally {
      setGerandoOC(false);
    }
  };

  const acoesOrdemCorte = [];
  if (podeVerOC && ordemCorte) {
    acoesOrdemCorte.push({
      label: `Ver Ordem de Corte ${ordemCorte.numero_fmt}`,
      onClick: semPendencias(() => navigate(`/producao/ordens-corte/${ordemCorte.id}`)),
    });
    if (podeCriarOC && ordemCorte.status === "RASCUNHO") {
      acoesOrdemCorte.push({
        label: "Continuar Ordem de Corte",
        onClick: semPendencias(() => setAssistenteOcId(ordemCorte.id)),
      });
    }
  } else if (podeCriarOC && pedido && pedido.status !== "Cancelado") {
    acoesOrdemCorte.push({
      label: gerandoOC ? "Gerando…" : "Gerar Ordem de Corte",
      disabled: gerandoOC,
      onClick: semPendencias(gerarOrdemCorte),
    });
  }

  // Menu "⋯": Ordem de Corte; Cancelar (Aberto, abre a confirmação atual);
  // pedido Fechado sem NF-e mantém Reabrir e Emitir Nota Fiscal aqui.
  const acoesMais = [...acoesOrdemCorte];
  if (podeEditar && pedido?.status === "Fechado" && pedido.nfe_id == null) {
    acoesMais.push(
      {
        label: "Reabrir Pedido",
        onClick: () => handleMudarStatus("Aberto"),
        disabled: statusLoading,
      },
      { label: "Emitir Nota Fiscal", onClick: abrirNfeModal }
    );
  }
  if (podeExcluir && !somenteLeitura) {
    acoesMais.push({
      label: "Cancelar Pedido",
      danger: true,
      onClick: () => setCancelarConfirm(true),
      disabled: statusLoading,
    });
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  if (loading)
    return (
      <div className="sc-page">
        <p className={styles.stateMsg}>Carregando…</p>
      </div>
    );
  if (!pedido || !headerForm)
    return (
      <div className="sc-page">
        <button className={styles.btnBack} onClick={() => navigate("/vendas/pedidos")}>
          Voltar
        </button>
        <p className={styles.stateMsg}>Pedido não encontrado.</p>
      </div>
    );

  return (
    <div className={`sc-page ${styles.pagina}`} ref={paginaRef}>
      <ConfirmModal
        isOpen={confirmSair}
        titulo="Alterações não salvas"
        mensagem={MSG_SAIR_SEM_SALVAR}
        labelConfirmar="Sair sem salvar"
        onConfirmar={() => {
          setConfirmSair(false);
          navigate("/vendas/pedidos");
        }}
        onCancelar={() => setConfirmSair(false)}
      />

      {cadastroClienteId != null && (
        <ClienteFormModal
          clienteId={cadastroClienteId}
          somenteLeitura={cadastroSomenteLeitura}
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
        onConfirmar={() => {
          if (!aplicandoTabela) confirmarAplicarTabela();
        }}
        onCancelar={() => {
          if (!aplicandoTabela) setConfirmTabela(null);
        }}
      />

      {/* Área densa (.sc-compact) — só o conteúdo da página; os modais acima
          e abaixo (cadastro do cliente, confirmações) ficam no padrão. */}
      <div className={`sc-compact ${styles.compacto}`}>
        {/* ── Barra do topo: identificação à esquerda, ações à direita ── */}
        <header className={styles.faixa}>
          <div className={styles.faixaEsq}>
            {/* Mesma proteção do antigo "Voltar" (confirma com pendência). */}
            <button type="button" className={styles.linkVoltar} onClick={voltar}>
              ← Pedidos de Venda
            </button>
            <div className={styles.identificacao}>
              <h1 className={styles.titulo}>Pedido {pedido.numero}</h1>
              <span
                className={`${styles.statusBadge} ${styles[STATUS_CLS[pedido.status] || "stAberto"]}`}
              >
                {STATUS_LABELS[pedido.status] || pedido.status}
              </span>
              {/* Pílula neutra: forma do status, cores de fundo/borda do tema. */}
              {modoVisualizar && (
                <span
                  className={styles.statusBadge}
                  style={{
                    background: "var(--sc-bg-secondary)",
                    borderColor: "var(--sc-border)",
                    color: "var(--sc-text-secondary)",
                  }}
                >
                  Visualização
                </span>
              )}
              {temPendencias ? (
                <span className={styles.pendente}>Alterações não salvas</span>
              ) : headerSalvo ? (
                <span className={styles.msgSalvo}>Alterações salvas.</span>
              ) : null}
            </div>
          </div>

          {/* Imprimir ▾ | Salvar | Fechar | ⋯ — Salvar/Fechar só em Aberto. */}
          <div className={styles.actionBar}>
            <MenuDropdown
              className={styles.btnHeaderSecondary}
              trigger={
                <>
                  Imprimir
                  <IconeChevron />
                </>
              }
              items={[
                {
                  // Formulário de corte = relPro001 da OC ativa do pedido.
                  label: "Formulário de Corte",
                  onClick: semPendencias(() => {
                    if (!ordemCorte) {
                      setStatusErro("Gere a Ordem de Corte primeiro.");
                      return;
                    }
                    imprimirRelatorio(RELATORIO_FORMULARIO_CORTE, ordemCorte.id).catch((e) =>
                      setStatusErro(e.message)
                    );
                  }),
                },
                {
                  label: gerandoRelatorio ? "Gerando…" : "Formulário de Pedido",
                  disabled: gerandoRelatorio,
                  onClick: semPendencias(() => imprimirPedido()),
                },
                // Mais de um modelo na pasta: escolha do arquivo num seletor.
                ...(modelosPedido.length > 1
                  ? [
                      {
                        label: "Outros modelos…",
                        disabled: gerandoRelatorio,
                        onClick: semPendencias(() => setSeletorModelos(true)),
                      },
                    ]
                  : []),
              ]}
            />
            {modoVisualizar && podeEditar && pedido.status === "Aberto" && (
              <button
                type="button"
                className={styles.btnHeaderSecondary}
                onClick={sairVisualizacao}
              >
                Editar
              </button>
            )}
            {/* Salvar Pedido: primário só com pendência; sem pendência fica
                neutro e desabilitado. */}
            {editavel && (
              <button
                type="button"
                className={temPendencias ? styles.btnHeaderPrimario : styles.btnHeaderSecondary}
                onClick={handleSalvarPedido}
                disabled={savingHeader || !temPendencias}
              >
                {savingHeader ? "Salvando…" : "Salvar Pedido"}
              </button>
            )}
            {editavel && (
              <button
                type="button"
                className={styles.btnHeaderSecondary}
                onClick={semPendencias(() => handleMudarStatus("Fechado"))}
                disabled={statusLoading}
              >
                Fechar Pedido
              </button>
            )}
            {acoesMais.length > 0 && (
              <MenuDropdown
                className={`${styles.btnHeaderSecondary} ${styles.btnHeaderIcone}`}
                ariaLabel="Mais ações"
                title="Mais ações"
                trigger={<IconeMais />}
                items={acoesMais}
              />
            )}
          </div>
        </header>

        {statusErro && <p className={styles.erroInline}>{statusErro}</p>}
        {erroHeader && <p className={styles.erroInline}>{erroHeader}</p>}

        {semPrecoTabela && (
          <div className={`${styles.avisoWarn} ${styles.avisoLinha}`}>
            <span>
              Sem preço na tabela aplicada — mantiveram o preço anterior:{" "}
              <strong>{semPrecoTabela.join(", ")}</strong>
            </span>
            <button
              type="button"
              className={styles.btnClose}
              onClick={() => setSemPrecoTabela(null)}
              aria-label="Fechar aviso"
            >
              ×
            </button>
          </div>
        )}

        {/* ══ CARD — Cabeçalho do pedido: abas no topo, grid de 12 colunas ══ */}
        <section className={`sc-card ${styles.headerCard}`} aria-label="Cabeçalho do pedido">
          <div className={styles.tabBar} role="tablist">
            {ABAS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={aba === t.id}
                className={`${styles.tabBtn} ${aba === t.id ? styles.tabBtnActive : ""}`}
                onClick={() => {
                  setAba(t.id);
                  setParcelasAbertas(false);
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Aba Dados (com os totais): grid de 12 colunas (.sc-grid-12) —
              todo campo começa e termina numa linha-guia. Transporte/Outros
              seguem em linhas flex com a escala --sc-field-*. As abas ficam
              empilhadas na mesma célula: a altura do card é a da aba Dados
              em qualquer aba, e o card de itens não se move. */}
          <div className={styles.cardCorpo}>
            {/* ══ ABA DADOS ══ */}
            {/* Sempre montada: oculta (visibility) nas outras abas, ela segura
                a altura do card — ver .painel no CSS. */}
            <div
              className={`${styles.painel} ${aba === "dados" ? "" : styles.painelOculto}`}
              aria-hidden={aba !== "dados"}
            >
              <div className="sc-grid-12">
                {/* Linha 1 — div, não label: o campo tem dois inputs e botões */}
                <div className={`${styles.field} ${styles.campoCliente} sc-col-9`}>
                  <span className={styles.rotulo}>Cliente</span>
                  <ClienteInput
                    cliente={headerForm.cliente}
                    readOnly={!editavel}
                    onChange={handleTrocarCliente}
                    onVerCadastro={
                      !somenteLeitura && hasPermission("cadastros_clientes", "ver")
                        ? verCadastroCliente
                        : null
                    }
                  />
                </div>
                <label className={`${styles.field} sc-col-3`}>
                  <span className={styles.rotulo}>Emissão</span>
                  <input
                    className={`${styles.input} sc-readonly`}
                    value={dataBR(headerForm.data_emissao)}
                    readOnly
                    tabIndex={-1}
                  />
                </label>

                {/* Linha 2 */}
                <label className={`${styles.field} ${styles.inicioLinha} sc-col-3`}>
                  <span className={styles.rotulo}>Condição pgto</span>
                  <select
                    className={styles.input}
                    disabled={!editavel}
                    value={headerForm.condicao_pagamento_id}
                    onChange={(e) =>
                      setHeaderForm((f) => ({ ...f, condicao_pagamento_id: e.target.value }))
                    }
                    title={
                      condicaoPagamentoSel
                        ? `${condicaoPagamentoSel.codigo} — ${condicaoPagamentoSel.descricao}`
                        : undefined
                    }
                  >
                    <option value="">Nenhuma</option>
                    {condicoesPagamento.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.codigo} — {c.descricao}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={`${styles.field} sc-col-2`}>
                  <span className={styles.rotulo}>1º vencimento</span>
                  <input
                    type="date"
                    className={styles.input}
                    disabled={!editavel || condicaoPagamentoSel?.tipo !== "intervalo"}
                    value={headerForm.primeiro_vencimento}
                    onChange={setH("primeiro_vencimento")}
                    // Data apagada só em parte (ex.: "dd/10/2026"): o valor já
                    // é "" mas o navegador segue mostrando o resto — e como o
                    // estado também é "", o React não limpa. Zera de vez.
                    onBlur={(e) => {
                      if (e.target.validity.badInput) {
                        e.target.value = "";
                        setHeaderForm((f) => ({ ...f, primeiro_vencimento: "" }));
                      }
                    }}
                  />
                </label>
                <label className={`${styles.field} sc-col-2`}>
                  <span className={styles.rotulo} title="Prazo de entrega (dias)">
                    Prazo (dias)
                  </span>
                  <input
                    type="number"
                    min="0"
                    className={`${styles.input} ${styles.num}`}
                    disabled={!editavel}
                    value={headerForm.prazo_entrega_dias}
                    onChange={setH("prazo_entrega_dias")}
                  />
                </label>
                {/* TES por código (valida no blur/Enter, lupa/F2 abre a busca);
                    descrição no tooltip. Vai para o pedido com "Salvar Pedido". */}
                <div className={`${styles.field} ${styles.campoTes} sc-col-2`}>
                  <span className={styles.rotulo}>TES</span>
                  <TesInput
                    variant="code"
                    tesId={headerForm.tes_id ? Number(headerForm.tes_id) : null}
                    tesList={tesList}
                    readOnly={!editavel}
                    onChange={(tes) => setHeaderForm((f) => ({ ...f, tes_id: tes.id }))}
                  />
                </div>
                <label className={`${styles.field} sc-col-3`}>
                  <span className={styles.rotulo}>Indicador presença</span>
                  <select
                    className={`${styles.input} ${styles.semCaixaAlta}`}
                    disabled={!editavel}
                    value={headerForm.indicador_presenca}
                    onChange={setH("indicador_presenca")}
                    title={
                      INDICADOR_PRESENCA_OPCOES.find(
                        (o) => o.value === headerForm.indicador_presenca
                      )?.completo
                    }
                  >
                    {INDICADOR_PRESENCA_OPCOES.map((o) => (
                      <option key={o.value} value={o.value} title={o.completo}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>

                {/* Linha 3 (termina na coluna 9) */}
                <label className={`${styles.field} ${styles.inicioLinha} sc-col-3`}>
                  <span className={styles.rotulo}>Vendedor</span>
                  <select
                    className={styles.input}
                    disabled={!editavel}
                    value={headerForm.vendedor_id}
                    onChange={(e) => {
                      const vid = e.target.value;
                      setHeaderForm((f) => ({ ...f, vendedor_id: vid }));
                    }}
                  >
                    <option value="">Sem vendedor</option>
                    {vendedores.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.nome}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={`${styles.field} sc-col-2`}>
                  <span className={styles.rotulo}>Tabela de preço</span>
                  <select
                    className={styles.input}
                    disabled={!editavel || aplicandoTabela}
                    value={headerForm.tabela_preco_id}
                    onChange={handleTrocarTabela}
                  >
                    <option value="">Nenhuma</option>
                    {tabelasSelecionaveis.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.nome}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={`${styles.field} sc-col-2`}>
                  {/* Não confundir com Condição pgto (parcelas): este só decide
                      preço à vista/a prazo na tabela (venda_service.get_preco). */}
                  <span className={styles.rotulo}>Preço da tabela</span>
                  <select
                    className={`${styles.input} ${styles.semCaixaAlta}`}
                    disabled={!editavel}
                    value={headerForm.condicoes}
                    onChange={setH("condicoes")}
                  >
                    <option value="avista">À vista</option>
                    <option value="aprazo">A prazo</option>
                  </select>
                </label>
                <label className={`${styles.field} sc-col-2`}>
                  <span className={styles.rotulo}>Comissão %</span>
                  <input
                    className={`${styles.input} ${styles.num} sc-readonly ${pedido.vendedor_id && pedido.comissao_origem === "NENHUMA" ? styles.inputAlerta : ""}`}
                    value={comissaoPctStr || "—"}
                    title={comissaoTooltip}
                    readOnly
                    tabIndex={-1}
                  />
                </label>
              </div>

              {/* ── Totais: só na aba Dados ── */}
              <div
                className={`sc-grid-12 ${styles.totais}`}
                title={totaisCabecalho.previa ? "Prévia com as alterações não salvas" : undefined}
              >
                <label className={`${styles.field} sc-col-2`}>
                  <span className={styles.rotulo}>Qtd. total</span>
                  <input
                    className={`${styles.input} ${styles.num} sc-readonly`}
                    value={numeroBR(totaisCabecalho.qtd_total, 0)}
                    readOnly
                    tabIndex={-1}
                  />
                </label>
                <label className={`${styles.field} sc-col-2`}>
                  <span className={styles.rotulo}>Valor mercadoria</span>
                  <input
                    className={`${styles.input} ${styles.num} sc-readonly`}
                    value={moeda(totaisCabecalho.valor_mercadoria)}
                    readOnly
                    tabIndex={-1}
                  />
                </label>
                {/* Desconto geral: "0,00" / "R$ 0,00" fora do foco; no blur/Enter
                  recalcula o par % ↔ R$ sobre o subtotal dos itens (pendente
                  até "Salvar Pedido"). */}
                <label className={`${styles.field} sc-col-2`}>
                  <span className={styles.rotulo}>Desc. geral %</span>
                  <CampoNumero
                    className={`${styles.input} ${styles.num}`}
                    disabled={!editavel}
                    valor={headerForm.desconto_geral_pct}
                    onConfirmar={(n) => aplicarDescontoGeral("pct", n)}
                  />
                </label>
                <label className={`${styles.field} sc-col-2`}>
                  <span className={styles.rotulo}>Desc. geral R$</span>
                  <CampoNumero
                    className={`${styles.input} ${styles.num}`}
                    disabled={!editavel}
                    prefixo="R$ "
                    valor={headerForm.desconto_geral_valor}
                    onConfirmar={(n) => aplicarDescontoGeral("valor", n)}
                  />
                </label>
                <label className={`${styles.field} sc-col-2`}>
                  <span className={styles.rotulo}>Valor comissão</span>
                  <input
                    className={`${styles.input} ${styles.num} sc-readonly`}
                    value={pedido.vendedor_id ? moeda(totaisCabecalho.comissao_valor) : "—"}
                    title={comissaoTooltip}
                    readOnly
                    tabIndex={-1}
                  />
                </label>
                {/* div: o label do valor + o link de parcelas (popover) abaixo. */}
                <div className={`${styles.field} sc-col-2`} ref={parcelasRef}>
                  <label className={styles.field}>
                    <span className={styles.rotulo}>Valor total</span>
                    <input
                      className={`${styles.input} ${styles.num} sc-readonly ${styles.valorTotal}`}
                      value={moeda(totaisCabecalho.valor_total)}
                      readOnly
                      tabIndex={-1}
                    />
                  </label>
                  <div className={styles.parcelas}>
                    {parcelasInfo.lista ? (
                      <button
                        type="button"
                        className={styles.linkParcelas}
                        aria-expanded={parcelasAbertas}
                        onClick={() => setParcelasAbertas((a) => !a)}
                      >
                        {parcelasInfo.texto}
                      </button>
                    ) : (
                      <span className={styles.parcelasMotivo} title={parcelasInfo.tooltip}>
                        {parcelasInfo.texto}
                      </span>
                    )}
                    {parcelasAbertas && parcelasInfo.lista && (
                      <div className={styles.parcelasPopover} role="dialog" aria-label="Parcelas">
                        <ul className={styles.parcelasLista}>
                          {parcelasInfo.lista.map((p) => (
                            <li key={p.numero}>
                              <span>
                                {p.numero}/{p.total_parcelas}
                              </span>
                              <span>{dataBR(p.vencimento)}</span>
                              <span className={styles.parcelaValor}>{moeda(p.valor)}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* ══ ABA TRANSPORTE ══ */}
            {aba === "transporte" && (
              <div className={`${styles.linhas} ${styles.painel}`}>
                <div className={styles.linha}>
                  <label className={`${styles.field} sc-field-l`}>
                    <span className={styles.rotulo}>Tipo de frete</span>
                    <select
                      className={styles.input}
                      disabled={!editavel}
                      value={headerForm.tipo_frete}
                      onChange={setH("tipo_frete")}
                    >
                      <option value="">Selecionar</option>
                      {TIPO_FRETE_OPCOES.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className={`${styles.field} sc-field-xl`}>
                    <span className={styles.rotulo}>Transportadora</span>
                    <select
                      className={styles.input}
                      disabled={!editavel}
                      value={headerForm.transportadora_id}
                      onChange={setH("transportadora_id")}
                    >
                      <option value="">Nenhuma</option>
                      {transportadoras.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.nome}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className={`${styles.field} sc-field-m`}>
                    <span className={styles.rotulo}>Valor frete (R$)</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className={`${styles.input} ${styles.num}`}
                      disabled={!editavel}
                      value={headerForm.valor_frete}
                      onChange={setH("valor_frete")}
                    />
                  </label>
                  <label className={`${styles.field} sc-field-m`}>
                    <span className={styles.rotulo}>Valor seguro (R$)</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className={`${styles.input} ${styles.num}`}
                      disabled={!editavel}
                      value={headerForm.valor_seguro}
                      onChange={setH("valor_seguro")}
                    />
                  </label>
                  <label className={`${styles.field} sc-field-m`}>
                    <span className={styles.rotulo}>Valor despesas (R$)</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className={`${styles.input} ${styles.num}`}
                      disabled={!editavel}
                      value={headerForm.valor_despesas}
                      onChange={setH("valor_despesas")}
                    />
                  </label>
                </div>
                <div className={styles.linha}>
                  <label className={`${styles.field} sc-field-s`}>
                    <span className={styles.rotulo}>Peso bruto (kg)</span>
                    <input
                      type="number"
                      step="0.001"
                      min="0"
                      className={`${styles.input} ${styles.num}`}
                      disabled={!editavel}
                      value={headerForm.peso_bruto}
                      onChange={setH("peso_bruto")}
                    />
                  </label>
                  <label className={`${styles.field} sc-field-s`}>
                    <span className={styles.rotulo}>Peso líquido (kg)</span>
                    <input
                      type="number"
                      step="0.001"
                      min="0"
                      className={`${styles.input} ${styles.num}`}
                      disabled={!editavel}
                      value={headerForm.peso_liquido}
                      onChange={setH("peso_liquido")}
                    />
                  </label>
                  <label className={`${styles.field} sc-field-xs`}>
                    <span className={styles.rotulo}>Volumes</span>
                    <input
                      type="number"
                      step="1"
                      min="0"
                      className={`${styles.input} ${styles.num}`}
                      disabled={!editavel}
                      value={headerForm.qtd_volumes}
                      onChange={setH("qtd_volumes")}
                    />
                  </label>
                  <label className={`${styles.field} sc-field-m`}>
                    <span className={styles.rotulo}>Espécie volumes</span>
                    <input
                      className={`${styles.input} sc-upper`}
                      disabled={!editavel}
                      value={headerForm.especie_volumes}
                      onChange={setHUpper("especie_volumes")}
                      placeholder="EX: CAIXA, FARDO"
                    />
                  </label>
                  <label className={`${styles.field} sc-field-s`}>
                    <span className={styles.rotulo}>Placa</span>
                    <input
                      className={`${styles.input} sc-upper`}
                      disabled={!editavel}
                      value={headerForm.placa_veiculo}
                      onChange={setHUpper("placa_veiculo")}
                      maxLength={10}
                    />
                  </label>
                  <label className={`${styles.field} sc-field-xs`}>
                    <span className={styles.rotulo}>UF</span>
                    <input
                      className={`${styles.input} sc-upper`}
                      disabled={!editavel}
                      value={headerForm.uf_veiculo}
                      onChange={setHUpper("uf_veiculo")}
                      maxLength={2}
                    />
                  </label>
                </div>
              </div>
            )}

            {/* ══ ABA OUTROS ══ */}
            {aba === "outros" && (
              <div className={`${styles.linhas} ${styles.painel}`}>
                <div className={styles.linha}>
                  <label className={`${styles.field} sc-field-flex`}>
                    <span className={styles.rotulo}>Informações adicionais da nota</span>
                    <textarea
                      className={`${styles.input} ${styles.textarea} sc-upper`}
                      disabled={!editavel}
                      rows={3}
                      value={headerForm.informacoes_adicionais}
                      onChange={setHUpper("informacoes_adicionais")}
                      placeholder="VAI PARA O XML DA NF-E"
                    />
                  </label>
                  <label className={`${styles.field} sc-field-flex`}>
                    <span className={styles.rotulo}>Observações internas</span>
                    <textarea
                      className={`${styles.input} ${styles.textarea} sc-upper`}
                      disabled={!editavel}
                      rows={3}
                      value={headerForm.observacoes_internas}
                      onChange={setHUpper("observacoes_internas")}
                      placeholder="USO INTERNO — NÃO VAI PARA A NF-E"
                    />
                  </label>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ══ CARD — Itens do pedido: ocupa o resto da altura, só a lista rola ══ */}
        <div className={styles.itensArea}>
          <ItensPedidoCard
            pedido={pedido}
            pendentes={pendentes}
            setPendentes={setPendentes}
            errosItens={errosItens}
            setErrosItens={setErrosItens}
            onItensSalvos={handleItensSalvos}
            onRecarregarPedido={recarregarPedido}
            tesList={tesList}
            tesPadraoId={headerForm.tes_id}
            podeEditar={podeEditar}
            readOnly={somenteLeitura}
          />
        </div>
      </div>

      {/* ══ MODAL — Outros modelos do Formulário de Pedido ══ */}
      {seletorModelos && (
        <div className={styles.overlay} {...seletorModelosOverlay}>
          <div
            className={styles.modalSm}
            role="dialog"
            aria-label="Outros modelos"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className={styles.modalTitle} style={{ marginBottom: "0.75rem" }}>
              Formulário de Pedido
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {modelosPedido.map((m) => (
                <button
                  key={m.arquivo}
                  type="button"
                  className={styles.btnSecondary}
                  style={{ textAlign: "left" }}
                  onClick={() => {
                    setSeletorModelos(false);
                    imprimirPedido(m.arquivo);
                  }}
                >
                  {m.arquivo}
                  {m.padrao ? " (padrão)" : ""}
                </button>
              ))}
            </div>
            <div
              className={styles.modalActions}
              style={{ padding: "1.25rem 0 0", marginTop: "1.25rem" }}
            >
              <button className={styles.btnSecondary} onClick={() => setSeletorModelos(false)}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Cancelar pedido ══ */}
      {cancelarConfirm && (
        <div className={styles.overlay} {...cancelarConfirmOverlay}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle} style={{ marginBottom: "0.75rem" }}>
              Cancelar pedido?
            </h2>
            <p className={styles.confirmText}>
              O pedido <strong>{pedido.numero}</strong> será marcado como Cancelado. Esta ação não
              pode ser desfeita.
            </p>
            {statusErro && <p className={styles.erro}>{statusErro}</p>}
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setCancelarConfirm(false)}>
                Voltar
              </button>
              <button
                className={styles.btnDanger}
                onClick={() => handleMudarStatus("Cancelado")}
                disabled={statusLoading}
              >
                {statusLoading ? "Cancelando…" : "Cancelar Pedido"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Emitir Nota Fiscal ══ */}
      {nfeModal && (
        <div className={styles.overlay} {...nfeModalOverlay}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle} style={{ marginBottom: "1rem" }}>
              Emitir Nota Fiscal
            </h2>

            {nfeResultado ? (
              <>
                <p className={styles.aviso}>NF-e emitida com sucesso.</p>
                <p
                  style={{
                    fontSize: "0.8rem",
                    wordBreak: "break-all",
                    color: "var(--sc-text-secondary)",
                  }}
                >
                  Chave de acesso: {nfeResultado.chave_acesso}
                </p>
                <div className={styles.modalActions}>
                  <button className={styles.btnSecondary} onClick={() => setNfeModal(null)}>
                    Fechar
                  </button>
                  <button className={styles.btnPrimary} onClick={() => navigate("/vendas/nfe")}>
                    Ver NF-e
                  </button>
                </div>
              </>
            ) : (
              <>
                <label className={styles.field}>
                  <span>Série</span>
                  <select
                    className={styles.input}
                    value={nfeModal.serie}
                    onChange={(e) => setNfeModal((m) => ({ ...m, serie: e.target.value }))}
                  >
                    {SERIE_NFE_OPCOES.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={styles.field} style={{ marginTop: "0.75rem" }}>
                  <span>Data de Emissão</span>
                  <input
                    type="date"
                    className={styles.input}
                    value={nfeModal.data_emissao}
                    onChange={(e) => setNfeModal((m) => ({ ...m, data_emissao: e.target.value }))}
                  />
                </label>
                <label className={styles.field} style={{ marginTop: "0.75rem" }}>
                  <span>Data de Saída</span>
                  <input
                    type="date"
                    className={styles.input}
                    value={nfeModal.data_saida}
                    onChange={(e) => setNfeModal((m) => ({ ...m, data_saida: e.target.value }))}
                  />
                </label>
                <label className={styles.field} style={{ marginTop: "0.75rem" }}>
                  <span>Hora de Saída</span>
                  <input
                    type="time"
                    className={styles.input}
                    value={nfeModal.hora_saida}
                    onChange={(e) => setNfeModal((m) => ({ ...m, hora_saida: e.target.value }))}
                  />
                </label>
                {nfeMsg && (
                  <p className={styles.erro} style={{ marginTop: "1rem" }}>
                    {nfeMsg}
                  </p>
                )}
                <div className={styles.modalActions}>
                  <button
                    className={styles.btnSecondary}
                    onClick={() => setNfeModal(null)}
                    disabled={nfeSaving}
                  >
                    Cancelar
                  </button>
                  <button
                    className={styles.btnPrimary}
                    onClick={handleConfirmarNfe}
                    disabled={nfeSaving}
                  >
                    {nfeSaving ? "Emitindo…" : "Confirmar"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {assistenteOcId && (
        <OrdemCorteAssistente
          ocId={assistenteOcId}
          onFechar={() => {
            setAssistenteOcId(null);
            recarregarOrdemCorte();
          }}
        />
      )}
    </div>
  );
}
