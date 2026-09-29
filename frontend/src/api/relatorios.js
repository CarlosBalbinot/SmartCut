import { createElement } from "react";
import { createRoot } from "react-dom/client";
import { API_BASE } from "../services/config";
import { apiFetch } from "../services/api";
import RelatorioViewer from "../components/RelatorioViewer/RelatorioViewer";

// Relatórios configuráveis (modelos HTML/Jinja2 da pasta relatorios/ — ver
// backend/services/relatorios/engine.py). Único ponto do frontend que
// imprime relatório: telas chamam só imprimirRelatorio/listarVariantes.

export const RELATORIO_PEDIDO_VENDA = "relVen001";
export const RELATORIO_FORMULARIO_CORTE = "relPro001";

// Rótulo do documento no título do visualizador ("Pedido 000001 · relVen001").
const ROTULOS = {
  [RELATORIO_PEDIDO_VENDA]: "Pedido",
  [RELATORIO_FORMULARIO_CORTE]: "Formulário de corte",
};

const BASE_URL = `${API_BASE}/api/v1/relatorios`;

const MSG_REINICIAR = "Reinicie o SmartCut para ativar a nova impressão";
const MSG_ERRO = "Não foi possível gerar o relatório.";

const noElectron = () => Boolean(window.electronAPI);

// Texto do erro para a tela. 422 de modelo: "Erro no modelo {arquivo},
// linha N: mensagem".
function mensagemErro({ modelo, erro, error, detail } = {}) {
  if (modelo) {
    const onde = modelo.linha ? `${modelo.arquivo}, linha ${modelo.linha}` : modelo.arquivo;
    return `Erro no modelo ${onde}: ${modelo.mensagem}`;
  }
  return erro || error || (typeof detail === "string" ? detail : null) || MSG_ERRO;
}

// Número do documento pelo <title> do modelo ("ORÇAMENTO 000001" → "000001").
function numeroDoTitulo(titulo) {
  const partes = String(titulo || "")
    .trim()
    .split(/\s+/);
  const ultimo = partes[partes.length - 1] || "";
  return /\d/.test(ultimo) ? ultimo : "";
}

function apiElectron() {
  const rel = window.smartcut?.relatorios;
  // Preload antigo (app aberto antes da atualização): sem a API nova.
  if (!rel?.gerarPdf) throw new Error(MSG_REINICIAR);
  return rel;
}

/** Modelos do relatório na pasta: [{ arquivo, padrao }] ([] se falhar). */
export async function listarVariantes(codigo) {
  try {
    const res = await apiFetch(`${BASE_URL}/${codigo}/variantes`);
    if (!res.ok) return [];
    const json = await res.json();
    return json.data || [];
  } catch {
    return [];
  }
}

/**
 * Conteúdo para o visualizador. Rejeita com Error(mensagem para a tela).
 *   Electron:  { tipo: "pdf", url (blob:), numero } — PDF gerado no processo
 *              principal (com rodapé "Página X/Y"). Liberar com URL.revokeObjectURL.
 *   Navegador: { tipo: "html", html, numero } — HTML do modelo (iframe srcdoc).
 */
async function carregarRelatorio(codigo, id, variante) {
  if (noElectron()) {
    // O preload repassa só (codigo, id, variante): as opções vão no 3º
    // argumento como objeto (ver relatorio:gerar-pdf no electron/main.js).
    const res = await apiElectron().gerarPdf(codigo, id, { variante: variante || null });
    if (!res?.ok) throw new Error(mensagemErro(res));
    const url = URL.createObjectURL(new Blob([res.pdf], { type: "application/pdf" }));
    return { tipo: "pdf", url, numero: numeroDoTitulo(res.titulo) };
  }

  try {
    const params = new URLSearchParams({ id });
    if (variante) params.set("variante", variante);
    const res = await apiFetch(`${BASE_URL}/${codigo}/html?${params}`);
    if (!res.ok) throw new Error(mensagemErro(await res.json().catch(() => ({}))));
    const html = await res.text();
    const titulo = new DOMParser().parseFromString(html, "text/html").title;
    return { tipo: "html", html, numero: numeroDoTitulo(titulo) };
  } catch (e) {
    // TypeError = falha de rede do fetch: mensagem genérica, não a técnica.
    throw e instanceof TypeError || !e?.message ? new Error(MSG_ERRO) : e;
  }
}

/** Electron: gera o PDF e grava onde o usuário escolher (diálogo nativo).
 *  Resolve { ok, cancelado?, caminho? }; rejeita com Error(mensagem). */
async function salvarPdf(codigo, id, variante, nomeSugerido) {
  const res = await apiElectron().gerarPdf(codigo, id, {
    variante: variante || null,
    acao: "salvar",
    nomeSugerido,
  });
  if (!res?.ok) throw new Error(mensagemErro(res));
  return res;
}

const LIMITE_IMAGENS_MS = 3000;

/**
 * Imprime o conteúdo do iframe do visualizador. Chamar só depois do evento
 * load do iframe: aqui ainda espera todas as imagens com complete=true
 * (limite de 3 s) antes do print() — sem isso o logo podia sair em branco.
 * PDF (Electron): o documento do visualizador não tem <img>, imprime direto.
 */
async function imprimirIframe(iframe) {
  const win = iframe?.contentWindow;
  if (!win) throw new Error("O relatório ainda não terminou de carregar.");
  const imagensProntas = () => {
    try {
      return Array.from(iframe.contentDocument?.images || []).every((img) => img.complete);
    } catch {
      return true; // documento inacessível: nada a verificar
    }
  };
  const inicio = Date.now();
  while (!imagensProntas() && Date.now() - inicio < LIMITE_IMAGENS_MS) {
    await new Promise((r) => setTimeout(r, 50));
  }
  win.focus();
  win.print();
}

// ── Visualizador (root próprio: as telas não precisam montar nada) ───────────

let visualizador = null; // { root, el }

function fecharVisualizador() {
  if (!visualizador) return;
  const { root, el } = visualizador;
  visualizador = null;
  root.unmount();
  el.remove();
}

/**
 * Abre o relatório `codigo` do registro `id` num card sobre o sistema, na
 * mesma aba (variante opcional; sem ela o backend usa o padrão do
 * config.json). Carregamento e erros (inclusive 422 do modelo) aparecem no
 * próprio card; Imprimir/Salvar PDF ficam na barra do card.
 */
export async function imprimirRelatorio(codigo, id, variante = null) {
  fecharVisualizador();
  const el = document.createElement("div");
  document.body.appendChild(el);
  const root = createRoot(el);
  visualizador = { root, el };
  root.render(
    createElement(RelatorioViewer, {
      codigo,
      id,
      varianteInicial: variante,
      rotulo: ROTULOS[codigo] || "Relatório",
      podeSalvar: noElectron(),
      carregar: carregarRelatorio,
      salvar: salvarPdf,
      imprimir: imprimirIframe,
      listarVariantes,
      onFechar: fecharVisualizador,
    })
  );
}
