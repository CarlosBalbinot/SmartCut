import { useState } from "react";
import { reenviarAnexo } from "../../api/financeiro";
import styles from "./AnexoArquivo.module.css";

// Botão de download de um anexo do financeiro. Quando o arquivo não está mais
// na pasta de dados (anexo.arquivo_existe === false — ex.: perdido numa
// reinstalação antiga), mostra "Arquivo não encontrado" com a opção de
// reenviar o arquivo, mantendo o registro do anexo.
export default function AnexoArquivo({
  anexo,
  onDownload,
  onReenviado,
  className,
  accept,
  rotulo = "Download",
}) {
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState(null);

  if (anexo.arquivo_existe !== false) {
    return (
      <button type="button" className={className} onClick={() => onDownload(anexo)}>
        {rotulo}
      </button>
    );
  }

  const reenviar = async (arquivo) => {
    setEnviando(true);
    setErro(null);
    try {
      const novo = await reenviarAnexo(anexo.id, arquivo);
      onReenviado?.(novo);
    } catch (e) {
      setErro(e.message || "Erro ao reenviar.");
    }
    setEnviando(false);
  };

  return (
    <>
      <span
        className={styles.aviso}
        title={erro || "O arquivo deste anexo não foi encontrado no computador"}
      >
        {erro ? "Erro ao reenviar" : "Arquivo não encontrado"}
      </span>
      <label className={className}>
        {enviando ? "Enviando…" : "Reenviar"}
        <input
          type="file"
          accept={accept}
          className={styles.inputOculto}
          disabled={enviando}
          onChange={(e) => {
            const f = e.target.files[0];
            if (f) reenviar(f);
            e.target.value = "";
          }}
        />
      </label>
    </>
  );
}
