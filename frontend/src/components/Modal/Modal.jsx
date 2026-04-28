import { useEffect } from "react";
import styles from "./Modal.module.css";

export default function Modal({ titulo, onClose, children, largura }) {
  useEffect(() => {
    function handleKey(e) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={styles.modal}
        style={largura ? { maxWidth: largura } : undefined}
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
