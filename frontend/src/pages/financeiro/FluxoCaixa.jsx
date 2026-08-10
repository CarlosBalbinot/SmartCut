import { useState, useEffect, useCallback } from "react";
import { SlidersHorizontal } from "lucide-react";
import {
  getLancamentos,
  getSaldoContas,
  getContasBancarias,
  confirmarPagamento as apiConfirmarPagamento,
  getAnexos,
  downloadAnexo,
  createLancamento,
  updateLancamento,
  deleteLancamento,
  getCompras,
  getVendasFinanceiras,
} from "../../api/financeiro";
import styles from "./FluxoCaixa.module.css";

const MESES = [
  "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
  "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro",
];

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

const hojeISO = () => new Date().toISOString().split("T")[0];

const dataFmt = (iso) => {
  if (!iso) return "—";
  const [y, m, d] = iso.split("T")[0].split("-");
  return `${d}/${m}/${y}`;
};

// Formato curto para a coluna Vencimento da tabela — sem o ano.
const dataFmtCurta = (iso) => {
  if (!iso) return "—";
  const [, m, d] = iso.split("T")[0].split("-");
  return `${d}/${m}`;
};

const STATUS_LABELS = { PAGO: "Pago", PENDENTE: "Pendente", CANCELADO: "Cancelado" };

// Categoria de vencimento de um lançamento: "pago" | "cancelado" | "atrasado"
// | "alerta" (vence hoje/amanhã) | "normal". Fonte única para o estilo da
// linha, a cor do texto de vencimento e o rótulo "Atrasado" do badge de status.
function vencimentoCategoria(item) {
  if (item.status === "PAGO") return "pago";
  if (item.status === "CANCELADO") return "cancelado";
  const vencStr = (item.data_vencimento || "").split("T")[0];
  if (!vencStr) return "normal";
  const [y, m, d] = vencStr.split("-").map(Number);
  const hoje = new Date();
  const hojeDia  = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  const vencDia  = new Date(y, m - 1, d);
  const amanha   = new Date(hojeDia);
  amanha.setDate(amanha.getDate() + 1);
  if (vencDia < hojeDia) return "atrasado";
  if (vencDia <= amanha)  return "alerta";
  return "normal";
}

function rowStatusClass(item) {
  const cat = vencimentoCategoria(item);
  if (cat === "pago") return styles.rowPago;
  if (cat === "atrasado") return styles.rowAtrasado;
  return "";
}

// Soma segura de valores monetários vindos da API (Decimal serializado como string).
const somaValores = (itens, getValor) =>
  itens.reduce((acc, item) => acc + (parseFloat(getValor(item)) || 0), 0);

// "Fornecedor — NF XXX" / "Cliente — NF XXX" quando o lançamento vem de uma
// compra/venda; cai para a descrição crua do lançamento caso contrário.
// (usado nos textos dos modais — não alterado pelo redesenho visual)
function descricaoLancamento(l, comprasMap, vendasMap) {
  if (l.compra_id && comprasMap[l.compra_id]) {
    const c = comprasMap[l.compra_id];
    return c.descricao ? `${c.fornecedor} — ${c.descricao}` : c.fornecedor;
  }
  if (l.venda_id && vendasMap[l.venda_id]) {
    const v = vendasMap[l.venda_id];
    return v.descricao ? `${v.cliente} — ${v.descricao}` : v.cliente;
  }
  return l.descricao || "—";
}

// Mesma informação, mas separada em título (fornecedor/cliente) e subtítulo
// (NF) para a célula de Descrição de duas linhas da tabela redesenhada.
function descricaoPartes(l, comprasMap, vendasMap) {
  if (l.compra_id && comprasMap[l.compra_id]) {
    const c = comprasMap[l.compra_id];
    return { titulo: c.fornecedor, subtitulo: c.descricao || null };
  }
  if (l.venda_id && vendasMap[l.venda_id]) {
    const v = vendasMap[l.venda_id];
    return { titulo: v.cliente, subtitulo: v.descricao || null };
  }
  return { titulo: l.descricao || "—", subtitulo: null };
}

// Mesmo dia, `meses` à frente, com clamp para o último dia do mês destino
// (espelha o _add_meses do backend).
function addMesClamp(dataISO, meses) {
  const [y, m, d] = dataISO.split("-").map(Number);
  const totalMeses = (m - 1) + meses;
  const novoAno = y + Math.floor(totalMeses / 12);
  const novoMes = (totalMeses % 12) + 1;
  const ultimoDia = new Date(novoAno, novoMes, 0).getDate();
  const novoDia = Math.min(d, ultimoDia);
  return `${novoAno}-${String(novoMes).padStart(2, "0")}-${String(novoDia).padStart(2, "0")}`;
}

const LANC_VAZIO = {
  tipo: "PAGAR", descricao: "", valor: "",
  vencimento: hojeISO(), categoria: "", parcelas: "1",
};

export default function FluxoCaixa() {
  const now = new Date();
  const [mes, setMes] = useState(now.getMonth() + 1);
  const [ano, setAno] = useState(now.getFullYear());

  const [lancamentos,    setLancamentos]    = useState([]);
  const [saldoContas,    setSaldoContas]    = useState([]);
  const [contasBanc,     setContasBanc]     = useState([]);
  const [comprasMap,     setComprasMap]     = useState({});
  const [vendasMap,      setVendasMap]      = useState({});
  const [loading,        setLoading]        = useState(false);

  const [mensagemSucesso, setMensagemSucesso] = useState(null);

  // Menu de ações "···" (dropdown por linha)
  const [openMenuId, setOpenMenuId] = useState(null);

  // Modal confirmar pagamento/recebimento
  const [modalPag,   setModalPag]   = useState(null);
  const [pagForm,    setPagForm]    = useState({ conta_bancaria_id: "", data_pagamento: hojeISO() });
  const [erroPag,    setErroPag]    = useState(null);
  const [savingPag,  setSavingPag]  = useState(false);
  const [tipoRecebimento,     setTipoRecebimento]     = useState("total"); // "total" | "parcial"
  const [valorRecebidoParcial, setValorRecebidoParcial] = useState("");

  // Modal desfazer pagamento
  const [modalDesfazer, setModalDesfazer] = useState(null);
  const [desfazendo,    setDesfazendo]    = useState(false);
  const [erroDesfazer,  setErroDesfazer]  = useState(null);

  // Modal editar parcela
  const [modalEditarParcela,  setModalEditarParcela]  = useState(null);
  const [editParcelaForm,     setEditParcelaForm]     = useState({ valor: "", vencimento: "", observacao: "" });
  const [savingEditParcela,   setSavingEditParcela]   = useState(false);
  const [erroEditarParcela,   setErroEditarParcela]   = useState(null);

  // Modal excluir lançamento
  const [modalExcluir, setModalExcluir] = useState(null);
  const [excluindo,    setExcluindo]    = useState(false);
  const [erroExcluir,  setErroExcluir]  = useState(null);

  // Modal anexos
  const [modalAnexos,    setModalAnexos]    = useState(null);
  const [anexos,         setAnexos]         = useState([]);
  const [loadingAnexos,  setLoadingAnexos]  = useState(false);

  // Modal novo lançamento
  const [modalLanc,    setModalLanc]    = useState(false);
  const [lancForm,     setLancForm]     = useState(LANC_VAZIO);
  const [erroLanc,     setErroLanc]     = useState(null);
  const [savingLanc,   setSavingLanc]   = useState(false);

  const carregarDados = useCallback(async () => {
    setLoading(true);
    try {
      const [lancs, saldos] = await Promise.all([
        getLancamentos(mes, ano),
        getSaldoContas(mes, ano),
      ]);
      setLancamentos(lancs  || []);
      setSaldoContas(saldos || []);
    } catch {}
    setLoading(false);
  }, [mes, ano]);

  useEffect(() => { carregarDados(); }, [carregarDados]);

  useEffect(() => {
    getContasBancarias().then((c) => setContasBanc(c || [])).catch(() => {});
  }, []);

  useEffect(() => {
    getCompras().then((rows) => {
      const map = {};
      (rows || []).forEach((c) => { map[c.id] = c; });
      setComprasMap(map);
    }).catch(() => {});
    getVendasFinanceiras().then((rows) => {
      const map = {};
      (rows || []).forEach((v) => { map[v.id] = v; });
      setVendasMap(map);
    }).catch(() => {});
  }, []);

  // Fecha o dropdown de ações ao clicar fora dele.
  useEffect(() => {
    if (!openMenuId) return;
    const handleClickOutside = (e) => {
      if (!e.target.closest("[data-menu-root]")) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [openMenuId]);

  // ── Navegação de mês ──────────────────────────────────────────────────────
  const navegarMes = (delta) => {
    const novo = mes + delta;
    if (novo > 12) { setMes(1);  setAno((a) => a + 1); }
    else if (novo < 1) { setMes(12); setAno((a) => a - 1); }
    else { setMes(novo); }
  };

  // ── Derived ──────────────────────────────────────────────────────────────
  const pagar        = lancamentos.filter((l) => l.tipo === "PAGAR");
  const receber      = lancamentos.filter((l) => l.tipo === "RECEBER");
  const totalPagar   = somaValores(pagar.filter((l) => l.status !== "PAGO"), (l) => l.valor);
  const totalReceber = somaValores(receber.filter((l) => l.status !== "PAGO"), (l) => l.valor);
  const saldoTotal   = somaValores(saldoContas, (c) => c.saldo_atual);
  const projecao     = saldoTotal + totalReceber - totalPagar;
  const countPagar   = pagar.filter((l) => l.status !== "PAGO").length;
  const countReceber = receber.filter((l) => l.status !== "PAGO").length;

  const valorTotalModal    = modalPag ? parseFloat(modalPag.valor) || 0 : 0;
  const valorRecebidoNum   = parseFloat(valorRecebidoParcial) || 0;
  const valorRestanteModal = Math.max(valorTotalModal - valorRecebidoNum, 0);

  // ── Confirmar pagamento / recebimento ─────────────────────────────────────
  const abrirModalPag = (l) => {
    setModalPag(l);
    setPagForm({ conta_bancaria_id: "", data_pagamento: hojeISO() });
    setErroPag(null);
    setTipoRecebimento("total");
    setValorRecebidoParcial("");
  };

  const handleConfirmarPag = async () => {
    if (!pagForm.conta_bancaria_id) { setErroPag("Selecione a conta bancária."); return; }
    if (!pagForm.data_pagamento)    { setErroPag("Informe a data."); return; }

    const parcial = modalPag.tipo === "RECEBER" && tipoRecebimento === "parcial";
    let valorRecebido = valorTotalModal;
    if (parcial) {
      valorRecebido = parseFloat(valorRecebidoParcial);
      if (!valorRecebidoParcial || isNaN(valorRecebido) || valorRecebido <= 0) {
        setErroPag("Informe o valor recebido."); return;
      }
      if (valorRecebido >= valorTotalModal) {
        setErroPag("O valor recebido deve ser menor que o valor total para um recebimento parcial.");
        return;
      }
    }

    setSavingPag(true);
    setErroPag(null);
    try {
      if (parcial) {
        const valorRestante = Math.round((valorTotalModal - valorRecebido) * 100) / 100;
        const novaData = addMesClamp((modalPag.data_vencimento || "").split("T")[0], 1);

        // 1. Lançamento atual: PAGO com o valor efetivamente recebido.
        await updateLancamento(modalPag.id, {
          status: "PAGO",
          data_pagamento: pagForm.data_pagamento,
          conta_bancaria_id: pagForm.conta_bancaria_id,
          valor: valorRecebido,
        });
        // 2. Novo lançamento com o saldo, mês seguinte.
        await createLancamento({
          tipo: "RECEBER",
          descricao: `${modalPag.descricao || ""} (saldo)`.trim(),
          valor: valorRestante,
          data_vencimento: novaData,
          venda_id: modalPag.venda_id || null,
          parcela_numero: modalPag.parcela_numero ? modalPag.parcela_numero + 1 : null,
          parcela_total: modalPag.parcela_total ? modalPag.parcela_total + 1 : null,
        });

        setModalPag(null);
        await carregarDados();
        setMensagemSucesso(
          `Recebimento parcial registrado. Saldo de ${moeda(valorRestante)} lançado para ${dataFmt(novaData)}.`
        );
      } else {
        await apiConfirmarPagamento(
          modalPag.id,
          pagForm.conta_bancaria_id,
          pagForm.data_pagamento,
        );
        setModalPag(null);
        await carregarDados();
      }
      getSaldoContas(mes, ano).then((s) => setSaldoContas(s || [])).catch(() => {});
    } catch (e) {
      setErroPag(e.message);
    }
    setSavingPag(false);
  };

  // ── Desfazer pagamento ────────────────────────────────────────────────────
  const abrirModalDesfazer = (l) => {
    setModalDesfazer(l);
    setErroDesfazer(null);
  };

  const handleConfirmarDesfazer = async () => {
    setDesfazendo(true);
    setErroDesfazer(null);
    try {
      await updateLancamento(modalDesfazer.id, {
        status: "PENDENTE",
        data_pagamento: null,
        conta_bancaria_id: null,
      });
      setModalDesfazer(null);
      await carregarDados();
      getSaldoContas(mes, ano).then((s) => setSaldoContas(s || [])).catch(() => {});
    } catch (e) {
      setErroDesfazer(e.message || "Erro ao desfazer pagamento.");
    }
    setDesfazendo(false);
  };

  // ── Editar parcela ────────────────────────────────────────────────────────
  const abrirModalEditarParcela = (l) => {
    setModalEditarParcela(l);
    setEditParcelaForm({
      valor: String(parseFloat(l.valor) || ""),
      vencimento: (l.data_vencimento || "").split("T")[0],
      observacao: "",
    });
    setErroEditarParcela(null);
  };

  const handleSalvarEditarParcela = async () => {
    const novoValor = parseFloat(editParcelaForm.valor);
    if (!editParcelaForm.valor || isNaN(novoValor) || novoValor <= 0) {
      setErroEditarParcela("Informe um valor válido."); return;
    }
    if (!editParcelaForm.vencimento) {
      setErroEditarParcela("Informe a data de vencimento."); return;
    }
    setSavingEditParcela(true);
    setErroEditarParcela(null);
    try {
      const dados = {
        valor: novoValor,
        data_vencimento: editParcelaForm.vencimento,
      };
      const obs = editParcelaForm.observacao.trim();
      if (obs) {
        const base = modalEditarParcela.descricao || "";
        dados.descricao = base ? `${base} — Obs: ${obs}` : `Obs: ${obs}`;
      }
      await updateLancamento(modalEditarParcela.id, dados);
      setModalEditarParcela(null);
      await carregarDados();
    } catch (e) {
      setErroEditarParcela(e.message || "Erro ao salvar parcela.");
    }
    setSavingEditParcela(false);
  };

  const handlePassarMesSeguinte = async () => {
    const vencAtual = editParcelaForm.vencimento || (modalEditarParcela.data_vencimento || "").split("T")[0];
    if (!vencAtual) { setErroEditarParcela("Informe a data de vencimento."); return; }
    const novaData = addMesClamp(vencAtual, 1);
    setSavingEditParcela(true);
    setErroEditarParcela(null);
    try {
      await updateLancamento(modalEditarParcela.id, { data_vencimento: novaData });
      setModalEditarParcela(null);
      await carregarDados();
    } catch (e) {
      setErroEditarParcela(e.message || "Erro ao mover parcela.");
    }
    setSavingEditParcela(false);
  };

  // Atalho do menu "···" — mesma operação de "Passar para o mês seguinte",
  // mas direto da linha da tabela, sem passar pelo modal de edição.
  const handlePassarMesSeguinteRapido = async (l) => {
    const vencAtual = (l.data_vencimento || "").split("T")[0];
    if (!vencAtual) return;
    const novaData = addMesClamp(vencAtual, 1);
    try {
      await updateLancamento(l.id, { data_vencimento: novaData });
      await carregarDados();
    } catch (e) {
      window.alert(e.message || "Erro ao mover parcela para o mês seguinte.");
    }
  };

  // ── Excluir lançamento ────────────────────────────────────────────────────
  const abrirModalExcluir = (l) => {
    setModalExcluir(l);
    setErroExcluir(null);
  };

  const handleConfirmarExcluir = async () => {
    setExcluindo(true);
    setErroExcluir(null);
    try {
      await deleteLancamento(modalExcluir.id);
      setModalExcluir(null);
      await carregarDados();
      getSaldoContas(mes, ano).then((s) => setSaldoContas(s || [])).catch(() => {});
    } catch (e) {
      setErroExcluir(e.message || "Erro ao excluir lançamento.");
    }
    setExcluindo(false);
  };

  // ── Anexos ────────────────────────────────────────────────────────────────
  const abrirAnexos = async (lancamentoId) => {
    setModalAnexos({ lancamentoId });
    setAnexos([]);
    setLoadingAnexos(true);
    try {
      setAnexos((await getAnexos(lancamentoId)) || []);
    } catch {}
    setLoadingAnexos(false);
  };

  const handleDownload = async (anexoId, nome) => {
    try {
      const blob = await downloadAnexo(anexoId);
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = nome || "anexo";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {}
  };

  // ── Novo lançamento ───────────────────────────────────────────────────────
  const setLanc = (key) => (e) =>
    setLancForm((f) => ({ ...f, [key]: e.target.value }));

  const abrirModalLanc = (tipoPadrao) => {
    setLancForm({ ...LANC_VAZIO, tipo: tipoPadrao || "PAGAR" });
    setErroLanc(null);
    setModalLanc(true);
  };

  const handleCriarLanc = async () => {
    if (!lancForm.descricao.trim()) { setErroLanc("Informe a descrição."); return; }
    if (!lancForm.valor || isNaN(parseFloat(lancForm.valor))) {
      setErroLanc("Informe o valor."); return;
    }
    if (!lancForm.vencimento) { setErroLanc("Informe o vencimento."); return; }
    setSavingLanc(true);
    try {
      await createLancamento({
        tipo:       lancForm.tipo,
        descricao:  lancForm.descricao.trim(),
        valor:      parseFloat(lancForm.valor),
        vencimento: lancForm.vencimento,
        categoria:  lancForm.categoria  || null,
        parcelas:   parseInt(lancForm.parcelas) || 1,
      });
      setModalLanc(false);
      await carregarDados();
    } catch (e) {
      setErroLanc(e.message);
    }
    setSavingLanc(false);
  };

  // ── Tabela helper ─────────────────────────────────────────────────────────
  const renderBloco = (itens, tipo) => {
    const total = tipo === "PAGAR" ? totalPagar : totalReceber;
    const titulo = tipo === "PAGAR" ? "Contas a Pagar" : "Contas a Receber";

    return (
      <section className={styles.tableSection}>
        <div className={styles.blockHeader}>
          <span className={styles.blockHeaderTitle}>{titulo}</span>
          <span className={styles.blockHeaderMeta}>
            {itens.length} lançamento{itens.length !== 1 ? "s" : ""} • Total: {moeda(total)}
          </span>
        </div>
        <div className={styles.blockDivider} />

        <div className={styles.card}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Descrição</th>
                <th>Venc.</th>
                <th>Valor</th>
                <th>Parcela</th>
                <th>Status</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((l) => {
                const partes = descricaoPartes(l, comprasMap, vendasMap);
                const valorNum = parseFloat(l.valor) || 0;
                const valorOrigNum = l.valor_original != null ? parseFloat(l.valor_original) : null;
                const valorAlterado = valorOrigNum != null && Math.abs(valorNum - valorOrigNum) > 0.005;

                const cat = vencimentoCategoria(l);
                const vencCls = cat === "atrasado" ? styles.vencAtrasado
                  : cat === "alerta" ? styles.vencAlerta
                  : styles.vencNormal;

                let statusLabel = STATUS_LABELS[l.status] || l.status || "Pendente";
                let statusCls = "st" + (l.status || "PENDENTE");
                if (l.status === "PENDENTE" && cat === "atrasado") {
                  statusLabel = "Atrasado";
                  statusCls = "stATRASADO";
                }

                const podeConfirmar = l.status !== "PAGO" && l.status !== "CANCELADO";

                return (
                  <tr key={l.id} className={rowStatusClass(l)}>
                    <td>
                      <div className={styles.descricaoCell}>
                        <span className={styles.descricaoTitulo} title={partes.titulo}>{partes.titulo}</span>
                        {partes.subtitulo && (
                          <span className={styles.descricaoSub}>{partes.subtitulo}</span>
                        )}
                      </div>
                    </td>
                    <td className={vencCls}>{dataFmtCurta(l.data_vencimento)}</td>
                    <td className={styles.tdValor}>
                      {valorAlterado ? (
                        <div className={styles.valorAlteradoWrap}>
                          <span className={styles.valorAlteradoAtual}>{moeda(valorNum)}</span>
                          <span className={styles.valorOriginalRiscado}>{moeda(valorOrigNum)}</span>
                        </div>
                      ) : (
                        moeda(valorNum)
                      )}
                    </td>
                    <td className={styles.tdParcela}>
                      {l.parcela_numero && l.parcela_total ? (
                        <span className={styles.parcelaBadge}>{l.parcela_numero}/{l.parcela_total}</span>
                      ) : "—"}
                    </td>
                    <td>
                      <span className={`${styles.badge} ${styles[statusCls]}`}>{statusLabel}</span>
                    </td>
                    <td>
                      <div className={styles.actionsMenu} data-menu-root>
                        {l.status === "PAGO" ? (
                          <button className={styles.btnAcaoSecundaria} onClick={() => abrirModalDesfazer(l)}>
                            ↩ Desfazer
                          </button>
                        ) : podeConfirmar ? (
                          <button className={styles.btnAcaoPrimaria} onClick={() => abrirModalPag(l)}>
                            ✓ Pagar
                          </button>
                        ) : null}

                        <div className={styles.dropdownWrap}>
                          <button
                            className={styles.btnDots}
                            onClick={() => setOpenMenuId(openMenuId === l.id ? null : l.id)}
                          >
                            ···
                          </button>
                          {openMenuId === l.id && (
                            <div className={styles.dropdownMenu}>
                              {l.status !== "PAGO" && (
                                <>
                                  <button
                                    className={styles.dropdownItem}
                                    onClick={() => { setOpenMenuId(null); abrirModalEditarParcela(l); }}
                                  >
                                    <SlidersHorizontal size={13} className={styles.dropdownItemIcon} />
                                    Editar parcela
                                  </button>
                                  <button
                                    className={styles.dropdownItem}
                                    onClick={() => { setOpenMenuId(null); handlePassarMesSeguinteRapido(l); }}
                                  >
                                    Passar para mês seguinte
                                  </button>
                                </>
                              )}
                              <button
                                className={styles.dropdownItem}
                                onClick={() => { setOpenMenuId(null); abrirAnexos(l.id); }}
                              >
                                Ver anexos
                              </button>
                              {l.status !== "PAGO" && (
                                <button
                                  className={`${styles.dropdownItem} ${styles.dropdownItemDanger}`}
                                  onClick={() => { setOpenMenuId(null); abrirModalExcluir(l); }}
                                >
                                  Excluir
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {itens.length === 0 && (
                <tr>
                  <td colSpan={6} className={styles.emptyCell}>
                    <div className={styles.emptyState}>
                      <span className={styles.emptyIcon}>{tipo === "PAGAR" ? "💸" : "💰"}</span>
                      <p className={styles.emptyText}>
                        {loading
                          ? "Carregando…"
                          : `Nenhum lançamento a ${tipo === "PAGAR" ? "pagar" : "receber"} este mês`}
                      </p>
                      {!loading && (
                        <button className={styles.btnEmptyAdd} onClick={() => abrirModalLanc(tipo)}>
                          + Adicionar lançamento
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    );
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className={styles.page}>

      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}>Fluxo de Caixa</h1>
          <div className={styles.navMes}>
            <button className={styles.btnNav} onClick={() => navegarMes(-1)}>‹</button>
            <span className={styles.mesLabel}>{MESES[mes - 1]} {ano}</span>
            <button className={styles.btnNav} onClick={() => navegarMes(1)}>›</button>
          </div>
        </div>
        <button className={styles.btnPrimary} onClick={() => abrirModalLanc()}>
          + Lançamento Manual
        </button>
      </div>

      {mensagemSucesso && (
        <div className={styles.avisoSucesso}>
          <span>{mensagemSucesso}</span>
          <button className={styles.btnClose} onClick={() => setMensagemSucesso(null)}>×</button>
        </div>
      )}

      {/* Saldo das contas */}
      <div className={styles.saldoGrid}>
        {saldoContas.map((c) => (
          <div key={c.conta_id} className={styles.saldoCard}>
            <span className={styles.saldoNome}>{c.conta_nome}</span>
            <span className={`${styles.saldoValor} ${(parseFloat(c.saldo_atual) || 0) < 0 ? styles.negativo : ""}`}>
              {moeda(parseFloat(c.saldo_atual) || 0)}
            </span>
          </div>
        ))}
        {saldoContas.length === 0 && pagar.length === 0 && receber.length === 0 && !loading && (
          <span className={styles.semContas}>Nenhuma conta cadastrada.</span>
        )}
      </div>

      {/* Resumo */}
      <div className={styles.resumoGrid}>
        <div className={`${styles.resumoCard} ${styles.resumoBorderPerigo}`}>
          <span className={styles.resumoLabel}>A Pagar</span>
          <span className={styles.resumoValor}>{moeda(totalPagar)}</span>
          <span className={styles.resumoSub}>{countPagar} lançamento{countPagar !== 1 ? "s" : ""}</span>
        </div>
        <div className={`${styles.resumoCard} ${styles.resumoBorderSucesso}`}>
          <span className={styles.resumoLabel}>A Receber</span>
          <span className={styles.resumoValor}>{moeda(totalReceber)}</span>
          <span className={styles.resumoSub}>{countReceber} lançamento{countReceber !== 1 ? "s" : ""}</span>
        </div>
        <div className={`${styles.resumoCard} ${projecao < 0 ? styles.resumoBorderPerigo : styles.resumoBorderNeutro}`}>
          <span className={styles.resumoLabel}>Projeção Final</span>
          <span className={styles.resumoValor}>{moeda(projecao)}</span>
          <span className={styles.resumoSub}>este mês</span>
        </div>
      </div>

      {/* Tabelas */}
      <div className={styles.tablesGrid}>
        {renderBloco(pagar, "PAGAR")}
        {renderBloco(receber, "RECEBER")}
      </div>

      {/* ── Modal: Confirmar Pagamento / Recebimento ── */}
      {modalPag && (
        <div className={styles.overlay} onClick={() => !savingPag && setModalPag(null)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>
                {modalPag.tipo === "PAGAR" ? "Confirmar Pagamento" : "Confirmar Recebimento"}
              </h2>
              <button className={styles.btnClose} onClick={() => setModalPag(null)} disabled={savingPag}>×</button>
            </div>
            <div className={styles.modalBody}>
              <p className={styles.confirmText}>
                {descricaoLancamento(modalPag, comprasMap, vendasMap)} — {moeda(valorTotalModal)}
                {modalPag.data_vencimento && (
                  <> &nbsp;·&nbsp; vence {dataFmt(modalPag.data_vencimento)}</>
                )}
              </p>

              {modalPag.tipo === "RECEBER" && (
                <div className={styles.field}>
                  <span>Tipo de recebimento</span>
                  <div className={styles.radioGroup}>
                    <label className={styles.radioOption}>
                      <input
                        type="radio"
                        name="tipoRecebimento"
                        checked={tipoRecebimento === "total"}
                        onChange={() => setTipoRecebimento("total")}
                      />
                      Recebimento total — {moeda(valorTotalModal)}
                    </label>
                    <label className={styles.radioOption}>
                      <input
                        type="radio"
                        name="tipoRecebimento"
                        checked={tipoRecebimento === "parcial"}
                        onChange={() => setTipoRecebimento("parcial")}
                      />
                      Recebimento parcial
                    </label>
                    {tipoRecebimento === "parcial" && (
                      <div className={styles.radioDetalhe}>
                        <label className={styles.field}>
                          <span>Valor recebido *</span>
                          <input
                            type="number" min="0" step="0.01"
                            className={styles.input}
                            value={valorRecebidoParcial}
                            onChange={(e) => setValorRecebidoParcial(e.target.value)}
                            placeholder="0,00"
                          />
                        </label>
                        <p className={styles.valorRestanteInfo}>
                          Valor restante: <strong>{moeda(valorRestanteModal)}</strong>
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <label className={`${styles.field} ${styles.fieldSpacer}`}>
                <span>Conta bancária *</span>
                <select
                  className={styles.input}
                  value={pagForm.conta_bancaria_id}
                  onChange={(e) => setPagForm((f) => ({ ...f, conta_bancaria_id: e.target.value }))}
                >
                  <option value="">— Selecionar —</option>
                  {contasBanc.map((c) => (
                    <option key={c.id} value={c.id}>{c.nome}</option>
                  ))}
                </select>
              </label>
              <label className={`${styles.field} ${styles.fieldSpacer}`}>
                <span>Data do {modalPag.tipo === "PAGAR" ? "pagamento" : "recebimento"} *</span>
                <input
                  type="date"
                  className={styles.input}
                  value={pagForm.data_pagamento}
                  onChange={(e) => setPagForm((f) => ({ ...f, data_pagamento: e.target.value }))}
                />
              </label>
              {erroPag && <p className={styles.erro}>{erroPag}</p>}
            </div>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setModalPag(null)} disabled={savingPag}>
                Cancelar
              </button>
              <button
                className={styles.btnPrimary}
                onClick={handleConfirmarPag}
                disabled={savingPag}
              >
                {savingPag ? "Confirmando…" : "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Desfazer Pagamento ── */}
      {modalDesfazer && (
        <div className={styles.overlay} onClick={() => !desfazendo && setModalDesfazer(null)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Desfazer Pagamento</h2>
              <button className={styles.btnClose} onClick={() => setModalDesfazer(null)} disabled={desfazendo}>×</button>
            </div>
            <div className={styles.modalBody}>
              <p className={styles.confirmText}>Deseja reverter este pagamento para Pendente?</p>
              <p className={styles.confirmText}>
                {descricaoLancamento(modalDesfazer, comprasMap, vendasMap)} — {moeda(parseFloat(modalDesfazer.valor) || 0)}
              </p>
              {erroDesfazer && <p className={styles.erro}>{erroDesfazer}</p>}
            </div>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setModalDesfazer(null)} disabled={desfazendo}>
                Cancelar
              </button>
              <button className={styles.btnPrimary} onClick={handleConfirmarDesfazer} disabled={desfazendo}>
                {desfazendo ? "Confirmando…" : "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Editar Parcela ── */}
      {modalEditarParcela && (
        <div className={styles.overlay} onClick={() => !savingEditParcela && setModalEditarParcela(null)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Editar Parcela</h2>
              <button
                className={styles.btnClose}
                onClick={() => setModalEditarParcela(null)}
                disabled={savingEditParcela}
              >
                ×
              </button>
            </div>
            <div className={styles.modalBody}>
              <label className={styles.field}>
                <span>Valor original</span>
                <input
                  className={`${styles.input} ${styles.inputReadonly}`}
                  value={moeda(parseFloat(modalEditarParcela.valor_original ?? modalEditarParcela.valor) || 0)}
                  readOnly
                />
              </label>
              <label className={`${styles.field} ${styles.fieldSpacer}`}>
                <span>Novo valor *</span>
                <input
                  type="number" min="0" step="0.01"
                  className={styles.input}
                  value={editParcelaForm.valor}
                  onChange={(e) => setEditParcelaForm((f) => ({ ...f, valor: e.target.value }))}
                />
              </label>
              <label className={`${styles.field} ${styles.fieldSpacer}`}>
                <span>Data de vencimento *</span>
                <input
                  type="date"
                  className={styles.input}
                  value={editParcelaForm.vencimento}
                  onChange={(e) => setEditParcelaForm((f) => ({ ...f, vencimento: e.target.value }))}
                />
              </label>
              <label className={`${styles.field} ${styles.fieldSpacer}`}>
                <span>Observação</span>
                <textarea
                  className={styles.textarea}
                  value={editParcelaForm.observacao}
                  onChange={(e) => setEditParcelaForm((f) => ({ ...f, observacao: e.target.value }))}
                  placeholder="Anotação livre sobre esta parcela…"
                />
              </label>
              {erroEditarParcela && <p className={styles.erro}>{erroEditarParcela}</p>}
            </div>
            <div className={styles.modalActionsSplit}>
              <button
                className={styles.btnSecondary}
                onClick={handlePassarMesSeguinte}
                disabled={savingEditParcela}
              >
                Passar para o mês seguinte
              </button>
              <div className={styles.modalActionsSplitRight}>
                <button
                  className={styles.btnSecondary}
                  onClick={() => setModalEditarParcela(null)}
                  disabled={savingEditParcela}
                >
                  Cancelar
                </button>
                <button
                  className={styles.btnPrimary}
                  onClick={handleSalvarEditarParcela}
                  disabled={savingEditParcela}
                >
                  {savingEditParcela ? "Salvando…" : "Salvar"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Excluir Lançamento ── */}
      {modalExcluir && (
        <div className={styles.overlay} onClick={() => !excluindo && setModalExcluir(null)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Excluir Lançamento</h2>
              <button className={styles.btnClose} onClick={() => setModalExcluir(null)} disabled={excluindo}>×</button>
            </div>
            <div className={styles.modalBody}>
              <p className={styles.confirmText}>
                Tem certeza que deseja excluir este lançamento? Esta ação não pode ser desfeita.
              </p>
              <p className={styles.confirmText}>
                {descricaoLancamento(modalExcluir, comprasMap, vendasMap)} — {moeda(parseFloat(modalExcluir.valor) || 0)}
              </p>
              {erroExcluir && <p className={styles.erro}>{erroExcluir}</p>}
            </div>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setModalExcluir(null)} disabled={excluindo}>
                Cancelar
              </button>
              <button className={styles.btnDanger} onClick={handleConfirmarExcluir} disabled={excluindo}>
                {excluindo ? "Excluindo…" : "Excluir"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Ver Anexos ── */}
      {modalAnexos && (
        <div className={styles.overlay} onClick={() => setModalAnexos(null)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Anexos</h2>
              <button className={styles.btnClose} onClick={() => setModalAnexos(null)}>×</button>
            </div>
            <div className={styles.modalBody}>
              {loadingAnexos ? (
                <p className={styles.confirmText}>Carregando…</p>
              ) : anexos.length === 0 ? (
                <p className={styles.confirmText}>Nenhum anexo neste lançamento.</p>
              ) : (
                <ul className={styles.attachList}>
                  {anexos.map((a) => (
                    <li key={a.id} className={styles.attachItem}>
                      <span className={styles.attachIcon}>📄</span>
                      <span className={styles.attachNome} title={a.nome || a.arquivo}>
                        {a.nome || a.arquivo || "Arquivo"}
                      </span>
                      {a.tipo && (
                        <span className={styles.attachTipo}>{a.tipo}</span>
                      )}
                      <button
                        className={styles.btnSmall}
                        onClick={() => handleDownload(a.id, a.nome || a.arquivo)}
                      >
                        ↓ Download
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setModalAnexos(null)}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Novo Lançamento Manual ── */}
      {modalLanc && (
        <div className={styles.overlay} onClick={() => setModalLanc(false)}>
          <div className={styles.modalSm} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Novo Lançamento Manual</h2>
              <button className={styles.btnClose} onClick={() => setModalLanc(false)}>×</button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.fieldGrid}>
                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Tipo *</span>
                  <select className={styles.input} value={lancForm.tipo} onChange={setLanc("tipo")}>
                    <option value="PAGAR">A Pagar</option>
                    <option value="RECEBER">A Receber</option>
                  </select>
                </label>
                <label className={`${styles.field} ${styles.fieldFull}`}>
                  <span>Descrição *</span>
                  <input
                    className={styles.input}
                    value={lancForm.descricao}
                    onChange={setLanc("descricao")}
                    placeholder="Ex: Aluguel, Energia elétrica…"
                  />
                </label>
                <label className={styles.field}>
                  <span>Valor *</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className={styles.input}
                    value={lancForm.valor}
                    onChange={setLanc("valor")}
                    placeholder="0,00"
                  />
                </label>
                <label className={styles.field}>
                  <span>Vencimento *</span>
                  <input
                    type="date"
                    className={styles.input}
                    value={lancForm.vencimento}
                    onChange={setLanc("vencimento")}
                  />
                </label>
                <label className={styles.field}>
                  <span>Categoria</span>
                  <input
                    className={styles.input}
                    value={lancForm.categoria}
                    onChange={setLanc("categoria")}
                    placeholder="Ex: Fornecedores"
                  />
                </label>
                <label className={styles.field}>
                  <span>Nº de parcelas</span>
                  <input
                    type="number"
                    min="1"
                    max="48"
                    className={styles.input}
                    value={lancForm.parcelas}
                    onChange={setLanc("parcelas")}
                  />
                </label>
              </div>
              {erroLanc && <p className={styles.erro}>{erroLanc}</p>}
            </div>
            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setModalLanc(false)}>
                Cancelar
              </button>
              <button
                className={styles.btnPrimary}
                onClick={handleCriarLanc}
                disabled={savingLanc}
              >
                {savingLanc ? "Criando…" : "Criar Lançamento"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
