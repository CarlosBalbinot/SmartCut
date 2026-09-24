/**
 * EditarMoldeModal — edição de um molde individual, com visualização da
 * peça e uma seta interativa (arrasto do mouse) para definir o sentido
 * do fio por ângulo, em vez de botões fixos.
 */
import { useMemo, useState } from "react";
import Modal from "../Modal/Modal";
import SetaFioArrastavel, {
  CATEGORIA_LABEL,
  anguloInicial,
  anguloParaCategoria,
} from "../SetaFioArrastavel";
import styles from "./EditarMoldeModal.module.css";

const TAMANHOS_DISPONIVEIS = ["PP", "P", "M", "G", "GG", "XGG"];

// ── Componente principal ─────────────────────────────────────────────

export default function EditarMoldeModal({
  molde,
  onClose,
  onSalvar,
  onExcluir,
  podeExcluir,
  salvando,
  erro,
}) {
  const [nome, setNome] = useState(molde.nome ?? "");
  const [peca, setPeca] = useState(molde.peca ?? "");
  const [tamanho, setTamanho] = useState(molde.tamanho ?? "");
  const [tipoCorte, setTipoCorte] = useState(molde.tipo_corte ?? "par");
  const [angulo, setAngulo] = useState(() => anguloInicial(molde.sentido_fio));

  const categoria = useMemo(() => anguloParaCategoria(angulo), [angulo]);

  function submeter(e) {
    e.preventDefault();
    onSalvar({
      nome: nome.trim(),
      peca: peca.trim() || null,
      tamanho: tamanho.trim() || null,
      sentido_fio: categoria,
      tipo_corte: tipoCorte,
    });
  }

  return (
    <Modal titulo="Editar Molde" onClose={onClose} largura="780px">
      {erro && <p className={styles.erro}>{erro}</p>}

      <div className={styles.layout}>
        {/* ── Coluna esquerda: visualização + seta ── */}
        <div className={styles.colunaEsquerda}>
          <span className={styles.tituloColuna}>Visualização</span>
          <SetaFioArrastavel
            geometria_json={molde.geometria_json}
            sentidoFio={molde.sentido_fio}
            onChange={(_categoria, novoAngulo) => setAngulo(novoAngulo)}
            width={300}
            height={300}
          />
        </div>

        {/* ── Coluna direita: campos ── */}
        <form className={styles.colunaDireita} onSubmit={submeter}>
          <div className={styles.campo}>
            <label className={styles.label}>Nome *</label>
            <input
              className={styles.input}
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              required
            />
          </div>

          <div className={styles.campo}>
            <label className={styles.label}>Parte</label>
            <input
              className={styles.input}
              value={peca}
              onChange={(e) => setPeca(e.target.value)}
              placeholder="Frente, Costa, Manga..."
            />
          </div>

          <div className={styles.campo}>
            <label className={styles.label}>Tamanho</label>
            <select
              className={styles.select}
              value={tamanho}
              onChange={(e) => setTamanho(e.target.value)}
            >
              <option value="">—</option>
              {TAMANHOS_DISPONIVEIS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.campo}>
            <label className={styles.label}>Sentido do fio</label>
            <input
              className={styles.input}
              value={`${CATEGORIA_LABEL[categoria]} (${Math.round(angulo)}°)`}
              disabled
              readOnly
            />
          </div>

          <div className={styles.campo}>
            <label className={styles.label}>Tipo de corte</label>
            <select
              className={styles.select}
              value={tipoCorte}
              onChange={(e) => setTipoCorte(e.target.value)}
            >
              <option value="simples">Simples (1 peça, sem espelho)</option>
              <option value="par">Par (2 peças espelhadas)</option>
              <option value="par_sem_espelho">Par sem espelho (2 peças)</option>
            </select>
          </div>

          <div className={styles.acoes}>
            {podeExcluir && (
              <button
                type="button"
                className={styles.btnExcluir}
                onClick={onExcluir}
                disabled={salvando}
              >
                Excluir esta peça
              </button>
            )}
            <div className={styles.acoesDireita}>
              <button type="button" className={styles.btnSecondary} onClick={onClose}>
                Cancelar
              </button>
              <button type="submit" className={styles.btnPrimary} disabled={salvando}>
                {salvando ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </Modal>
  );
}
