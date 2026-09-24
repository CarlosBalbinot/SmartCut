import { useEffect, useMemo, useRef, useState } from "react";
import {
  getPrecosProdutoTabela,
  removerPrecoProdutoTabela,
  salvarPrecosProdutoTabela,
} from "../../api/tabelasPreco";
import { produtosApi } from "../../api/produtos";
import styles from "./PrecosProdutoTabela.module.css";

/*
 * Preços por produto pai numa tabela de preço, com exceção opcional por SKU
 * (backend: /tabelas-preco/{id}/precos-produto — precos_tabela_produto).
 *
 * O backend guarda a exceção do SKU como um par (à vista + a prazo). Para a
 * tela funcionar campo a campo ("vazio = herda do pai"):
 *   - campo do SKU igual ao do pai é exibido vazio (herdado);
 *   - preencher só um campo grava o outro com o valor do pai;
 *   - quando os dois ficam iguais ao pai, a exceção é removida;
 *   - mudar o preço do pai leva junto os SKUs que herdavam aquele campo
 *     (mesmo PUT em lote), para a cópia não virar exceção sem querer.
 */

const CAMPOS = ["preco_avista", "preco_aprazo"];
const ROTULO = { preco_avista: "à vista", preco_aprazo: "a prazo" };
const outroCampo = (campo) => (campo === "preco_avista" ? "preco_aprazo" : "preco_avista");

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(v) || 0);
const numeroBR = (v) =>
  new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v) || 0);
const num = (v) => (v === null || v === undefined || v === "" ? null : Number(v));
const iguais = (a, b) => a != null && b != null && Math.abs(a - b) < 0.005;

// "1.234,56" / "1234,56" / "1234.56" / "R$ 12,50" → número; "" → null.
function parseNumeroBR(texto) {
  let t = String(texto ?? "").replace(/R\$/gi, "").replace(/\s/g, "");
  if (!t) return null;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  else if ((t.match(/\./g) || []).length > 1 || /\.\d{3,}$/.test(t)) t = t.replace(/\./g, "");
  return /^\d*\.?\d+$/.test(t) ? Number(Number(t).toFixed(2)) : NaN;
}

// ── Campo de preço inline ────────────────────────────────────────────────────
// Fora do foco mostra "R$ …"; vazio mostra o placeholder (valor herdado).
// Salva no blur/Enter, Esc reverte. Erro: fundo vermelho claro + tooltip.
function CampoPreco({ valor, placeholder, destaque, readOnly, onSalvar, autoFocus }) {
  const [focado, setFocado] = useState(false);
  const [texto, setTexto] = useState("");
  const [erro, setErro] = useState(null);
  const [salvando, setSalvando] = useState(false);
  const ignorarBlur = useRef(false);

  const paraEdicao = () => (valor == null ? "" : numeroBR(valor).replace(/\./g, ""));
  const exibido = focado || erro ? texto : (valor == null ? "" : moeda(valor));

  const salvar = async () => {
    const n = parseNumeroBR(texto);
    if (Number.isNaN(n)) { setErro("Valor inválido."); return false; }
    if ((n === null && valor == null) || iguais(n, valor)) { setErro(null); return true; }
    setSalvando(true);
    try {
      await onSalvar(n);
      setErro(null);
      return true;
    } catch (e) {
      setErro(e.message || "Erro ao salvar.");
      return false;
    } finally {
      setSalvando(false);
    }
  };

  const handleKeyDown = async (e) => {
    if (readOnly || salvando) return;
    if (e.key === "Enter") {
      e.preventDefault();
      const el = e.currentTarget;
      if (await salvar()) { ignorarBlur.current = true; el.blur(); }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setTexto(paraEdicao());
      setErro(null);
      ignorarBlur.current = true;
      e.currentTarget.blur();
    }
  };

  let title = erro || "";
  if (!title) title = valor == null ? (placeholder ? `Herdado do produto: ${placeholder}` : "") : moeda(valor);

  return (
    <input
      className={`${styles.campo} ${destaque ? styles.campoExcecao : ""} ${erro ? styles.campoErro : ""}`}
      value={exibido}
      placeholder={placeholder}
      title={title}
      readOnly={readOnly || salvando}
      tabIndex={readOnly ? -1 : 0}
      inputMode="decimal"
      autoFocus={autoFocus}
      onChange={(e) => setTexto(e.target.value.toUpperCase())}
      onFocus={(e) => {
        if (!erro) setTexto(paraEdicao());
        setFocado(true);
        const el = e.target;
        requestAnimationFrame(() => el.select());
      }}
      onBlur={() => {
        setFocado(false);
        if (ignorarBlur.current) { ignorarBlur.current = false; return; }
        if (!readOnly) salvar();
      }}
      onKeyDown={handleKeyDown}
    />
  );
}

function Chevron({ aberto }) {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"
      className={`${styles.chevron} ${aberto ? styles.chevronAberto : ""}`}>
      <path d="M4 2.5 7.5 6 4 9.5" fill="none" stroke="currentColor" strokeWidth="1.6"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Seção ────────────────────────────────────────────────────────────────────

export default function PrecosProdutoTabela({ tabelaId, editavel }) {
  const [precos, setPrecos] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erroCarga, setErroCarga] = useState(null);
  const [abertos, setAbertos] = useState({});
  const [grades, setGrades] = useState({});
  const [modalAdd, setModalAdd] = useState(false);
  const [confirmacao, setConfirmacao] = useState(null); // { tipo: "remover" | "limpar", paiId }
  const [erroAcao, setErroAcao] = useState(null);       // { paiId, msg }

  useEffect(() => {
    let ativo = true;
    setCarregando(true); setErroCarga(null);
    setAbertos({}); setConfirmacao(null); setErroAcao(null);
    getPrecosProdutoTabela(tabelaId)
      .then((d) => { if (ativo) setPrecos(d || []); })
      .catch((e) => { if (ativo) { setPrecos([]); setErroCarga(e.message); } })
      .finally(() => { if (ativo) setCarregando(false); });
    return () => { ativo = false; };
  }, [tabelaId]);

  // Agrupa por produto pai: { paiId, pai (linha PRODUTO ou null), skus: { sku_id: linha } }.
  const grupos = useMemo(() => {
    const mapa = new Map();
    for (const p of precos) {
      const paiId = String(p.produto_pai_id);
      if (!mapa.has(paiId)) mapa.set(paiId, { paiId, pai: null, skus: {} });
      const g = mapa.get(paiId);
      if (p.tipo === "PRODUTO") g.pai = p;
      else g.skus[p.sku_id] = p;
    }
    return [...mapa.values()].sort((a, b) =>
      (a.pai?.codigo || "").localeCompare(b.pai?.codigo || ""));
  }, [precos]);

  const carregarGrade = async (paiId) => {
    setGrades((g) => ({ ...g, [paiId]: { carregando: true } }));
    try {
      const grade = await produtosApi.gradePedido(paiId);
      const descItem = (eixo, id) => eixo?.itens?.find((i) => i.id === id)?.descricao;
      const skus = (grade.skus || [])
        .filter((s) => s.situacao === "Ativo")
        .map((s) => ({
          id: s.id,
          codigo: s.codigo,
          descricao: [grade.produto?.descricao, descItem(grade.linha_grade, s.linha_item_id),
            descItem(grade.coluna_grade, s.coluna_item_id)].filter(Boolean).join(" "),
        }));
      setGrades((g) => ({ ...g, [paiId]: { produto: grade.produto, skus } }));
    } catch (e) {
      setGrades((g) => ({ ...g, [paiId]: { erro: e.message, skus: [] } }));
    }
  };

  const alternar = (paiId) => {
    setAbertos((a) => ({ ...a, [paiId]: !a[paiId] }));
    if (!grades[paiId]) carregarGrade(paiId);
  };

  const salvarLinhas = async (linhas) => {
    const lista = await salvarPrecosProdutoTabela(tabelaId, linhas);
    setPrecos(lista || []);
  };

  const plusDe = (base) => ({
    tem_plus_size: base?.tem_plus_size || false,
    preco_avista_plus: base?.preco_avista_plus ?? null,
    preco_aprazo_plus: base?.preco_aprazo_plus ?? null,
  });

  // ── Pai ──
  const salvarPai = async (grupo, campo, valor) => {
    const pai = grupo.pai;
    if (valor == null) throw new Error("Preço do produto é obrigatório.");
    const outro = outroCampo(campo);
    // Grupo só com exceções de SKU (pai sem linha na tabela): o primeiro
    // preço digitado vale para os dois campos, depois é só ajustar o outro.
    const valorOutro = pai ? num(pai[outro]) : valor;
    if (valorOutro == null) throw new Error(`Informe também o preço ${ROTULO[outro]}.`);

    const linhas = [{
      produto_id: grupo.paiId, [campo]: valor, [outro]: valorOutro, ...plusDe(pai),
    }];
    // SKUs que herdavam este campo acompanham o novo valor do pai.
    const antigo = num(pai?.[campo]);
    for (const ex of Object.values(grupo.skus)) {
      if (iguais(num(ex[campo]), antigo)) {
        linhas.push({ sku_id: ex.sku_id, [campo]: valor, [outro]: num(ex[outro]), ...plusDe(ex) });
      }
    }
    await salvarLinhas(linhas);
  };

  // ── SKU ──
  const salvarSku = async (grupo, sku, campo, valor) => {
    const ex = grupo.skus[sku.id];
    const pai = grupo.pai;
    const outro = outroCampo(campo);
    const paiCampo = num(pai?.[campo]);
    const paiOutro = num(pai?.[outro]);

    // Campo apagado: volta a herdar o valor do pai.
    const novoCampo = valor == null ? paiCampo : valor;
    const novoOutro = ex ? num(ex[outro]) : paiOutro;

    if (novoCampo == null || novoOutro == null) {
      if (valor == null && ex) { await removerIds([ex.id]); return; }
      throw new Error("Produto pai sem preço nesta tabela.");
    }
    if (iguais(novoCampo, paiCampo) && iguais(novoOutro, paiOutro)) {
      if (ex) await removerIds([ex.id]);
      return;
    }
    await salvarLinhas([{ sku_id: sku.id, [campo]: novoCampo, [outro]: novoOutro, ...plusDe(ex) }]);
  };

  const removerIds = async (ids) => {
    for (const id of ids) await removerPrecoProdutoTabela(tabelaId, id);
    setPrecos((ps) => ps.filter((p) => !ids.includes(p.id)));
  };

  const confirmar = async () => {
    const { tipo, paiId } = confirmacao;
    const grupo = grupos.find((g) => g.paiId === paiId);
    setConfirmacao(null);
    if (!grupo) return;
    const excecoes = Object.values(grupo.skus).map((s) => s.id);
    const ids = tipo === "remover" && grupo.pai ? [grupo.pai.id, ...excecoes] : excecoes;
    try {
      await removerIds(ids);
      setErroAcao(null);
    } catch (e) {
      setErroAcao({ paiId, msg: e.message });
      setPrecos(await getPrecosProdutoTabela(tabelaId).catch(() => precos));
    }
  };

  const adicionar = async (produto, avista, aprazo) => {
    await salvarLinhas([{ produto_id: produto.id, preco_avista: avista, preco_aprazo: aprazo, tem_plus_size: false }]);
    setModalAdd(false);
    setAbertos((a) => ({ ...a, [String(produto.id)]: true }));
    carregarGrade(String(produto.id));
  };

  return (
    <section className={styles.secao}>
      <div className={styles.cabecalho}>
        <span className={styles.titulo}>Preços por produto ({grupos.length})</span>
        {editavel && (
          <button className={styles.btnSecondary} onClick={() => setModalAdd(true)}>
            + Adicionar Produto
          </button>
        )}
      </div>
      <p className={styles.dica}>
        Preço do produto pai vale para todos os SKUs. Preencha o SKU só quando ele tiver preço próprio.
      </p>

      {carregando ? (
        <p className={styles.vazio}>Carregando…</p>
      ) : erroCarga ? (
        <p className={styles.vazio} title={erroCarga}>Não foi possível carregar os preços por produto.</p>
      ) : grupos.length === 0 ? (
        <p className={styles.vazio}>Nenhum produto com preço nesta tabela.</p>
      ) : (
        <table className={styles.tabela}>
          <colgroup>
            <col style={{ width: 190 }} />
            <col />
            <col style={{ width: 130 }} />
            <col style={{ width: 130 }} />
            <col style={{ width: 44 }} />
          </colgroup>
          <thead>
            <tr>
              <th>Código</th>
              <th>Descrição</th>
              <th className={styles.num}>À vista</th>
              <th className={styles.num}>A prazo</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {grupos.map((grupo) => {
              const { paiId, pai } = grupo;
              const grade = grades[paiId];
              const aberto = !!abertos[paiId];
              const nExcecoes = Object.keys(grupo.skus).length;
              const codigo = pai?.codigo || grade?.produto?.codigo || "—";
              const descricao = pai?.descricao || grade?.produto?.descricao || "";
              const confirmando = confirmacao?.paiId === paiId ? confirmacao.tipo : null;
              return [
                <tr key={paiId} className={styles.linhaPai}>
                  <td>
                    <button className={styles.btnToggle} onClick={() => alternar(paiId)}
                      aria-expanded={aberto} title={aberto ? "Recolher SKUs" : "Expandir SKUs"}>
                      <Chevron aberto={aberto} />
                      <span className={styles.refBadge}>{codigo}</span>
                    </button>
                    {nExcecoes > 0 && (
                      <span className={styles.contExcecoes} title="SKUs com preço próprio">
                        {nExcecoes} {nExcecoes === 1 ? "exceção" : "exceções"}
                      </span>
                    )}
                  </td>
                  <td className={styles.descricao} title={descricao}>{descricao}</td>
                  {CAMPOS.map((campo) => (
                    <td key={campo}>
                      <CampoPreco
                        valor={num(pai?.[campo])}
                        readOnly={!editavel}
                        onSalvar={(v) => salvarPai(grupo, campo, v)}
                      />
                    </td>
                  ))}
                  <td className={styles.acoes}>
                    {editavel && (confirmando === "remover" ? (
                      <span className={styles.confirmar}>
                        <button className={styles.btnSim} onClick={confirmar}
                          title="Remove o preço do produto e as exceções dos SKUs">Sim</button>
                        <button className={styles.btnNao} onClick={() => setConfirmacao(null)}>Não</button>
                      </span>
                    ) : (
                      <button className={styles.btnRemover} title="Remover produto da tabela"
                        onClick={() => setConfirmacao({ tipo: "remover", paiId })}>×</button>
                    ))}
                  </td>
                </tr>,

                aberto && (grade?.carregando || !grade) && (
                  <tr key={`${paiId}-carregando`} className={styles.linhaSku}>
                    <td colSpan={5} className={styles.skuInfo}>Carregando SKUs…</td>
                  </tr>
                ),
                aberto && grade?.erro && (
                  <tr key={`${paiId}-erro`} className={styles.linhaSku}>
                    <td colSpan={5} className={styles.skuInfo} title={grade.erro}>
                      Não foi possível carregar os SKUs deste produto.
                    </td>
                  </tr>
                ),
                ...(aberto && grade?.skus ? grade.skus.map((sku) => {
                  const ex = grupo.skus[sku.id];
                  return (
                    <tr key={`${paiId}-${sku.id}`} className={styles.linhaSku}>
                      <td className={styles.skuCodigo} title={sku.codigo}>{sku.codigo}</td>
                      <td className={styles.descricao} title={sku.descricao}>{sku.descricao}</td>
                      {CAMPOS.map((campo) => {
                        const valorPai = num(pai?.[campo]);
                        const valorSku = ex ? num(ex[campo]) : null;
                        const proprio = valorSku != null && !iguais(valorSku, valorPai);
                        return (
                          <td key={campo}>
                            <CampoPreco
                              valor={proprio ? valorSku : null}
                              placeholder={valorPai != null ? moeda(valorPai) : "—"}
                              destaque={proprio}
                              readOnly={!editavel}
                              onSalvar={(v) => salvarSku(grupo, sku, campo, v)}
                            />
                          </td>
                        );
                      })}
                      <td />
                    </tr>
                  );
                }) : []),
                aberto && grade?.skus && !grade.carregando && (
                  <tr key={`${paiId}-rodape`} className={styles.linhaSkuRodape}>
                    <td colSpan={5}>
                      {grade.skus.length === 0 && <span className={styles.skuInfoInline}>Nenhum SKU ativo.</span>}
                      {erroAcao?.paiId === paiId && (
                        <span className={styles.erroAcao} title={erroAcao.msg}>Falha ao remover. Passe o mouse para ver o motivo.</span>
                      )}
                      {editavel && (confirmando === "limpar" ? (
                        <span className={styles.confirmar}>
                          <span className={styles.skuInfoInline}>Remover {nExcecoes} {nExcecoes === 1 ? "exceção" : "exceções"}?</span>
                          <button className={styles.btnSim} onClick={confirmar}>Sim</button>
                          <button className={styles.btnNao} onClick={() => setConfirmacao(null)}>Não</button>
                        </span>
                      ) : (
                        <button className={styles.btnLink} disabled={nExcecoes === 0}
                          onClick={() => setConfirmacao({ tipo: "limpar", paiId })}>
                          Limpar exceções
                        </button>
                      ))}
                    </td>
                  </tr>
                ),
              ];
            })}
          </tbody>
        </table>
      )}

      {modalAdd && (
        <ModalAdicionarProduto
          existentes={new Set(grupos.map((g) => g.paiId))}
          onFechar={() => setModalAdd(false)}
          onSalvar={adicionar}
        />
      )}
    </section>
  );
}

// ── Modal: adicionar produto pai ─────────────────────────────────────────────

function ModalAdicionarProduto({ existentes, onFechar, onSalvar }) {
  const [busca, setBusca] = useState("");
  const [resultados, setResultados] = useState([]);
  const [buscando, setBuscando] = useState(false);
  const [produto, setProduto] = useState(null);
  const [precos, setPrecos] = useState({ preco_avista: "", preco_aprazo: "" });
  const [erros, setErros] = useState({});
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    const q = busca.trim();
    if (!q) { setResultados([]); return undefined; }
    const t = setTimeout(async () => {
      setBuscando(true);
      try {
        const r = await produtosApi.buscaPedido(q);
        setResultados((r || []).filter((p) => p.tipo === "pai" && !existentes.has(String(p.id))));
      } catch {
        setResultados([]);
      } finally {
        setBuscando(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [busca]); // eslint-disable-line react-hooks/exhaustive-deps

  const salvar = async () => {
    const novos = {};
    const valores = {};
    for (const campo of CAMPOS) {
      const n = parseNumeroBR(precos[campo]);
      if (n === null) novos[campo] = `Informe o preço ${ROTULO[campo]}.`;
      else if (Number.isNaN(n)) novos[campo] = "Valor inválido.";
      else valores[campo] = n;
    }
    if (!produto) novos.produto = "Selecione um produto.";
    setErros(novos);
    if (Object.keys(novos).length) return;
    setSalvando(true);
    try {
      await onSalvar(produto, valores.preco_avista, valores.preco_aprazo);
    } catch (e) {
      setErros({ geral: e.message });
      setSalvando(false);
    }
  };

  return (
    <div className={styles.overlay} onMouseDown={(e) => { if (e.target === e.currentTarget) onFechar(); }}
      onKeyDown={(e) => { if (e.key === "Escape") onFechar(); }}>
      <div className={styles.modal}>
        <h3 className={styles.modalTitulo}>Adicionar Produto</h3>

        {produto ? (
          <div className={styles.produtoSel}>
            <div>
              <span className={styles.refBadge}>{produto.codigo}</span>
              <div className={styles.produtoSelNome}>{produto.descricao}</div>
            </div>
            <button className={styles.btnLink} onClick={() => { setProduto(null); setBusca(""); }}>Trocar</button>
          </div>
        ) : (
          <div className={styles.buscaWrap}>
            <label className={styles.campoLabel}>
              <span>Produto pai (código ou descrição)</span>
              <input
                className={`${styles.inputModal} ${erros.produto ? styles.campoErro : ""}`}
                title={erros.produto || ""}
                value={busca}
                onChange={(e) => setBusca(e.target.value.toUpperCase())}
                placeholder="DIGITE PARA BUSCAR…"
                autoFocus
              />
            </label>
            {(resultados.length > 0 || buscando) && (
              <ul className={styles.dropdown}>
                {buscando && <li className={styles.dropdownInfo}>Buscando…</li>}
                {resultados.map((p) => (
                  <li key={p.id} className={styles.dropdownItem}
                    onMouseDown={(e) => { e.preventDefault(); setProduto(p); setErros({}); }}>
                    <strong>{p.codigo}</strong> · {p.descricao}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className={styles.linhaPrecos}>
          {CAMPOS.map((campo) => (
            <label key={campo} className={styles.campoLabel}>
              <span>Preço {ROTULO[campo]} (R$)</span>
              <input
                className={`${styles.inputModal} ${styles.inputNum} ${erros[campo] ? styles.campoErro : ""}`}
                title={erros[campo] || ""}
                inputMode="decimal"
                value={precos[campo]}
                placeholder="0,00"
                onChange={(e) => {
                  const v = e.target.value.toUpperCase();
                  setPrecos((p) => ({ ...p, [campo]: v }));
                  setErros((er) => ({ ...er, [campo]: undefined }));
                }}
                onKeyDown={(e) => { if (e.key === "Enter") salvar(); }}
              />
            </label>
          ))}
        </div>

        <div className={styles.modalAcoes}>
          <button className={styles.btnPillSecondary} onClick={onFechar}>Cancelar</button>
          <button
            className={`${styles.btnPillPrimary} ${erros.geral ? styles.btnErro : ""}`}
            title={erros.geral || ""}
            onClick={salvar}
            disabled={salvando}
          >
            {salvando ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}
