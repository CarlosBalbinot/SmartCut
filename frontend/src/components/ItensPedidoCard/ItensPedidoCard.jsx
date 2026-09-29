import { useEffect, useLayoutEffect, useState, useRef } from "react";
import ReactDOM from "react-dom";
import { addItensBulkPedidoVenda, salvarItensPedidoVenda } from "../../api/pedidos";
import { produtosApi } from "../../api/produtos";
import useResizableColumns from "../../hooks/useResizableColumns";
import useResizableHeight from "../../hooks/useResizableHeight";
import ProdutoSkuInput from "../ProdutoSkuInput/ProdutoSkuInput";
import TesInput from "../TesInput/TesInput";
import styles from "./ItensPedidoCard.module.css";
import useOverlayDismiss from "../../hooks/useOverlayDismiss";

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

// ── Tabela de itens: colunas redimensionáveis + edição inline ────────────────
// Tabela com width 100% e table-layout fixed: descricao = null é a única
// coluna sem largura (absorve a sobra), então a tabela nunca passa do card.
// Aumentar uma coluna tira da Descrição e para quando ela chega a 160px.
// Fixas somam 694px: em 1366px com menu aberto o card tem ~1077px
// (Descrição ~383px); com escala 125% do Windows (~804px) a Descrição fica
// com ~110px pelos padrões — abaixo do mínimo, mas sem rolagem lateral.
const ITENS_COLUNAS_CHAVE = "sc.pedido.itens.colunas.v7";
const ITENS_COLUNAS_CHAVES_ANTIGAS = [
  "sc.pedido.itens.colunas",
  ...[1, 2, 3, 4, 5, 6].map((v) => `sc.pedido.itens.colunas.v${v}`),
];
const ITENS_COLUNAS_PADRAO = {
  item: 44,
  ref: 120,
  descricao: null,
  qtde: 60,
  punit: 96,
  descPct: 64,
  desc: 88,
  total: 100,
  tes: 90,
  acao: 32,
};
const DESCRICAO_MINIMA = 160;

// Larguras para renderizar: se as salvas (de uma tela mais larga) não
// cabem mais com a Descrição no mínimo, o excesso sai do que cada coluna
// tem acima do padrão. Com os padrões a Descrição apenas encolhe.
function largurasQueCabem(larguras, disponivel) {
  if (!disponivel) return larguras;
  const soma = Object.values(larguras).reduce((acc, w) => acc + (w || 0), 0);
  let excesso = soma + DESCRICAO_MINIMA - disponivel;
  const extras = Object.keys(larguras).map((c) => [
    c,
    Math.max(0, (larguras[c] || 0) - (ITENS_COLUNAS_PADRAO[c] || 0)),
  ]);
  const totalExtra = extras.reduce((acc, [, e]) => acc + e, 0);
  if (excesso <= 0 || totalExtra === 0) return larguras;
  excesso = Math.min(excesso, totalExtra);
  const out = { ...larguras };
  for (const [c, e] of extras) {
    if (e) out[c] = Math.round(larguras[c] - (excesso * e) / totalExtra);
  }
  return out;
}

// Altura da área da tabela (alça na borda inferior do card). Mínimo 280px
// (cabeçalho 28 + 8 linhas de 30); máximo = todas as linhas visíveis;
// padrão = o que sobra da tela abaixo da tabela.
const ITENS_ALTURA_CHAVE = "sc.pedido.itens.altura";
const ITENS_ALTURA_MINIMA = 280;
// Abaixo da tabela: alça (10) + borda do card + padding inferior do .content.
const ITENS_ALTURA_RESERVA = 40;

// Ancestral que rola (o .content do App) — base para medir o espaço livre.
function ancestralRolavel(el) {
  for (let p = el?.parentElement; p; p = p.parentElement) {
    if (/(auto|scroll)/.test(getComputedStyle(p).overflowY)) return p;
  }
  return document.scrollingElement;
}
// fixa: sem handle de redimensionar (Item e ×; a Descrição é a flexível).
const ITENS_COLUNAS = [
  { key: "item", label: "Item", fixa: true },
  { key: "ref", label: "REF" },
  { key: "descricao", label: "Descrição", fixa: true },
  { key: "qtde", label: "Qtde", num: true },
  { key: "punit", label: "P. Unit.", num: true },
  { key: "descPct", label: "Desc. %", num: true },
  { key: "desc", label: "Desc. R$", num: true },
  { key: "total", label: "Total", num: true },
  { key: "tes", label: "TES" },
  { key: "acao", label: "", fixa: true },
];

// Coluna editável → campo do lote (PUT /itens, mesmos nomes do PATCH).
// desconto e desconto_percentual são exclusivos (o backend recusa os dois):
// editar um descarta a pendência do outro.
const CAMPO_LOTE = {
  qtde: "quantidade",
  punit: "preco_unitario",
  descPct: "desconto_percentual",
  desc: "desconto",
};
const DESCONTO_OPOSTO = { desconto: "desconto_percentual", desconto_percentual: "desconto" };

// Campo devolvido no 422 do lote → coluna marcada com erro. O que não é
// coluna editável (item_id, sku_id, sku_codigo…) marca a REF.
const COLUNA_DO_CAMPO = {
  quantidade: "qtde",
  preco_unitario: "punit",
  desconto: "desc",
  desconto_percentual: "descPct",
  tes_codigo: "tes",
  tes_id: "tes",
  descricao: "descricao",
};

// Descrição do item: maiúscula, até 120 (mesmo limite do backend). A do
// cadastro (pai + linha + coluna) é a referência para "personalizada".
const DESCRICAO_MAX = 120;
const descricaoCadastro = (texto) => (texto || "").slice(0, DESCRICAO_MAX);
const mesmoTexto = (a, b) => (a || "").trim().toUpperCase() === (b || "").trim().toUpperCase();

// Preço de prévia do SKU trocado: o resolvido pela tabela do pedido; sem
// preço em lugar nenhum o backend mantém o atual (null aqui).
const precoDoSku = (sku) => {
  const preco = sku.preco_resolvido !== undefined ? sku.preco_resolvido : sku.preco_venda;
  return preco == null ? null : num(preco);
};

const numeroBR = (v, casas) =>
  new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  }).format(Number(v) || 0);

const num = (v) => Number(v) || 0;
const round2 = (v) => Math.round(v * 100) / 100;

// Aceita "1.234,56", "1234,56", "1234.56" e "R$ 12,50". Vírgula presente →
// pontos são milhar; só ponto → decimal se tiver até 2 casas depois dele.
function parseNumeroBR(texto) {
  let t = String(texto ?? "")
    .replace(/R\$/gi, "")
    .replace(/\s/g, "");
  if (!t) return NaN;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  else if ((t.match(/\./g) || []).length > 1 || /\.\d{3,}$/.test(t)) t = t.replace(/\./g, "");
  return /^-?\d*\.?\d+$/.test(t) ? Number(t) : NaN;
}

// ── Estado pendente dos itens (fica na página: "Salvar Pedido" também envia) ──
// alterados: { [item_id]: { quantidade?, preco_unitario?, desconto? | desconto_percentual?,
//                           tes_codigo?, tes_id?, sku_codigo?, descricao?,
//                           _sku? } }
//   _sku (só prévia, não vai no lote): { codigo, descricao, preco } do SKU
//   trocado — o backend resolve preço e descrição de novo ao salvar.
//   descricao "" = voltar para a descrição do cadastro.
// novos:     [{ ref_temp, sku_id, ref_codigo, descricao_cadastro, descricao?,
//               quantidade, preco_unitario, preco_editado, desconto,
//               desconto_percentual?, tes_id, tes_codigo }]
//   descricao só existe quando personalizada.
// removidos: [item_id]
export const PENDENTES_VAZIO = { alterados: {}, novos: [], removidos: [] };

export const contarPendencias = (p) =>
  Object.keys(p.alterados).filter((id) => !p.removidos.includes(id)).length +
  p.novos.length +
  p.removidos.length;

// Corpo do PUT /pedidos-venda/{id}/itens (e do campo "itens" do PUT do pedido).
export function montarLoteItens(p) {
  const campos = (a) => {
    const out = {};
    for (const k of [
      "quantidade",
      "preco_unitario",
      "desconto",
      "desconto_percentual",
      "tes_codigo",
      "sku_codigo",
      "descricao",
    ]) {
      if (a[k] !== undefined) out[k] = a[k];
    }
    return out;
  };
  return {
    criar: p.novos.map((n) => ({
      ref_temp: n.ref_temp,
      sku_id: n.sku_id,
      quantidade: n.quantidade,
      // Sem preço digitado o backend resolve (tabela > SKU > produto pai).
      ...(n.preco_editado ? { preco_unitario: n.preco_unitario } : {}),
      ...(n.desconto_percentual != null
        ? { desconto_percentual: n.desconto_percentual }
        : n.desconto
          ? { desconto: n.desconto }
          : {}),
      ...(n.tes_codigo ? { tes_codigo: n.tes_codigo } : {}),
      ...(n.descricao ? { descricao: n.descricao } : {}),
    })),
    atualizar: Object.entries(p.alterados)
      .filter(([itemId]) => !p.removidos.includes(itemId))
      .map(([itemId, a]) => ({ item_id: itemId, ...campos(a) })),
    remover: p.removidos,
  };
}

// 422 do lote → { "<item_id|ref_temp>|<coluna>": mensagem }.
export function mapearErrosItens(erros) {
  const mapa = {};
  for (const e of erros || []) {
    const chave = String(e.item_id ?? e.ref_temp);
    mapa[`${chave}|${COLUNA_DO_CAMPO[e.campo] || "ref"}`] = e.mensagem;
  }
  return mapa;
}

const valorTotalItem = (item) =>
  num(item.preco_total) - num(item.desconto_valor) + num(item.acrescimo_valor);

// Par desconto R$ / % sobre o bruto — o que foi informado manda, o outro é
// derivado (mesma conta do _aplicar_desconto do backend).
function descontos(bruto, { valor, pct }) {
  if (pct != null) return { valor: round2((bruto * pct) / 100), pct };
  return { valor, pct: bruto ? Math.round((valor / bruto) * 1000000) / 10000 : 0 };
}

/**
 * Linhas da tabela = itens gravados com as edições pendentes aplicadas +
 * itens novos. Total da linha recalculado aqui só como prévia — o valor
 * definitivo vem da resposta ao salvar. Desconto PERCENTUAL sem R$ digitado
 * mantém o % (mesma regra do backend).
 */
export function linhasEfetivas(itens, p) {
  const gravadas = (itens || []).map((i) => {
    const a = p.alterados[i.id];
    // SKU trocado (pendente): descrição do cadastro passa a ser a do novo
    // SKU e a personalizada anterior é descartada.
    const cadastro = a?._sku ? a._sku.descricao : descricaoCadastro(i.descricao_completa);
    const gravada = a?._sku ? cadastro : i.descricao || cadastro;
    const descricao = a?.descricao !== undefined ? a.descricao || cadastro : gravada;
    const base = {
      chave: String(i.id),
      numero_item: i.numero_item,
      novo: false,
      alterado: !!a,
      removido: p.removidos.includes(i.id),
      grupo_id: i.grupo_id,
      ref_codigo: a?._sku ? a._sku.codigo : i.ref_codigo,
      descricao,
      descricao_cadastro: cadastro,
      acrescimo_valor: num(i.acrescimo_valor),
    };
    if (!a) {
      return {
        ...base,
        quantidade: i.quantidade_total,
        preco_unitario: i.preco_unitario,
        preco_manual: i.preco_manual,
        desconto_valor: i.desconto_valor,
        desconto_percentual: num(i.desconto_percentual),
        tes_id: i.tes_id,
        total: valorTotalItem(i),
      };
    }
    const quantidade = a.quantidade ?? num(i.quantidade_total);
    const preco = a.preco_unitario ?? a._sku?.preco ?? num(i.preco_unitario);
    const bruto = quantidade * preco;
    const d =
      a.desconto_percentual !== undefined
        ? descontos(bruto, { pct: a.desconto_percentual })
        : a.desconto !== undefined
          ? descontos(bruto, { valor: a.desconto })
          : i.desconto_tipo === "PERCENTUAL"
            ? descontos(bruto, { pct: num(i.desconto_percentual) })
            : descontos(bruto, { valor: num(i.desconto_valor) });
    return {
      ...base,
      quantidade,
      preco_unitario: preco,
      preco_manual: a.preco_unitario !== undefined ? true : a._sku ? false : i.preco_manual,
      desconto_valor: d.valor,
      desconto_percentual: d.pct,
      tes_id: a.tes_id ?? i.tes_id,
      total: bruto - d.valor + base.acrescimo_valor,
    };
  });
  const novas = p.novos.map((n) => {
    const bruto = n.quantidade * n.preco_unitario;
    const d = descontos(
      bruto,
      n.desconto_percentual != null ? { pct: n.desconto_percentual } : { valor: n.desconto || 0 }
    );
    return {
      chave: String(n.ref_temp),
      numero_item: null,
      novo: true,
      alterado: true,
      removido: false,
      grupo_id: null,
      ref_codigo: n.ref_codigo,
      descricao: n.descricao || n.descricao_cadastro,
      descricao_cadastro: n.descricao_cadastro,
      quantidade: n.quantidade,
      preco_unitario: n.preco_unitario,
      preco_manual: n.preco_editado,
      desconto_valor: d.valor,
      desconto_percentual: d.pct,
      tes_id: n.tes_id,
      acrescimo_valor: 0,
      total: bruto - d.valor,
    };
  });
  return [...gravadas, ...novas];
}

// Soma líquida das linhas não removidas — a página usa para o desconto
// geral (% ↔ R$) e para a prévia dos totais do cabeçalho.
export const subtotalItensPedido = (linhas) =>
  linhas.filter((l) => !l.removido).reduce((acc, l) => acc + l.total, 0);

/**
 * Célula numérica sempre em modo input. Fora do foco mostra o valor
 * formatado (com "R$" quando moeda); no foco, o número cru para edição.
 * Confirma no blur ou Enter (só altera o estado pendente); Esc reverte.
 * erroServidor: motivo do 422 do lote — borda vermelha + tooltip.
 */
function CelulaNumero({
  valor,
  casas,
  moeda: ehMoeda,
  readOnly,
  onSalvar,
  onProximo,
  inputRef,
  marcador,
  erroServidor,
}) {
  const [focado, setFocado] = useState(false);
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState(null);
  const ignorarBlur = useRef(false);

  const formatado = ehMoeda ? moeda(valor) : numeroBR(valor, casas);
  const paraEdicao = () => numeroBR(valor, casas).replace(/\./g, "");
  const exibido = focado || erro ? texto : formatado;

  const salvar = () => {
    const n = parseNumeroBR(texto);
    if (Number.isNaN(n)) {
      setErro("Valor inválido.");
      return false;
    }
    const arredondado = Number(n.toFixed(casas));
    setErro(null);
    if (arredondado !== Number(valor || 0)) onSalvar(arredondado);
    return true;
  };

  const handleFocus = (e) => {
    if (!erro) setTexto(paraEdicao());
    setFocado(true);
    const el = e.target;
    requestAnimationFrame(() => el.select());
  };

  const handleBlur = () => {
    setFocado(false);
    if (ignorarBlur.current) {
      ignorarBlur.current = false;
      return;
    }
    if (!readOnly) salvar();
  };

  const handleKeyDown = (e) => {
    if (readOnly) return;
    if (e.key === "Enter") {
      e.preventDefault();
      if (salvar()) {
        ignorarBlur.current = true;
        onProximo?.();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setTexto(paraEdicao());
      setErro(null);
      ignorarBlur.current = true;
      e.currentTarget.blur();
    }
  };

  const erroExibido = erro || erroServidor;
  return (
    <div className={styles.celulaEdit}>
      {marcador}
      <input
        ref={inputRef}
        className={`${styles.inputCelula} ${erroExibido ? "sc-campo-erro" : ""}`}
        value={exibido}
        readOnly={readOnly}
        tabIndex={readOnly ? -1 : 0}
        inputMode="decimal"
        title={erroExibido || formatado}
        onChange={(e) => setTexto(e.target.value.toUpperCase())}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
      />
      {erro && (
        <div className={styles.celulaErro} title={erro}>
          {erro}
        </div>
      )}
    </div>
  );
}

/**
 * Descrição do item — vale só para este item deste pedido (o cadastro do
 * produto nunca muda). Confirma no blur/Enter; Esc reverte; apagar tudo
 * volta para a descrição do cadastro (onSalvar("")). Diferente do cadastro
 * → ícone discreto com a descrição original no tooltip.
 */
function CelulaDescricao({
  valor,
  cadastro,
  readOnly,
  onSalvar,
  onProximo,
  inputRef,
  erroServidor,
}) {
  const [focado, setFocado] = useState(false);
  const [texto, setTexto] = useState("");
  const ignorarBlur = useRef(false);

  const salvar = () => {
    const t = texto.trim().toUpperCase();
    if (!mesmoTexto(t || cadastro, valor)) onSalvar(t);
  };

  const handleBlur = () => {
    setFocado(false);
    if (ignorarBlur.current) {
      ignorarBlur.current = false;
      return;
    }
    if (!readOnly) salvar();
  };

  const handleKeyDown = (e) => {
    if (readOnly) return;
    if (e.key === "Enter") {
      e.preventDefault();
      salvar();
      ignorarBlur.current = true;
      onProximo?.();
    } else if (e.key === "Escape") {
      e.preventDefault();
      setTexto(valor || "");
      ignorarBlur.current = true;
      e.currentTarget.blur();
    }
  };

  const personalizada = !mesmoTexto(valor, cadastro);
  return (
    <div className={styles.celulaEdit}>
      <input
        ref={inputRef}
        className={`${styles.inputCelula} ${styles.inputTexto} ${personalizada ? styles.inputComMarca : ""} ${erroServidor ? "sc-campo-erro" : ""} sc-upper`}
        value={focado ? texto : valor || ""}
        readOnly={readOnly}
        tabIndex={readOnly ? -1 : 0}
        maxLength={DESCRICAO_MAX}
        title={erroServidor || valor || ""}
        onChange={(e) => setTexto(e.target.value.toUpperCase())}
        onFocus={(e) => {
          setTexto(valor || "");
          setFocado(true);
          const el = e.target;
          requestAnimationFrame(() => el.select());
        }}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
      />
      {personalizada && (
        <span
          className={styles.marcaPersonalizada}
          title={`Descrição personalizada neste pedido.\nCadastro: ${cadastro || "(sem descrição)"}`}
        >
          <svg
            width="11"
            height="11"
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M11 2.5l2.5 2.5L6 12.5 3 13l.5-3z" />
          </svg>
        </span>
      )}
    </div>
  );
}

// ── Modal "Adicionar Item" — 3 passos: busca (pai/avulso) → grade do pai
// → linha simples do avulso. Ver PART 2a do fluxo de itens.
const ITEM_MODAL_VAZIO = {
  step: 1,
  searchQuery: "",
  searchResults: [],
  searching: false,
  produtoPai: null,
  grade: null,
  gradeLoading: false,
  gradeQtds: {},
  avulso: null,
  avulsoForm: null,
};

/**
 * Card "Itens do pedido": edições ficam pendentes (props pendentes /
 * setPendentes, estado da página) até "Salvar Itens" aqui ou "Salvar
 * Pedido" no rodapé da página.
 *
 * errosItens/setErrosItens: erros do 422 do lote (ver mapearErrosItens).
 * onItensSalvos(pedido): lote gravado — a página troca o pedido e limpa as
 * pendências. onRecarregarPedido: busca o pedido de novo sem mexer nas
 * pendências (usado pelo produto avulso, que ainda grava na hora).
 * tesPadraoId: TES do cabeçalho (formulário), sugerido nos itens novos.
 * readOnly: força só leitura (modo visualização), mesmo com o pedido Aberto.
 * Totais ficam no cabeçalho do pedido (página), não aqui.
 */
export default function ItensPedidoCard({
  pedido,
  pendentes,
  setPendentes,
  errosItens,
  setErrosItens,
  onItensSalvos,
  onRecarregarPedido,
  tesList,
  tesPadraoId,
  podeEditar,
  readOnly = false,
}) {
  const fecharItemModalOverlay = useOverlayDismiss(() => fecharItemModal());

  const pedidoId = pedido.id;
  const itens = pedido.itens || [];
  // readOnly: modo visualização da página — sem adicionar/remover/editar;
  // colunas e altura do card continuam ajustáveis.
  const itensEditaveis = podeEditar && !readOnly && pedido.status === "Aberto";

  const [itemModal, setItemModal] = useState(null);
  const [saving, setSaving] = useState(false);
  const [erroItem, setErroItem] = useState(null);
  const [salvandoItens, setSalvandoItens] = useState(false);
  const [erroLote, setErroLote] = useState(null);

  const searchTimer = useRef(null);
  const searchInputRef = useRef(null);
  const [acPos, setAcPos] = useState({ top: 0, left: 0, width: 200 });
  const seqNovo = useRef(0);

  const linhas = linhasEfetivas(itens, pendentes);
  const qtdPendencias = contarPendencias(pendentes);

  // ── Item modal ────────────────────────────────────────────────────────────────
  const abrirItemModal = () => {
    setItemModal({ ...ITEM_MODAL_VAZIO });
    setErroItem(null);
  };

  const fecharItemModal = () => {
    setItemModal(null);
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
          tesId: tesPadraoId || "",
          descontoPct: "0",
        },
      }));
      return;
    }
    setItemModal((m) => ({
      ...m,
      step: 2,
      searchResults: [],
      produtoPai: resultado,
      gradeLoading: true,
      gradeQtds: {},
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
    itemModal?.grade?.skus.find(
      (s) => s.linha_item_id === linhaId && s.coluna_item_id === colunaId
    );

  const setGradeQtd = (linhaId, colunaId, valor) => {
    const key = `${linhaId}-${colunaId}`;
    setItemModal((m) => ({ ...m, gradeQtds: { ...m.gradeQtds, [key]: valor } }));
  };

  const gradeTotais = (() => {
    if (!itemModal?.grade) return { pecas: 0, valor: 0, temSemPreco: false };
    let pecas = 0,
      valor = 0,
      temSemPreco = false;
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

  // Itens da grade entram como pendentes (ref_temp) — gravam no próximo
  // "Salvar Itens"/"Salvar Pedido". O preço aqui é prévia: sem preço
  // digitado, o backend aplica a tabela do pedido ao salvar.
  const handleAdicionarGrade = () => {
    const { grade, produtoPai } = itemModal;
    const tesPadrao = tesPadraoId
      ? tesList.find((t) => String(t.id) === String(tesPadraoId))
      : null;
    const novos = [];
    for (const [key, qtdStr] of Object.entries(itemModal.gradeQtds)) {
      const qtd = parseInt(qtdStr) || 0;
      if (qtd <= 0) continue;
      const [linhaId, colunaId] = key.split("-").map((v) => (v === "null" ? null : Number(v)));
      const sku = skuNaCelula(linhaId, colunaId);
      if (!sku || sku.situacao !== "Ativo") continue;
      const linha = grade.linha_grade.itens.find((i) => i.id === linhaId);
      const coluna = grade.coluna_grade.itens.find((i) => i.id === colunaId);
      seqNovo.current += 1;
      novos.push({
        ref_temp: `novo-${seqNovo.current}`,
        sku_id: sku.id,
        ref_codigo: sku.codigo,
        descricao_cadastro: descricaoCadastro(
          [produtoPai.descricao, linha?.descricao, coluna?.descricao].filter(Boolean).join(" ")
        ),
        quantidade: qtd,
        preco_unitario: num(sku.preco_venda),
        preco_editado: false,
        desconto: 0,
        tes_id: tesPadrao?.id ?? null,
        tes_codigo: tesPadrao?.codigo ?? null,
      });
    }
    if (novos.length === 0) {
      setErroItem("Informe ao menos uma quantidade na grade.");
      return;
    }
    setPendentes((p) => ({ ...p, novos: [...p.novos, ...novos] }));
    setItemModal(null);
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

  // Produto avulso (sem SKU) ainda grava na hora: o lote (PUT /itens) só
  // cria item por SKU. Recarrega só o pedido — as pendências continuam.
  const handleAdicionarAvulso = async () => {
    const { quantidade, precoUnit, tesId, descontoPct } = itemModal.avulsoForm;
    if (!parseInt(quantidade) || parseInt(quantidade) <= 0) {
      setErroItem("Informe uma quantidade válida.");
      return;
    }
    setSaving(true);
    setErroItem(null);
    try {
      await addItensBulkPedidoVenda(pedidoId, [
        {
          produto_id: itemModal.avulso.id,
          sku_id: null,
          quantidade: parseInt(quantidade),
          preco_unitario: parseFloat(precoUnit) || 0,
          tes_id: tesId ? Number(tesId) : null,
          desconto_pct: parseFloat(descontoPct) || 0,
        },
      ]);
      await onRecarregarPedido();
      setItemModal(null);
    } catch (e) {
      setErroItem(e.message);
    } finally {
      setSaving(false);
    }
  };

  // ── Edição pendente ───────────────────────────────────────────────────────────
  const limparErro = (linha, coluna) => {
    const chave = `${linha.chave}|${coluna}`;
    if (errosItens[chave]) {
      setErrosItens((e) => {
        const { [chave]: _, ...resto } = e;
        return resto;
      });
    }
  };

  // Valor igual ao gravado desfaz a pendência do campo (não conta alteração).
  const alterarCampo = (linha, coluna, campos) => {
    limparErro(linha, coluna);
    if (linha.novo) {
      setPendentes((p) => ({
        ...p,
        novos: p.novos.map((n) => (String(n.ref_temp) === linha.chave ? { ...n, ...campos } : n)),
      }));
      return;
    }
    const item = itens.find((i) => String(i.id) === linha.chave);
    setPendentes((p) => {
      const anterior = p.alterados[item.id] || {};
      const gravado = {
        quantidade: num(item.quantidade_total),
        // Com SKU trocado, a referência é o preço que o backend resolveria.
        preco_unitario: anterior._sku?.preco ?? num(item.preco_unitario),
        desconto: num(item.desconto_valor),
        desconto_percentual: num(item.desconto_percentual),
        tes_id: item.tes_id,
      };
      const atual = { ...anterior, ...campos };
      const igual =
        coluna === "tes"
          ? campos.tes_id === gravado.tes_id
          : campos[CAMPO_LOTE[coluna]] === gravado[CAMPO_LOTE[coluna]];
      if (igual) {
        for (const k of Object.keys(campos)) delete atual[k];
      }
      // Campo limpo (undefined = desconto do outro tipo descartado) sai do patch.
      for (const k of Object.keys(atual)) if (atual[k] === undefined) delete atual[k];
      const alterados = { ...p.alterados };
      if (Object.keys(atual).length) alterados[item.id] = atual;
      else delete alterados[item.id];
      return { ...p, alterados };
    });
  };

  const editarNumero = (linha, coluna, valor) => {
    const campo = CAMPO_LOTE[coluna];
    const campos = { [campo]: valor };
    if (linha.novo && coluna === "punit") campos.preco_editado = true;
    // Desconto em R$ e em % são exclusivos: o digitado agora manda.
    if (DESCONTO_OPOSTO[campo]) campos[DESCONTO_OPOSTO[campo]] = undefined;
    alterarCampo(linha, coluna, campos);
  };

  // TesInput já validou o código (GET); o lote revalida pelo tes_codigo.
  const editarTes = (linha, tes) =>
    alterarCampo(linha, "tes", { tes_id: tes.id, tes_codigo: tes.codigo });

  // Grava (ou desfaz) a pendência de um item salvo com uma função que edita
  // a cópia do patch; patch vazio sai de "alterados".
  const editarPatch = (linha, editar) => {
    const item = itens.find((i) => String(i.id) === linha.chave);
    setPendentes((p) => {
      const atual = { ...(p.alterados[item.id] || {}) };
      editar(atual, item);
      const alterados = { ...p.alterados };
      if (Object.keys(atual).length) alterados[item.id] = atual;
      else delete alterados[item.id];
      return { ...p, alterados };
    });
  };

  // REF: ProdutoSkuInput já validou o código (GET com a tabela do pedido).
  // Troca = novo SKU + descrição do cadastro dele (descarta a personalizada)
  // + preço resolvido pela tabela, sem preço manual. Quantidade, TES,
  // desconto e número do item ficam. Voltar ao SKU gravado desfaz a troca.
  const trocarSku = (linha, sku) => {
    limparErro(linha, "ref");
    limparErro(linha, "descricao");
    const preco = precoDoSku(sku);
    if (linha.novo) {
      setPendentes((p) => ({
        ...p,
        novos: p.novos.map((n) => {
          if (String(n.ref_temp) !== linha.chave) return n;
          const { descricao: _, ...resto } = n;
          return {
            ...resto,
            sku_id: sku.id,
            ref_codigo: sku.codigo,
            descricao_cadastro: descricaoCadastro(sku.descricao_completa),
            preco_unitario: preco ?? n.preco_unitario,
            preco_editado: false,
          };
        }),
      }));
      return;
    }
    editarPatch(linha, (a, item) => {
      delete a.descricao;
      delete a.preco_unitario;
      if (mesmoTexto(sku.codigo, item.sku_codigo ?? item.ref_codigo)) {
        delete a.sku_codigo;
        delete a._sku;
      } else {
        a.sku_codigo = sku.codigo;
        a._sku = {
          codigo: sku.codigo,
          descricao: descricaoCadastro(sku.descricao_completa),
          preco,
        };
      }
    });
  };

  // DESCRIÇÃO: só o item (ItemPedido.descricao). texto "" = cadastro.
  const editarDescricao = (linha, texto) => {
    limparErro(linha, "descricao");
    const personalizada = texto && !mesmoTexto(texto, linha.descricao_cadastro) ? texto : undefined;
    if (linha.novo) {
      setPendentes((p) => ({
        ...p,
        novos: p.novos.map((n) =>
          String(n.ref_temp) === linha.chave ? { ...n, descricao: personalizada } : n
        ),
      }));
      return;
    }
    editarPatch(linha, (a, item) => {
      // Com SKU trocado o backend já grava a do cadastro novo; sem troca,
      // a referência é a descrição gravada no item.
      const gravada = a._sku
        ? linha.descricao_cadastro
        : item.descricao || descricaoCadastro(item.descricao_completa);
      if (mesmoTexto(texto || linha.descricao_cadastro, gravada)) delete a.descricao;
      else a.descricao = personalizada ?? "";
    });
  };

  const removerLinha = (linha) => {
    if (linha.novo) {
      setPendentes((p) => ({
        ...p,
        novos: p.novos.filter((n) => String(n.ref_temp) !== linha.chave),
      }));
    } else {
      const item = itens.find((i) => String(i.id) === linha.chave);
      setPendentes((p) => ({ ...p, removidos: [...p.removidos, item.id] }));
    }
  };

  const desfazerRemocao = (linha) =>
    setPendentes((p) => ({
      ...p,
      removidos: p.removidos.filter((id) => String(id) !== linha.chave),
    }));

  const descartar = () => {
    setPendentes(PENDENTES_VAZIO);
    setErrosItens({});
    setErroLote(null);
  };

  const salvarItens = async () => {
    setSalvandoItens(true);
    setErroLote(null);
    try {
      const atualizado = await salvarItensPedidoVenda(pedidoId, montarLoteItens(pendentes));
      setErrosItens({});
      onItensSalvos(atualizado);
    } catch (e) {
      // 422: marca os campos e mantém tudo pendente para corrigir.
      if (e.erros) setErrosItens(mapearErrosItens(e.erros));
      setErroLote(e.message);
    } finally {
      setSalvandoItens(false);
    }
  };

  // ── Tabela de itens ───────────────────────────────────────────────────────────
  // Largura útil da área da tabela (sem a barra vertical) — teto do arraste.
  const [larguraWrap, setLarguraWrap] = useState(null);
  const { larguras, arrastando, iniciarArrasto, restaurar } = useResizableColumns(
    ITENS_COLUNAS_CHAVE,
    ITENS_COLUNAS_PADRAO,
    {},
    {
      chavesAntigas: ITENS_COLUNAS_CHAVES_ANTIGAS,
      // Cresce só até a Descrição ficar com o mínimo (sem rolagem lateral).
      obterMaximo: (coluna, atuais) => {
        if (!larguraWrap) return Infinity;
        const outras = Object.entries(atuais)
          .filter(([c]) => c !== coluna)
          .reduce((acc, [, w]) => acc + (w || 0), 0);
        return larguraWrap - DESCRICAO_MINIMA - outras;
      },
    }
  );
  const camposItemRef = useRef(new Map());

  // ── Altura ajustável da lista ─────────────────────────────────────────────
  const tableWrapRef = useRef(null);
  const tableRef = useRef(null);
  const [alturaConteudo, setAlturaConteudo] = useState(null);
  const [alturaPadrao, setAlturaPadrao] = useState(ITENS_ALTURA_MINIMA);
  const temLinhas = linhas.length > 0;

  useEffect(() => {
    const wrap = tableWrapRef.current;
    if (!wrap) return;
    const medir = () => setLarguraWrap(wrap.clientWidth);
    medir();
    const ro = new ResizeObserver(medir);
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [temLinhas]);

  // Máximo: altura da tabela inteira (+ barra horizontal, se houver).
  useEffect(() => {
    const wrap = tableWrapRef.current;
    const tabela = tableRef.current;
    if (!wrap || !tabela) return;
    const medir = () =>
      setAlturaConteudo(tabela.offsetHeight + (wrap.offsetHeight - wrap.clientHeight));
    medir();
    const ro = new ResizeObserver(medir);
    ro.observe(tabela);
    return () => ro.disconnect();
  }, [temLinhas]);

  // Padrão: da posição da tabela (no conteúdo rolável, sem a rolagem atual)
  // até o fim da tela visível.
  useLayoutEffect(() => {
    const wrap = tableWrapRef.current;
    if (!wrap) return;
    const calcular = () => {
      const rolavel = ancestralRolavel(wrap);
      const topo =
        wrap.getBoundingClientRect().top - rolavel.getBoundingClientRect().top + rolavel.scrollTop;
      setAlturaPadrao(Math.round(rolavel.clientHeight - topo - ITENS_ALTURA_RESERVA));
    };
    calcular();
    window.addEventListener("resize", calcular);
    return () => window.removeEventListener("resize", calcular);
  }, [temLinhas]);

  const { altura: alturaLista, handleProps: alcaProps } = useResizableHeight(ITENS_ALTURA_CHAVE, {
    min: ITENS_ALTURA_MINIMA,
    padrao: alturaPadrao,
    max: alturaConteudo,
  });

  // Item legado de corte (grupo_id) tem quantidade por tamanho e não troca
  // de produto — o backend recusa "quantidade" e "sku_codigo" para ele,
  // então REF e Qtde ficam só leitura. Ordem = navegação do Enter.
  const camposEditaveisLinha = (linha) => {
    if (!itensEditaveis || linha.removido) return [];
    return linha.grupo_id
      ? ["descricao", "punit", "descPct", "desc", "tes"]
      : ["ref", "descricao", "qtde", "punit", "descPct", "desc", "tes"];
  };

  const registrarCampo = (chave) => (el) => {
    if (el) camposItemRef.current.set(chave, el);
    else camposItemRef.current.delete(chave);
  };

  // Ordem de navegação do Enter: campos editáveis da linha, depois a
  // primeira coluna editável da linha seguinte.
  const focarProximoCampo = (chaveAtual) => {
    const ordem = linhas.flatMap((l) => camposEditaveisLinha(l).map((c) => `${l.chave}:${c}`));
    const proximo = ordem[ordem.indexOf(chaveAtual) + 1];
    if (proximo) camposItemRef.current.get(proximo)?.focus();
    else camposItemRef.current.get(chaveAtual)?.blur();
  };

  const largurasColunas = largurasQueCabem(larguras, larguraWrap);

  const botaoAdicionar = itensEditaveis && (
    <button type="button" className={styles.btnPrimary} onClick={abrirItemModal}>
      + Adicionar Item
    </button>
  );

  return (
    <section className={`sc-card ${styles.card}`}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}>
          Itens do pedido ({linhas.filter((l) => !l.removido).length})
        </h2>
        {botaoAdicionar}
      </div>

      {linhas.length === 0 ? (
        <div className={styles.vazio}>
          <p className={styles.vazioMsg}>Nenhum item no pedido</p>
          {botaoAdicionar}
        </div>
      ) : (
        <>
          {/* Altura escolhida pela alça (useResizableHeight); com mais itens
              que a altura, só esta área rola e o cabeçalho fica fixo (sticky). */}
          <div className={styles.tableWrap} ref={tableWrapRef} style={{ height: alturaLista }}>
            <table ref={tableRef} className={styles.table}>
              <colgroup>
                {ITENS_COLUNAS.map((col) => (
                  <col
                    key={col.key}
                    style={
                      col.key !== "descricao" && largurasColunas[col.key] != null
                        ? { width: largurasColunas[col.key] }
                        : undefined
                    }
                  />
                ))}
              </colgroup>
              <thead>
                <tr>
                  {ITENS_COLUNAS.map((col) => (
                    <th key={col.key} className={col.num ? styles.thNum : ""} title={col.label}>
                      {col.label}
                      {!col.fixa && (
                        <span
                          className={`${styles.resizeHandle} ${arrastando === col.key ? styles.resizeHandleAtivo : ""}`}
                          onMouseDown={iniciarArrasto(col.key)}
                          onDoubleClick={() => restaurar(col.key)}
                          title="Arraste para redimensionar. Duplo clique restaura o padrão."
                        />
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {linhas.map((linha) => {
                  const editaveis = camposEditaveisLinha(linha);
                  const erroDe = (coluna) => errosItens[`${linha.chave}|${coluna}`];
                  const celula = (coluna, props) => {
                    const chave = `${linha.chave}:${coluna}`;
                    return (
                      <CelulaNumero
                        {...props}
                        readOnly={!editaveis.includes(coluna)}
                        erroServidor={erroDe(coluna)}
                        onSalvar={(valor) => editarNumero(linha, coluna, valor)}
                        onProximo={() => focarProximoCampo(chave)}
                        inputRef={registrarCampo(chave)}
                      />
                    );
                  };
                  const chaveCampo = (coluna) => `${linha.chave}:${coluna}`;
                  const classeLinha = linha.removido
                    ? styles.linhaRemovida
                    : linha.alterado
                      ? styles.linhaAlterada
                      : "";
                  const erroRef = erroDe("ref");
                  const erroDescricao = erroDe("descricao");
                  const erroTes = erroDe("tes");
                  return (
                    <tr
                      key={linha.chave}
                      className={classeLinha}
                      title={
                        linha.removido
                          ? "Será removido ao salvar"
                          : linha.novo
                            ? "Item novo — ainda não salvo"
                            : linha.alterado
                              ? "Alterado — ainda não salvo"
                              : undefined
                      }
                    >
                      <td
                        className={styles.tdItem}
                        title={linha.novo ? "Número atribuído ao salvar" : undefined}
                      >
                        {linha.numero_item != null
                          ? String(linha.numero_item).padStart(3, "0")
                          : "—"}
                      </td>
                      <td
                        className={`${styles.tdEdit} ${styles.tdRef} ${erroRef ? "sc-campo-erro" : ""}`}
                        title={erroRef || undefined}
                      >
                        <ProdutoSkuInput
                          className={styles.refInput}
                          codigo={linha.ref_codigo || ""}
                          readOnly={!editaveis.includes("ref")}
                          erroServidor={erroRef}
                          tabelaPrecoId={pedido.tabela_preco_id}
                          tipoPreco={pedido.condicoes || ""}
                          onChange={(sku) => trocarSku(linha, sku)}
                          onProximo={() => focarProximoCampo(chaveCampo("ref"))}
                          inputRef={registrarCampo(chaveCampo("ref"))}
                        />
                      </td>
                      <td
                        className={`${styles.tdEdit} ${erroDescricao ? "sc-campo-erro" : ""}`}
                        title={erroDescricao || undefined}
                      >
                        <CelulaDescricao
                          valor={linha.descricao}
                          cadastro={linha.descricao_cadastro}
                          readOnly={!editaveis.includes("descricao")}
                          erroServidor={erroDescricao}
                          onSalvar={(texto) => editarDescricao(linha, texto)}
                          onProximo={() => focarProximoCampo(chaveCampo("descricao"))}
                          inputRef={registrarCampo(chaveCampo("descricao"))}
                        />
                      </td>
                      <td className={styles.tdEdit}>
                        {celula("qtde", { valor: linha.quantidade, casas: 0 })}
                      </td>
                      <td className={styles.tdEdit}>
                        {celula("punit", {
                          valor: linha.preco_unitario,
                          casas: 2,
                          moeda: true,
                          marcador: linha.preco_manual ? (
                            <span
                              className={styles.marcadorManual}
                              title="Preço alterado manualmente"
                            />
                          ) : null,
                        })}
                      </td>
                      <td className={styles.tdEdit}>
                        {celula("descPct", { valor: linha.desconto_percentual, casas: 2 })}
                      </td>
                      <td className={styles.tdEdit}>
                        {celula("desc", { valor: linha.desconto_valor, casas: 2, moeda: true })}
                      </td>
                      <td className={styles.tdTotal} title={moeda(linha.total)}>
                        {moeda(linha.total)}
                      </td>
                      {/* TesInput não expõe ref nem "próximo": o input é
                          achado no td, e o Enter é interceptado na captura
                          para seguir a navegação — o blur valida o código.
                          Só o input do td (o modal da TES é portal). */}
                      <td
                        className={erroTes ? "sc-campo-erro" : ""}
                        title={erroTes || undefined}
                        ref={(td) => registrarCampo(chaveCampo("tes"))(td?.querySelector("input"))}
                        onKeyDownCapture={(e) => {
                          if (
                            e.key === "Enter" &&
                            editaveis.includes("tes") &&
                            e.target.tagName === "INPUT" &&
                            e.currentTarget.contains(e.target)
                          ) {
                            e.preventDefault();
                            e.stopPropagation();
                            focarProximoCampo(chaveCampo("tes"));
                          }
                        }}
                      >
                        <TesInput
                          variant="code"
                          tesId={linha.tes_id}
                          tesList={tesList}
                          readOnly={!itensEditaveis || linha.removido}
                          onChange={(tes) => editarTes(linha, tes)}
                        />
                      </td>
                      <td className={styles.tdAcao}>
                        {itensEditaveis &&
                          (linha.removido ? (
                            <button
                              type="button"
                              className={styles.btnDesfazer}
                              onClick={() => desfazerRemocao(linha)}
                              title="Desfazer remoção"
                              aria-label="Desfazer remoção"
                            >
                              {/* Ícone: a coluna × tem 32px, sem espaço para texto. */}
                              <svg
                                width="13"
                                height="13"
                                viewBox="0 0 16 16"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.6"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                aria-hidden="true"
                              >
                                <path d="M4 6h6.5a3.5 3.5 0 0 1 0 7H7" />
                                <path d="M6.5 3.5 4 6l2.5 2.5" />
                              </svg>
                            </button>
                          ) : (
                            <button
                              type="button"
                              className={styles.btnExcluir}
                              onClick={() => removerLinha(linha)}
                              title="Remover"
                            >
                              ×
                            </button>
                          ))}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ── Rodapé mínimo, só com pendência: Descartar / Salvar Itens ── */}
      {itensEditaveis && qtdPendencias > 0 && (
        <div className={styles.acoes}>
          <span className={erroLote ? styles.acoesErro : styles.acoesMsg}>
            {erroLote ||
              (qtdPendencias === 1
                ? "1 alteração não salva"
                : `${qtdPendencias} alterações não salvas`)}
          </span>
          <button
            type="button"
            className={styles.btnSecondary}
            onClick={descartar}
            disabled={salvandoItens}
          >
            Descartar
          </button>
          <button
            type="button"
            className={styles.btnPrimary}
            onClick={salvarItens}
            disabled={salvandoItens}
          >
            {salvandoItens ? "Salvando…" : "Salvar Itens"}
          </button>
        </div>
      )}

      {/* ── Alça de altura: borda inferior do card ── */}
      {temLinhas && (
        <div className={styles.alca} {...alcaProps}>
          <svg width="16" height="7" viewBox="0 0 16 7" aria-hidden="true">
            <path
              d="M3 1h10M3 3.5h10M3 6h10"
              stroke="currentColor"
              strokeWidth="1"
              strokeLinecap="round"
            />
          </svg>
        </div>
      )}

      {/* ══ MODAL — Adicionar item (3 passos: busca → grade do pai / avulso) ══ */}
      {itemModal && (
        <div className={styles.overlay} {...fecharItemModalOverlay}>
          <div
            className={`${styles.modalMd} ${
              itemModal.step === 2
                ? styles.modalGrade
                : itemModal.step === 3
                  ? styles.modalAvulso
                  : styles.modalBusca
            }`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>
                {itemModal.step === 1 ? (
                  "Adicionar Item"
                ) : (
                  <>
                    <button
                      className={styles.btnVoltarModal}
                      onClick={voltarParaBusca}
                      title="Voltar"
                    >
                      ←
                    </button>
                    {itemModal.step === 2
                      ? itemModal.produtoPai?.descricao
                      : itemModal.avulso?.descricao}
                  </>
                )}
              </h2>
              <button className={styles.btnClose} onClick={fecharItemModal}>
                ×
              </button>
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
                      onBlur={() =>
                        setTimeout(
                          () => setItemModal((m) => (m ? { ...m, searchResults: [] } : m)),
                          200
                        )
                      }
                      autoComplete="off"
                      autoFocus
                    />
                  </label>
                  {itemModal.searching && <small className={styles.precoHint}>Buscando…</small>}
                  {itemModal.searchResults.length > 0 &&
                    ReactDOM.createPortal(
                      <ul
                        className={styles.autocomplete}
                        style={{ top: acPos.top, left: acPos.left, width: acPos.width }}
                      >
                        {itemModal.searchResults.map((r) => (
                          <li
                            key={`${r.tipo}-${r.id}`}
                            className={styles.acItem}
                            onClick={() => selecionarResultadoBusca(r)}
                          >
                            <span
                              className={styles.acIcone}
                              title={r.tipo === "pai" ? "Produto com grade" : "Produto avulso"}
                            >
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
                                        type="number"
                                        min="0"
                                        className={styles.gradeCell}
                                        disabled={disabled}
                                        value={itemModal.gradeQtds[key] || ""}
                                        onChange={(e) =>
                                          setGradeQtd(linha.id, col.id, e.target.value)
                                        }
                                      />
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <table className={styles.gradePrecoTable}>
                          <thead>
                            <tr>
                              <th>Preço Unit.</th>
                            </tr>
                          </thead>
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
                                    className={
                                      skuRef?.preco_origem === "sem_preco"
                                        ? styles.gradePrecoSemPreco
                                        : ""
                                    }
                                  >
                                    {skuRef?.preco_origem === "sem_preco"
                                      ? "—"
                                      : moeda(skuRef?.preco_venda)}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      <div className={styles.itemTotal}>
                        Total de peças: <strong>{gradeTotais.pecas}</strong> | Total:{" "}
                        <strong>{moeda(gradeTotais.valor)}</strong>
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
                      <input
                        type="number"
                        min="1"
                        className={styles.input}
                        value={itemModal.avulsoForm.quantidade}
                        onChange={setAvulsoForm("quantidade")}
                      />
                    </label>
                    <label className={styles.field}>
                      <span>Preço unitário (R$) *</span>
                      <input
                        type="number"
                        step="0.01"
                        className={styles.input}
                        value={itemModal.avulsoForm.precoUnit}
                        onChange={setAvulsoForm("precoUnit")}
                      />
                    </label>
                  </div>
                  <div className={styles.grid2}>
                    <label className={styles.field}>
                      <span>TES</span>
                      <select
                        className={styles.input}
                        value={itemModal.avulsoForm.tesId}
                        onChange={setAvulsoForm("tesId")}
                      >
                        <option value="">Nenhum</option>
                        {tesList.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.codigo} — {t.descricao}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className={styles.field}>
                      <span>Desconto (%)</span>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        max="100"
                        className={styles.input}
                        value={itemModal.avulsoForm.descontoPct}
                        onChange={setAvulsoForm("descontoPct")}
                      />
                    </label>
                  </div>
                  <p className={styles.precoHint}>
                    Produto avulso é gravado no pedido ao adicionar.
                  </p>
                  <div className={styles.itemTotal}>
                    Total: <strong>{moeda(totalAvulso)}</strong>
                  </div>
                </>
              )}

              {erroItem && <p className={styles.erro}>{erroItem}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={fecharItemModal}>
                Cancelar
              </button>
              {itemModal.step === 2 && (
                <button
                  className={styles.btnPrimary}
                  onClick={handleAdicionarGrade}
                  disabled={gradeTotais.pecas === 0}
                >
                  Adicionar à grade →
                </button>
              )}
              {itemModal.step === 3 && (
                <button
                  className={styles.btnPrimary}
                  onClick={handleAdicionarAvulso}
                  disabled={saving}
                >
                  {saving ? "Adicionando…" : "Adicionar item"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
