import { useEffect, useState } from "react";
import {
  getModelos, createModelo, updateModelo, deleteModelo, createCorDoModelo,
  updateCor, deleteCor, createLoteDaCor,
  arquivarLote, getHistoricoLotes, getProximoCodigoLote,
} from "../api/tecidos";
import Modal from "../components/Modal/Modal";
import ConfirmModal from "../components/ConfirmModal/ConfirmModal";
import { useAuth } from "../auth/useAuth";
import ts from "./TecidosPage.module.css";

const MODULO = "tecidos";

// ─────────────────────────────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────────────────────────────

function hojeISO() {
  return new Date().toISOString().slice(0, 10);
}

function badgeLote(lote) {
  if (lote.status === "arquivado") return null;
  const kg = Number(lote.peso_disponivel_kg);
  if (kg <= 5) return "critico";
  if (lote.status === "aberto") return "aberto";
  return "intacto";
}

// Campos numéricos que devem aceitar só inteiro (largura útil, gramatura,
// máx. camadas) — evita o erro de digitar "1.4" num campo que deveria
// receber "140" (ponto/vírgula vira decimal errado, não separador de milhar).
function bloquearDecimal(e) {
  if (e.key === "." || e.key === ",") {
    e.preventDefault();
  }
}

function bloquearColarDecimal(e) {
  const text = e.clipboardData.getData("text");
  if (/[.,]/.test(text)) {
    e.preventDefault();
  }
}

function apenasInteiro(valor) {
  return valor.replace(/[^0-9]/g, "");
}

// ─────────────────────────────────────────────────────────────────────
//  Componente principal
// ─────────────────────────────────────────────────────────────────────

export default function TecidosPage() {
  const { hasPermission } = useAuth();
  const [modelos, setModelos] = useState([]);
  const [carregando, setCarregando] = useState(true);

  // Accordions abertos
  const [modelosAbertos, setModelosAbertos] = useState(new Set());
  const [coresAbertas, setCoresAbertas] = useState(new Set());

  // Modal histórico
  const [modalHistorico, setModalHistorico] = useState(false);
  const [historico, setHistorico] = useState([]);

  // Modal Novo Modelo
  const [modalModelo, setModalModelo] = useState(false);
  const [editandoModelo, setEditandoModelo] = useState(null);
  const [formModelo, setFormModelo] = useState({ nome: "", tipo: "", max_camadas: "15" });
  const [erroModelo, setErroModelo] = useState(null);
  const [salvandoModelo, setSalvandoModelo] = useState(false);

  // Modal Nova Cor
  const [modalCor, setModalCor] = useState(null); // modelo_id ou null
  const [editandoCor, setEditandoCor] = useState(null); // { cor, modelo_id }
  const [formCor, setFormCor] = useState({ nome_cor: "", largura_util_cm: "", gramatura_g_m2: "", encolhimento_pct: "0" });
  const [erroCor, setErroCor] = useState(null);
  const [salvandoCor, setSalvandoCor] = useState(false);

  // Modal Novo Lote
  const [modalLote, setModalLote] = useState(null); // cor_id ou null
  const [formLote, setFormLote] = useState({ codigo_lote: "", peso_inicial_kg: "", valor_kg: "", data_compra: hojeISO() });
  const [erroLote, setErroLote] = useState(null);
  const [salvandoLote, setSalvandoLote] = useState(false);

  // Confirm excluir
  const [confirmModelo, setConfirmModelo] = useState(null);
  const [confirmCor, setConfirmCor] = useState(null);
  const [confirmArquivar, setConfirmArquivar] = useState(null);

  // ── Carregamento ──────────────────────────────────────────────────

  async function carregar() {
    setCarregando(true);
    try {
      const lista = await getModelos();
      setModelos(lista);
    } catch (e) {
      console.error(e);
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => { carregar(); }, []);

  // ── Accordions ────────────────────────────────────────────────────

  function toggleModelo(id) {
    setModelosAbertos((prev) => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });
  }

  function toggleCor(id) {
    setCoresAbertas((prev) => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });
  }

  // ── Histórico ─────────────────────────────────────────────────────

  async function abrirHistorico() {
    try {
      const h = await getHistoricoLotes();
      setHistorico(h);
      setModalHistorico(true);
    } catch (e) {
      console.error(e);
    }
  }

  // ── Modelo CRUD ───────────────────────────────────────────────────

  function abrirNovoModelo() {
    setFormModelo({ nome: "", tipo: "", max_camadas: "15" });
    setErroModelo(null);
    setEditandoModelo(null);
    setModalModelo(true);
  }

  function abrirEditarModelo(m) {
    setFormModelo({ nome: m.nome, tipo: m.tipo ?? "", max_camadas: String(m.max_camadas) });
    setErroModelo(null);
    setEditandoModelo(m);
    setModalModelo(true);
  }

  async function salvarModelo(e) {
    e.preventDefault();
    setSalvandoModelo(true);
    setErroModelo(null);
    const payload = {
      nome: formModelo.nome,
      tipo: formModelo.tipo || null,
      max_camadas: Number(formModelo.max_camadas) || 15,
    };
    try {
      if (editandoModelo) {
        await updateModelo(editandoModelo.id, payload);
      } else {
        await createModelo(payload);
      }
      setModalModelo(false);
      await carregar();
    } catch (ex) {
      setErroModelo(ex.message);
    } finally {
      setSalvandoModelo(false);
    }
  }

  async function confirmarExcluirModelo() {
    const m = confirmModelo;
    setConfirmModelo(null);
    try {
      await deleteModelo(m.id);
      await carregar();
    } catch (e) {
      console.error(e);
    }
  }

  // ── Cor CRUD ──────────────────────────────────────────────────────

  function abrirNovaCor(modeloId) {
    setFormCor({ nome_cor: "", largura_util_cm: "", gramatura_g_m2: "", encolhimento_pct: "0" });
    setErroCor(null);
    setEditandoCor(null);
    setModalCor(modeloId);
  }

  function abrirEditarCor(cor, modeloId) {
    setFormCor({
      nome_cor: cor.nome_cor,
      largura_util_cm: String(cor.largura_util_cm),
      gramatura_g_m2: String(cor.gramatura_g_m2),
      encolhimento_pct: String(cor.encolhimento_pct ?? "0"),
    });
    setErroCor(null);
    setEditandoCor({ cor, modelo_id: modeloId });
    setModalCor(modeloId);
  }

  async function salvarCor(e) {
    e.preventDefault();
    setSalvandoCor(true);
    setErroCor(null);
    const payload = {
      nome_cor: formCor.nome_cor,
      largura_util_cm: Number(formCor.largura_util_cm),
      gramatura_g_m2: Number(formCor.gramatura_g_m2),
      encolhimento_pct: Number(formCor.encolhimento_pct) || 0,
    };
    try {
      if (editandoCor) {
        await updateCor(editandoCor.cor.id, payload);
      } else {
        await createCorDoModelo(modalCor, payload);
      }
      setModalCor(null);
      setEditandoCor(null);
      await carregar();
    } catch (ex) {
      setErroCor(ex.message);
    } finally {
      setSalvandoCor(false);
    }
  }

  async function confirmarExcluirCor() {
    const c = confirmCor;
    setConfirmCor(null);
    try {
      await deleteCor(c.id);
      await carregar();
    } catch (e) {
      console.error(e);
    }
  }

  // ── Lote CRUD ─────────────────────────────────────────────────────

  async function abrirNovoLote(corId) {
    setErroLote(null);
    setSalvandoLote(false);
    const codigo = await getProximoCodigoLote().catch(() => "LT001");
    setFormLote({ codigo_lote: codigo, peso_inicial_kg: "", valor_kg: "", data_compra: hojeISO() });
    setModalLote(corId);
  }

  async function salvarLote(e) {
    e.preventDefault();
    setSalvandoLote(true);
    setErroLote(null);
    const payload = {
      codigo_lote: formLote.codigo_lote,
      peso_inicial_kg: Number(formLote.peso_inicial_kg),
      valor_kg: Number(formLote.valor_kg),
      data_compra: formLote.data_compra,
    };
    try {
      await createLoteDaCor(modalLote, payload);
      setModalLote(null);
      await carregar();
    } catch (ex) {
      setErroLote(ex.message);
    } finally {
      setSalvandoLote(false);
    }
  }

  async function confirmarArquivar() {
    const lote = confirmArquivar;
    setConfirmArquivar(null);
    try {
      await arquivarLote(lote.id);
      await carregar();
    } catch (e) {
      console.error(e);
    }
  }

  // ─────────────────────────────────────────────────────────────────
  //  Render
  // ─────────────────────────────────────────────────────────────────

  if (carregando) {
    return (
      <div className="sc-page">
        <div className="sc-page-header">
          <h1>Tecidos</h1>
        </div>
        <p className={ts.carregando}>Carregando...</p>
      </div>
    );
  }

  return (
    <div className="sc-page">
      {/* ── Cabeçalho ── */}
      <div className="sc-page-header">
        <h1>Tecidos</h1>
        <div className={ts.headerAcoes}>
          <button className={ts.btnHistorico} onClick={abrirHistorico}>
            Ver Histórico
          </button>
          {hasPermission(MODULO, "criar") && (
            <button className={ts.btnNovo} onClick={abrirNovoModelo}>
              + Novo Modelo
            </button>
          )}
        </div>
      </div>

      {/* ── Lista de modelos ── */}
      {modelos.length === 0 ? (
        <div className={ts.vazio}>
          <p>Nenhum modelo de tecido cadastrado.</p>
          {hasPermission(MODULO, "criar") && (
            <button className={ts.btnNovo} onClick={abrirNovoModelo}>
              Cadastrar primeiro modelo
            </button>
          )}
        </div>
      ) : (
        <div className={ts.lista}>
          {modelos.map((modelo) => (
            <ModeloAccordion
              key={modelo.id}
              modelo={modelo}
              aberto={modelosAbertos.has(modelo.id)}
              onToggle={() => toggleModelo(modelo.id)}
              coresAbertas={coresAbertas}
              onToggleCor={toggleCor}
              podeCriar={hasPermission(MODULO, "criar")}
              podeEditar={hasPermission(MODULO, "editar")}
              podeExcluir={hasPermission(MODULO, "excluir")}
              onEditarModelo={() => abrirEditarModelo(modelo)}
              onExcluirModelo={() => setConfirmModelo(modelo)}
              onNovaCor={() => abrirNovaCor(modelo.id)}
              onEditarCor={(cor) => abrirEditarCor(cor, modelo.id)}
              onExcluirCor={(cor) => setConfirmCor(cor)}
              onNovoLote={(corId) => abrirNovoLote(corId)}
              onArquivar={(lote) => setConfirmArquivar(lote)}
            />
          ))}
        </div>
      )}

      {/* ── Modal: Novo/Editar Modelo ── */}
      {modalModelo && (
        <Modal
          titulo={editandoModelo ? "Editar Modelo" : "Novo Modelo"}
          onClose={() => setModalModelo(false)}
        >
          <form className={ts.form} onSubmit={salvarModelo}>
            {erroModelo && <p className={ts.erroForm}>{erroModelo}</p>}
            <div className={ts.campo}>
              <label className={ts.label}>Nome do modelo *</label>
              <input
                className={ts.input}
                value={formModelo.nome}
                onChange={(e) => setFormModelo((p) => ({ ...p, nome: e.target.value }))}
                required
                autoFocus
                placeholder="ex: Maxxi, Wish, Suplex"
              />
            </div>
            <div className={ts.fileiraDupla}>
              <div className={ts.campo}>
                <label className={ts.label}>Tipo</label>
                <input
                  className={ts.input}
                  value={formModelo.tipo}
                  onChange={(e) => setFormModelo((p) => ({ ...p, tipo: e.target.value }))}
                  placeholder="ex: Compressão, Canelado"
                />
              </div>
              <div className={ts.campo}>
                <label className={ts.label}>Máx. camadas</label>
                <input
                  className={ts.input}
                  type="number"
                  step="1"
                  min="1"
                  max="500"
                  value={formModelo.max_camadas}
                  onChange={(e) => setFormModelo((p) => ({ ...p, max_camadas: apenasInteiro(e.target.value) }))}
                  onKeyDown={bloquearDecimal}
                  onPaste={bloquearColarDecimal}
                />
              </div>
            </div>
            <div className={ts.formActions}>
              <button type="button" className={ts.btnSecondary} onClick={() => setModalModelo(false)}>
                Cancelar
              </button>
              <button type="submit" className={ts.btnPrimary} disabled={salvandoModelo}>
                {salvandoModelo ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Modal: Nova/Editar Cor ── */}
      {(modalCor || editandoCor) && (
        <Modal
          titulo={editandoCor ? "Editar Cor" : "Nova Cor"}
          onClose={() => { setModalCor(null); setEditandoCor(null); }}
        >
          <form className={ts.form} onSubmit={salvarCor}>
            {erroCor && <p className={ts.erroForm}>{erroCor}</p>}
            <div className={ts.campo}>
              <label className={ts.label}>Nome da cor *</label>
              <input
                className={ts.input}
                value={formCor.nome_cor}
                onChange={(e) => setFormCor((p) => ({ ...p, nome_cor: e.target.value }))}
                required
                autoFocus
                placeholder="ex: Preto, Marrom, Azul Royal"
              />
            </div>
            <div className={ts.fileiraDupla}>
              <div className={ts.campo}>
                <label className={ts.label}>Largura útil (cm) *</label>
                <input
                  className={ts.input}
                  type="number"
                  step="1"
                  min="0"
                  placeholder="ex: 140"
                  value={formCor.largura_util_cm}
                  onChange={(e) => setFormCor((p) => ({ ...p, largura_util_cm: apenasInteiro(e.target.value) }))}
                  onKeyDown={bloquearDecimal}
                  onPaste={bloquearColarDecimal}
                  required
                />
                <span className={ts.hint}>Informe em centímetros (ex: 140 = 1,40m)</span>
              </div>
              <div className={ts.campo}>
                <label className={ts.label}>Gramatura (g/m²) *</label>
                <input
                  className={ts.input}
                  type="number"
                  step="1"
                  min="0"
                  placeholder="ex: 220"
                  value={formCor.gramatura_g_m2}
                  onChange={(e) => setFormCor((p) => ({ ...p, gramatura_g_m2: apenasInteiro(e.target.value) }))}
                  onKeyDown={bloquearDecimal}
                  onPaste={bloquearColarDecimal}
                  required
                />
                <span className={ts.hint}>Gramas por metro quadrado</span>
              </div>
            </div>
            <div className={ts.campo}>
              <label className={ts.label}>Encolhimento (%)</label>
              <input
                className={ts.input}
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={formCor.encolhimento_pct}
                onChange={(e) => setFormCor((p) => ({ ...p, encolhimento_pct: e.target.value }))}
              />
            </div>
            <div className={ts.formActions}>
              <button type="button" className={ts.btnSecondary} onClick={() => { setModalCor(null); setEditandoCor(null); }}>
                Cancelar
              </button>
              <button type="submit" className={ts.btnPrimary} disabled={salvandoCor}>
                {salvandoCor ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Modal: Novo Lote ── */}
      {modalLote && (
        <Modal titulo="Novo Lote" onClose={() => setModalLote(null)}>
          <form className={ts.form} onSubmit={salvarLote}>
            {erroLote && <p className={ts.erroForm}>{erroLote}</p>}
            <div className={ts.campo}>
              <label className={ts.label}>Código do lote *</label>
              <input
                className={ts.input}
                value={formLote.codigo_lote}
                onChange={(e) => setFormLote((p) => ({ ...p, codigo_lote: e.target.value }))}
                required
                autoFocus
                placeholder="ex: LT001"
              />
            </div>
            <div className={ts.fileiraDupla}>
              <div className={ts.campo}>
                <label className={ts.label}>Peso inicial (kg) *</label>
                <input
                  className={ts.input}
                  type="number"
                  step="0.001"
                  min="0.001"
                  value={formLote.peso_inicial_kg}
                  onChange={(e) => setFormLote((p) => ({ ...p, peso_inicial_kg: e.target.value }))}
                  required
                />
              </div>
              <div className={ts.campo}>
                <label className={ts.label}>Valor por kg (R$) *</label>
                <input
                  className={ts.input}
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={formLote.valor_kg}
                  onChange={(e) => setFormLote((p) => ({ ...p, valor_kg: e.target.value }))}
                  required
                />
              </div>
            </div>
            <div className={ts.campo}>
              <label className={ts.label}>Data de compra *</label>
              <input
                className={ts.input}
                type="date"
                value={formLote.data_compra}
                onChange={(e) => setFormLote((p) => ({ ...p, data_compra: e.target.value }))}
                required
              />
            </div>
            <div className={ts.formActions}>
              <button type="button" className={ts.btnSecondary} onClick={() => setModalLote(null)}>
                Cancelar
              </button>
              <button type="submit" className={ts.btnPrimary} disabled={salvandoLote}>
                {salvandoLote ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ── Modal: Histórico ── */}
      {modalHistorico && (
        <Modal titulo="Histórico de Lotes" onClose={() => setModalHistorico(false)}>
          {historico.length === 0 ? (
            <p className={ts.vazioModal}>Nenhum lote arquivado ou esgotado.</p>
          ) : (
            <div className={ts.tabelaHistorico}>
              {historico.map((lt) => (
                <div key={lt.id} className={ts.linhaHistorico}>
                  <span className={ts.codigoLote}>{lt.codigo_lote}</span>
                  <span className={ts.pesoHistorico}>{Number(lt.peso_inicial_kg).toFixed(1)} kg inicial</span>
                  <span className={ts[`badge_${lt.status}`] ?? ts.badgeArquivado}>
                    {lt.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}

      {/* ── Confirms ── */}
      <ConfirmModal
        isOpen={!!confirmModelo}
        titulo="Excluir modelo"
        mensagem={`Excluir "${confirmModelo?.nome}" e todas as suas cores e lotes?`}
        labelConfirmar="Excluir"
        variante="perigo"
        onConfirmar={confirmarExcluirModelo}
        onCancelar={() => setConfirmModelo(null)}
      />
      <ConfirmModal
        isOpen={!!confirmCor}
        titulo="Excluir cor"
        mensagem={`Excluir a cor "${confirmCor?.nome_cor}" e todos os seus lotes?`}
        labelConfirmar="Excluir"
        variante="perigo"
        onConfirmar={confirmarExcluirCor}
        onCancelar={() => setConfirmCor(null)}
      />
      <ConfirmModal
        isOpen={!!confirmArquivar}
        titulo="Arquivar lote"
        mensagem={`Arquivar o lote "${confirmArquivar?.codigo_lote}"? Ele ficará visível apenas no histórico.`}
        labelConfirmar="Arquivar"
        variante="neutro"
        onConfirmar={confirmarArquivar}
        onCancelar={() => setConfirmArquivar(null)}
      />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  ModeloAccordion
// ─────────────────────────────────────────────────────────────────────

function ModeloAccordion({
  modelo, aberto, onToggle, coresAbertas, onToggleCor,
  podeCriar, podeEditar, podeExcluir,
  onEditarModelo, onExcluirModelo, onNovaCor,
  onEditarCor, onExcluirCor, onNovoLote, onArquivar,
}) {
  return (
    <div className={ts.modeloCard}>
      {/* Cabeçalho do modelo */}
      <div className={ts.modeloHeader} onClick={onToggle} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onToggle()}>
        <div className={ts.modeloLeft}>
          <span className={`${ts.chevron} ${aberto ? ts.chevronAberto : ""}`}>›</span>
          <span className={ts.modeloNome}>{modelo.nome}</span>
          {modelo.tipo && <span className={ts.modeloTipo}>{modelo.tipo}</span>}
          <span className={ts.modeloCores}>{modelo.cores.length} {modelo.cores.length === 1 ? "cor" : "cores"}</span>
        </div>
        <div className={ts.modeloAcoes} onClick={(e) => e.stopPropagation()}>
          {podeCriar && <button className={ts.btnAcao} onClick={onNovaCor}>+ Nova Cor</button>}
          {podeEditar && <button className={ts.btnAcao} onClick={onEditarModelo}>Editar</button>}
          {podeExcluir && <button className={`${ts.btnAcao} ${ts.btnPerigo}`} onClick={onExcluirModelo}>Excluir</button>}
        </div>
      </div>

      {/* Cores */}
      {aberto && (
        <div className={ts.coresList}>
          {modelo.cores.length === 0 ? (
            <p className={ts.semCores}>
              Nenhuma cor cadastrada.{" "}
              {podeCriar && <button className={ts.btnLink} onClick={onNovaCor}>Adicionar cor</button>}
            </p>
          ) : (
            modelo.cores.map((cor) => (
              <CorAccordion
                key={cor.id}
                cor={cor}
                aberto={coresAbertas.has(cor.id)}
                onToggle={() => onToggleCor(cor.id)}
                podeCriar={podeCriar}
                podeEditar={podeEditar}
                podeExcluir={podeExcluir}
                onEditarCor={() => onEditarCor(cor)}
                onExcluirCor={() => onExcluirCor(cor)}
                onNovoLote={() => onNovoLote(cor.id)}
                onArquivar={onArquivar}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  CorAccordion
// ─────────────────────────────────────────────────────────────────────

function CorAccordion({ cor, aberto, onToggle, podeCriar, podeEditar, podeExcluir, onEditarCor, onExcluirCor, onNovoLote, onArquivar }) {
  const lotesAtivos = cor.lotes.filter((l) => l.status !== "arquivado");

  return (
    <div className={ts.corCard}>
      {/* Cabeçalho da cor */}
      <div className={ts.corHeader} onClick={onToggle} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && onToggle()}>
        <div className={ts.corLeft}>
          <span className={`${ts.chevron} ${ts.chevronSm} ${aberto ? ts.chevronAberto : ""}`}>›</span>
          <span className={ts.corNome}>{cor.nome_cor}</span>
          <span className={ts.corSpec}>{cor.largura_util_cm} cm · {cor.gramatura_g_m2} g/m²</span>
          {cor.encolhimento_pct > 0 && (
            <span className={ts.corEncolhimento}>enc. {cor.encolhimento_pct}%</span>
          )}
          <span className={ts.corLotes}>{lotesAtivos.length} {lotesAtivos.length === 1 ? "lote" : "lotes"}</span>
        </div>
        <div className={ts.corAcoes} onClick={(e) => e.stopPropagation()}>
          {podeCriar && <button className={ts.btnAcaoSm} onClick={onNovoLote}>+ Novo Lote</button>}
          {podeEditar && <button className={ts.btnAcaoSm} onClick={onEditarCor}>Editar</button>}
          {podeExcluir && <button className={`${ts.btnAcaoSm} ${ts.btnPerigo}`} onClick={onExcluirCor}>Excluir</button>}
        </div>
      </div>

      {/* Lotes */}
      {aberto && (
        <div className={ts.lotesList}>
          {lotesAtivos.length === 0 ? (
            <p className={ts.semLotes}>
              Nenhum lote ativo.{" "}
              {podeCriar && <button className={ts.btnLink} onClick={onNovoLote}>Adicionar lote</button>}
            </p>
          ) : (
            lotesAtivos.map((lote) => (
              <LoteRow key={lote.id} lote={lote} podeEditar={podeEditar} onArquivar={() => onArquivar(lote)} />
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
//  LoteRow
// ─────────────────────────────────────────────────────────────────────

function LoteRow({ lote, podeEditar, onArquivar }) {
  const badge = badgeLote(lote);
  const kg = Number(lote.peso_disponivel_kg);
  const dataCompra = new Date(lote.data_compra).toLocaleDateString("pt-BR");

  return (
    <div className={`${ts.loteRow} ${badge === "critico" ? ts.loteCritico : ""}`}>
      <div className={ts.loteLeft}>
        <span className={ts.loteCodigo}>{lote.codigo_lote}</span>
        <span className={ts.loteKg}>
          {badge === "critico" && <span className={ts.alertaIcon}>⚠</span>}
          <strong>{kg.toFixed(1)} kg</strong> disp.
        </span>
        <span className={ts.loteValor}>R$ {Number(lote.valor_kg).toFixed(0)}/kg</span>
        <span className={ts.loteData}>compra: {dataCompra}</span>
        <span className={`${ts.badge} ${ts[`badge_${badge}`]}`}>
          {badge === "critico" ? "Crítico" : lote.status.charAt(0).toUpperCase() + lote.status.slice(1)}
        </span>
      </div>
      <div className={ts.loteAcoes}>
        {podeEditar && <button className={ts.btnArquivar} onClick={onArquivar}>Arquivar</button>}
      </div>
    </div>
  );
}
