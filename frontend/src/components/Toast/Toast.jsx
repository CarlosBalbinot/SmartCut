import { useEffect, useRef, useState } from "react";
import styles from "./Toast.module.css";

const DURACAO_MS = 4000;

const ICONES = {
  sucesso: "✓",
  erro:    "✕",
  aviso:   "⚠",
  info:    "ℹ",
};

export default function Toast({ toast, onRemove }) {
  const { id, message, type } = toast;
  const [saindo, setSaindo] = useState(false);
  const timerRef = useRef(null);

  function fechar() {
    setSaindo(true);
    setTimeout(() => onRemove(id), 280);
  }

  useEffect(() => {
    timerRef.current = setTimeout(fechar, DURACAO_MS);
    return () => clearTimeout(timerRef.current);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      className={`${styles.toast} ${styles[`toast_${type}`]} ${saindo ? styles.saindo : styles.entrando}`}
      role="alert"
    >
      <span className={styles.icone}>{ICONES[type] ?? "ℹ"}</span>
      <span className={styles.mensagem}>{message}</span>
      <button className={styles.fechar} onClick={fechar} aria-label="Fechar">×</button>
      <div
        className={`${styles.barra} ${styles[`barra_${type}`]}`}
        style={{ animationDuration: `${DURACAO_MS}ms` }}
      />
    </div>
  );
}
