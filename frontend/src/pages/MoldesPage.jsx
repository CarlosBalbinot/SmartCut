import { useEffect, useRef, useState } from "react";
import {
  getGrupos,
  importarGrupoMolde,
  renomearGrupo,
  deleteGrupo,
  previewMolde,
  updateMolde,
  deleteMolde,
  buscarProdutos,
} from "../api/moldes";
import Modal from "../components/Modal/Modal";
import GrupoAccordion from "../components/MoldesGrupo/GrupoAccordion";
import ParteCard from "../components/ImportacaoMoldes/ParteCard";
import EditarMoldeModal from "../components/ImportacaoMoldes/EditarMoldeModal";
import { useAuth } from "../auth/useAuth";
import ms from "./MoldesPage.module.css";

const MODULO = "moldes";

// ── Constantes ───────────────────────────────────────────────────────

const TAMANHOS_DISPONIVEIS = ["PP", "P", "M", "G", "GG", "XGG"];

const UPLOAD_INICIAL = {
  produto: null, // { id, codigo, descricao }
  tamanhosSelecionados: [],
  arquivo: null,
};

const DEBOUNCE_BUSCA_PRODUTO_MS = 400;

// ── Funções auxiliares ───────────────────────────────────────────────

const NOME_GENERICO = /^Peça \d+$/i;

/**
 * Agrupa as peças extraídas do arquivo em "partes" (Frente, Costa, Manga...).
 *
 * Peças com o mesmo nome_sugerido (texto lido do DXF) são a mesma parte —
 * cada uma delas é um tamanho diferente da mesma peça. Dentro de cada
 * parte, as peças são ordenadas por área crescente (proxy de PP→GG, já
 * que o backend não retorna o tamanho real de cada peça).
 *
 * Peças sem nome real (fallback "Peça N" do parser) não têm identidade
 * confiável para agrupar por nome, então caem no método antigo: blocos
 * posicionais de N peças (N = qtd. de tamanhos selecionados).
 */
function agruparEmPartes(pecas, tamanhosSelecionados) {
  const N = tamanhosSelecionados.length;
  if (N === 0 || pecas.length === 0) return { partes: [], sobra: pecas };

  const temNomeReal = (p) => p.nome_sugerido && !NOME_GENERICO.test(p.nome_sugerido);

  const grupos = {};
  for (const peca of pecas) {
    const chave = temNomeReal(peca) ? peca.nome_sugerido : "__generica__";
    if (!grupos[chave]) grupos[chave] = [];
    grupos[chave].push(peca);
  }

  const partes = [];
  const usadas = new Set();

  for (const [nome, bloco] of Object.entries(grupos)) {
    if (nome === "__generica__") continue;
    const ordenado = [...bloco].sort((a, b) => a.area_cm2 - b.area_cm2);
    const pecasDaParte = ordenado.slice(0, N);
    pecasDaParte.forEach((p) => usadas.add(p));
    const sentidoDetectado =
      bloco.find((p) => p.sentido_fio_detectado)?.sentido_fio_detectado ?? null;
    partes.push({
      nome,
      tipo_corte: "simples",
      // a seta arrastável sempre mostra uma pose (default vertical), então o
      // valor nunca deve começar nulo — evita bloquear a confirmação com um
      // campo que o usuário nunca foi explicitamente solicitado a definir
      sentido_fio: sentidoDetectado ?? "vertical",
      sentido_fio_auto: !!sentidoDetectado,
      rotacao_base: 0,
      pecas: tamanhosSelecionados.map((tam, i) => ({
        tamanho: tam,
        geometria_json: pecasDaParte[i]?.geometria_json ?? null,
        area_cm2: pecasDaParte[i]?.area_cm2 ?? null,
      })),
    });
  }

  // Peças genéricas (sem nome real): fallback posicional antigo
  const genericas = grupos["__generica__"] || [];
  const nPartesGenericas = Math.floor(genericas.length / N);
  for (let i = 0; i < nPartesGenericas; i++) {
    const bloco = genericas.slice(i * N, i * N + N);
    bloco.forEach((p) => usadas.add(p));
    const sentidoDetectado =
      bloco.find((p) => p.sentido_fio_detectado)?.sentido_fio_detectado ?? null;
    partes.push({
      nome: `Parte ${partes.length + 1}`,
      tipo_corte: "simples",
      sentido_fio: sentidoDetectado ?? "vertical",
      sentido_fio_auto: !!sentidoDetectado,
      rotacao_base: 0,
      pecas: tamanhosSelecionados.map((tam, j) => ({
        tamanho: tam,
        geometria_json: bloco[j].geometria_json,
        area_cm2: bloco[j].area_cm2,
      })),
    });
  }

  return { partes, sobra: pecas.filter((p) => !usadas.has(p)) };
}

// ── Componente principal ─────────────────────────────────────────────

export default function MoldesPage() {
  const { hasPermission } = useAuth();
  const [grupos, setGrupos] = useState([]);
  const [erro, setErro] = useState(null);
  const [sucesso, setSucesso] = useState(null);

  // Fluxo de importação: null | "upload" | "preview"
  const [fase, setFase] = useState(null);
  const [uploadForm, setUploadForm] = useState(UPLOAD_INICIAL);
  const [extraindo, setExtraindo] = useState(false);
  const [erroUpload, setErroUpload] = useState(null);
  const [previewMeta, setPreviewMeta] = useState(null); // {arquivo_path, formato}
  const [partes, setPartes] = useState([]); // estado editável de cada parte
  const [sobra, setSobra] = useState([]); // polylines que não cabem na grade
  const [salvando, setSalvando] = useState(false);
  const inputFileRef = useRef(null);

  // Autocomplete de produto
  const [buscaProduto, setBuscaProduto] = useState("");
  const [resultadosProduto, setResultadosProduto] = useState([]);
  const [buscandoProduto, setBuscandoProduto] = useState(false);
  const debounceProdutoRef = useRef(null);

  // Edição de molde individual
  const [editando, setEditando] = useState(null);
  const [erroEdit, setErroEdit] = useState(null);
  const [salvandoEdit, setSalvandoEdit] = useState(false);

  function carregarGrupos() {
    getGrupos()
      .then(setGrupos)
      .catch((e) => setErro(e.message));
  }

  useEffect(() => {
    carregarGrupos();
  }, []);

  // ── Upload ──────────────────────────────────────────────────────────

  function abrirUpload() {
    setUploadForm(UPLOAD_INICIAL);
    setErroUpload(null);
    setBuscaProduto("");
    setResultadosProduto([]);
    setFase("upload");
  }

  function fecharImportacao() {
    setFase(null);
    setPreviewMeta(null);
    setPartes([]);
    setSobra([]);
  }

  function handleBuscaProdutoChange(termo) {
    setBuscaProduto(termo);
    clearTimeout(debounceProdutoRef.current);
    if (!termo.trim()) {
      setResultadosProduto([]);
      return;
    }
    debounceProdutoRef.current = setTimeout(async () => {
      setBuscandoProduto(true);
      try {
        const data = await buscarProdutos(termo.trim());
        setResultadosProduto(data);
      } catch {
        setResultadosProduto([]);
      } finally {
        setBuscandoProduto(false);
      }
    }, DEBOUNCE_BUSCA_PRODUTO_MS);
  }

  function selecionarProduto(produto) {
    const tamanhosDoProduto = Array.isArray(produto.tamanhos_disponiveis)
      ? TAMANHOS_DISPONIVEIS.filter((t) => produto.tamanhos_disponiveis.includes(t))
      : [];
    setUploadForm((p) => ({
      ...p,
      produto,
      tamanhosSelecionados: tamanhosDoProduto,
    }));
    setBuscaProduto("");
    setResultadosProduto([]);
  }

  function limparProduto() {
    setUploadForm((p) => ({ ...p, produto: null }));
  }

  function toggleTamanho(t) {
    setUploadForm((prev) => {
      const sel = prev.tamanhosSelecionados;
      const novo = sel.includes(t) ? sel.filter((x) => x !== t) : [...sel, t];
      // mantém a ordem original de TAMANHOS_DISPONIVEIS
      return {
        ...prev,
        tamanhosSelecionados: TAMANHOS_DISPONIVEIS.filter((x) => novo.includes(x)),
      };
    });
  }

  async function extrairPecas(e) {
    e.preventDefault();
    const { produto, tamanhosSelecionados, arquivo } = uploadForm;
    if (!produto) {
      setErroUpload("Selecione o produto vinculado a este molde.");
      return;
    }
    if (tamanhosSelecionados.length === 0) {
      setErroUpload("Selecione pelo menos um tamanho.");
      return;
    }
    if (!arquivo) {
      setErroUpload("Selecione um arquivo DXF, PLT ou ADS.");
      return;
    }

    setExtraindo(true);
    setErroUpload(null);
    try {
      const fd = new FormData();
      fd.append("arquivo", arquivo);
      const data = await previewMolde(fd);
      // data.pecas já vêm ordenadas por área (backend ordena)
      const { partes: partesGeradas, sobra: sobraGerada } = agruparEmPartes(
        data.pecas,
        tamanhosSelecionados
      );
      setSobra(sobraGerada);
      setPreviewMeta({ arquivo_path: data.arquivo_path, formato: data.formato });
      setPartes(partesGeradas);
      setFase("preview");
    } catch (ex) {
      setErroUpload(ex.message);
    } finally {
      setExtraindo(false);
    }
  }

  // ── Edição de partes ─────────────────────────────────────────────────

  function handleParteChange(index, campo, valor) {
    setPartes((prev) => {
      const copia = [...prev];
      const atualizada = { ...copia[index], [campo]: valor };
      if (campo === "sentido_fio") {
        atualizada.sentido_fio_auto = false;
      }
      copia[index] = atualizada;
      return copia;
    });
  }

  function handleRemoveParte(index) {
    setPartes((prev) => prev.filter((_, i) => i !== index));
  }

  // ── Confirmação ──────────────────────────────────────────────────────

  async function confirmarImportacao() {
    if (partes.some((p) => !p.nome.trim())) {
      setErro("Todas as partes precisam ter um nome.");
      return;
    }
    if (partes.some((p) => !p.sentido_fio)) {
      setErro("Selecione o sentido do fio de todas as partes.");
      return;
    }
    if (partes.some((p) => p.pecas.some((pc) => !pc.geometria_json))) {
      setErro(
        "Alguma parte não tem peça para todos os tamanhos selecionados. Ajuste os tamanhos ou o arquivo importado."
      );
      return;
    }
    setSalvando(true);
    setErro(null);
    try {
      const nomeGrupo = uploadForm.produto.descricao;
      const grupo = await importarGrupoMolde({
        nome_grupo: nomeGrupo,
        arquivo_path: previewMeta.arquivo_path,
        formato: previewMeta.formato,
        produto_id: uploadForm.produto.id,
        partes: partes.map((p) => ({
          nome: p.nome.trim(),
          tipo_corte: p.tipo_corte,
          sentido_fio: p.sentido_fio,
          rotacao_base: p.rotacao_base ?? 0,
          pecas: p.pecas.map((pc) => ({
            tamanho: pc.tamanho,
            geometria_json: pc.geometria_json,
            area_cm2: pc.area_cm2,
          })),
        })),
      });

      if (uploadForm.produto.codigo) {
        await renomearGrupo(grupo.id, { codigo: uploadForm.produto.codigo });
      }

      fecharImportacao();
      setSucesso(`Grupo "${nomeGrupo}" importado com ${partes.length} parte(s).`);
      carregarGrupos();
      setTimeout(() => setSucesso(null), 5000);
    } catch (ex) {
      setErro(ex.message);
    } finally {
      setSalvando(false);
    }
  }

  // ── Deletar grupo ────────────────────────────────────────────────────

  async function deletarGrupo(id, nome) {
    if (!confirm(`Excluir o grupo "${nome}"? Os moldes ficarão sem grupo.`)) return;
    try {
      await deleteGrupo(id);
      setSucesso(`Grupo "${nome}" excluído.`);
      carregarGrupos();
      setTimeout(() => setSucesso(null), 4000);
    } catch (ex) {
      setErro(ex.message);
    }
  }

  // ── Edição de molde individual ───────────────────────────────────────

  function abrirEdicao(molde) {
    setEditando(molde);
    setErroEdit(null);
  }

  function fecharEdicao() {
    setEditando(null);
  }

  async function salvarEdicao(payload) {
    setSalvandoEdit(true);
    setErroEdit(null);
    try {
      await updateMolde(editando.id, payload);
      fecharEdicao();
      setSucesso("Molde atualizado.");
      carregarGrupos();
      setTimeout(() => setSucesso(null), 4000);
    } catch (ex) {
      setErroEdit(ex.message);
    } finally {
      setSalvandoEdit(false);
    }
  }

  async function excluirMoldeIndividual() {
    if (!editando) return;
    if (!confirm("Tem certeza que deseja excluir este molde? Esta ação não pode ser desfeita."))
      return;
    setSalvandoEdit(true);
    setErroEdit(null);
    try {
      await deleteMolde(editando.id);
      fecharEdicao();
      setSucesso("Molde excluído.");
      carregarGrupos();
      setTimeout(() => setSucesso(null), 4000);
    } catch (ex) {
      setErroEdit(ex.message);
    } finally {
      setSalvandoEdit(false);
    }
  }

  // ── Render ───────────────────────────────────────────────────────────

  const nTamanhos = uploadForm.tamanhosSelecionados.length;

  // Peças genéricas (sem nome legível no DXF) que sobraram sem formar uma parte completa
  const genericasIgnoradas = sobra.filter(
    (p) => !p.nome_sugerido || NOME_GENERICO.test(p.nome_sugerido)
  ).length;

  // Partes com algum tamanho sem peça correspondente no arquivo
  const partesIncompletas = partes
    .map((p) => ({
      nome: p.nome || "(sem nome)",
      faltando: p.pecas.filter((pc) => !pc.geometria_json).map((pc) => pc.tamanho),
    }))
    .filter((p) => p.faltando.length > 0);

  // Moldes efetivamente prontos para importar (peças com geometria válida)
  const totalMoldesValidos = partes.reduce(
    (soma, p) => soma + p.pecas.filter((pc) => pc.geometria_json).length,
    0
  );

  // Grupos com pelo menos um molde, organizados por grupo de produto
  const gruposComMoldes = grupos.filter((g) => g.moldes.length > 0);
  const SEM_PRODUTO = "SEM PRODUTO VINCULADO";
  const porGrupoProduto = {};
  for (const g of gruposComMoldes) {
    const chave = g.produto_grupo || SEM_PRODUTO;
    if (!porGrupoProduto[chave]) porGrupoProduto[chave] = [];
    porGrupoProduto[chave].push(g);
  }
  const secoesProduto = Object.keys(porGrupoProduto).sort((a, b) => {
    if (a === SEM_PRODUTO) return 1;
    if (b === SEM_PRODUTO) return -1;
    return a.localeCompare(b, "pt-BR");
  });

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Moldes</h1>
        {hasPermission(MODULO, "criar") && (
          <button className={ms.btnNovo} onClick={abrirUpload}>
            + Importar Molde
          </button>
        )}
      </div>

      {erro && <p className={ms.erro}>{erro}</p>}
      {sucesso && <p className={ms.sucesso}>{sucesso}</p>}

      {/* ── Lista de grupos (accordion), agrupados por grupo de produto ── */}
      <div className={ms.listaGrupos}>
        {gruposComMoldes.length === 0 && (
          <p className={ms.vazio} style={{ textAlign: "center", padding: "32px 0" }}>
            Nenhum molde importado ainda.
          </p>
        )}
        {secoesProduto.map((secao) => (
          <div key={secao} className={ms.secaoProduto}>
            <div className={ms.secaoProdutoLabel}>{secao}</div>
            <div className={ms.secaoProdutoGrupos}>
              {porGrupoProduto[secao].map((g) => (
                <GrupoAccordion
                  key={g.id}
                  grupo={g}
                  podeEditar={hasPermission(MODULO, "editar")}
                  podeExcluir={hasPermission(MODULO, "excluir")}
                  onEditarMolde={abrirEdicao}
                  onDeletarGrupo={deletarGrupo}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* ══ MODAL: Passo 1 — Upload ══════════════════════════════════════ */}
      {fase === "upload" && (
        <Modal titulo="Importar Molde" onClose={fecharImportacao}>
          <form className={ms.form} onSubmit={extrairPecas}>
            {erroUpload && <p className={ms.erroForm}>{erroUpload}</p>}

            <div className={ms.campo}>
              <label className={ms.label}>Produto *</label>
              {uploadForm.produto ? (
                <div className={ms.produtoChip}>
                  <span className={ms.produtoChipCodigo}>{uploadForm.produto.codigo}</span>
                  <span className={ms.produtoChipNome}>{uploadForm.produto.descricao}</span>
                  <button
                    type="button"
                    className={ms.btnLimparProduto}
                    onClick={limparProduto}
                    title="Escolher outro produto"
                  >
                    ×
                  </button>
                </div>
              ) : (
                <div className={ms.autocompleteWrap}>
                  <input
                    className={ms.input}
                    value={buscaProduto}
                    onChange={(e) => handleBuscaProdutoChange(e.target.value)}
                    placeholder="Buscar produto por código ou descrição..."
                  />
                  {buscaProduto.trim() && (
                    <div className={ms.autocompleteDropdown}>
                      {buscandoProduto && <div className={ms.autocompleteInfo}>Buscando...</div>}
                      {!buscandoProduto && resultadosProduto.length === 0 && (
                        <div className={ms.autocompleteInfo}>Nenhum produto encontrado.</div>
                      )}
                      {!buscandoProduto &&
                        resultadosProduto.map((p) => (
                          <div
                            key={p.id}
                            className={ms.autocompleteItem}
                            onClick={() => selecionarProduto(p)}
                          >
                            <span className={ms.produtoChipCodigo}>{p.codigo}</span>
                            <span className={ms.produtoChipNome}>{p.descricao}</span>
                          </div>
                        ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className={ms.campo}>
              <label className={ms.label}>Tamanhos no arquivo *</label>
              <div className={ms.checkboxGrid}>
                {TAMANHOS_DISPONIVEIS.map((t) => (
                  <label key={t} className={ms.checkboxItem}>
                    <input
                      type="checkbox"
                      checked={uploadForm.tamanhosSelecionados.includes(t)}
                      onChange={() => toggleTamanho(t)}
                    />
                    <span>{t}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className={ms.campo}>
              <label className={ms.label}>Arquivo (DXF, PLT ou ADS) *</label>
              <div className={ms.fileDrop} onClick={() => inputFileRef.current.click()}>
                {uploadForm.arquivo ? (
                  <span className={ms.fileNome}>{uploadForm.arquivo.name}</span>
                ) : (
                  "Clique para selecionar um arquivo .dxf, .plt ou .ads"
                )}
              </div>
              <input
                ref={inputFileRef}
                type="file"
                accept=".dxf,.plt,.ads,.DXF,.PLT,.ADS"
                style={{ display: "none" }}
                onChange={(e) => {
                  const f = e.target.files[0];
                  if (f) setUploadForm((p) => ({ ...p, arquivo: f }));
                }}
              />
            </div>

            <div className={ms.formActions}>
              <button type="button" className={ms.btnSecondary} onClick={fecharImportacao}>
                Cancelar
              </button>
              <button
                type="submit"
                className={ms.btnPrimary}
                disabled={extraindo || !uploadForm.produto || !uploadForm.arquivo}
              >
                {extraindo ? "Extraindo peças..." : "Extrair Peças →"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ══ MODAL: Passo 2 — Preview e configuração das partes ══════════ */}
      {fase === "preview" && previewMeta && (
        <Modal
          titulo={`"${uploadForm.produto?.descricao ?? ""}" — ${partes.length} parte(s) × ${nTamanhos} tamanho(s)`}
          onClose={fecharImportacao}
          largura="1400px"
          largura95vw
        >
          <div className={ms.previewContainer}>
            {erro && <p className={ms.erroForm}>{erro}</p>}

            {genericasIgnoradas > 0 && (
              <p className={ms.avisoSobra}>
                ⚠ {genericasIgnoradas} peça(s) do arquivo não foram agrupadas automaticamente porque
                não possuem nome legível no arquivo DXF. Isso pode acontecer quando o arquivo não
                contém textos identificando as peças. Verifique se o arquivo exportado do Audaces
                contém as anotações de nome de cada peça.
              </p>
            )}

            {partesIncompletas.length > 0 && (
              <div className={ms.avisoSobra}>
                ⚠ As seguintes partes estão com tamanhos incompletos:
                <ul className={ms.avisoLista}>
                  {partesIncompletas.map((p) => (
                    <li key={p.nome}>
                      {p.nome}: faltando {p.faltando.join(", ")}
                    </li>
                  ))}
                </ul>
                Isso pode indicar que o arquivo não contém todas as variações de tamanho
                selecionadas, ou que as peças estão com áreas muito próximas e foram agrupadas
                juntas. Tente importar com menos tamanhos selecionados ou verifique o arquivo.
              </div>
            )}

            <div className={ms.partesGrid}>
              {partes.map((parte, idx) => (
                <ParteCard
                  key={idx}
                  parte={parte}
                  index={idx}
                  onChange={handleParteChange}
                  onRemove={handleRemoveParte}
                />
              ))}
            </div>

            <div className={ms.formActions}>
              <button className={ms.btnSecondary} onClick={fecharImportacao}>
                Cancelar
              </button>
              <button
                className={ms.btnPrimary}
                onClick={confirmarImportacao}
                disabled={salvando || partes.length === 0}
              >
                {salvando
                  ? "Salvando..."
                  : `Confirmar importação (${totalMoldesValidos} molde${totalMoldesValidos !== 1 ? "s" : ""})`}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ══ MODAL: Edição de molde individual ════════════════════════════ */}
      {editando && (
        <EditarMoldeModal
          molde={editando}
          onClose={fecharEdicao}
          onSalvar={salvarEdicao}
          onExcluir={excluirMoldeIndividual}
          podeExcluir={hasPermission(MODULO, "excluir")}
          salvando={salvandoEdit}
          erro={erroEdit}
        />
      )}
    </div>
  );
}
