import { FileText, FileX, Download } from "lucide-react";
import styles from "./comprasVendas.module.css";

/*
 * Props:
 *   anchor             — { x, y } posição (viewport) onde o card deve aparecer
 *   titulo             — string, ex.: "Documentos Fiscais"
 *   subtitulo          — string, ex.: "NF 000123 — Fornecedor X"
 *   carregando         — bool, mostra estado de carregamento
 *   anexoXml           — anexo (tipo='XML') ou null
 *   anexoNf            — anexo (tipo='NF', PDF) ou null
 *   mostrarGerarDanfe  — bool, exibe a opção "DANFE Simplificada" quando há XML
 *   onGerarDanfe       — () => void
 *   onDownloadXml      — () => void
 *   onDownloadNf       — () => void
 *   onAnexarDocumento  — () => void
 *   onFechar           — () => void
 */
export default function DocumentosFiscaisCard({
  anchor,
  titulo,
  subtitulo,
  carregando,
  anexoXml,
  anexoNf,
  mostrarGerarDanfe,
  onGerarDanfe,
  onDownloadXml,
  onDownloadNf,
  onAnexarDocumento,
  onFechar,
}) {
  const temDocumento = !!anexoXml || !!anexoNf;

  return (
    <>
      <div className={styles.docCardBackdrop} onClick={onFechar} />
      <div
        className={styles.docCard}
        style={{ left: anchor.x, top: anchor.y }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.docCardHead}>
          <div>
            <p className={styles.docCardTitulo}>{titulo}</p>
            {subtitulo && <p className={styles.docCardSubtitulo}>{subtitulo}</p>}
          </div>
          <button className={styles.btnClose} onClick={onFechar} title="Fechar">
            ×
          </button>
        </div>

        <div className={styles.docCardBody}>
          {carregando ? (
            <p className={styles.docCardLoading}>Carregando…</p>
          ) : !temDocumento ? (
            <div className={styles.docCardEmpty}>
              <FileX size={30} strokeWidth={1.5} />
              <p className={styles.docCardEmptyTitulo}>Nenhum documento fiscal anexado</p>
              <p className={styles.docCardEmptyTexto}>
                Importe o XML ou PDF da nota fiscal para acessar os documentos.
              </p>
              <button className={styles.btnSecondary} onClick={onAnexarDocumento}>
                Anexar documento
              </button>
            </div>
          ) : (
            <>
              {anexoXml && mostrarGerarDanfe && (
                <button className={styles.docCardOption} onClick={onGerarDanfe}>
                  <FileText size={16} strokeWidth={1.75} />
                  <span>DANFE Simplificada</span>
                </button>
              )}
              {anexoXml && (
                <button className={styles.docCardOption} onClick={onDownloadXml}>
                  <Download size={16} strokeWidth={1.75} />
                  <span>Download XML</span>
                </button>
              )}
              {anexoNf && (
                <button className={styles.docCardOption} onClick={onDownloadNf}>
                  <Download size={16} strokeWidth={1.75} />
                  <span>Download DANFE (PDF)</span>
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
