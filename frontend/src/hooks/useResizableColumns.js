import { useCallback, useEffect, useRef, useState } from "react";

const LARGURA_MINIMA = 50;

// Largura null = coluna flexível (ocupa o espaço que sobrar na tabela).
function carregar(chave, larguraPadrao) {
  try {
    const salvo = JSON.parse(localStorage.getItem(chave) || "{}");
    const larguras = { ...larguraPadrao };
    for (const coluna of Object.keys(larguraPadrao)) {
      if (typeof salvo[coluna] === "number" || salvo[coluna] === null) {
        larguras[coluna] = salvo[coluna];
      }
    }
    return larguras;
  } catch {
    return { ...larguraPadrao };
  }
}

/**
 * Colunas redimensionáveis com persistência em localStorage.
 *
 * larguraPadrao: { coluna: px | null }. minimos (opcional): { coluna: px }
 * para colunas que precisam de mais que o mínimo geral de 50px.
 *
 * Uso: coloque o handle na borda direita de cada <th> com
 * onMouseDown={iniciarArrasto("coluna")} e
 * onDoubleClick={() => restaurar("coluna")}.
 */
export default function useResizableColumns(chave, larguraPadrao, minimos = {}) {
  const padraoRef = useRef(larguraPadrao);
  const minimosRef = useRef(minimos);
  const [larguras, setLarguras] = useState(() => carregar(chave, larguraPadrao));
  const [arrastando, setArrastando] = useState(null);

  useEffect(() => {
    try {
      localStorage.setItem(chave, JSON.stringify(larguras));
    } catch {
      // localStorage indisponível — larguras valem só nesta sessão.
    }
  }, [chave, larguras]);

  const iniciarArrasto = useCallback(
    (coluna) => (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      e.stopPropagation();
      const th = e.currentTarget.parentElement;
      const inicioX = e.clientX;
      // Coluna flexível ainda não tem largura salva — parte da renderizada.
      const inicioLargura = th ? th.getBoundingClientRect().width : LARGURA_MINIMA;
      const minimo = Math.max(LARGURA_MINIMA, minimosRef.current[coluna] || 0);

      const aoMover = (ev) => {
        const nova = Math.max(minimo, Math.round(inicioLargura + ev.clientX - inicioX));
        setLarguras((prev) => (prev[coluna] === nova ? prev : { ...prev, [coluna]: nova }));
      };
      const aoSoltar = () => {
        window.removeEventListener("mousemove", aoMover);
        window.removeEventListener("mouseup", aoSoltar);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        setArrastando(null);
      };

      window.addEventListener("mousemove", aoMover);
      window.addEventListener("mouseup", aoSoltar);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      setArrastando(coluna);
    },
    []
  );

  const restaurar = useCallback((coluna) => {
    setLarguras((prev) => ({ ...prev, [coluna]: padraoRef.current[coluna] ?? null }));
  }, []);

  return { larguras, arrastando, iniciarArrasto, restaurar };
}
