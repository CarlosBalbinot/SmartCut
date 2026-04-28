import { useState, useEffect } from "react";
import { gruposApi, precificacoesApi } from "../services/api";
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from "recharts";
import styles from "./ProjecaoPage.module.css";

/* ── Helpers ── */
const R = (v) => v != null ? `R$ ${parseFloat(v).toFixed(2).replace(".", ",")}` : "—";
const Pct = (v) => v != null ? `${(parseFloat(v) * 100).toFixed(1)}%` : "—";

function calcLocal(p, config, custos) {
  const usaKg = !!(p.valor_kg_tecido && p.pecas_por_kg && parseFloat(p.pecas_por_kg) > 0);
  let custo_tecido = 0;
  if (usaKg) {
    custo_tecido = parseFloat(p.valor_kg_tecido) / parseFloat(p.pecas_por_kg);
  } else if (p.usar_custo_encaixe) {
    custo_tecido = parseFloat(p.custo_tecido_encaixe) || 0;
  } else {
    custo_tecido = parseFloat(p.custo_tecido_manual) || 0;
  }

  const metros_overlock = parseFloat(p.metros_linha_overlock) || 0;
  const metros_reta = parseFloat(p.metros_linha_reta) || 0;
  const val_overlock = parseFloat(custos?.valor_kg_overlock) || 0;
  const val_reta = parseFloat(custos?.valor_kg_reta) || 0;
  const custo_linha = metros_overlock * val_overlock + metros_reta * val_reta;

  let custo_gasolina = 0;
  const dist = parseFloat(custos?.distancia_costureira_km) || 0;
  const num_viagens = parseFloat(custos?.num_viagens) || 2;
  const consumo = parseFloat(custos?.consumo_veiculo_km_l) || 0;
  const preco_comb = parseFloat(custos?.preco_combustivel) || 0;
  const pecas_viagem = parseFloat(p.pecas_por_viagem) || 50;
  if (dist > 0 && consumo > 0 && preco_comb > 0 && pecas_viagem > 0) {
    custo_gasolina = (dist * 2 * num_viagens / consumo) * preco_comb / pecas_viagem;
  }

  let custo_caixa = 0;
  const custo_cx = parseFloat(custos?.custo_caixa) || 0;
  const pecas_cx = parseFloat(custos?.pecas_por_caixa) || 0;
  if (custo_cx > 0 && pecas_cx > 0) custo_caixa = custo_cx / pecas_cx;

  const custo_costura = parseFloat(p.custo_costura) || 0;
  const custo_etiqueta = parseFloat(config?.custo_etiqueta) || 0;
  const custo_embalagem = parseFloat(config?.custo_embalagem) || 0;
  const custo_base = custo_tecido + custo_costura + custo_linha + custo_gasolina + custo_caixa + custo_etiqueta + custo_embalagem;

  const aliquota = parseFloat(config?.aliquota_simples) || 0;
  const margem = parseFloat(p.margem_desejada) || 0.6;
  const denom = 1 - aliquota - margem;

  const base = { custo_tecido, custo_costura, custo_linha, custo_gasolina, custo_caixa, custo_etiqueta, custo_embalagem, custo_base };
  if (denom <= 0 || custo_base <= 0) return { ...base, preco: null, imposto: null, lucro: null };

  const preco = custo_base / denom;
  const imposto = preco * aliquota;
  const lucro = preco - custo_base - imposto;
  return { ...base, preco, imposto, lucro };
}

const GRAYSCALE = ["#1D1D1F", "#6E6E73", "#AEAEB2", "#C7C7CC", "#D1D1D6", "#E5E5EA", "#3A3A3C", "#8E8E93"];

export default function ProjecaoPage() {
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(null);

  const [grupos, setGrupos] = useState([]);
  const [config, setConfig] = useState(null);
  const [custos, setCustos] = useState(null);
  const [precsPorGrupo, setPrecsPorGrupo] = useState({});

  // Itens da projeção: [{grupoId, tamanho, faixa, quantidade}]
  const [itens, setItens] = useState([{ grupoId: "", tamanho: "", faixa: "padrao", quantidade: "100" }]);
  const [calculando, setCalculando] = useState(false);
  const [resultado, setResultado] = useState(null);

  useEffect(() => {
    Promise.all([gruposApi.listar(), precificacoesApi.getConfig(), precificacoesApi.getCustos()])
      .then(([gs, cfg, cst]) => {
        setGrupos(gs);
        setConfig(cfg);
        setCustos(cst);
      })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, []);

  const carregarPrecs = async (grupoId) => {
    if (precsPorGrupo[grupoId]) return precsPorGrupo[grupoId];
    const data = await precificacoesApi.listar(grupoId);
    setPrecsPorGrupo((p) => ({ ...p, [grupoId]: data }));
    return data;
  };

  const calcular = async () => {
    const itensValidos = itens.filter((i) => i.grupoId && i.tamanho && parseFloat(i.quantidade) > 0);
    if (itensValidos.length === 0) return;
    setCalculando(true);
    try {
      // Garantir que todos os grupos estão carregados
      const promises = [...new Set(itensValidos.map((i) => i.grupoId))].map(carregarPrecs);
      const resultados = await Promise.all(promises);
      // Merge into local state snapshot
      const snap = { ...precsPorGrupo };
      [...new Set(itensValidos.map((i) => i.grupoId))].forEach((gid, idx) => {
        snap[gid] = resultados[idx];
      });

      const linhas = itensValidos.map((item) => {
        const grupo = grupos.find((g) => g.id === item.grupoId);
        const precs = snap[item.grupoId] || [];
        const prec = precs.find((p) => p.tamanho === item.tamanho && (p.faixa_tamanho || "padrao") === item.faixa);
        if (!prec) return { ...item, grupoNome: grupo?.nome || item.grupoId, erro: "Precificação não encontrada" };

        const r = calcLocal(prec, config, custos);
        const preco_unit = prec.preco_venda_final ? parseFloat(prec.preco_venda_final) : (r.preco || 0);
        const custo_unit = r.custo_base || 0;
        const qty = parseFloat(item.quantidade);
        const receita = preco_unit * qty;
        const custo_total = custo_unit * qty;
        const lucro = receita - custo_total;
        const margem = receita > 0 ? lucro / receita : 0;

        return {
          grupoNome: grupo?.nome || item.grupoId,
          tamanho: item.tamanho,
          faixa: item.faixa,
          quantidade: qty,
          preco_unit,
          custo_unit,
          receita,
          custo_total,
          lucro,
          margem,
          breakdown: r,
        };
      });

      setResultado(linhas);
    } catch (e) {
      setErro(e.message);
    } finally {
      setCalculando(false);
    }
  };

  const adicionarItem = () =>
    setItens((prev) => [...prev, { grupoId: "", tamanho: "", faixa: "padrao", quantidade: "100" }]);

  const removerItem = (idx) =>
    setItens((prev) => prev.filter((_, i) => i !== idx));

  const updateItem = (idx, field, value) =>
    setItens((prev) => prev.map((it, i) => i === idx ? { ...it, [field]: value } : it));

  /* ── Dados derivados ── */
  const linhasOk = resultado?.filter((r) => !r.erro) || [];
  const totalReceita = linhasOk.reduce((s, r) => s + r.receita, 0);
  const totalCusto = linhasOk.reduce((s, r) => s + r.custo_total, 0);
  const totalLucro = linhasOk.reduce((s, r) => s + r.lucro, 0);
  const margemMedia = totalReceita > 0 ? totalLucro / totalReceita : 0;

  // Agrupado por modelo para os gráficos
  const porModelo = linhasOk.reduce((acc, r) => {
    if (!acc[r.grupoNome]) acc[r.grupoNome] = { receita: 0, custo: 0, lucro: 0 };
    acc[r.grupoNome].receita += r.receita;
    acc[r.grupoNome].custo += r.custo_total;
    acc[r.grupoNome].lucro += r.lucro;
    return acc;
  }, {});

  const barData = Object.entries(porModelo).map(([nome, v]) => ({
    nome: nome.length > 12 ? nome.slice(0, 12) + "…" : nome,
    Receita: parseFloat(v.receita.toFixed(2)),
    Custo: parseFloat(v.custo.toFixed(2)),
    Lucro: parseFloat(v.lucro.toFixed(2)),
  }));

  const margemData = Object.entries(porModelo)
    .map(([nome, v]) => ({
      nome: nome.length > 14 ? nome.slice(0, 14) + "…" : nome,
      margem: v.receita > 0 ? parseFloat(((v.lucro / v.receita) * 100).toFixed(1)) : 0,
    }))
    .sort((a, b) => b.margem - a.margem);

  // Composição de custo (média ponderada)
  const custoTotal_sum = linhasOk.reduce((s, r) => s + r.custo_total, 0);
  const pieData = custoTotal_sum > 0 ? [
    { name: "Tecido", value: parseFloat((linhasOk.reduce((s, r) => s + r.breakdown.custo_tecido * r.quantidade, 0)).toFixed(2)) },
    { name: "Costura", value: parseFloat((linhasOk.reduce((s, r) => s + r.breakdown.custo_costura * r.quantidade, 0)).toFixed(2)) },
    { name: "Linha", value: parseFloat((linhasOk.reduce((s, r) => s + r.breakdown.custo_linha * r.quantidade, 0)).toFixed(2)) },
    { name: "Gasolina", value: parseFloat((linhasOk.reduce((s, r) => s + r.breakdown.custo_gasolina * r.quantidade, 0)).toFixed(2)) },
    { name: "Caixa", value: parseFloat((linhasOk.reduce((s, r) => s + r.breakdown.custo_caixa * r.quantidade, 0)).toFixed(2)) },
    { name: "Etiqueta", value: parseFloat((linhasOk.reduce((s, r) => s + (r.breakdown.custo_etiqueta + r.breakdown.custo_embalagem) * r.quantidade, 0)).toFixed(2)) },
  ].filter((d) => d.value > 0) : [];

  if (loading) return <p className={styles.loading}>Carregando…</p>;
  if (erro) return <p className={styles.erro}>{erro}</p>;

  return (
    <div className={styles.pagina}>

      {/* ── Formulário de projeção ── */}
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <span className={styles.cardTitulo}>Projeção de produção</span>
        </div>
        <div className={styles.cardBody}>
          <div className={styles.itensList}>
            {itens.map((item, idx) => {
              const precsGrupo = item.grupoId ? (precsPorGrupo[item.grupoId] || []) : [];
              const tamanhos = [...new Set(precsGrupo.map((p) => ({ t: p.tamanho, f: p.faixa_tamanho || "padrao" })))];
              return (
                <div key={idx} className={styles.itemRow}>
                  <div className={styles.campo}>
                    <label className={styles.labelSub}>Modelo</label>
                    <select className={styles.select}
                      value={item.grupoId}
                      onChange={(e) => {
                        updateItem(idx, "grupoId", e.target.value);
                        updateItem(idx, "tamanho", "");
                        if (e.target.value) carregarPrecs(e.target.value);
                      }}>
                      <option value="">Selecione…</option>
                      {grupos.map((g) => <option key={g.id} value={g.id}>{g.nome}</option>)}
                    </select>
                  </div>
                  <div className={styles.campo}>
                    <label className={styles.labelSub}>Tamanho</label>
                    <select className={styles.select}
                      value={`${item.tamanho}|${item.faixa}`}
                      onChange={(e) => {
                        const [t, f] = e.target.value.split("|");
                        updateItem(idx, "tamanho", t);
                        updateItem(idx, "faixa", f);
                      }}
                      disabled={!item.grupoId}>
                      <option value="|padrao">Selecione…</option>
                      {tamanhos.map(({ t, f }) => (
                        <option key={`${t}|${f}`} value={`${t}|${f}`}>
                          {t} {f === "plus" ? "(Plus)" : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className={styles.campoQtd}>
                    <label className={styles.labelSub}>Quantidade</label>
                    <input type="number" step="1" min="1" className={styles.input}
                      value={item.quantidade}
                      onChange={(e) => updateItem(idx, "quantidade", e.target.value)} />
                  </div>
                  {itens.length > 1 && (
                    <button className={styles.btnRemoverItem} onClick={() => removerItem(idx)} title="Remover">×</button>
                  )}
                </div>
              );
            })}
          </div>
          <div className={styles.formAcoes}>
            <button className={styles.btnSecundario} onClick={adicionarItem}>+ Adicionar item</button>
            <button className={styles.btnPrimario} onClick={calcular} disabled={calculando}>
              {calculando ? "Calculando…" : "Calcular projeção"}
            </button>
          </div>
        </div>
      </div>

      {/* ── Resultado ── */}
      {resultado && linhasOk.length > 0 && (
        <>
          {/* Cards de resumo */}
          <div className={styles.statsGrid}>
            <div className={styles.statCard}>
              <span className={styles.statLabel}>Receita total</span>
              <span className={styles.statValor}>{R(totalReceita)}</span>
            </div>
            <div className={styles.statCard}>
              <span className={styles.statLabel}>Custo total</span>
              <span className={styles.statValor}>{R(totalCusto)}</span>
            </div>
            <div className={styles.statCard}>
              <span className={styles.statLabel}>Lucro total</span>
              <span className={`${styles.statValor} ${totalLucro >= 0 ? styles.statPositivo : styles.statNegativo}`}>
                {R(totalLucro)}
              </span>
            </div>
            <div className={styles.statCard}>
              <span className={styles.statLabel}>Margem média</span>
              <span className={`${styles.statValor} ${margemMedia >= 0.4 ? styles.statPositivo : margemMedia >= 0.2 ? styles.statNeutro : styles.statNegativo}`}>
                {Pct(margemMedia)}
              </span>
            </div>
          </div>

          {/* Gráficos */}
          <div className={styles.graficosGrid}>

            {/* Pizza — composição de custo */}
            {pieData.length > 0 && (
              <div className={styles.graficoCard}>
                <h3 className={styles.graficoTitulo}>Composição de custo</h3>
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                      {pieData.map((_, i) => (
                        <Cell key={i} fill={GRAYSCALE[i % GRAYSCALE.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v) => `R$ ${v.toFixed(2)}`} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Barras — receita / custo / lucro por modelo */}
            {barData.length > 0 && (
              <div className={styles.graficoCard}>
                <h3 className={styles.graficoTitulo}>Receita × Custo × Lucro por modelo</h3>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={barData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                    <XAxis dataKey="nome" tick={{ fontSize: 11, fill: "#AEAEB2" }} />
                    <YAxis tick={{ fontSize: 11, fill: "#AEAEB2" }} tickFormatter={(v) => `${v.toFixed(0)}`} />
                    <Tooltip formatter={(v) => `R$ ${v.toFixed(2)}`} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="Receita" fill="#1D1D1F" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="Custo" fill="#AEAEB2" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="Lucro" fill="#6E6E73" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Barras horizontais — margem por modelo */}
            {margemData.length > 0 && (
              <div className={`${styles.graficoCard} ${styles.graficoFull}`}>
                <h3 className={styles.graficoTitulo}>Margem por modelo (decrescente)</h3>
                <ResponsiveContainer width="100%" height={Math.max(160, margemData.length * 36)}>
                  <BarChart data={margemData} layout="vertical" margin={{ top: 4, right: 32, left: 8, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" horizontal={false} />
                    <XAxis type="number" unit="%" tick={{ fontSize: 11, fill: "#AEAEB2" }} />
                    <YAxis type="category" dataKey="nome" width={110} tick={{ fontSize: 11, fill: "#6E6E73" }} />
                    <Tooltip formatter={(v) => `${v}%`} />
                    <Bar dataKey="margem" fill="#1D1D1F" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Tabela detalhada */}
          <div className={styles.secao}>
            <div className={styles.secaoHeader}>
              <h2 className={styles.secaoTitulo}>Detalhamento por item</h2>
            </div>
            <table className={styles.tabelaResultado}>
              <thead>
                <tr>
                  <th>Modelo</th><th>Tam.</th><th>Faixa</th><th>Qtd</th>
                  <th>Preço unit.</th><th>Custo unit.</th>
                  <th>Receita</th><th>Custo</th><th>Lucro</th><th>Margem</th>
                </tr>
              </thead>
              <tbody>
                {resultado.map((r, i) => (
                  <tr key={i} className={r.erro ? styles.linhaErro : ""}>
                    <td>{r.grupoNome}</td>
                    <td><span className={styles.tamanhoTag}>{r.tamanho || "—"}</span></td>
                    <td>{r.faixa === "plus" ? <span className={styles.faixaPlus}>Plus</span> : <span className={styles.faixaPadrao}>Padrão</span>}</td>
                    {r.erro ? (
                      <td colSpan="7" className={styles.erroCell}>{r.erro}</td>
                    ) : (
                      <>
                        <td>{r.quantidade}</td>
                        <td>{R(r.preco_unit)}</td>
                        <td>{R(r.custo_unit)}</td>
                        <td className={styles.destaque}>{R(r.receita)}</td>
                        <td>{R(r.custo_total)}</td>
                        <td>{R(r.lucro)}</td>
                        <td>
                          <span className={r.margem >= 0.5 ? styles.margemBoa : r.margem >= 0.3 ? styles.margemMedia : styles.margemBaixa}>
                            {Pct(r.margem)}
                          </span>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {resultado && linhasOk.length === 0 && (
        <p className={styles.vazio}>Nenhuma precificação encontrada para os itens selecionados.</p>
      )}
    </div>
  );
}
