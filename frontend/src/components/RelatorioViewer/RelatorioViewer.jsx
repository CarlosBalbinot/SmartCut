import { useCallback, useEffect, useRef, useState } from "react";
import useOverlayDismiss from "../../hooks/useOverlayDismiss";
import styles from "./RelatorioViewer.module.css";

// Card sobre o sistema (mesma aba) que mostra um relatório configurável.
// Montado por api/relatorios.js (imprimirRelatorio) em root próprio; as
// funções de dados chegam por props:
//   carregar(codigo, id, variante) → { tipo: "pdf", url } | { tipo: "html", html }, + numero
//   salvar(codigo, id, variante, nomeSugerido) → { ok, cancelado? }  (só Electron)
//   imprimir(iframe) → print() quando as imagens do iframe estiverem prontas
//   listarVariantes(codigo) → [{ arquivo, padrao }]

function IconeImprimir() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6 9V3h12v6" />
      <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
      <path d="M6 14h12v7H6z" />
    </svg>
  );
}

function IconeSalvar() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 3v12" />
      <path d="m7 10 5 5 5-5" />
      <path d="M5 21h14" />
    </svg>
  );
}

function IconeFechar() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </svg>
  );
}

function IconeErro() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" />
      <path d="M12 7v6" />
      <path d="M12 17h.01" />
    </svg>
  );
}

export default function RelatorioViewer({
  codigo,
  id,
  varianteInicial = null,
  rotulo = "Relatório",
  podeSalvar = false,
  carregar,
  salvar,
  imprimir,
  listarVariantes,
  onFechar,
}) {
  const overlayProps = useOverlayDismiss(() => onFechar());
  const [variantes, setVariantes] = useState([]);
  const [variante, setVariante] = useState(varianteInicial);
  const [conteudo, setConteudo] = useState(null); // { tipo, url | html, numero }
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [salvando, setSalvando] = useState(false);
  const [numero, setNumero] = useState("");
  const [iframeCarregado, setIframeCarregado] = useState(false);

  const cardRef = useRef(null);
  const iframeRef = useRef(null);
  const requisicao = useRef(0);

  useEffect(() => {
    let ativo = true;
    listarVariantes(codigo).then((lista) => ativo && setVariantes(lista));
    return () => {
      ativo = false;
    };
  }, [codigo, listarVariantes]);

  // (Re)carrega ao abrir e ao trocar de modelo. Só a última requisição vale;
  // o blob URL anterior é liberado na troca e ao fechar.
  useEffect(() => {
    const atual = ++requisicao.current;
    let urlCriada = null;
    setCarregando(true);
    setErro(null);
    setAviso(null);
    setConteudo(null);
    setIframeCarregado(false);
    carregar(codigo, id, variante)
      .then((res) => {
        if (res.tipo === "pdf") urlCriada = res.url;
        if (atual !== requisicao.current) {
          if (urlCriada) URL.revokeObjectURL(urlCriada);
          return;
        }
        setConteudo(res);
        if (res.numero) setNumero(res.numero);
      })
      .catch((e) => {
        if (atual === requisicao.current) setErro(e.message);
      })
      .finally(() => {
        if (atual === requisicao.current) setCarregando(false);
      });
    return () => {
      if (urlCriada) URL.revokeObjectURL(urlCriada);
    };
  }, [codigo, id, variante, carregar]);

  // Esc fecha. O foco vai para o card ao abrir (Esc funciona de imediato).
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onFechar();
    };
    window.addEventListener("keydown", onKey);
    cardRef.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onFechar]);

  // HTML (srcdoc) é da mesma origem: Esc dentro dele também fecha. O
  // visualizador de PDF do Chromium não repassa teclas para a página.
  const onIframeLoad = useCallback(() => {
    setIframeCarregado(true);
    const win = iframeRef.current?.contentWindow;
    if (!win || conteudo?.tipo !== "html") return;
    try {
      win.addEventListener("keydown", (e) => {
        if (e.key === "Escape") onFechar();
      });
    } catch {
      /* frame inacessível: só o Esc da página vale */
    }
  }, [conteudo, onFechar]);

  const imprimirRelatorio = async () => {
    setAviso(null);
    try {
      await imprimir(iframeRef.current);
    } catch {
      setAviso("Não foi possível abrir a impressão. Use o botão de imprimir do visualizador.");
    }
  };

  const salvarPdf = async () => {
    if (salvando) return;
    setSalvando(true);
    setAviso(null);
    try {
      const nome = `${rotulo}_${numero || id}.pdf`.replace(/[\\/:*?"<>|\s]+/g, "_");
      await salvar(codigo, id, variante, nome);
    } catch (e) {
      setAviso(e.message);
    } finally {
      setSalvando(false);
    }
  };

  const titulo = numero ? `${rotulo} ${numero}` : rotulo;
  const pronto = Boolean(conteudo) && !carregando && !erro;
  const arquivoSelecionado = variante || variantes.find((v) => v.padrao)?.arquivo || "";

  return (
    <div className={styles.overlay} {...overlayProps}>
      <div
        ref={cardRef}
        className={styles.card}
        role="dialog"
        aria-modal="true"
        aria-label={`${titulo} · ${codigo}`}
        tabIndex={-1}
      >
        <div className={styles.barra}>
          <div className={styles.titulo}>
            {titulo}
            <span className={styles.codigo}> · {codigo}</span>
          </div>
          <div className={styles.acoes}>
            {variantes.length > 1 && (
              <select
                className={styles.seletor}
                value={arquivoSelecionado}
                onChange={(e) => setVariante(e.target.value)}
                aria-label="Modelo do relatório"
              >
                {variantes.map((v) => (
                  <option key={v.arquivo} value={v.arquivo}>
                    {v.arquivo}
                    {v.padrao ? " (padrão)" : ""}
                  </option>
                ))}
              </select>
            )}
            <button
              type="button"
              className={styles.botao}
              onClick={imprimirRelatorio}
              disabled={!pronto || (conteudo.tipo === "html" && !iframeCarregado)}
            >
              <IconeImprimir />
              Imprimir
            </button>
            {podeSalvar && (
              <button
                type="button"
                className={styles.botao}
                onClick={salvarPdf}
                disabled={!pronto || salvando}
              >
                <IconeSalvar />
                {salvando ? "Salvando..." : "Salvar PDF"}
              </button>
            )}
            <button
              type="button"
              className={styles.fechar}
              onClick={onFechar}
              aria-label="Fechar"
              title="Fechar (Esc)"
            >
              <IconeFechar />
            </button>
          </div>
        </div>

        {aviso && <div className={styles.aviso}>{aviso}</div>}

        <div className={styles.corpo}>
          {carregando && (
            <div className={styles.estado}>
              <span className={styles.spinner} aria-hidden="true" />
              Gerando relatório...
            </div>
          )}
          {!carregando && erro && (
            <div className={styles.estado}>
              <div className={styles.erro}>
                <IconeErro />
                <span>{erro}</span>
              </div>
            </div>
          )}
          {pronto && conteudo.tipo === "pdf" && (
            <iframe
              ref={iframeRef}
              className={styles.iframe}
              src={conteudo.url}
              title={titulo}
              onLoad={onIframeLoad}
            />
          )}
          {pronto && conteudo.tipo === "html" && (
            // Sem allow-scripts: o modelo não usa JavaScript. allow-same-origin
            // permite o print() daqui; allow-modals libera o diálogo de impressão.
            <iframe
              ref={iframeRef}
              className={styles.iframe}
              srcDoc={conteudo.html}
              sandbox="allow-same-origin allow-modals"
              title={titulo}
              onLoad={onIframeLoad}
            />
          )}
        </div>
      </div>
    </div>
  );
}
