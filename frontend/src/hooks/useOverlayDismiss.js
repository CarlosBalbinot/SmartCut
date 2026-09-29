import { useRef } from "react";

/**
 * Props para o fundo (overlay) de um modal que fecha ao clicar fora.
 *
 * Só fecha quando o mousedown E o click acontecem no próprio overlay.
 * Assim, selecionar texto de um campo (ou arrastar coluna/alça) e soltar o
 * botão fora do card não fecha o modal — nesse caso o navegador dispara o
 * click no ancestral comum (o overlay), mas o mousedown começou dentro.
 *
 * Uso: <div className={styles.overlay} {...useOverlayDismiss(fechar)}>
 * Esc continua sendo responsabilidade de cada modal.
 */
export default function useOverlayDismiss(onClose, { enabled = true } = {}) {
  const downNoOverlay = useRef(false);

  return {
    onMouseDown: (e) => {
      downNoOverlay.current = e.target === e.currentTarget;
    },
    onClick: (e) => {
      const fechar = downNoOverlay.current && e.target === e.currentTarget;
      downNoOverlay.current = false;
      if (fechar && enabled) onClose?.();
    },
  };
}
