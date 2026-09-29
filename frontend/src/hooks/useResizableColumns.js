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
 * opcoes:
 *   chavesAntigas — chaves de versões anteriores, apagadas ao montar
 *   obterMaximo   — (coluna, larguras) => px: teto do arraste (ex.: o que
 *                   sobra antes da coluna flexível chegar ao mínimo dela);
 *                   sem ele o arraste não tem teto
 *
 * Uso: coloque o handle na borda direita de cada <th> com
 * onMouseDown={iniciarArrasto("coluna")} e
 * onDoubleClick={() => restaurar("coluna")}.
 */
export default function useResizableColumns(chave, larguraPadrao, minimos = {}, opcoes = {}) {
  const padraoRef = useRef(larguraPadrao);
  const minimosRef = useRef(minimos);
  const obterMaximoRef = useRef(opcoes.obterMaximo);
  obterMaximoRef.current = opcoes.obterMaximo;
  const [larguras, setLarguras] = useState(() => carregar(chave, larguraPadrao));
  const [arrastando, setArrastando] = useState(null);

  useEffect(() => {
    try {
      for (const antiga of opcoes.chavesAntigas || []) localStorage.removeItem(antiga);
    } catch {
      // localStorage indisponível — nada a limpar.
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(chave, JSON.stringify(larguras));
    } catch {
      // localStorage indisponível — larguras valem só nesta sessão.
    }
  }, [chave, larguras]);

  const minimoDe = (coluna) => Math.max(LARGURA_MINIMA, minimosRef.current[coluna] || 0);

  // Entre o mínimo e o teto (se houver); teto abaixo do mínimo → mínimo.
  const limitar = (coluna, largura, prev) => {
    const minimo = minimoDe(coluna);
    const maximo = obterMaximoRef.current?.(coluna, prev) ?? Infinity;
    return Math.max(minimo, Math.min(largura, maximo));
  };

  const iniciarArrasto = useCallback(
    (coluna) => (e) => {
      if (e.button !== 0) return;
      e.preventDefault();
      e.stopPropagation();
      const th = e.currentTarget.parentElement;
      const inicioX = e.clientX;
      // Coluna flexível ainda não tem largura salva — parte da renderizada.
      const inicioLargura = th ? th.getBoundingClientRect().width : LARGURA_MINIMA;

      const aoMover = (ev) => {
        setLarguras((prev) => {
          const nova = limitar(coluna, Math.round(inicioLargura + ev.clientX - inicioX), prev);
          return prev[coluna] === nova ? prev : { ...prev, [coluna]: nova };
        });
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
    setLarguras((prev) => {
      const padrao = padraoRef.current[coluna] ?? null;
      return { ...prev, [coluna]: padrao == null ? null : limitar(coluna, padrao, prev) };
    });
  }, []);

  return { larguras, arrastando, iniciarArrasto, restaurar };
}
