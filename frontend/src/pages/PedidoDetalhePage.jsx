import { Fragment, useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { coresApi, encaixesApi, gruposApi, modelosApi, pedidosApi } from "../services/api";
import Modal from "../components/Modal/Modal";
import ConfirmModal from "../components/ConfirmModal/ConfirmModal";
import { useToast } from "../contexts/ToastContext";
import styles from "./Page.module.css";
import ds from "./PedidoDetalhePage.module.css";

// ── Constantes ───────────────────────────────────────────────────────

const STATUS_OPTIONS = [
  { value: "rascunho",    label: "Rascunho",    cor: "cinza" },
  { value: "processando", label: "Em produção", cor: "azul"  },
  { value: "concluido",   label: "Concluído",   cor: "verde" },
];

const TAMANHOS_ORDEM = ["PP", "P", "M", "G", "GG", "XGG"];

const TIPO_LABEL = {
  simples: "Simples",
  par: "Par ↔",
  par_sem_espelho: "Par s/↔",
};

// ── Página principal ─────────────────────────────────────────────────

export default function PedidoDetalhePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { addToast } = useToast();

  const modoEditar = searchParams.get("modo") === "editar";

  const [pedido, setPedido] = useState(null);
  const [resumo, setResumo] = useState(null);
  const [carregando, setCarregando] = useState(true);

  // Modal de edição do cabeçalho
  const [editando, setEditando] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [salvandoEdit, setSalvandoEdit] = useState(false);
  const [erroEdit, setErroEdit] = useState(null);

  // Modal de adicionar tecido (hierarquia: Modelo → Cor → Lote)
  const [modalTecido, setModalTecido] = useState(false);
  const [modelosDisponiveis, setModelosDisponiveis] = useState([]);
  const [modeloSelecionado, setModeloSelecionado] = useState("");
  const [coresDisponiveis, setCoresDisponiveis] = useState([]);
  const [corSelecionada, setCorSelecionada] = useState("");
  const [lotesDisponiveis, setLotesDisponiveis] = useState([]);
  const [loteSelecionado, setLoteSelecionado] = useState("");
  const [recomendacaoLote, setRecomendacaoLote] = useState(null);
  const [salvandoTecido, setSalvandoTecido] = useState(false);
  const [erroTecido, setErroTecido] = useState(null);

  // Modal de adicionar peça
  const [modalPeca, setModalPeca] = useState(false);
  const [grupos, setGrupos] = useState([]);
  const [grupoSelecionado, setGrupoSelecionado] = useState(null);
  const [quantidades, setQuantidades] = useState({});
  const [tecidoPeca, setTecidoPeca] = useState("");
  const [salvandoPeca, setSalvandoPeca] = useState(false);
  const [erroPeca, setErroPeca] = useState(null);

  // Modal de editar quantidade de linha
  const [modalEditarQtd, setModalEditarQtd] = useState(false);
  const [linhaEditando, setLinhaEditando] = useState(null);
  const [novaQtd, setNovaQtd] = useState(1);
  const [salvandoQtd, setSalvandoQtd] = useState(false);
  const [erroQtd, setErroQtd] = useState(null);

  // ConfirmModals
  const [confirmRemoverTecido, setConfirmRemoverTecido] = useState(null);
  const [confirmRemoverPeca, setConfirmRemoverPeca] = useState(null);
  const [confirmExcluir, setConfirmExcluir] = useState(false);

  // PDF
  const [gerandoPdf, setGerandoPdf] = useState(false);

  // Encaixe
  const [gerandoEncaixe, setGerandoEncaixe] = useState(false);

  // ── Carregamento ────────────────────────────────────────────────────

  const carregar = useCallback(async () => {
    try {
      const [ped, res] = await Promise.all([
        pedidosApi.obter(id),
        pedidosApi.resumoCorte(id),
      ]);
      setPedido(ped);
      setResumo(res);
    } catch (ex) {
      addToast(ex.message, "erro");
    } finally {
      setCarregando(false);
    }
  }, [id, addToast]);

  useEffect(() => { carregar(); }, [carregar]);

  // ── Modo visualização / edição ───────────────────────────────────────

  function entrarModoEditar() {
    setSearchParams({ modo: "editar" });
  }

  function sairModoEditar() {
    setSearchParams({});
  }

  // ── Edição do cabeçalho ─────────────────────────────────────────────

  function abrirEdicao() {
    setEditForm({ cliente: pedido.cliente ?? "", data_pedido: pedido.data_pedido });
    setErroEdit(null);
    setEditando(true);
  }

  async function salvarEdicao(e) {
    e.preventDefault();
    setSalvandoEdit(true);
    setErroEdit(null);
    try {
      const atualizado = await pedidosApi.atualizar(id, {
        cliente: editForm.cliente || null,
        data_pedido: editForm.data_pedido,
      });
      setPedido(atualizado);
      setEditando(false);
      addToast("Pedido atualizado.", "sucesso");
    } catch (ex) {
      setErroEdit(ex.message);
    } finally {
      setSalvandoEdit(false);
    }
  }

  // ── Alterar status ──────────────────────────────────────────────────

  async function mudarStatus(e) {
    const novoStatus = e.target.value;
    try {
      const atualizado = await pedidosApi.alterarStatus(id, novoStatus);
      setPedido(atualizado);
      const label = STATUS_OPTIONS.find((s) => s.value === novoStatus)?.label ?? novoStatus;
      addToast(`Status alterado para "${label}".`, "sucesso");
    } catch (ex) {
      addToast(ex.message, "erro");
    }
  }

  // ── Tecidos ─────────────────────────────────────────────────────────

  function abrirModalTecido() {
    setModeloSelecionado("");
    setCoresDisponiveis([]);
    setCorSelecionada("");
    setLotesDisponiveis([]);
    setLoteSelecionado("");
    setRecomendacaoLote(null);
    setErroTecido(null);
    setModalTecido(true);
    modelosApi.listar().then(setModelosDisponiveis).catch(() => {});
  }

  function selecionarModelo(modeloId) {
    setModeloSelecionado(modeloId);
    setCorSelecionada("");
    setLotesDisponiveis([]);
    setLoteSelecionado("");
    setRecomendacaoLote(null);
    if (!modeloId) { setCoresDisponiveis([]); return; }
    const modelo = modelosDisponiveis.find((m) => m.id === modeloId);
    setCoresDisponiveis(modelo?.cores ?? []);
  }

  async function selecionarCor(corId) {
    setCorSelecionada(corId);
    setLoteSelecionado("");
    setRecomendacaoLote(null);
    if (!corId) { setLotesDisponiveis([]); return; }
    const cor = coresDisponiveis.find((c) => c.id === corId);
    const lotes = (cor?.lotes ?? []).filter((l) => l.status !== "arquivado");
    setLotesDisponiveis(lotes);
    const rec = await coresApi.recomendar(corId).catch(() => null);
    setRecomendacaoLote(rec);
    if (rec) setLoteSelecionado(rec.id);
  }

  async function confirmarAdicionarTecido(e) {
    e.preventDefault();
    if (!loteSelecionado) { setErroTecido("Selecione um lote."); return; }
    setSalvandoTecido(true);
    setErroTecido(null);
    try {
      const atualizado = await pedidosApi.adicionarTecido(id, loteSelecionado);
      setPedido(atualizado);
      const res = await pedidosApi.resumoCorte(id);
      setResumo(res);
      setModalTecido(false);
      addToast("Tecido adicionado ao pedido.", "sucesso");
    } catch (ex) {
      setErroTecido(ex.message);
    } finally {
      setSalvandoTecido(false);
    }
  }

  async function confirmarRemoverTecido() {
    const ptId = confirmRemoverTecido;
    setConfirmRemoverTecido(null);
    try {
      const atualizado = await pedidosApi.removerTecido(id, ptId);
      setPedido(atualizado);
      const res = await pedidosApi.resumoCorte(id);
      setResumo(res);
      addToast("Tecido removido.", "sucesso");
    } catch (ex) {
      addToast(ex.message, "erro");
    }
  }

  // ── Modal adicionar peça ────────────────────────────────────────────

  function abrirModalPeca() {
    setGrupoSelecionado(null);
    setQuantidades({});
    setTecidoPeca("");
    setErroPeca(null);
    setModalPeca(true);
    gruposApi.listar().then(setGrupos).catch(() => {});
  }

  function selecionarGrupo(grupoId) {
    const g = grupos.find((g) => g.id === grupoId);
    setGrupoSelecionado(g ?? null);
    if (g) {
      const tamanhos = [
        ...new Set(g.moldes.map((m) => m.tamanho).filter(Boolean)),
      ].sort((a, b) => TAMANHOS_ORDEM.indexOf(a) - TAMANHOS_ORDEM.indexOf(b));
      const init = {};
      tamanhos.forEach((t) => { init[t] = 0; });
      setQuantidades(init);
    }
  }

  async function confirmarPeca(e) {
    e.preventDefault();
    const qtdsValidas = Object.fromEntries(
      Object.entries(quantidades).filter(([, v]) => v > 0)
    );
    if (Object.keys(qtdsValidas).length === 0) {
      setErroPeca("Informe pelo menos uma quantidade maior que zero.");
      return;
    }
    setSalvandoPeca(true);
    setErroPeca(null);
    try {
      const atualizado = await pedidosApi.adicionarGrupoPecas(id, {
        grupo_id: grupoSelecionado.id,
        quantidades: qtdsValidas,
        cor_id: tecidoPeca || null,
      });
      setPedido(atualizado);
      const res = await pedidosApi.resumoCorte(id);
      setResumo(res);
      setModalPeca(false);
      addToast("Peças adicionadas ao pedido.", "sucesso");
    } catch (ex) {
      setErroPeca(ex.message);
    } finally {
      setSalvandoPeca(false);
    }
  }

  // ── Editar quantidade de linha ───────────────────────────────────────

  function abrirEditarQtd(gp) {
    setLinhaEditando(gp);
    setNovaQtd(gp.quantidade);
    setErroQtd(null);
    setModalEditarQtd(true);
  }

  async function confirmarEditarQtd(e) {
    e.preventDefault();
    if (!novaQtd || novaQtd <= 0) { setErroQtd("Quantidade deve ser maior que zero."); return; }
    setSalvandoQtd(true);
    setErroQtd(null);
    try {
      const atualizado = await pedidosApi.adicionarGrupoPecas(id, {
        grupo_id: linhaEditando.grupo_id,
        quantidades: { [linhaEditando.tamanho]: Number(novaQtd) },
        cor_id: linhaEditando.cor_id || null,
      });
      setPedido(atualizado);
      const res = await pedidosApi.resumoCorte(id);
      setResumo(res);
      setModalEditarQtd(false);
      addToast("Quantidade atualizada.", "sucesso");
    } catch (ex) {
      setErroQtd(ex.message);
    } finally {
      setSalvandoQtd(false);
    }
  }

  // ── Remover linha de peça ───────────────────────────────────────────

  async function confirmarRemoverPeca() {
    const { grupo_id, tamanho } = confirmRemoverPeca;
    setConfirmRemoverPeca(null);
    try {
      const atualizado = await pedidosApi.removerGrupoPecas(id, grupo_id, tamanho);
      setPedido(atualizado);
      const res = await pedidosApi.resumoCorte(id);
      setResumo(res);
      addToast(`Tamanho ${tamanho} removido do pedido.`, "sucesso");
    } catch (ex) {
      addToast(ex.message, "erro");
    }
  }

  // ── PDF ─────────────────────────────────────────────────────────────

  async function baixarPdf() {
    setGerandoPdf(true);
    try {
      const blob = await pedidosApi.relatorioPdf(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pedido-${pedido.num_pedido.replace(/\//g, "-")}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      addToast("Relatório PDF gerado com sucesso.", "sucesso");
    } catch (ex) {
      addToast(ex.message, "erro");
    } finally {
      setGerandoPdf(false);
    }
  }

  // ── Gerar encaixe ───────────────────────────────────────────────────

  async function gerarEncaixe() {
    setGerandoEncaixe(true);
    try {
      await encaixesApi.gerarAutomatico(id);
      navigate(`/encaixes/${id}`);
    } catch (ex) {
      addToast(ex.message, "erro");
    } finally {
      setGerandoEncaixe(false);
    }
  }

  // ── Excluir pedido ──────────────────────────────────────────────────

  async function confirmarExclusao() {
    setConfirmExcluir(false);
    try {
      await pedidosApi.deletar(id);
      addToast(`Pedido ${pedido.num_pedido} excluído.`, "sucesso");
      navigate("/pedidos");
    } catch (ex) {
      addToast(ex.message, "erro");
    }
  }

  // ── Render: loading ─────────────────────────────────────────────────

  if (carregando) return <div className={ds.loading}>Carregando pedido…</div>;
  if (!pedido) return (
    <div>
      <button className={styles.btnSecondary} onClick={() => navigate("/pedidos")}>← Voltar</button>
    </div>
  );

  const statusAtual = STATUS_OPTIONS.find((s) => s.value === pedido.status) ?? STATUS_OPTIONS[0];
  const tamanhosPorGrupo = grupoSelecionado
    ? [...new Set(grupoSelecionado.moldes.map((m) => m.tamanho).filter(Boolean))].sort(
        (a, b) => TAMANHOS_ORDEM.indexOf(a) - TAMANHOS_ORDEM.indexOf(b)
      )
    : [];
  const resumoAgrupadoPorTecido = resumo
    ? agruparResumoPorTecido(resumo.itens, resumo.estimativa_por_tecido)
    : [];

  // ── Render principal ─────────────────────────────────────────────────

  return (
    <div className={ds.pagina}>

      {/* ── Breadcrumb + modo ── */}
      <div className={ds.topBar}>
        <button className={ds.voltar} onClick={() => navigate("/pedidos")}>← Pedidos</button>
        {modoEditar ? (
          <div className={ds.modoEditarBanner}>
            <span className={ds.modoEditarLabel}>✏ Modo edição</span>
            <button className={ds.btnSairEdicao} onClick={sairModoEditar}>Sair da edição</button>
          </div>
        ) : (
          <button className={ds.btnEntrarEdicao} onClick={entrarModoEditar}>✏ Editar pedido</button>
        )}
      </div>

      {/* ══ CABEÇALHO DO PEDIDO ══ */}
      <div className={ds.cabecalho}>
        <div className={ds.cabecalhoTopo}>
          <div>
            <h1 className={ds.tituloPedido}>Pedido {pedido.num_pedido}</h1>
            {pedido.cliente && <p className={ds.cliente}>{pedido.cliente}</p>}
          </div>
          <div className={ds.cabecalhoAcoes}>
            {modoEditar ? (
              <div className={ds.statusSelectWrapper}>
                <select
                  className={`${ds.statusSelect} ${ds[`statusSelect_${statusAtual.cor}`]}`}
                  value={pedido.status}
                  onChange={mudarStatus}
                >
                  {STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            ) : (
              <span className={`${ds.badge} ${ds[`badge_${statusAtual.cor}`]}`}>
                {statusAtual.label}
              </span>
            )}
            {modoEditar && (
              <button className={styles.btnSecondary} onClick={abrirEdicao}>Editar dados</button>
            )}
          </div>
        </div>

        <div className={ds.metaGrid}>
          <div className={ds.metaItem}>
            <span className={ds.metaLabel}>Data</span>
            <span className={ds.metaValor}>{pedido.data_pedido}</span>
          </div>
          <div className={ds.metaItem}>
            <span className={ds.metaLabel}>Tecidos</span>
            <span className={ds.metaValor}>
              {pedido.tecidos.length > 0 ? pedido.tecidos.map((t) => t.nome).join(", ") : "—"}
            </span>
          </div>
          <div className={ds.metaItem}>
            <span className={ds.metaLabel}>Grupos</span>
            <span className={ds.metaValor}>
              {new Set(pedido.grupos_pecas.map((g) => g.grupo_id)).size || "—"}
            </span>
          </div>
        </div>
      </div>

      {/* ══ TECIDOS DO PEDIDO ══ */}
      <section className={ds.secao}>
        <div className={ds.secaoHeader}>
          <h2 className={ds.secaoTitulo}>Tecidos do Pedido</h2>
          {modoEditar && (
            <button className={styles.btnNovo} onClick={abrirModalTecido}>+ Adicionar Tecido</button>
          )}
        </div>
        {pedido.tecidos.length === 0 ? (
          <p className={ds.vazio}>Nenhum tecido adicionado.{modoEditar ? " Clique em \"+Adicionar Tecido\"." : ""}</p>
        ) : (
          <div className={ds.tecidosList}>
            {pedido.tecidos.map((t) => (
              <div key={t.id} className={ds.tecidoCard}>
                <div className={ds.tecidoInfo}>
                  <span className={ds.tecidoNome}>{t.nome}</span>
                  <span className={ds.tecidoMeta}>
                    {t.codigo_lote
                      ? `Lote ${t.codigo_lote} · ${Number(t.peso_disponivel_kg).toFixed(1)} kg disp. · R$ ${Number(t.valor_por_kg).toFixed(2)}/kg`
                      : `${t.largura_util_cm} cm · ${t.gramatura_g_m2} g/m² · R$ ${Number(t.valor_por_kg).toFixed(2)}/kg${t.encolhimento_pct > 0 ? ` · Enc: ${t.encolhimento_pct}%` : ""}`
                    }
                  </span>
                </div>
                {modoEditar && (
                  <button
                    className={ds.btnRemoverTecido}
                    onClick={() => setConfirmRemoverTecido(t.pt_id)}
                    title="Remover tecido"
                  >✕</button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ══ PEÇAS DO PEDIDO ══ */}
      <section className={ds.secao}>
        <div className={ds.secaoHeader}>
          <h2 className={ds.secaoTitulo}>Peças do Pedido</h2>
          {modoEditar && (
            <button className={styles.btnNovo} onClick={abrirModalPeca}>+ Adicionar Peça</button>
          )}
        </div>
        {pedido.grupos_pecas.length === 0 ? (
          <p className={ds.vazio}>Nenhuma peça adicionada.{modoEditar ? " Clique em \"+Adicionar Peça\"." : ""}</p>
        ) : (
          <table className={styles.tabela}>
            <thead>
              <tr>
                <th>Grupo</th>
                <th>Tamanho</th>
                <th>Qtd. produção</th>
                <th>Tecido</th>
                {modoEditar && <th></th>}
              </tr>
            </thead>
            <tbody>
              {renderGruposPecas(pedido.grupos_pecas, modoEditar, abrirEditarQtd, setConfirmRemoverPeca, ds)}
            </tbody>
          </table>
        )}
      </section>

      {/* ══ RESUMO DO CORTE ══ */}
      {resumo && (
        <section className={ds.secao}>
          <h2 className={ds.secaoTitulo}>Resumo do Corte</h2>

          {resumo.itens.length === 0 ? (
            <p className={ds.vazio}>Adicione peças ao pedido para ver o resumo.</p>
          ) : (
            <>
              <table className={`${styles.tabela} ${ds.tabelaResumo}`}>
                <thead>
                  <tr>
                    <th>Grupo</th>
                    <th>Parte</th>
                    <th>Tam.</th>
                    <th>Tipo</th>
                    <th>Produção</th>
                    <th>Corte</th>
                    <th>Área (cm²)</th>
                  </tr>
                </thead>
                <tbody>
                  {resumoAgrupadoPorTecido.map(({ tecidoNome, itens: tItens, totalCorte, totalArea, estimativa }) => (
                    <Fragment key={`tec-${tecidoNome}`}>
                      {/* Cabeçalho do grupo de tecido */}
                      <tr className={ds.tecidoHeaderRow}>
                        <td colSpan={7}>
                          <span className={ds.tecidoHeaderLabel}>
                            {tecidoNome ?? "Sem tecido atribuído"}
                          </span>
                          <span className={ds.tecidoHeaderMeta}>
                            {totalCorte} peças · {totalArea.toFixed(0)} cm²
                            {estimativa && (
                              <>
                                {" · "}<strong>{estimativa.estimativa_metros.toFixed(2)} m</strong>
                                {" · "}{estimativa.estimativa_peso_kg.toFixed(3)} kg
                                {" · "}
                                <strong className={ds.estimativaCustoInline}>
                                  R$ {Number(estimativa.estimativa_custo).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                                </strong>
                              </>
                            )}
                          </span>
                        </td>
                      </tr>

                      {/* Itens agrupados por parte */}
                      {agruparPorParte(tItens).map(({ parte, itens: parteItens }) => (
                        <Fragment key={`parte-${tecidoNome}-${parte}`}>
                          <tr className={ds.subheaderRow}>
                            <td colSpan={7}>
                              <span className={ds.parteLabel}>{parte || "Sem parte"}</span>
                            </td>
                          </tr>
                          {parteItens.map((item) => (
                            <tr key={item.molde_id}>
                              <td className={ds.grupoNome}>{item.grupo_nome}</td>
                              <td>{item.peca ?? "—"}</td>
                              <td><span className={ds.tamanhoTag}>{item.tamanho ?? "—"}</span></td>
                              <td className={ds.tipoCorte}>{TIPO_LABEL[item.tipo_corte] ?? item.tipo_corte}</td>
                              <td>{item.quantidade_producao} un.</td>
                              <td className={ds.qtdCorte}>
                                <strong>{item.quantidade_corte}</strong>
                                {item.tipo_corte !== "simples" && (
                                  <span className={ds.qtdDetalhe}>
                                    {" "}(×{item.quantidade_corte / item.quantidade_producao})
                                  </span>
                                )}
                              </td>
                              <td>{item.area_cm2 != null ? Number(item.area_cm2).toFixed(1) : "—"}</td>
                            </tr>
                          ))}
                        </Fragment>
                      ))}
                    </Fragment>
                  ))}
                </tbody>
              </table>

              {/* Totais globais */}
              <div className={ds.totais}>
                <div className={ds.totalItem}>
                  <span className={ds.totalLabel}>Peças a cortar</span>
                  <span className={ds.totalValor}>{resumo.total_pecas_corte}</span>
                </div>
                <div className={ds.totalItem}>
                  <span className={ds.totalLabel}>Área total</span>
                  <span className={ds.totalValor}>{Number(resumo.total_area_cm2).toFixed(0)} cm²</span>
                </div>
                {resumo.estimativa_metros != null && (
                  <>
                    <div className={ds.totalItem}>
                      <span className={ds.totalLabel}>Metros totais</span>
                      <span className={ds.totalValor}>{resumo.estimativa_metros.toFixed(2)} m</span>
                    </div>
                    <div className={ds.totalItem}>
                      <span className={ds.totalLabel}>Peso total</span>
                      <span className={ds.totalValor}>{resumo.estimativa_peso_kg.toFixed(3)} kg</span>
                    </div>
                    <div className={`${ds.totalItem} ${ds.totalDestaque}`}>
                      <span className={ds.totalLabel}>Custo total estimado</span>
                      <span className={ds.totalValor}>
                        R$ {Number(resumo.estimativa_custo).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  </>
                )}
              </div>
            </>
          )}

          {/* Botões de ação */}
          <div className={ds.acoesPrincipais}>
            <button
              className={ds.btnRelatorio}
              onClick={baixarPdf}
              disabled={gerandoPdf || resumo.itens.length === 0}
            >
              {gerandoPdf ? "Gerando…" : "↓ Baixar Relatório PDF"}
            </button>
            <button
              className={`${ds.btnEncaixe}${gerandoEncaixe ? ` ${ds.btnEncaixeCarregando}` : ""}`}
              onClick={gerarEncaixe}
              disabled={gerandoEncaixe || resumo.itens.length === 0}
              title={resumo.itens.length === 0 ? "Adicione peças ao pedido primeiro" : undefined}
            >
              {gerandoEncaixe
                ? "Calculando melhor encaixe… até 2 minutos"
                : "Gerar Encaixe"}
            </button>
          </div>
        </section>
      )}

      {/* ══ RODAPÉ — zona de perigo (apenas no modo edição) ══ */}
      {modoEditar && (
        <div className={ds.rodapePerigo}>
          <button className={ds.btnExcluir} onClick={() => setConfirmExcluir(true)}>
            Excluir Pedido
          </button>
        </div>
      )}

      {/* ══ MODAIS ══ */}

      {editando && (
        <Modal titulo="Editar Pedido" onClose={() => setEditando(false)}>
          <form className={styles.form} onSubmit={salvarEdicao}>
            {erroEdit && <p className={styles.erroForm}>{erroEdit}</p>}
            <div className={styles.fileiraDupla}>
              <div className={styles.campo}>
                <label className={styles.label}>Cliente</label>
                <input
                  className={styles.input}
                  value={editForm.cliente}
                  onChange={(e) => setEditForm((p) => ({ ...p, cliente: e.target.value }))}
                />
              </div>
              <div className={styles.campo}>
                <label className={styles.label}>Data *</label>
                <input
                  className={styles.input}
                  type="date"
                  value={editForm.data_pedido}
                  onChange={(e) => setEditForm((p) => ({ ...p, data_pedido: e.target.value }))}
                  required
                />
              </div>
            </div>
            <div className={styles.formActions}>
              <button type="button" className={styles.btnSecondary} onClick={() => setEditando(false)}>Cancelar</button>
              <button type="submit" className={styles.btnPrimary} disabled={salvandoEdit}>
                {salvandoEdit ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {modalTecido && (
        <Modal titulo="Adicionar Tecido ao Pedido" onClose={() => setModalTecido(false)}>
          <form className={styles.form} onSubmit={confirmarAdicionarTecido}>
            {erroTecido && <p className={styles.erroForm}>{erroTecido}</p>}

            <div className={styles.campo}>
              <label className={styles.label}>Modelo *</label>
              <select
                className={styles.select}
                value={modeloSelecionado}
                onChange={(e) => selecionarModelo(e.target.value)}
                autoFocus
              >
                <option value="">— Selecione o modelo —</option>
                {modelosDisponiveis.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nome}{m.tipo ? ` (${m.tipo})` : ""}
                  </option>
                ))}
              </select>
            </div>

            {modeloSelecionado && (
              <div className={styles.campo}>
                <label className={styles.label}>Cor *</label>
                <select
                  className={styles.select}
                  value={corSelecionada}
                  onChange={(e) => selecionarCor(e.target.value)}
                >
                  <option value="">— Selecione a cor —</option>
                  {coresDisponiveis.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome_cor} — {c.largura_util_cm} cm · {c.gramatura_g_m2} g/m²
                    </option>
                  ))}
                </select>
              </div>
            )}

            {corSelecionada && lotesDisponiveis.length > 0 && (
              <div className={styles.campo}>
                <label className={styles.label}>Lote *</label>
                {recomendacaoLote && (
                  <p className={ds.recomendacaoMsg}>
                    Recomendado: {recomendacaoLote.codigo_lote} — {Number(recomendacaoLote.peso_disponivel_kg).toFixed(1)} kg disponíveis
                  </p>
                )}
                <select
                  className={styles.select}
                  value={loteSelecionado}
                  onChange={(e) => setLoteSelecionado(e.target.value)}
                >
                  <option value="">— Selecione o lote —</option>
                  {lotesDisponiveis.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.codigo_lote} · {Number(l.peso_disponivel_kg).toFixed(1)} kg · R$ {Number(l.valor_kg).toFixed(2)}/kg · {l.status}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {corSelecionada && lotesDisponiveis.length === 0 && (
              <p className={ds.avisoVazio}>Nenhum lote disponível para esta cor.</p>
            )}

            <div className={styles.formActions}>
              <button type="button" className={styles.btnSecondary} onClick={() => setModalTecido(false)}>Cancelar</button>
              <button type="submit" className={styles.btnPrimary} disabled={salvandoTecido || !loteSelecionado}>
                {salvandoTecido ? "Adicionando..." : "Adicionar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {modalPeca && (
        <Modal titulo="Adicionar Peça ao Pedido" onClose={() => setModalPeca(false)}>
          <form className={styles.form} onSubmit={confirmarPeca}>
            {erroPeca && <p className={styles.erroForm}>{erroPeca}</p>}

            <div className={styles.campo}>
              <label className={styles.label}>Grupo de molde *</label>
              <select
                className={styles.select}
                value={grupoSelecionado?.id ?? ""}
                onChange={(e) => selecionarGrupo(e.target.value)}
                required
              >
                <option value="">— Selecione um grupo —</option>
                {grupos.map((g) => (
                  <option key={g.id} value={g.id}>{g.nome}</option>
                ))}
              </select>
            </div>

            <div className={styles.campo}>
              <label className={styles.label}>Tecido desta peça</label>
              <select
                className={styles.select}
                value={tecidoPeca}
                onChange={(e) => setTecidoPeca(e.target.value)}
              >
                <option value="">— Sem tecido atribuído —</option>
                {pedido.tecidos.map((t) => (
                  <option key={t.cor_id ?? t.id} value={t.cor_id ?? ""}>
                    {t.nome}{t.codigo_lote ? ` (${t.codigo_lote})` : ""}
                  </option>
                ))}
              </select>
              {pedido.tecidos.length === 0 && (
                <p className={ds.avisoVazio}>Adicione tecidos ao pedido para atribuir aqui.</p>
              )}
            </div>

            {grupoSelecionado && tamanhosPorGrupo.length > 0 && (
              <div className={styles.campo}>
                <label className={styles.label}>Quantidades por tamanho</label>
                <table className={ds.tabelaQtd}>
                  <thead>
                    <tr><th>Tamanho</th><th>Quantidade</th></tr>
                  </thead>
                  <tbody>
                    {tamanhosPorGrupo.map((t) => (
                      <tr key={t}>
                        <td><span className={ds.tamanhoTag}>{t}</span></td>
                        <td>
                          <input
                            className={`${styles.input} ${ds.inputQtd}`}
                            type="number"
                            min={0}
                            value={quantidades[t] ?? 0}
                            onChange={(e) =>
                              setQuantidades((prev) => ({ ...prev, [t]: Number(e.target.value) }))
                            }
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {grupoSelecionado && tamanhosPorGrupo.length === 0 && (
              <p className={ds.avisoVazio}>Este grupo não possui moldes com tamanhos cadastrados.</p>
            )}

            <div className={styles.formActions}>
              <button type="button" className={styles.btnSecondary} onClick={() => setModalPeca(false)}>Cancelar</button>
              <button type="submit" className={styles.btnPrimary} disabled={salvandoPeca || !grupoSelecionado}>
                {salvandoPeca ? "Salvando..." : "Confirmar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {modalEditarQtd && linhaEditando && (
        <Modal titulo="Editar Quantidade" onClose={() => setModalEditarQtd(false)}>
          <form className={styles.form} onSubmit={confirmarEditarQtd}>
            {erroQtd && <p className={styles.erroForm}>{erroQtd}</p>}
            <p className={ds.editarQtdInfo}>
              <strong>{linhaEditando.grupo_nome}</strong> — tamanho{" "}
              <span className={ds.tamanhoTag}>{linhaEditando.tamanho}</span>
            </p>
            <div className={styles.campo}>
              <label className={styles.label}>Quantidade de produção *</label>
              <input
                className={styles.input}
                type="number"
                min={1}
                value={novaQtd}
                onChange={(e) => setNovaQtd(Number(e.target.value))}
                required
                autoFocus
              />
            </div>
            <div className={styles.formActions}>
              <button type="button" className={styles.btnSecondary} onClick={() => setModalEditarQtd(false)}>Cancelar</button>
              <button type="submit" className={styles.btnPrimary} disabled={salvandoQtd}>
                {salvandoQtd ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ConfirmModals */}
      <ConfirmModal
        isOpen={!!confirmRemoverTecido}
        titulo="Remover tecido"
        mensagem="Remover este tecido do pedido? As peças vinculadas a ele perderão a atribuição."
        labelConfirmar="Remover"
        variante="perigo"
        onConfirmar={confirmarRemoverTecido}
        onCancelar={() => setConfirmRemoverTecido(null)}
      />
      <ConfirmModal
        isOpen={!!confirmRemoverPeca}
        titulo="Remover peça"
        mensagem={confirmRemoverPeca
          ? `Remover tamanho ${confirmRemoverPeca.tamanho} do grupo "${confirmRemoverPeca.grupo_nome}" deste pedido?`
          : ""}
        labelConfirmar="Remover"
        variante="perigo"
        onConfirmar={confirmarRemoverPeca}
        onCancelar={() => setConfirmRemoverPeca(null)}
      />
      <ConfirmModal
        isOpen={confirmExcluir}
        titulo="Excluir pedido"
        mensagem={`Excluir o pedido "${pedido.num_pedido}"? Esta ação não pode ser desfeita.`}
        labelConfirmar="Excluir pedido"
        variante="perigo"
        onConfirmar={confirmarExclusao}
        onCancelar={() => setConfirmExcluir(false)}
      />
    </div>
  );
}

// ── Funções auxiliares ────────────────────────────────────────────────

function agruparResumoPorTecido(itens, estimativas = []) {
  const estMap = Object.fromEntries(estimativas.map((e) => [e.tecido_id, e]));
  const map = new Map();
  for (const item of itens) {
    const key = item.tecido_nome ?? null;
    if (!map.has(key)) {
      map.set(key, {
        tecidoId: item.tecido_id,
        tecidoNome: item.tecido_nome,
        estimativa: item.tecido_id ? (estMap[item.tecido_id] ?? null) : null,
        itens: [],
        totalCorte: 0,
        totalArea: 0,
      });
    }
    const g = map.get(key);
    g.itens.push(item);
    g.totalCorte += item.quantidade_corte;
    g.totalArea += (item.area_cm2 ?? 0) * item.quantidade_corte;
  }
  return [...map.values()];
}

function agruparPorParte(itens) {
  const map = new Map();
  for (const item of itens) {
    const parte = item.peca || "—";
    if (!map.has(parte)) map.set(parte, { parte, itens: [] });
    map.get(parte).itens.push(item);
  }
  return [...map.values()];
}

function renderGruposPecas(grupos_pecas, modoEditar, onEditar, onRemover, ds) {
  const rows = [];
  let ultimoGrupo = null;
  for (const gp of grupos_pecas) {
    const isNovo = gp.grupo_nome !== ultimoGrupo;
    ultimoGrupo = gp.grupo_nome;
    rows.push(
      <tr key={`${gp.grupo_id}-${gp.tamanho}`} className={isNovo ? ds.primeiraLinhGrupo : ""}>
        <td className={ds.grupoNome}>{isNovo ? gp.grupo_nome : ""}</td>
        <td><span className={ds.tamanhoTag}>{gp.tamanho}</span></td>
        <td>{gp.quantidade} unid.</td>
        <td>
          {gp.tecido_nome
            ? <span className={ds.tecidoTagPeca}>{gp.tecido_nome}</span>
            : <span className={ds.semTecidoTag}>—</span>
          }
        </td>
        {modoEditar && (
          <td className={ds.acoesPeca}>
            <button className={ds.btnEditar} onClick={() => onEditar(gp)}>Editar</button>
            <button className={ds.btnRemover} onClick={() => onRemover({ grupo_id: gp.grupo_id, tamanho: gp.tamanho, grupo_nome: gp.grupo_nome })}>✕</button>
          </td>
        )}
      </tr>
    );
  }
  return rows;
}
