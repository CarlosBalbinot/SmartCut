import { useState, useEffect } from "react";
import { getGrupos } from "../api/moldes";
import {
  createPrecificacao,
  deletePrecificacao,
  getConfigPrecificacao,
  getCustosFixos,
  getPrecificacoes,
  updatePrecificacao,
} from "../api/precificacoes";
import Modal from "../components/Modal/Modal";
import styles from "./PrecificacaoPage.module.css";

/* ── Helpers ── */
const R = (v) =>
  v != null ? `R$ ${parseFloat(v).toFixed(2).replace(".", ",")}` : "—";
const Pct = (v) =>
  v != null ? `${(parseFloat(v) * 100).toFixed(1)}%` : "—";

function calcLocal(form, config, custos) {
  // custo tecido
  let custo_tecido = 0;
  if (form.usar_kg && (parseFloat(form.valor_kg_tecido) > 0) && (parseFloat(form.pecas_por_kg) > 0)) {
    custo_tecido = parseFloat(form.valor_kg_tecido) / parseFloat(form.pecas_por_kg);
  } else if (form.usar_custo_encaixe) {
    custo_tecido = parseFloat(form.custo_tecido_encaixe) || 0;
  } else {
    custo_tecido = parseFloat(form.custo_tecido_manual) || 0;
  }

  // custo linha (por metro)
  const metros_overlock = parseFloat(form.metros_linha_overlock) || 0;
  const metros_reta = parseFloat(form.metros_linha_reta) || 0;
  const metros_rolo_ov = parseFloat(custos?.metros_rolo_overlock) || 1;
  const metros_rolo_re = parseFloat(custos?.metros_rolo_reta) || 1;
  const custo_metro_overlock = (parseFloat(custos?.custo_rolo_overlock) || 0) / metros_rolo_ov;
  const custo_metro_reta = (parseFloat(custos?.custo_rolo_reta) || 0) / metros_rolo_re;
  const custo_overlock = metros_overlock * custo_metro_overlock;
  const custo_reta = metros_reta * custo_metro_reta;

  // custo gasolina
  let custo_gasolina = 0;
  const dist = parseFloat(custos?.distancia_costureira_km) || 0;
  const num_viagens = parseFloat(custos?.num_viagens) || 2;
  const consumo = parseFloat(custos?.consumo_veiculo_km_l) || 0;
  const preco_comb = parseFloat(custos?.preco_combustivel) || 0;
  const pecas_viagem = parseFloat(form.pecas_por_viagem) || 50;
  if (dist > 0 && consumo > 0 && preco_comb > 0 && pecas_viagem > 0) {
    custo_gasolina = (dist * 2 * num_viagens / consumo) * preco_comb / pecas_viagem;
  }

  // custo saquinho (automático, 1 por peça)
  const unid_saq = parseFloat(custos?.unidades_saquinho_lote) || 1;
  const custo_saquinho = (parseFloat(custos?.custo_saquinho_lote) || 0) / unid_saq;

  // custo caixa
  let custo_caixa = 0;
  const custo_cx = parseFloat(custos?.custo_caixa) || 0;
  const pecas_cx = parseFloat(custos?.pecas_por_caixa) || 0;
  if (custo_cx > 0 && pecas_cx > 0) {
    custo_caixa = custo_cx / pecas_cx;
  }

  const custo_costura = parseFloat(form.custo_costura) || 0;
  const custo_etiqueta = parseFloat(config?.custo_etiqueta) || 0;

  const custo_base = custo_tecido + custo_costura + custo_overlock + custo_reta + custo_gasolina + custo_saquinho + custo_caixa + custo_etiqueta;

  const aliquota = (parseFloat(config?.aliquota_simples) || 0) / 100;
  const margem = (parseFloat(form.margem_desejada) || 60) / 100;
  const denom = 1 - aliquota - margem;

  const base = { custo_tecido, custo_costura, custo_overlock, custo_reta, custo_metro_overlock, custo_metro_reta, custo_gasolina, custo_saquinho, custo_caixa, custo_etiqueta, custo_base };

  if (denom <= 0 || custo_base <= 0) return { ...base, preco: null, imposto: null, lucro: null };

  const preco = custo_base / denom;
  const imposto = preco * aliquota;
  const lucro = preco - custo_base - imposto;
  return { ...base, preco, imposto, lucro };
}

const FORM_VAZIO = {
  tamanho: "",
  faixa_tamanho: "padrao",
  usar_kg: false,
  valor_kg_tecido: "",
  pecas_por_kg: "",
  usar_custo_encaixe: false,
  custo_tecido_manual: "",
  custo_tecido_encaixe: "",
  custo_costura: "",
  metros_linha_overlock: "",
  metros_linha_reta: "",
  pecas_por_viagem: "50",
  margem_desejada: "60",
  preco_venda_final: "",
  preco_final_manual: false,
};

export default function PrecificacaoPage() {
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(null);

  const [config, setConfig] = useState(null);
  const [custos, setCustos] = useState(null);

  const [grupos, setGrupos] = useState([]);
  const [expandidos, setExpandidos] = useState({});
  const [precsPorGrupo, setPrecsPorGrupo] = useState({});
  const [carregando, setCarregando] = useState({});

  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(FORM_VAZIO);
  const [calc, setCalc] = useState({});
  const [salvando, setSalvando] = useState(false);
  const [erroModal, setErroModal] = useState(null);

  const [confirmarDeletar, setConfirmarDeletar] = useState(null);

  useEffect(() => {
    Promise.all([getGrupos(), getConfigPrecificacao(), getCustosFixos()])
      .then(([gs, cfg, cst]) => {
        setGrupos(gs);
        setConfig(cfg);
        setCustos(cst);
      })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, []);

  /* ── Cálculo em tempo real no modal ── */
  useEffect(() => {
    if (!modal || !config) return;
    const resultado = calcLocal(form, config, custos);
    setCalc(resultado);
    if (!form.preco_final_manual) {
      setForm((f) => ({ ...f, preco_venda_final: resultado.preco ? resultado.preco.toFixed(2) : "" }));
    }
  }, [
    form.usar_kg, form.valor_kg_tecido, form.pecas_por_kg,
    form.custo_tecido_manual, form.custo_tecido_encaixe, form.usar_custo_encaixe,
    form.custo_costura, form.metros_linha_overlock, form.metros_linha_reta,
    form.pecas_por_viagem, form.margem_desejada,
    modal, config, custos,
  ]);

  /* ── Accordion ── */
  const toggleGrupo = async (grupoId) => {
    const abrindo = !expandidos[grupoId];
    setExpandidos((e) => ({ ...e, [grupoId]: abrindo }));
    if (abrindo && !precsPorGrupo[grupoId]) {
      setCarregando((c) => ({ ...c, [grupoId]: true }));
      try {
        const data = await getPrecificacoes(grupoId);
        setPrecsPorGrupo((p) => ({ ...p, [grupoId]: data }));
      } catch {
        setPrecsPorGrupo((p) => ({ ...p, [grupoId]: [] }));
      } finally {
        setCarregando((c) => ({ ...c, [grupoId]: false }));
      }
    }
  };

  /* ── Modal ── */
  const abrirCriar = (grupo) => {
    setForm({ ...FORM_VAZIO, grupo_id: grupo.id });
    setErroModal(null);
    setModal({ modo: "criar", grupoId: grupo.id, grupoNome: grupo.nome });
  };

  const abrirEditar = (grupo, prec) => {
    const usaKg = !!(prec.valor_kg_tecido && prec.pecas_por_kg);
    setForm({
      grupo_id: prec.grupo_id,
      tamanho: prec.tamanho,
      faixa_tamanho: prec.faixa_tamanho ?? "padrao",
      usar_kg: usaKg,
      valor_kg_tecido: prec.valor_kg_tecido ?? "",
      pecas_por_kg: prec.pecas_por_kg ?? "",
      usar_custo_encaixe: prec.usar_custo_encaixe,
      custo_tecido_manual: prec.custo_tecido_manual ?? "",
      custo_tecido_encaixe: prec.custo_tecido_encaixe ?? "",
      custo_costura: prec.custo_costura ?? "",
      metros_linha_overlock: parseFloat(prec.metros_linha_overlock ?? 0) || "",
      metros_linha_reta: parseFloat(prec.metros_linha_reta ?? 0) || "",
      pecas_por_viagem: String(prec.pecas_por_viagem ?? 50),
      margem_desejada: ((parseFloat(prec.margem_desejada) || 0.6) * 100).toFixed(0),
      preco_venda_final: prec.preco_venda_final ?? "",
      preco_final_manual: !!prec.preco_venda_final,
    });
    setErroModal(null);
    setModal({ modo: "editar", grupoId: grupo.id, grupoNome: grupo.nome, prec });
  };

  const salvarModal = async () => {
    if (!form.tamanho && modal.modo === "criar") { setErroModal("Informe o tamanho."); return; }
    setSalvando(true);
    setErroModal(null);
    try {
      const payload = {
        grupo_id: form.grupo_id,
        tamanho: form.tamanho?.trim().toUpperCase() || modal.prec?.tamanho,
        faixa_tamanho: form.faixa_tamanho || "padrao",
        usar_kg: undefined,
        valor_kg_tecido: form.usar_kg && form.valor_kg_tecido !== "" ? parseFloat(form.valor_kg_tecido) : null,
        pecas_por_kg: form.usar_kg && form.pecas_por_kg !== "" ? parseFloat(form.pecas_por_kg) : null,
        usar_custo_encaixe: !form.usar_kg && form.usar_custo_encaixe,
        custo_tecido_manual: !form.usar_kg && !form.usar_custo_encaixe && form.custo_tecido_manual !== "" ? parseFloat(form.custo_tecido_manual) : null,
        custo_tecido_encaixe: !form.usar_kg && form.usar_custo_encaixe && form.custo_tecido_encaixe !== "" ? parseFloat(form.custo_tecido_encaixe) : null,
        custo_costura: parseFloat(form.custo_costura) || 0,
        metros_linha_overlock: parseFloat(form.metros_linha_overlock) || 0,
        metros_linha_reta: parseFloat(form.metros_linha_reta) || 0,
        pecas_por_viagem: parseInt(form.pecas_por_viagem) || 50,
        margem_desejada: (parseFloat(form.margem_desejada) || 60) / 100,
        preco_venda_final: form.preco_venda_final !== "" ? parseFloat(form.preco_venda_final) : null,
      };
      delete payload.usar_kg;

      let result;
      if (modal.modo === "criar") {
        result = await createPrecificacao(payload);
        setPrecsPorGrupo((p) => {
          const lista = p[modal.grupoId] || [];
          const idx = lista.findIndex((x) => x.tamanho === result.tamanho);
          const nova = idx >= 0
            ? lista.map((x, i) => (i === idx ? result : x))
            : [...lista, result].sort((a, b) => a.tamanho.localeCompare(b.tamanho));
          return { ...p, [modal.grupoId]: nova };
        });
      } else {
        const updatePayload = { ...payload };
        delete updatePayload.grupo_id;
        delete updatePayload.tamanho;
        result = await updatePrecificacao(modal.prec.id, updatePayload);
        setPrecsPorGrupo((p) => ({
          ...p,
          [modal.grupoId]: (p[modal.grupoId] || []).map((x) => x.id === result.id ? result : x),
        }));
      }
      setModal(null);
    } catch (e) {
      setErroModal(e.message);
    } finally {
      setSalvando(false);
    }
  };

  const confirmarDeletarPrec = async (grupoId, precId) => {
    try {
      await deletePrecificacao(precId);
      setPrecsPorGrupo((p) => ({
        ...p,
        [grupoId]: (p[grupoId] || []).filter((x) => x.id !== precId),
      }));
    } catch (e) {
      alert(e.message);
    } finally {
      setConfirmarDeletar(null);
    }
  };

  /* ── CSV ── */
  const exportarCSV = () => {
    const linhas = [["Modelo", "Tamanho", "Faixa", "Custo", "Imposto", "Preço", "Lucro", "Margem%"]];
    grupos.forEach((g) => {
      (precsPorGrupo[g.id] || []).forEach((p) => {
        const r = calcLocal(
          { ...p, usar_kg: !!(p.valor_kg_tecido && p.pecas_por_kg), margem_desejada: parseFloat(p.margem_desejada) * 100 },
          config, custos
        );
        const preco = p.preco_venda_final || r.preco;
        linhas.push([g.nome, p.tamanho, p.faixa_tamanho || "padrao",
          r.custo_base?.toFixed(2) || "", r.imposto?.toFixed(2) || "",
          preco?.toFixed(2) || "", r.lucro?.toFixed(2) || "",
          r.lucro && preco ? ((r.lucro / preco) * 100).toFixed(1) : ""]);
      });
    });
    const csv = linhas.map((l) => l.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "precificacao.csv"; a.click();
    URL.revokeObjectURL(url);
  };

  /* ── Resumo ── */
  const resumo = grupos.flatMap((g) =>
    (precsPorGrupo[g.id] || []).map((p) => {
      const r = calcLocal(
        { ...p, usar_kg: !!(p.valor_kg_tecido && p.pecas_por_kg), margem_desejada: parseFloat(p.margem_desejada) * 100 },
        config, custos
      );
      const preco = p.preco_venda_final || r.preco;
      return { grupo: g.nome, tamanho: p.tamanho, faixa: p.faixa_tamanho || "padrao", custo: r.custo_base, imposto: r.imposto, preco, lucro: r.lucro, margem: preco && r.lucro != null ? (r.lucro / preco) : null };
    })
  );

  if (loading) return (
    <div className="sc-page">
      <div className="sc-page-header"><h1>Precificação</h1></div>
      <p className={styles.loading}>Carregando…</p>
    </div>
  );
  if (erro) return (
    <div className="sc-page">
      <div className="sc-page-header"><h1>Precificação</h1></div>
      <p className={styles.erro}>{erro}</p>
    </div>
  );

  const tipoTecidoAtivo = form.usar_kg ? "kg" : form.usar_custo_encaixe ? "encaixe" : "manual";

  return (
    <div className={`sc-page ${styles.pagina}`}>
      <div className="sc-page-header"><h1>Precificação</h1></div>

      {/* ══ Seção — Accordion por grupo ══ */}
      <div className={`sc-card ${styles.secao}`}>
        <div className={styles.secaoHeader}>
          <h2 className={styles.secaoTitulo}>Precificação por grupo</h2>
        </div>
        {grupos.length === 0 && <p className={styles.vazio}>Nenhum grupo de molde cadastrado.</p>}
        <div className={styles.listaGrupos}>
          {grupos.map((g) => {
            const aberto = !!expandidos[g.id];
            const precs = precsPorGrupo[g.id] || [];
            return (
              <div key={g.id} className={styles.grupoCard}>
                <button className={styles.grupoHeader} onClick={() => toggleGrupo(g.id)}>
                  <span className={`${styles.seta} ${aberto ? styles.setaAberta : ""}`}>›</span>
                  <span className={styles.grupoNome}>{g.nome}</span>
                  {precsPorGrupo[g.id] !== undefined && (
                    <span className={styles.grupoCount}>{precs.length} tamanho{precs.length !== 1 ? "s" : ""}</span>
                  )}
                </button>
                {aberto && (
                  <div className={styles.grupoCorpo}>
                    {carregando[g.id] ? (
                      <p className={styles.loadingInline}>Carregando…</p>
                    ) : (
                      <>
                        {precs.length > 0 && (
                          <table className={styles.tabelaPrec}>
                            <thead>
                              <tr>
                                <th>Tamanho</th>
                                <th>Faixa</th>
                                <th>Custo base</th>
                                <th>Preço sugerido</th>
                                <th>Preço final</th>
                                <th></th>
                              </tr>
                            </thead>
                            <tbody>
                              {precs.map((p) => {
                                const r = calcLocal(
                                  { ...p, usar_kg: !!(p.valor_kg_tecido && p.pecas_por_kg), margem_desejada: parseFloat(p.margem_desejada) * 100 },
                                  config, custos
                                );
                                const isDeletando = confirmarDeletar === p.id;
                                return (
                                  <tr key={p.id}>
                                    <td><span className={styles.tamanhoTag}>{p.tamanho}</span></td>
                                    <td><span className={p.faixa_tamanho === "plus" ? styles.faixaPlus : styles.faixaPadrao}>{p.faixa_tamanho === "plus" ? "Plus" : "Padrão"}</span></td>
                                    <td>{R(r.custo_base)}</td>
                                    <td>{R(p.preco_venda_sugerido || r.preco)}</td>
                                    <td className={styles.precoFinalCell}>
                                      {p.preco_venda_final
                                        ? <><span className={styles.precoFinal}>{R(p.preco_venda_final)}</span><span className={styles.precoFinalTag}>editado</span></>
                                        : R(r.preco)}
                                    </td>
                                    <td>
                                      {isDeletando ? (
                                        <span className={styles.confirmarDeletar}>
                                          Deletar?{" "}
                                          <button className={styles.btnDeletarSim} onClick={() => confirmarDeletarPrec(g.id, p.id)}>Sim</button>
                                          {" "}
                                          <button className={styles.btnDeletarNao} onClick={() => setConfirmarDeletar(null)}>Não</button>
                                        </span>
                                      ) : (
                                        <span className={styles.acoesCelula}>
                                          <button className={styles.btnEditar} onClick={() => abrirEditar(g, p)}>Editar</button>
                                          <button className={styles.btnDeletar} onClick={() => setConfirmarDeletar(p.id)}>×</button>
                                        </span>
                                      )}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        )}
                        <button className={styles.btnNovaTamanho} onClick={() => abrirCriar(g)}>
                          + Adicionar tamanho
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* ══ Resumo ══ */}
      {resumo.length > 0 && (
        <div className={`sc-card ${styles.secao}`}>
          <div className={styles.secaoHeader}>
            <h2 className={styles.secaoTitulo}>Resumo</h2>
            <button className={styles.btnSecundario} onClick={exportarCSV}>Exportar CSV</button>
          </div>
          <table className={styles.tabelaResumo}>
            <thead>
              <tr>
                <th>Modelo</th><th>Tam.</th><th>Faixa</th><th>Custo</th>
                <th>Imposto</th><th>Preço</th><th>Lucro</th><th>Margem</th>
              </tr>
            </thead>
            <tbody>
              {resumo.map((r, i) => (
                <tr key={i}>
                  <td>{r.grupo}</td>
                  <td><span className={styles.tamanhoTag}>{r.tamanho}</span></td>
                  <td><span className={r.faixa === "plus" ? styles.faixaPlus : styles.faixaPadrao}>{r.faixa === "plus" ? "Plus" : "Padrão"}</span></td>
                  <td>{R(r.custo)}</td>
                  <td>{R(r.imposto)}</td>
                  <td className={styles.precoDestaque}>{R(r.preco)}</td>
                  <td>{R(r.lucro)}</td>
                  <td>
                    <span className={r.margem >= 0.5 ? styles.margemBoa : r.margem >= 0.3 ? styles.margemMedia : styles.margemBaixa}>
                      {Pct(r.margem)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ══ Modal ══ */}
      {modal && (
        <Modal
          titulo={modal.modo === "criar"
            ? `Nova precificação — ${modal.grupoNome}`
            : `Editar — ${modal.grupoNome} · ${modal.prec.tamanho}`}
          onFechar={() => setModal(null)}
        >
          <div className={styles.modalForm}>

            {modal.modo === "criar" && (
              <div className={styles.campo}>
                <label className={styles.label}>Tamanho</label>
                <input className={styles.input} placeholder="P, M, G, 38, 40…"
                  value={form.tamanho}
                  onChange={(e) => setForm((f) => ({ ...f, tamanho: e.target.value }))} />
              </div>
            )}

            {/* Faixa tamanho */}
            <div className={styles.campo}>
              <label className={styles.label}>Faixa</label>
              <div className={styles.toggle}>
                <button
                  className={`${styles.toggleBtn} ${form.faixa_tamanho === "padrao" ? styles.toggleAtivo : ""}`}
                  onClick={() => setForm((f) => ({ ...f, faixa_tamanho: "padrao" }))}>
                  Padrão
                </button>
                <button
                  className={`${styles.toggleBtn} ${form.faixa_tamanho === "plus" ? styles.toggleAtivo : ""}`}
                  onClick={() => setForm((f) => ({ ...f, faixa_tamanho: "plus" }))}>
                  Plus
                </button>
              </div>
            </div>

            {/* Custo do tecido */}
            <div className={styles.campo}>
              <label className={styles.label}>Custo do tecido</label>
              <div className={styles.toggle}>
                <button className={`${styles.toggleBtn} ${tipoTecidoAtivo === "kg" ? styles.toggleAtivo : ""}`}
                  onClick={() => setForm((f) => ({ ...f, usar_kg: true, usar_custo_encaixe: false }))}>
                  Por kg
                </button>
                <button className={`${styles.toggleBtn} ${tipoTecidoAtivo === "manual" ? styles.toggleAtivo : ""}`}
                  onClick={() => setForm((f) => ({ ...f, usar_kg: false, usar_custo_encaixe: false }))}>
                  Manual
                </button>
                <button className={`${styles.toggleBtn} ${tipoTecidoAtivo === "encaixe" ? styles.toggleAtivo : ""}`}
                  onClick={() => setForm((f) => ({ ...f, usar_kg: false, usar_custo_encaixe: true }))}>
                  Encaixe
                </button>
              </div>
              {form.usar_kg ? (
                <div className={styles.grade2}>
                  <div className={styles.campo}>
                    <label className={styles.labelSub}>Valor/kg (R$)</label>
                    <input type="number" step="0.01" className={styles.input} placeholder="0,00"
                      value={form.valor_kg_tecido}
                      onChange={(e) => setForm((f) => ({ ...f, valor_kg_tecido: e.target.value }))} />
                  </div>
                  <div className={styles.campo}>
                    <label className={styles.labelSub}>Peças/kg</label>
                    <input type="number" step="0.001" className={styles.input} placeholder="0,000"
                      value={form.pecas_por_kg}
                      onChange={(e) => setForm((f) => ({ ...f, pecas_por_kg: e.target.value }))} />
                  </div>
                </div>
              ) : (
                <input type="number" step="0.01" className={styles.input} placeholder="R$ 0,00"
                  value={form.usar_custo_encaixe ? form.custo_tecido_encaixe : form.custo_tecido_manual}
                  onChange={(e) => setForm((f) =>
                    form.usar_custo_encaixe
                      ? { ...f, custo_tecido_encaixe: e.target.value }
                      : { ...f, custo_tecido_manual: e.target.value }
                  )} />
              )}
            </div>

            {/* Costura */}
            <div className={styles.campo}>
              <label className={styles.label}>Custo costura/peça (R$)</label>
              <input type="number" step="0.01" className={styles.input} placeholder="0,00"
                value={form.custo_costura}
                onChange={(e) => setForm((f) => ({ ...f, custo_costura: e.target.value }))} />
            </div>

            {/* Linha */}
            <div className={styles.grade2}>
              <div className={styles.campo}>
                <label className={styles.label}>
                  Linha overlock por peça (m)
                  {calc.custo_metro_overlock > 0 && (
                    <span className={styles.labelDica}> — {R(calc.custo_metro_overlock)}/m</span>
                  )}
                </label>
                <input type="number" step="0.01" className={styles.input} placeholder="0,00"
                  value={form.metros_linha_overlock}
                  onChange={(e) => setForm((f) => ({ ...f, metros_linha_overlock: e.target.value }))} />
              </div>
              <div className={styles.campo}>
                <label className={styles.label}>
                  Linha reta por peça (m)
                  {calc.custo_metro_reta > 0 && (
                    <span className={styles.labelDica}> — {R(calc.custo_metro_reta)}/m</span>
                  )}
                </label>
                <input type="number" step="0.01" className={styles.input} placeholder="0,00"
                  value={form.metros_linha_reta}
                  onChange={(e) => setForm((f) => ({ ...f, metros_linha_reta: e.target.value }))} />
              </div>
            </div>

            {/* Peças por viagem */}
            <div className={styles.campo}>
              <label className={styles.label}>Peças por viagem <span className={styles.labelDica}>(para rateio gasolina)</span></label>
              <input type="number" step="1" className={styles.input}
                value={form.pecas_por_viagem}
                onChange={(e) => setForm((f) => ({ ...f, pecas_por_viagem: e.target.value }))} />
            </div>

            {/* Margem */}
            <div className={styles.campo}>
              <div className={styles.labelRow}>
                <label className={styles.label}>Margem desejada</label>
                <span className={styles.margemValor}>{form.margem_desejada}%</span>
              </div>
              <input type="range" min="0" max="90" step="1" className={styles.slider}
                value={form.margem_desejada}
                onChange={(e) => setForm((f) => ({ ...f, margem_desejada: e.target.value }))} />
              <div className={styles.sliderLabels}><span>0%</span><span>45%</span><span>90%</span></div>
            </div>

            {/* Preview breakdown */}
            <div className={styles.preview}>
              <div className={styles.previewRow}>
                <span>Tecido{form.usar_kg && form.pecas_por_kg ? ` (${parseFloat(form.pecas_por_kg) > 0 ? (1/parseFloat(form.pecas_por_kg)).toFixed(3) : "?"}kg)` : ""}</span>
                <span>{R(calc.custo_tecido)}</span>
              </div>
              <div className={styles.previewRow}><span>Costura</span><span>{R(calc.custo_costura)}</span></div>
              <div className={styles.previewRow}>
                <span>Overlock ({form.metros_linha_overlock || 0}m)</span>
                <span>{R(calc.custo_overlock)}</span>
              </div>
              <div className={styles.previewRow}>
                <span>Reta ({form.metros_linha_reta || 0}m)</span>
                <span>{R(calc.custo_reta)}</span>
              </div>
              <div className={styles.previewRow}><span>Gasolina</span><span>{R(calc.custo_gasolina)}</span></div>
              <div className={styles.previewRow}><span>Saquinho</span><span>{R(calc.custo_saquinho)}</span></div>
              <div className={styles.previewRow}>
                <span>Caixa (÷{custos?.pecas_por_caixa || 50} peças)</span>
                <span>{R(calc.custo_caixa)}</span>
              </div>
              <div className={styles.previewRow}><span>Etiqueta</span><span>{R(calc.custo_etiqueta)}</span></div>
              <div className={`${styles.previewRow} ${styles.previewSubtotal}`}><span>Custo base</span><span>{R(calc.custo_base)}</span></div>
              <div className={styles.previewRow}><span>Imposto ({config?.aliquota_simples != null ? `${parseFloat(config.aliquota_simples).toFixed(2)}%` : "—"})</span><span>{R(calc.imposto)}</span></div>
              <div className={`${styles.previewRow} ${styles.previewTotal}`}><span>Preço sugerido</span><span>{R(calc.preco)}</span></div>
            </div>

            {/* Preço final + lucro */}
            <div className={styles.campo}>
              <label className={styles.label}>Preço final <span className={styles.labelDica}>(vazio = usar sugerido)</span></label>
              <input type="number" step="0.01" className={styles.input} placeholder="R$ 0,00"
                value={form.preco_venda_final}
                onChange={(e) => setForm((f) => ({ ...f, preco_venda_final: e.target.value, preco_final_manual: true }))} />
              {calc.lucro != null && (() => {
                const precoFinal = form.preco_venda_final !== "" ? parseFloat(form.preco_venda_final) : calc.preco;
                const lucroFinal = precoFinal && calc.custo_base ? precoFinal - calc.custo_base - (precoFinal * ((parseFloat(config?.aliquota_simples) || 0) / 100)) : calc.lucro;
                const margemFinal = precoFinal > 0 ? lucroFinal / precoFinal : null;
                return (
                  <span className={styles.lucroInfo}>
                    Lucro: {R(lucroFinal)} {margemFinal != null ? `(${(margemFinal * 100).toFixed(1)}%)` : ""}
                  </span>
                );
              })()}
            </div>

            {erroModal && <p className={styles.erroInline}>{erroModal}</p>}

            <div className={styles.modalAcoes}>
              <button className={styles.btnSecundario} onClick={() => setModal(null)}>Cancelar</button>
              <button className={styles.btnPrimario} onClick={salvarModal} disabled={salvando}>
                {salvando ? "Salvando…" : "Salvar"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
