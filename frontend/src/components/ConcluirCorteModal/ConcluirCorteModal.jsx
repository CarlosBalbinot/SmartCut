import { useMemo, useState } from "react";
import Modal from "../Modal/Modal";
import styles from "./ConcluirCorteModal.module.css";

/**
 * Conclusão do corte (EM_CORTE → CONCLUIDA).
 *
 * Uma linha por LOTE — dois produtos podem sair do mesmo rolo, e a baixa do
 * estoque é por rolo. O CONSUMIDO REAL vem editável com o planejado como
 * padrão (é o que o backend debita do lote) e a SOBRA é o retalho que
 * sobrou do corte, opcional.
 *
 * O desvio do real contra o planejado só acende acima de 10%: abaixo disso
 * é imprecisão de balança, não uma diferença de corte.
 *
 * O componente não chama a API — devolve o payload e deixa quem abriu (a
 * página da OC) tratar o erro, recarregar e destravar os botões.
 *
 * Props:
 *   oc          — OC completa (usa `tecidos` e `planejado_por_lote`)
 *   enviando    — trava o botão enquanto a página conclui
 *   onConfirmar — (payload) => void; payload = { cortador, consumos, observacao }
 *   onCancelar  — () => void
 */

// Fora de 10% o real versus o planejado ganha destaque; dentro, não.
const TOLERANCIA_PCT = 10;

const numBR = (v, casas = 3) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("pt-BR", {
        minimumFractionDigits: casas,
        maximumFractionDigits: casas,
      });

/** Aceita "1.234,56", "1234,56" e "1234.56" — vírgula presente → pontos são
 *  milhar; só ponto → decimal se tiver até 2 casas depois dele. Mesma regra do
 *  resto do app: para kg, digite a vírgula (o campo já vem preenchido com
 *  vírgula). */
function parseNumeroBR(texto) {
  let t = String(texto ?? "").replace(/\s/g, "");
  if (!t) return NaN;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  else if ((t.match(/\./g) || []).length > 1 || /\.\d{2,}$/.test(t)) t = t.replace(/\./g, "");
  return /^-?\d*\.?\d*$/.test(t) ? Number(t) : NaN;
}

export default function ConcluirCorteModal({ oc, enviando = false, onConfirmar, onCancelar }) {
  // Uma linha por lote, na ordem dos tecidos da OC. Só entram lotes com
  // peso planejado: sem plano não há consumo a informar.
  const linhas = useMemo(() => {
    const planejado = oc.planejado_por_lote || {};
    const porLote = new Map();
    for (const t of oc.tecidos || []) {
      const lote = t.lote;
      if (!lote) continue;
      const alvo = porLote.get(lote.id) || {
        lote_id: lote.id,
        codigo: lote.codigo_lote,
        tecido: [lote.modelo, lote.cor_tecido].filter(Boolean).join(" — ") || "—",
        produtos: [],
        planejado: planejado[lote.id] ?? null,
      };
      const produto = t.produto_descricao || t.produto_codigo;
      if (produto && !alvo.produtos.includes(produto)) alvo.produtos.push(produto);
      porLote.set(lote.id, alvo);
    }
    return [...porLote.values()].filter((l) => l.planejado != null);
  }, [oc]);

  // Os textos ficam como string enquanto o usuário digita (senão o input
  // briga com o cursor em "12," ou "12."); a conversão é na hora de enviar.
  const [valores, setValores] = useState(() =>
    Object.fromEntries(linhas.map((l) => [l.lote_id, { real: numBR(l.planejado, 3), sobra: "" }]))
  );
  const [cortador, setCortador] = useState(oc.cortador || "");
  const [observacao, setObservacao] = useState("");
  const [erros, setErros] = useState({});

  const editar = (loteId, campo) => (e) => {
    const texto = e.target.value;
    setValores((v) => ({ ...v, [loteId]: { ...v[loteId], [campo]: texto } }));
    setErros((x) => {
      if (!x[loteId]?.[campo]) return x;
      const { [campo]: _, ...resto } = x[loteId];
      return { ...x, [loteId]: resto };
    });
  };

  const confirmar = () => {
    const novos = {};

    if (!cortador.trim()) {
      novos.cortador = "Informe quem fez o corte.";
    }

    const consumos = [];
    for (const l of linhas) {
      const v = valores[l.lote_id] || {};
      const erroLote = {};
      // Vazio = consome o planejado (mesma regra do backend).
      const real = String(v.real ?? "").trim() === "" ? l.planejado : parseNumeroBR(v.real);
      if (Number.isNaN(real)) erroLote.real = "Peso inválido.";
      else if (real < 0) erroLote.real = "Peso negativo.";

      const sobra = String(v.sobra ?? "").trim() === "" ? null : parseNumeroBR(v.sobra);
      if (sobra !== null && Number.isNaN(sobra)) erroLote.sobra = "Sobra inválida.";
      else if (sobra !== null && sobra < 0) erroLote.sobra = "Sobra negativa.";

      if (Object.keys(erroLote).length) {
        novos[l.lote_id] = erroLote;
      } else {
        consumos.push({
          lote_id: l.lote_id,
          kg_real: real,
          sobra_kg: sobra,
        });
      }
    }

    setErros(novos);
    if (Object.keys(novos).length) return;

    onConfirmar({
      cortador: cortador.trim(),
      consumos,
      observacao: observacao.trim() || null,
    });
  };

  const totalPlanejado = linhas.reduce((s, l) => s + (l.planejado || 0), 0);
  const totalReal = linhas.reduce((s, l) => {
    const bruto = String(valores[l.lote_id]?.real ?? "").trim();
    const n = bruto === "" ? l.planejado : parseNumeroBR(bruto);
    return s + (Number.isNaN(n) ? 0 : n);
  }, 0);

  return (
    <Modal titulo={`Concluir corte — ${oc.numero_fmt}`} onClose={onCancelar} largura="860px">
      <div className={styles.corpo}>
        <div className={styles.campos}>
          <label className={`${styles.campo} ${styles.campoLargo}`}>
            <span className={styles.rotulo}>
              Cortador <em>(obrigatório)</em>
            </span>
            <input
              className={`sc-input sc-upper ${erros.cortador ? "sc-campo-erro" : ""}`}
              value={cortador}
              maxLength={150}
              placeholder="Nome de quem fez o corte"
              title={erros.cortador || ""}
              onChange={(e) => {
                setCortador(e.target.value.toUpperCase());
                setErros((x) => (x.cortador ? { ...x, cortador: null } : x));
              }}
            />
          </label>
        </div>

        {linhas.length === 0 ? (
          <p className={styles.vazio}>
            Nenhum lote com peso planejado. Concluir vai encerrar a OC sem baixa de estoque.
          </p>
        ) : (
          <div className={styles.tabelaWrap}>
            <table className={styles.tabela}>
              <thead>
                <tr>
                  <th>Lote</th>
                  <th>Tecido</th>
                  <th className={styles.num}>Planejado (kg)</th>
                  <th className={styles.num}>Consumido real (kg)</th>
                  <th className={styles.num}>Sobra (kg)</th>
                </tr>
              </thead>
              <tbody>
                {linhas.map((l) => {
                  const v = valores[l.lote_id] || {};
                  const erroReal = erros[l.lote_id]?.real;
                  const erroSobra = erros[l.lote_id]?.sobra;
                  const bruto = String(v.real ?? "").trim();
                  const real = bruto === "" ? l.planejado : parseNumeroBR(bruto);
                  const desvio = Number.isNaN(real) ? null : real - l.planejado;
                  const desvioPct =
                    desvio === null || !l.planejado ? 0 : (Math.abs(desvio) / l.planejado) * 100;
                  return (
                    <tr key={l.lote_id}>
                      <td className={styles.lote}>{l.codigo}</td>
                      <td title={l.produtos.join(" · ")}>
                        <span className={styles.tecido}>{l.tecido}</span>
                        {l.produtos.length > 0 && (
                          <span className={styles.produtos}>{l.produtos.join(" · ")}</span>
                        )}
                      </td>
                      <td className={styles.num}>{numBR(l.planejado, 3)}</td>
                      <td className={styles.num}>
                        <div className={styles.celulaKg}>
                          <input
                            className={`sc-input ${erroReal ? "sc-campo-erro" : ""} ${desvioPct > TOLERANCIA_PCT ? styles.desvio : ""}`}
                            value={bruto}
                            inputMode="decimal"
                            placeholder={numBR(l.planejado, 3)}
                            title={
                              erroReal ||
                              "Use vírgula para os decimais (ex.: 12,500). Vazio = planejado."
                            }
                            onChange={editar(l.lote_id, "real")}
                          />
                          {desvioPct > TOLERANCIA_PCT && (
                            <span
                              className={`${styles.delta} ${desvio > 0 ? styles.deltaAcima : styles.deltaAbaixo}`}
                              title={
                                desvio > 0
                                  ? `Consumiu ${numBR(desvio, 3)} kg a mais que o planejado (${numBR(desvioPct, 1)}%).`
                                  : `Consumiu ${numBR(Math.abs(desvio), 3)} kg a menos que o planejado (${numBR(desvioPct, 1)}%).`
                              }
                            >
                              {desvio > 0 ? "+" : "−"}
                              {numBR(Math.abs(desvio), 3)}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className={styles.num}>
                        <input
                          className={`sc-input ${styles.inputKg} ${erroSobra ? "sc-campo-erro" : ""}`}
                          value={String(v.sobra ?? "")}
                          inputMode="decimal"
                          placeholder="—"
                          title={erroSobra || "Retalho que sobrou do corte (opcional)."}
                          onChange={editar(l.lote_id, "sobra")}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={2}>Total</td>
                  <td className={styles.num}>{numBR(totalPlanejado, 3)}</td>
                  <td className={styles.num}>{numBR(totalReal, 3)}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
            <p className={styles.nota}>
              O peso consumido sai do estoque de cada lote. A sobra é só um registro.
            </p>
          </div>
        )}

        <label className={styles.campo}>
          <span className={styles.rotulo}>
            Observação <em>(opcional)</em>
          </span>
          <textarea
            className={`sc-input ${styles.textarea}`}
            rows={2}
            maxLength={2000}
            value={observacao}
            placeholder="Aparelhamento, paradas, sobras…"
            onChange={(e) => setObservacao(e.target.value)}
          />
        </label>

        <div className={styles.acoes}>
          <button
            type="button"
            className={styles.btnCancelar}
            onClick={onCancelar}
            disabled={enviando}
          >
            Cancelar
          </button>
          <button
            type="button"
            className={styles.btnConfirmar}
            onClick={confirmar}
            disabled={enviando}
            autoFocus
          >
            {enviando ? "Concluindo…" : "Confirmar conclusão"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
