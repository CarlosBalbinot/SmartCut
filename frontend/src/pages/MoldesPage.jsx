import { useEffect, useRef, useState } from "react";
import { getGrupos, importarGrupoMolde, renomearGrupo, deleteGrupo, previewMolde, updateMolde } from "../api/moldes";
import Modal from "../components/Modal/Modal";
import GrupoAccordion from "../components/MoldesGrupo/GrupoAccordion";
import ParteCard from "../components/ImportacaoMoldes/ParteCard";
import { useAuth } from "../auth/useAuth";
import ms from "./MoldesPage.module.css";

const MODULO = "moldes";

// ── Constantes ───────────────────────────────────────────────────────

const TAMANHOS_DISPONIVEIS = ["PP", "P", "M", "G", "GG", "XGG"];

const UPLOAD_INICIAL = {
  nomeGrupo: "",
  codigoRef: "",
  tamanhosSelecionados: [],
  arquivo: null,
};

const EDIT_INICIAL = {
  nome: "",
  peca: "",
  tamanho: "",
  sentido_fio: "vertical",
  tipo_corte: "par",
};

// ── Funções auxiliares ───────────────────────────────────────────────

/**
 * Distribui N polylines (ordenadas por área) em (N / nTamanhos) partes.
 * Cada parte recebe um conjunto de tamanhos ordenados do menor para o maior.
 */
function agruparEmPartes(polylines, tamanhos) {
  const n = tamanhos.length;
  if (n === 0 || polylines.length === 0) return [];
  const nPartes = Math.floor(polylines.length / n);
  const partes = [];
  for (let i = 0; i < nPartes; i++) {
    const bloco = polylines.slice(i * n, i * n + n);
    partes.push({
      nome: `Parte ${i + 1}`,
      tipo_corte: "par",
      sentido_fio: "vertical",
      rotacao_base: 0,
      pecas: tamanhos.map((t, j) => ({
        tamanho: t,
        geometria_json: bloco[j].geometria_json,
        area_cm2: bloco[j].area_cm2,
      })),
    });
  }
  return partes;
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

  // Edição de molde individual
  const [editando, setEditando] = useState(null);
  const [editForm, setEditForm] = useState(EDIT_INICIAL);
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
    setFase("upload");
  }

  function fecharImportacao() {
    setFase(null);
    setPreviewMeta(null);
    setPartes([]);
    setSobra([]);
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
    const { nomeGrupo, tamanhosSelecionados, arquivo } = uploadForm;
    if (!nomeGrupo.trim()) {
      setErroUpload("Informe o nome da peça (ex: Leg Transpassado).");
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
      const partesGeradas = agruparEmPartes(data.pecas, tamanhosSelecionados);
      const usadas = partesGeradas.length * tamanhosSelecionados.length;
      setSobra(data.pecas.slice(usadas));
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
      copia[index] = { ...copia[index], [campo]: valor };
      return copia;
    });
  }

  // ── Confirmação ──────────────────────────────────────────────────────

  async function confirmarImportacao() {
    if (partes.some((p) => !p.nome.trim())) {
      setErro("Todas as partes precisam ter um nome.");
      return;
    }
    setSalvando(true);
    setErro(null);
    try {
      const grupo = await importarGrupoMolde({
        nome_grupo: uploadForm.nomeGrupo.trim(),
        arquivo_path: previewMeta.arquivo_path,
        formato: previewMeta.formato,
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

      if (uploadForm.codigoRef.trim()) {
        await renomearGrupo(grupo.id, { codigo: uploadForm.codigoRef.trim() });
      }

      fecharImportacao();
      setSucesso(
        `Grupo "${uploadForm.nomeGrupo.trim()}" importado com ${partes.length} parte(s).`
      );
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
    setEditForm({
      nome: molde.nome,
      peca: molde.peca ?? "",
      tamanho: molde.tamanho ?? "",
      sentido_fio: molde.sentido_fio ?? "vertical",
      tipo_corte: molde.tipo_corte ?? "par",
    });
    setErroEdit(null);
  }

  function fecharEdicao() {
    setEditando(null);
  }

  async function salvarEdicao(e) {
    e.preventDefault();
    setSalvandoEdit(true);
    setErroEdit(null);
    try {
      await updateMolde(editando.id, {
        nome: editForm.nome.trim(),
        peca: editForm.peca.trim() || null,
        tamanho: editForm.tamanho.trim() || null,
        sentido_fio: editForm.sentido_fio || null,
        tipo_corte: editForm.tipo_corte,
      });
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

  // ── Render ───────────────────────────────────────────────────────────

  const nTamanhos = uploadForm.tamanhosSelecionados.length;
  const totalPolylines = partes.length * nTamanhos;

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

      {/* ── Lista de grupos (accordion) ── */}
      <div className={ms.listaGrupos}>
        {grupos.length === 0 && (
          <p className={ms.vazio} style={{ textAlign: "center", padding: "32px 0" }}>
            Nenhum molde importado ainda.
          </p>
        )}
        {grupos.map((g) => (
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

      {/* ══ MODAL: Passo 1 — Upload ══════════════════════════════════════ */}
      {fase === "upload" && (
        <Modal titulo="Importar Molde" onClose={fecharImportacao}>
          <form className={ms.form} onSubmit={extrairPecas}>
            {erroUpload && <p className={ms.erroForm}>{erroUpload}</p>}

            <div className={ms.campo}>
              <label className={ms.label}>Nome da peça *</label>
              <input
                className={ms.input}
                value={uploadForm.nomeGrupo}
                onChange={(e) =>
                  setUploadForm((p) => ({ ...p, nomeGrupo: e.target.value }))
                }
                placeholder="ex: Leg Transpassado, Frente Básica..."
                required
              />
            </div>

            <div className={ms.campo}>
              <label className={ms.label}>Referência (opcional)</label>
              <input
                className={ms.input}
                value={uploadForm.codigoRef}
                onChange={(e) =>
                  setUploadForm((p) => ({ ...p, codigoRef: e.target.value.slice(0, 20) }))
                }
                placeholder="Ex: 300, 201, 100..."
                maxLength={20}
              />
              <small style={{ color: "var(--sc-text-muted)", fontSize: "0.78rem", marginTop: "0.25rem", display: "block" }}>
                Código usado nos pedidos de venda e tabelas de preço
              </small>
            </div>

            <div className={ms.campo}>
              <label className={ms.label}>Tamanhos disponíveis no arquivo *</label>
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
              <div
                className={ms.fileDrop}
                onClick={() => inputFileRef.current.click()}
              >
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
              <button type="submit" className={ms.btnPrimary} disabled={extraindo}>
                {extraindo ? "Extraindo peças..." : "Extrair Peças →"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ══ MODAL: Passo 2 — Preview e configuração das partes ══════════ */}
      {fase === "preview" && previewMeta && (
        <Modal
          titulo={`"${uploadForm.nomeGrupo}" — ${partes.length} parte(s) × ${nTamanhos} tamanho(s)`}
          onClose={fecharImportacao}
          largura="960px"
        >
          <div className={ms.previewContainer}>
            {erro && <p className={ms.erroForm}>{erro}</p>}

            {sobra.length > 0 && (
              <p className={ms.avisoSobra}>
                ⚠ {sobra.length} polyline(s) não encaixaram na grade (
                {totalPolylines} esperadas para {partes.length} partes × {nTamanhos} tamanhos) e
                foram ignoradas. Verifique se os tamanhos marcados estão corretos.
              </p>
            )}

            <div className={ms.partesGrid}>
              {partes.map((parte, idx) => (
                <ParteCard
                  key={idx}
                  parte={parte}
                  index={idx}
                  onChange={handleParteChange}
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
                  : `Confirmar importação (${totalPolylines} molde${totalPolylines !== 1 ? "s" : ""})`}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ══ MODAL: Edição de molde individual ════════════════════════════ */}
      {editando && (
        <Modal titulo="Editar Molde" onClose={fecharEdicao}>
          <form className={ms.form} onSubmit={salvarEdicao}>
            {erroEdit && <p className={ms.erroForm}>{erroEdit}</p>}

            <div className={ms.campo}>
              <label className={ms.label}>Nome *</label>
              <input
                className={ms.input}
                value={editForm.nome}
                onChange={(e) => setEditForm((p) => ({ ...p, nome: e.target.value }))}
                required
              />
            </div>

            <div className={ms.fileiraDupla}>
              <div className={ms.campo}>
                <label className={ms.label}>Parte</label>
                <input
                  className={ms.input}
                  value={editForm.peca}
                  onChange={(e) => setEditForm((p) => ({ ...p, peca: e.target.value }))}
                  placeholder="Frente, Costa, Manga..."
                />
              </div>
              <div className={ms.campo}>
                <label className={ms.label}>Tamanho</label>
                <select
                  className={ms.select}
                  value={editForm.tamanho}
                  onChange={(e) => setEditForm((p) => ({ ...p, tamanho: e.target.value }))}
                >
                  <option value="">—</option>
                  {TAMANHOS_DISPONIVEIS.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className={ms.campo}>
              <label className={ms.label}>Sentido do fio</label>
              <select
                className={ms.select}
                value={editForm.sentido_fio}
                onChange={(e) => setEditForm((p) => ({ ...p, sentido_fio: e.target.value }))}
              >
                <option value="vertical">↕ Vertical</option>
                <option value="horizontal">↔ Horizontal</option>
                <option value="45graus">↗ 45 graus</option>
              </select>
            </div>

            <div className={ms.campo}>
              <label className={ms.label}>Tipo de corte</label>
              <select
                className={ms.select}
                value={editForm.tipo_corte}
                onChange={(e) => setEditForm((p) => ({ ...p, tipo_corte: e.target.value }))}
              >
                <option value="simples">Simples (1 peça, sem espelho)</option>
                <option value="par">Par (2 peças espelhadas)</option>
                <option value="par_sem_espelho">Par sem espelho (2 peças)</option>
              </select>
            </div>

            <div className={ms.formActions}>
              <button type="button" className={ms.btnSecondary} onClick={fecharEdicao}>
                Cancelar
              </button>
              <button type="submit" className={ms.btnPrimary} disabled={salvandoEdit}>
                {salvandoEdit ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
