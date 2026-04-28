import Modal from "../Modal/Modal";
import styles from "./ConfirmModal.module.css";

/**
 * Modal de confirmação reutilizável.
 * @param {Object} props
 * @param {boolean} props.isOpen
 * @param {string}  props.titulo
 * @param {string}  props.mensagem
 * @param {string}  [props.labelConfirmar="Confirmar"]
 * @param {string}  [props.variante="perigo"] — "perigo" | "neutro"
 * @param {Function} props.onConfirmar
 * @param {Function} props.onCancelar
 */
export default function ConfirmModal({
  isOpen,
  titulo,
  mensagem,
  labelConfirmar = "Confirmar",
  variante = "perigo",
  onConfirmar,
  onCancelar,
}) {
  if (!isOpen) return null;
  return (
    <Modal titulo={titulo} onClose={onCancelar} largura="420px">
      <div className={styles.corpo}>
        <p className={styles.mensagem}>{mensagem}</p>
        <div className={styles.acoes}>
          <button className={styles.btnCancelar} onClick={onCancelar}>
            Cancelar
          </button>
          <button
            className={`${styles.btnConfirmar} ${styles[`btnConfirmar_${variante}`]}`}
            onClick={onConfirmar}
            autoFocus
          >
            {labelConfirmar}
          </button>
        </div>
      </div>
    </Modal>
  );
}
