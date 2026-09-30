import { useState } from "react";
import styles from "./DecisaoEnfesto.module.css";

/**
 * Quadro "Decisão do sistema": como cada lote vai ser estendido (enfesto
 * simples ou enfesto duplo, modo de camadas, camadas) e o porquê, em uma ou duas
 * frases. "Ver alternativas" abre a tabela das formas avaliadas (metros,
 * mesas, camadas, sobra) e das que não couberam no tempo da ordem — é a
 * decisão do backend (nesting_v2/decisor.py).
 *
 * Props:
 *   decisoes — [{ lote_id, grupo, tecido, produto_nome?, lote_codigo?, tipo_enfesto, tipo_nome,
 *                modo_camadas, motivo, regra, manual, tempo_esgotado,
 *                candidatos: [{ tipo, modo, rotulo, metros, mesas, camadas,
 *                               sobra, avaliado, erro }] }]
 */

export const NOME_TIPO_ENFESTO = { MESMA_FACE: "Enfesto simples", FACE_A_FACE: "Enfesto duplo" };
const NOME_MODO = { SEM_SOBRA: "sem sobra", MENOS_ENFESTOS: "menos enfestos" };

const fmtM = (v) =>
  v == null
    ? "—"
    : `${Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m`;

const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

function escolhido(d) {
  return (d.candidatos || []).find((c) => c.tipo === d.tipo_enfesto && c.modo === d.modo_camadas);
}

function Lote({ d, varios }) {
  const [aberto, setAberto] = useState(false);
  const venc = escolhido(d);
  // A tabela abre sempre que houve mais de uma forma possível: é ela que
  // mostra o que ficou "não avaliada" — que é justamente o que o usuário
  // precisa ver quando a comparação não coube no tempo (ou não sobrou tempo
  // para ela). Antes o botão só aparecia com duas ou mais avaliadas, e a
  // meia comparação ficava sem explicação.
  const temAlternativas = (d.candidatos || []).length > 1;
  const titulo = [
    NOME_TIPO_ENFESTO[d.tipo_enfesto] || d.tipo_nome,
    NOME_MODO[d.modo_camadas] || d.modo_camadas,
    venc?.avaliado && venc.camadas ? plural(venc.camadas, "camada", "camadas") : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className={styles.lote}>
      {varios && (
        <div className={styles.tecido}>
          {d.lote_codigo ? `${d.lote_codigo} · ` : ""}
          {d.tecido || "Lote"}
          {d.produto_nome ? ` · ${d.produto_nome}` : ""}
        </div>
      )}
      <div className={styles.escolha}>
        {titulo}
        {d.manual && <span className={styles.selo}>manual</span>}
      </div>
      <p className={styles.motivo}>{d.motivo}</p>
      {temAlternativas && (
        <button type="button" className={styles.link} onClick={() => setAberto((a) => !a)}>
          {aberto ? "ocultar alternativas" : "ver alternativas"}
        </button>
      )}
      {aberto && (
        <table className={styles.tabela}>
          <thead>
            <tr>
              <th>Forma de enfesto</th>
              <th className={styles.num}>Metros</th>
              <th className={styles.num}>Mesas</th>
              <th className={styles.num}>Camadas</th>
              <th className={styles.num}>Sobra</th>
            </tr>
          </thead>
          <tbody>
            {d.candidatos.map((c) => {
              const eh = c.tipo === d.tipo_enfesto && c.modo === d.modo_camadas;
              return (
                <tr key={`${c.tipo}-${c.modo}`} className={eh ? styles.vencedor : ""}>
                  <td>
                    {NOME_TIPO_ENFESTO[c.tipo]}, {NOME_MODO[c.modo] || c.modo}
                    {eh && <span className={styles.selo}>escolhida</span>}
                  </td>
                  {c.erro || !c.avaliado ? (
                    <td colSpan={4} className={styles.naoAvaliado}>
                      {c.erro ? `não encaixou: ${c.erro}` : "não avaliada"}
                    </td>
                  ) : (
                    <>
                      <td className={styles.num}>{fmtM(c.metros)}</td>
                      <td className={styles.num}>{c.mesas}</td>
                      <td className={styles.num}>{c.camadas}</td>
                      <td className={styles.num}>{c.sobra || "—"}</td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function DecisaoEnfesto({ decisoes }) {
  if (!decisoes?.length) return null;
  return (
    <section className={styles.quadro} aria-label="Decisão do sistema">
      <h4 className={styles.cabecalho}>Decisão do sistema</h4>
      {decisoes.map((d) => (
        <Lote key={d.grupo || d.lote_id || d.tecido} d={d} varios={decisoes.length > 1} />
      ))}
    </section>
  );
}
