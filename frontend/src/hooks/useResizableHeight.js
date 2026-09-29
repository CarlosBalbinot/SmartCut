import { useCallback, useRef, useState } from "react";

const PASSO_TECLADO = 40;

function carregar(chave) {
  try {
    const salvo = JSON.parse(localStorage.getItem(chave));
    return typeof salvo === "number" && salvo > 0 ? salvo : null;
  } catch {
    return null;
  }
}

function persistir(chave, altura) {
  try {
    if (altura == null) localStorage.removeItem(chave);
    else localStorage.setItem(chave, JSON.stringify(Math.round(altura)));
  } catch {
    // localStorage indisponível — a altura vale só nesta sessão.
  }
}

/**
 * Altura ajustável por arraste (alça na borda inferior), com persistência
 * em localStorage.
 *
 * min     — altura mínima (px); valor salvo abaixo dele usa o mínimo.
 * padrao  — altura sem valor salvo (px); o duplo clique volta para ela.
 * max     — opcional: teto (ex.: altura do conteúdo). Abaixo de min, vence.
 *
 * Retorna { altura, handleProps, resetar }: altura já limitada; espalhe
 * handleProps na alça. Arraste por pointer events com captura (continua
 * fora da alça); setas ↑/↓ ajustam de 40 em 40px; duplo clique restaura.
 */
export default function useResizableHeight(chave, { min, padrao, max = null }) {
  const [salvo, setSalvo] = useState(() => carregar(chave));
  const [arrastando, setArrastando] = useState(false);
  const arraste = useRef(null);

  const limitar = useCallback(
    (v) => {
      const comMinimo = Math.max(min, v);
      return max != null ? Math.min(comMinimo, max) : comMinimo;
    },
    [min, max]
  );

  const altura = limitar(salvo ?? padrao);

  const gravar = (v) => {
    const nova = limitar(v);
    setSalvo(nova);
    persistir(chave, nova);
  };

  const resetar = () => {
    setSalvo(null);
    persistir(chave, null);
  };

  const onPointerDown = (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    arraste.current = { inicioY: e.clientY, inicioAltura: altura, atual: altura };
    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    setArrastando(true);
  };

  const onPointerMove = (e) => {
    const a = arraste.current;
    if (!a) return;
    a.atual = limitar(a.inicioAltura + e.clientY - a.inicioY);
    setSalvo(a.atual);
  };

  const fimArraste = (e) => {
    const a = arraste.current;
    if (!a) return;
    arraste.current = null;
    if (e.currentTarget.hasPointerCapture?.(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    setArrastando(false);
    // Clique sem mover não grava: o padrão continua valendo.
    if (a.atual !== a.inicioAltura) persistir(chave, a.atual);
  };

  const onKeyDown = (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      gravar(altura + (e.key === "ArrowDown" ? PASSO_TECLADO : -PASSO_TECLADO));
    }
  };

  const handleProps = {
    role: "separator",
    "aria-orientation": "horizontal",
    "aria-label": "Altura da lista",
    "aria-valuenow": Math.round(altura),
    "aria-valuemin": min,
    ...(max != null ? { "aria-valuemax": Math.max(min, max) } : {}),
    tabIndex: 0,
    title: "Arraste para ajustar a altura",
    "data-arrastando": arrastando || undefined,
    onPointerDown,
    onPointerMove,
    onPointerUp: fimArraste,
    onPointerCancel: fimArraste,
    onDoubleClick: resetar,
    onKeyDown,
  };

  return { altura, handleProps, resetar };
}
