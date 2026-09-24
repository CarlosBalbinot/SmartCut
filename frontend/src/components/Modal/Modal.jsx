import { useEffect } from "react";
import styles from "./Modal.module.css";

export default function Modal({ titulo, onClose, children, largura, largura95vw }) {
  useEffect(() => {
    function handleKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const style = {};
  if (largura) style.maxWidth = largura;
  if (largura95vw) style.width = "95vw";

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={styles.modal}
        style={Object.keys(style).length ? style : undefined}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <h2 className={styles.titulo}>{titulo}</h2>
          <button className={styles.fechar} onClick={onClose} aria-label="Fechar">
            ✕
          </button>
        </div>
        <div className={styles.body}>{children}</div>
      </div>
    </div>
  );
}
