import { useEffect, useState } from "react";
import { simetriaMolde } from "../../api/moldes";

// Tipos em que as peças NÃO saem espelhadas: se a peça é assimétrica, quase
// sempre a roupa tem uma de cada lado e o tipo certo é "par".
const SEM_ESPELHO = ["simples", "par_sem_espelho"];

export const TEXTO_AVISO_SIMETRIA =
  "Esta peça não é simétrica. Se a roupa tem uma de cada lado (direita e esquerda), o tipo correto é Par.";

/**
 * Aviso (não bloqueia) de peça assimétrica marcada como simples ou par sem
 * espelho. A medida é a do decisor do enfesto (POST /moldes/simetria), no
 * eixo do sentido do fio e com a rotação base — vale o pior tamanho.
 * Devolve true quando o aviso deve aparecer.
 */
export default function useAvisoSimetria({ geometrias, sentidoFio, rotacaoBase = 0, tipoCorte }) {
  const [assimetrica, setAssimetrica] = useState(false);
  const validas = (geometrias || []).filter(Boolean);
  // Chave estável: as geometrias não mudam depois da leitura do arquivo.
  const chave = `${validas.length}|${sentidoFio}|${rotacaoBase}`;
  const consultar = SEM_ESPELHO.includes(tipoCorte) && validas.length > 0;

  useEffect(() => {
    if (!consultar) return undefined;
    let vivo = true;
    const t = setTimeout(async () => {
      try {
        const r = await simetriaMolde({
          geometrias: validas,
          sentido_fio: sentidoFio || null,
          rotacao_base: rotacaoBase || 0,
        });
        if (vivo) setAssimetrica(r.simetrica === false);
      } catch {
        // Aviso é ajuda, não validação: sem resposta, sem aviso.
        if (vivo) setAssimetrica(false);
      }
    }, 300);
    return () => {
      vivo = false;
      clearTimeout(t);
    };
  }, [chave, consultar]);

  return consultar && assimetrica;
}
