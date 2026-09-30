import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getCoresDoModelo, getLotesDaCor, getModelos } from "../api/tecidos";
import { buscarGrupos } from "../api/moldes";
import {
  cancelarJobEncaixeRapido,
  gerarEncaixeRapido,
  getEncaixeRapido,
  getJobEncaixeRapido,
  getPdfEncaixe,
  validarEncaixeRapido,
} from "../api/encaixes";
import { getProximoNumeroPedidoVenda, createPedidoVenda, addItemPedidoVenda } from "../api/pedidos";
import ProgressoEncaixe, {
  CardMesa,
  ResumoEnfesto,
  RotuloMotor,
  agruparEnfestos,
  cardsGridClass,
} from "../components/ProgressoEncaixe/ProgressoEncaixe";
import styles from "./EncaixeRapidoPage.module.css";
import useOverlayDismiss from "../hooks/useOverlayDismiss";
import DecisaoEnfesto from "../components/DecisaoEnfesto/DecisaoEnfesto";

const TAMANHOS_BASE = ["P", "M", "G", "GG"];
const TAMANHOS_PLUS = ["P", "M", "G", "GG", "G1", "G2", "G3"];
const TAM_KEY = {
  P: "qtd_p",
  M: "qtd_m",
  G: "qtd_g",
  GG: "qtd_gg",
  G1: "qtd_g1",
  G2: "qtd_g2",
  G3: "qtd_g3",
};
const QTD_KEYS = ["qtd_p", "qtd_m", "qtd_g", "qtd_gg", "qtd_g1", "qtd_g2", "qtd_g3"];

// Comprimento máximo do enfesto (limite da mesa de corte), em cm.
const COMP_MIN = 50;
const COMP_MAX = 2000;
const COMP_PADRAO = 150;

// "Avançado" (recolhido): o enfesto é decidido pelo sistema (face única ou
// face a face, sem sobra ou menos enfestos) e a qualidade é Automática; a
// escolha manual fica aqui, para exceções.
const QUALIDADES = [
  { valor: "AUTOMATICO", rotulo: "Automático" },
  { valor: "RAPIDO", rotulo: "Rápido" },
  { valor: "EQUILIBRADO", rotulo: "Equilibrado" },
  { valor: "MAXIMO", rotulo: "Máximo" },
];
const TIPOS_ENFESTO = [
  { valor: "AUTOMATICO", rotulo: "Automático" },
  { valor: "MESMA_FACE", rotulo: "Face única" },
  { valor: "FACE_A_FACE", rotulo: "Face a face" },
];
const MODOS_CAMADAS = [
  { valor: "AUTOMATICO", rotulo: "Automático" },
  { valor: "SEM_SOBRA", rotulo: "Sem sobra" },
  { valor: "MENOS_ENFESTOS", rotulo: "Menos enfestos" },
];

const IconeTesoura = () => (
  <svg
    width="28"
    height="28"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <circle cx="6" cy="6" r="3" />
    <circle cx="6" cy="18" r="3" />
    <line x1="20" y1="4" x2="8.1" y2="15.9" />
    <line x1="14.5" y1="14.5" x2="20" y2="20" />
    <line x1="8.1" y1="8.1" x2="12" y2="12" />
  </svg>
);

// Totais de todas as mesas do resultado (comprimento é de UMA camada — o
// risco; peso e custo, de todas as camadas). Aproveitamento médio ponderado
// pelo comprimento de cada mesa.
function totaisResultado(encaixes) {
  const soma = (f) => encaixes.reduce((s, e) => s + (Number(f(e)) || 0), 0);
  const metros = soma((e) => e.comp_metros);
  const ponderado = soma((e) => (e.aproveitamento_pct ?? 0) * (e.comp_metros ?? 0));
  return {
    metros,
    peso: soma((e) => e.peso_total_kg),
    custo: soma((e) => e.custo_total_camadas),
    aproveitamento: metros > 0 ? ponderado / metros : null,
  };
}

const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

// Nível semântico do aproveitamento — a cor fica no CSS, via data-nivel
// (ver .resultMetricValue[data-nivel]). Limiares 85/70, como antes.
const nivelAproveitamento = (v) => {
  if (v == null) return "neutro";
  if (v >= 85) return "bom";
  if (v >= 70) return "medio";
  return "ruim";
};

const ITEM_VAZIO = {
  searchQuery: "",
  searchResults: [],
  selectedGrupo: null,
  tecido_id: "",
  qtd_p: "",
  qtd_m: "",
  qtd_g: "",
  qtd_gg: "",
  qtd_g1: "",
  qtd_g2: "",
  qtd_g3: "",
};

// Job em andamento guardado na sessão: recarregar a página retoma o
// acompanhamento (a OC faz o mesmo pelo id na URL). sessionStorage some ao
// fechar o app — junto com o backend, que leva o job.
const CHAVE_JOB = "smartcut.encaixeRapido.job";

const lerJobSalvo = () => {
  try {
    return JSON.parse(sessionStorage.getItem(CHAVE_JOB)) || null;
  } catch {
    return null;
  }
};

const salvarJob = (job) => {
  try {
    if (job) sessionStorage.setItem(CHAVE_JOB, JSON.stringify(job));
    else sessionStorage.removeItem(CHAVE_JOB);
  } catch {}
};

const TM_VAZIO = {
  tmModeloId: "",
  tmCores: [],
  tmCorId: "",
  tmLotes: [],
  tmLoteId: "",
  tmErr: null,
};

export default function EncaixeRapidoPage() {
  const tecidoModalOverlay = useOverlayDismiss(() => setTecidoModal(null));
  const itemModalOverlay = useOverlayDismiss(() => {
    setItemModal(null);
    setErroModal(null);
  });

  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  // id do Encaixe Rápido na URL (?id=<pedido_id>): abrir com ele recarrega a
  // configuração e o resultado do backend, sem gerar de novo.
  const idRapido = searchParams.get("id");

  const [nome, setNome] = useState(() => lerJobSalvo()?.nome ?? "");
  // Limite da mesa de corte (cm): risco maior sai dividido em partes.
  const [comprimentoMax, setComprimentoMax] = useState(String(COMP_PADRAO));
  const [qualidade, setQualidade] = useState("AUTOMATICO");
  const [tipoEnfesto, setTipoEnfesto] = useState("AUTOMATICO");
  const [modoCamadas, setModoCamadas] = useState("AUTOMATICO");
  const [modelos, setModelos] = useState([]);
  const [tecidos, setTecidos] = useState([]);
  const [tecidoModal, setTecidoModal] = useState(null);
  const [pecas, setPecas] = useState([]);

  const [itemModal, setItemModal] = useState(null);
  // gerando: criando o pedido interno e enfileirando; jobPedidoId: job no
  // backend (o ProgressoEncaixe acompanha e entrega o resultado).
  const [gerando, setGerando] = useState(false);
  const [jobPedidoId, setJobPedidoId] = useState(() => lerJobSalvo()?.pedidoId ?? null);
  const [resultado, setResultado] = useState(null);
  const [avisos, setAvisos] = useState([]);
  const [problemas, setProblemas] = useState([]);
  const [erroGeral, setErroGeral] = useState(null);
  const [erroModal, setErroModal] = useState(null);
  const [carregandoRecarga, setCarregandoRecarga] = useState(false);
  // Encaixe com ?id= que falhou ao carregar (não existe mais, por exemplo).
  const [erroRecarga, setErroRecarga] = useState(null);
  const searchTimer = useRef(null);

  useEffect(() => {
    getModelos()
      .then((m) => setModelos(m || []))
      .catch(() => {});
  }, []);

  // ── Reabrir um Encaixe Rápido já gerado (?id= na URL) ──────────────────────
  // Carrega configuração (nome, tecidos, peças, comprimento, qualidade) e o
  // resultado do backend, sem gerar de novo nem retomar job.
  useEffect(() => {
    if (!idRapido || jobPedidoId || resultado || erroRecarga || carregandoRecarga) return;
    let vivo = true;
    setCarregandoRecarga(true);
    getEncaixeRapido(idRapido)
      .then((d) => {
        if (!vivo) return;
        const cfg = d.config || {};
        setNome(cfg.nome || "");
        setTecidos(cfg.tecidos || []);
        setPecas(cfg.pecas || []);
        setComprimentoMax(String(cfg.comprimento_max_cm ?? COMP_PADRAO));
        setQualidade(cfg.qualidade || "AUTOMATICO");
        const r = d.resultado || {};
        setResultado(r);
        setAvisos(r.avisos || []);
        setErroGeral(null);
      })
      .catch((e) => {
        if (!vivo) return;
        setErroRecarga(
          (e.message || "Não foi possível carregar este encaixe.") +
            " Clique em “Novo encaixe” para começar do zero."
        );
      })
      .finally(() => {
        if (vivo) setCarregandoRecarga(false);
      });
    return () => {
      vivo = false;
    };
  }, [idRapido, jobPedidoId, resultado, erroRecarga]);

  // ── Tecido modal handlers ──────────────────────────────────────────────────
  const abrirTecidoModal = () => setTecidoModal({ ...TM_VAZIO });

  const handleTmModelo = async (id) => {
    setTecidoModal((m) => ({
      ...m,
      tmModeloId: id,
      tmCores: [],
      tmCorId: "",
      tmLotes: [],
      tmLoteId: "",
    }));
    if (!id) return;
    try {
      const cs = (await getCoresDoModelo(id)) || [];
      setTecidoModal((m) => ({ ...m, tmCores: cs }));
    } catch {}
  };

  const handleTmCor = async (id) => {
    setTecidoModal((m) => ({ ...m, tmCorId: id, tmLotes: [], tmLoteId: "" }));
    if (!id) return;
    try {
      const all = (await getLotesDaCor(id)) || [];
      setTecidoModal((m) => ({
        ...m,
        tmLotes: all.filter((l) => l.status !== "esgotado" && l.status !== "arquivado"),
      }));
    } catch {}
  };

  const handleConfirmarTecido = () => {
    const { tmModeloId, tmCorId, tmLoteId, tmCores, tmLotes } = tecidoModal;
    if (!tmModeloId || !tmCorId || !tmLoteId) {
      setTecidoModal((m) => ({ ...m, tmErr: "Selecione modelo, cor e lote." }));
      return;
    }
    const modelo = modelos.find((m) => m.id === tmModeloId);
    const cor = tmCores.find((c) => c.id === tmCorId);
    const lote = tmLotes.find((l) => l.id === tmLoteId);
    setTecidos((ts) => [
      ...ts,
      {
        _id: `tm-${Date.now()}-${Math.random()}`,
        modelo_id: modelo.id,
        modelo_nome: modelo.nome,
        cor_id: cor.id,
        cor_nome: cor.nome_cor,
        cor_largura_cm: cor.largura_util_cm,
        lote_id: lote.id,
        lote_codigo: lote.codigo_lote,
        lote_peso_kg: lote.peso_disponivel_kg,
      },
    ]);
    setTecidoModal(null);
  };

  const removerTecido = (_id) => setTecidos((ts) => ts.filter((t) => t._id !== _id));

  // ── Item modal handlers ────────────────────────────────────────────────────
  const abrirItemModal = () => {
    setItemModal({ ...ITEM_VAZIO });
    setErroModal(null);
  };

  const handleSearchChange = (query) => {
    setItemModal((m) => ({ ...m, searchQuery: query, selectedGrupo: null, searchResults: [] }));
    clearTimeout(searchTimer.current);
    if (query.trim().length < 2) return;
    searchTimer.current = setTimeout(async () => {
      try {
        const results = await buscarGrupos(query);
        setItemModal((m) => ({ ...m, searchResults: (results || []).slice(0, 10) }));
      } catch {}
    }, 400);
  };

  const selecionarGrupo = (grupo) => {
    setItemModal((m) => ({
      ...m,
      searchQuery: `${grupo.codigo ? grupo.codigo + " — " : ""}${grupo.nome}`,
      searchResults: [],
      selectedGrupo: grupo,
      qtd_p: "",
      qtd_m: "",
      qtd_g: "",
      qtd_gg: "",
      qtd_g1: "",
      qtd_g2: "",
      qtd_g3: "",
    }));
  };

  const handleConfirmarItem = () => {
    if (!itemModal.selectedGrupo) {
      setErroModal("Selecione uma referência.");
      return;
    }
    if (!itemModal.tecido_id) {
      setErroModal("Selecione o tecido desta peça.");
      return;
    }
    const qtdTotal = QTD_KEYS.reduce((s, k) => s + (parseInt(itemModal[k]) || 0), 0);
    if (qtdTotal === 0) {
      setErroModal("Informe ao menos uma quantidade.");
      return;
    }

    const isPlus = itemModal.selectedGrupo.tem_plus;
    const tamCols = isPlus ? TAMANHOS_PLUS : TAMANHOS_BASE;
    const qtds = Object.fromEntries(
      tamCols.map((t) => [TAM_KEY[t], parseInt(itemModal[TAM_KEY[t]]) || 0])
    );

    const tecSel = tecidos.find((t) => t._id === itemModal.tecido_id);
    setPecas((ps) => [
      ...ps,
      {
        _id: `${Date.now()}-${Math.random()}`,
        grupo_id: itemModal.selectedGrupo.id,
        grupo_nome: itemModal.selectedGrupo.nome,
        grupo_codigo: itemModal.selectedGrupo.codigo,
        tem_plus: isPlus,
        cor: tecSel?.cor_nome ?? "",
        tecido_id: itemModal.tecido_id,
        ...qtds,
      },
    ]);
    setItemModal(null);
  };

  const removerPeca = (_id) => setPecas((ps) => ps.filter((p) => p._id !== _id));

  const pecaQtdEntries = (peca) => {
    const cols = peca.tem_plus ? TAMANHOS_PLUS : TAMANHOS_BASE;
    return cols
      .filter((t) => (peca[TAM_KEY[t]] || 0) > 0)
      .map((t) => ({ tam: t, qtd: peca[TAM_KEY[t]] }));
  };

  // ── Gerar encaixe ─────────────────────────────────────────────────────────
  const handleGerar = async () => {
    if (tecidos.length === 0) {
      setErroGeral("Adicione ao menos um tecido.");
      return;
    }
    if (pecas.length === 0) {
      setErroGeral("Adicione ao menos uma peça.");
      return;
    }
    if (pecas.some((p) => !p.tecido_id)) {
      setErroGeral("Todas as peças precisam ter um tecido.");
      return;
    }
    const cm = Number(comprimentoMax.trim());
    if (!Number.isInteger(cm) || cm < COMP_MIN || cm > COMP_MAX) {
      setErroGeral(
        `O comprimento máximo deve ser um número inteiro entre ${COMP_MIN} e ${COMP_MAX} cm.`
      );
      return;
    }
    setGerando(true);
    setErroGeral(null);
    setProblemas([]);
    setResultado(null);
    setAvisos([]);

    try {
      await getProximoNumeroPedidoVenda("encaixe_rapido").catch(() => "001");
      const pedido = await createPedidoVenda({
        tipo: "encaixe_rapido",
        data_emissao: new Date().toISOString().split("T")[0],
        prazo_entrega_dias: 0,
        condicoes: "avista",
        observacoes_internas: nome || null,
        cliente_razao_social: nome || "Encaixe Rápido",
      });

      for (const peca of pecas) {
        const tecido = tecidos.find((t) => t._id === peca.tecido_id);
        await addItemPedidoVenda(pedido.id, {
          grupo_id: peca.grupo_id,
          cor: peca.cor,
          lote_id: tecido?.lote_id ?? null,
          qtd_p: peca.qtd_p || 0,
          qtd_m: peca.qtd_m || 0,
          qtd_g: peca.qtd_g || 0,
          qtd_gg: peca.qtd_gg || 0,
          qtd_g1: peca.qtd_g1 || 0,
          qtd_g2: peca.qtd_g2 || 0,
          qtd_g3: peca.qtd_g3 || 0,
          preco_unitario: 0,
        });
      }

      // Valida as peças ANTES de enfileirar: peça mais larga que a largura
      // útil do tecido ou polígono inválido param aqui, com o molde e o
      // tecido citados. Os avisos (peça maior que a mesa) só informam.
      const { problemas, avisos: avisosValidacao } = await validarEncaixeRapido(pedido.id, {
        comprimentoMaxCm: cm,
      });
      if (problemas?.length) {
        setProblemas(problemas);
        setErroGeral(
          "Não foi possível gerar o encaixe: resolva os problemas das peças abaixo. Nenhum encaixe foi gravado."
        );
        return;
      }
      if (avisosValidacao?.length) setAvisos(avisosValidacao);

      // 202 { job_id }: o encaixe roda em segundo plano; o resultado chega
      // pelo ProgressoEncaixe (jobConcluido).
      await gerarEncaixeRapido(pedido.id, {
        comprimentoMaxCm: cm,
        qualidade,
        tipoEnfesto,
        modoCamadas,
      });
      salvarJob({ pedidoId: pedido.id, nome });
      setJobPedidoId(pedido.id);
    } catch (e) {
      setErroGeral(e.message || "Erro ao gerar encaixe.");
    } finally {
      setGerando(false);
    }
  };

  const jobConcluido = (estado) => {
    const r = estado.resultado || {};
    const encaixes = r.encaixes || [];
    salvarJob(null);
    setJobPedidoId(null);
    if (!encaixes.length) {
      navigate("/producao/encaixes");
      return;
    }
    setResultado({
      pedido_id: estado.pedido_id,
      encaixes,
      comprimento_max_cm: encaixes[0].comprimento_max_cm,
      decisoes: r.decisoes ?? [],
    });
    setAvisos(r.avisos ?? []);
    // Mantém a URL reabrível: /producao/encaixe-rapido?id=<pedido_id>
    navigate(`/producao/encaixe-rapido?id=${estado.pedido_id}`, { replace: true });
  };

  // Cancelado, erro dispensado ou job perdido (backend reiniciou).
  const jobEncerrado = (estado) => {
    salvarJob(null);
    setJobPedidoId(null);
    if (estado?.status === "CANCELADO")
      setErroGeral("Geração cancelada. Nenhum encaixe foi gravado.");
    else if (estado?.status === "ERRO") setErroGeral(estado.erro || "Erro ao gerar encaixe.");
    else setErroGeral("A geração foi interrompida (o servidor reiniciou?). Tente novamente.");
  };

  // "Novo encaixe": limpa a tela e remove o ?id= da URL (e o job salvo).
  const novoEncaixe = () => {
    salvarJob(null);
    setJobPedidoId(null);
    setResultado(null);
    setAvisos([]);
    setErroGeral(null);
    setErroRecarga(null);
    setNome("");
    setTecidos([]);
    setPecas([]);
    setComprimentoMax(String(COMP_PADRAO));
    setQualidade("AUTOMATICO");
    setTipoEnfesto("AUTOMATICO");
    setModoCamadas("AUTOMATICO");
    setSearchParams({}, { replace: true });
  };

  const isPlus = itemModal?.selectedGrupo?.tem_plus;
  const tamForm = isPlus ? TAMANHOS_PLUS : TAMANHOS_BASE;
  const tmCor = tecidoModal?.tmCores.find((c) => c.id === tecidoModal.tmCorId);

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Encaixe Rápido</h1>
      </div>
      <div className={styles.cols}>
        {/* ── Coluna esquerda ── */}
        <div className={styles.colLeft}>
          <div className="sc-card">
            <p className={styles.sectionLabel}>Configuração do Encaixe</p>
            <label className={styles.field}>
              <span>Nome / identificação (opcional)</span>
              <input
                className={`${styles.input} sc-upper`}
                placeholder="Ex: Legging / Pedido 001"
                value={nome}
                onChange={(e) => setNome(e.target.value.toUpperCase())}
              />
            </label>
            <label className={styles.field}>
              <span>Comprimento máximo (cm)</span>
              <input
                className={styles.input}
                type="number"
                inputMode="numeric"
                min={COMP_MIN}
                max={COMP_MAX}
                step={1}
                value={comprimentoMax}
                onChange={(e) => setComprimentoMax(e.target.value)}
                title="Limite da mesa. Riscos menores saem com o tamanho real; maiores são divididos em partes."
              />
            </label>
            <details
              className={styles.avancado}
              open={
                tipoEnfesto !== "AUTOMATICO" ||
                modoCamadas !== "AUTOMATICO" ||
                qualidade !== "AUTOMATICO" ||
                undefined
              }
            >
              <summary>Avançado</summary>
              <p className={styles.avancadoNota}>
                O sistema escolhe como estender cada tecido e explica o porquê no resultado. Use só
                para exceções.
              </p>
              <label className={styles.field}>
                <span>Tipo de enfesto</span>
                <select
                  className={styles.input}
                  value={tipoEnfesto}
                  onChange={(e) => setTipoEnfesto(e.target.value)}
                  title="Face a face só vale para tecido sem direção e sem peça única assimétrica."
                >
                  {TIPOS_ENFESTO.map((t) => (
                    <option key={t.valor} value={t.valor}>
                      {t.rotulo}
                    </option>
                  ))}
                </select>
              </label>
              <label className={styles.field}>
                <span>Modo de camadas</span>
                <select
                  className={styles.input}
                  value={modoCamadas}
                  onChange={(e) => setModoCamadas(e.target.value)}
                >
                  {MODOS_CAMADAS.map((m) => (
                    <option key={m.valor} value={m.valor}>
                      {m.rotulo}
                    </option>
                  ))}
                </select>
              </label>
              <label className={styles.field}>
                <span>Qualidade do encaixe</span>
                <select
                  className={styles.input}
                  value={qualidade}
                  onChange={(e) => setQualidade(e.target.value)}
                  title="Automático escolhe o perfil pelo número de peças do enfesto: poucas → Máximo, médias → Equilibrado, muitas → Rápido."
                >
                  {QUALIDADES.map((q) => (
                    <option key={q.valor} value={q.valor}>
                      {q.rotulo}
                    </option>
                  ))}
                </select>
              </label>
            </details>
          </div>

          {/* ── Card Tecidos ── */}
          <div className="sc-card">
            <p className={styles.sectionLabel}>Tecidos do Encaixe</p>

            {tecidos.length === 0 ? (
              <p className={styles.tecidosVazio}>Adicione ao menos um tecido</p>
            ) : (
              <ul className={styles.tecidosList}>
                {tecidos.map((t) => (
                  <li key={t._id} className={styles.tecidoCard}>
                    <div className={styles.tecidoInfo}>
                      <span className={styles.tecidoNome}>
                        {t.modelo_nome} — {t.cor_nome}
                      </span>
                      <span className={styles.tecidoMeta}>
                        Lote {t.lote_codigo} · {t.lote_peso_kg} kg disp. · {t.cor_largura_cm} cm
                        largura
                      </span>
                    </div>
                    <button
                      className={styles.btnRemovePeca}
                      onClick={() => removerTecido(t._id)}
                      title="Remover tecido"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <button
              className={`${styles.btnAddPeca} ${tecidos.length ? styles.btnAddComEspaco : styles.btnAddSemEspaco}`}
              onClick={abrirTecidoModal}
            >
              + Adicionar Tecido
            </button>
          </div>

          {/* ── Card Peças ── */}
          <div className="sc-card">
            <p className={styles.sectionLabel}>Peças a encaixar</p>

            {pecas.length > 0 && (
              <ul className={styles.pecasList}>
                {pecas.map((peca) => {
                  const tec = tecidos.find((t) => t._id === peca.tecido_id);
                  return (
                    <li key={peca._id} className={styles.pecaCard}>
                      <div className={styles.pecaInfo}>
                        <div>
                          <code className={styles.pecaCod}>{peca.grupo_codigo || "?"}</code>
                          {peca.grupo_nome}
                          {tec && (
                            <span className={styles.pecaTecido}>
                              {" | "}Tecido: {tec.modelo_nome} — {tec.cor_nome}
                            </span>
                          )}
                        </div>
                        <div className={styles.pecaQtds}>
                          {pecaQtdEntries(peca).map(({ tam, qtd }) => (
                            <span key={tam} className={styles.tamBadge}>
                              {tam}×{qtd}
                            </span>
                          ))}
                        </div>
                      </div>
                      <button
                        className={styles.btnRemovePeca}
                        onClick={() => removerPeca(peca._id)}
                        title="Remover peça"
                      >
                        ×
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}

            <button className={styles.btnAddPeca} onClick={abrirItemModal}>
              + Adicionar peça
            </button>
          </div>

          <button
            className={styles.btnGerar}
            onClick={handleGerar}
            disabled={gerando || !!jobPedidoId}
          >
            {gerando ? "Preparando…" : jobPedidoId ? "Gerando encaixe…" : "Gerar Encaixe"}
          </button>
        </div>

        {/* ── Coluna direita ── */}
        <div className={styles.colRight}>
          {jobPedidoId ? (
            <div className={styles.resultCard}>
              <ProgressoEncaixe
                chave={jobPedidoId}
                consultarJob={() => getJobEncaixeRapido(jobPedidoId)}
                cancelarJob={() => cancelarJobEncaixeRapido(jobPedidoId)}
                onConcluido={jobConcluido}
                onFim={jobEncerrado}
              />
            </div>
          ) : gerando ? (
            <div className={styles.emptyState}>
              <div className={styles.spinner} />
              <p className={styles.emptyText}>Preparando o encaixe…</p>
            </div>
          ) : carregandoRecarga ? (
            <div className={styles.emptyState}>
              <div className={styles.spinner} />
              <p className={styles.emptyText}>Carregando o encaixe salvo…</p>
            </div>
          ) : erroRecarga ? (
            <div className={styles.errorState}>
              <p className={styles.errorText}>{erroRecarga}</p>
              <button className={styles.btnPrimary} onClick={novoEncaixe}>
                Novo encaixe
              </button>
            </div>
          ) : erroGeral ? (
            <div className={styles.errorState}>
              <p className={styles.errorText}>{erroGeral}</p>
              {problemas.length > 0 && (
                <ul className={styles.errorList}>
                  {problemas.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              )}
              <button className={styles.btnPrimary} onClick={handleGerar}>
                Tentar novamente
              </button>
            </div>
          ) : !resultado ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>
                <IconeTesoura />
              </div>
              <p className={styles.emptyText}>
                Configure as peças e clique em
                <br />
                <strong>Gerar Encaixe</strong>
              </p>
            </div>
          ) : (
            <ResultadoRapido
              resultado={resultado}
              avisos={avisos}
              nome={nome}
              onTentar={handleGerar}
              onNovo={novoEncaixe}
              onVer={(id) => navigate(`/producao/encaixes/${id}`)}
            />
          )}
        </div>
      </div>

      {/* ══ MODAL — Adicionar Tecido ══ */}
      {tecidoModal && (
        <div className={styles.overlay} {...tecidoModalOverlay}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Adicionar Tecido</h2>
              <button className={styles.btnClose} onClick={() => setTecidoModal(null)}>
                ×
              </button>
            </div>

            <div className={styles.modalBody}>
              <label className={styles.field}>
                <span>Modelo</span>
                <select
                  className={styles.input}
                  value={tecidoModal.tmModeloId}
                  onChange={(e) => handleTmModelo(e.target.value)}
                >
                  <option value="">— Selecionar modelo —</option>
                  {modelos.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.nome}
                      {m.tipo ? ` (${m.tipo})` : ""}
                    </option>
                  ))}
                </select>
              </label>

              <label className={styles.field}>
                <span>Cor</span>
                <select
                  className={styles.input}
                  value={tecidoModal.tmCorId}
                  onChange={(e) => handleTmCor(e.target.value)}
                  disabled={!tecidoModal.tmModeloId || tecidoModal.tmCores.length === 0}
                >
                  <option value="">— Selecionar cor —</option>
                  {tecidoModal.tmCores.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome_cor} — {c.largura_util_cm} cm
                    </option>
                  ))}
                </select>
              </label>

              <label className={styles.field}>
                <span>Lote</span>
                <select
                  className={styles.input}
                  value={tecidoModal.tmLoteId}
                  onChange={(e) => setTecidoModal((m) => ({ ...m, tmLoteId: e.target.value }))}
                  disabled={!tecidoModal.tmCorId || tecidoModal.tmLotes.length === 0}
                >
                  <option value="">— Selecionar lote —</option>
                  {tecidoModal.tmLotes.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.codigo_lote} — {l.peso_disponivel_kg} kg · {tmCor?.largura_util_cm} cm
                    </option>
                  ))}
                </select>
              </label>

              {tecidoModal.tmErr && <p className={styles.erroModal}>{tecidoModal.tmErr}</p>}
            </div>

            <div className={styles.modalActions}>
              <button className={styles.btnSecondary} onClick={() => setTecidoModal(null)}>
                Cancelar
              </button>
              <button
                className={styles.btnPrimary}
                onClick={handleConfirmarTecido}
                disabled={!tecidoModal.tmLoteId}
              >
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ MODAL — Adicionar peça ══ */}
      {itemModal && (
        <div className={styles.overlay} {...itemModalOverlay}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHead}>
              <h2 className={styles.modalTitle}>Adicionar peça</h2>
              <button
                className={styles.btnClose}
                onClick={() => {
                  setItemModal(null);
                  setErroModal(null);
                }}
              >
                ×
              </button>
            </div>

            <div className={styles.modalBody}>
              <div className={styles.searchWrap}>
                <label className={styles.field}>
                  <span>Referência — código ou nome</span>
                  <input
                    className={styles.input}
                    placeholder="Digite para buscar…"
                    value={itemModal.searchQuery}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    autoComplete="off"
                    autoFocus
                  />
                </label>
                {itemModal.searchResults.length > 0 && (
                  <ul className={styles.autocomplete}>
                    {itemModal.searchResults.map((g) => (
                      <li key={g.id} className={styles.acItem} onClick={() => selecionarGrupo(g)}>
                        <code className={styles.acCod}>{g.codigo || "?"}</code>
                        <span className={styles.acNome}>{g.nome}</span>
                        {g.tem_plus && <span className={styles.acPlus}>Plus</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {itemModal.selectedGrupo && (
                <>
                  <label className={styles.field}>
                    <span>Tecido desta peça</span>
                    {tecidos.length === 0 ? (
                      <>
                        <select className={styles.input} disabled>
                          <option>Nenhum tecido disponível</option>
                        </select>
                        <span className={styles.tecidoAviso}>Adicione um tecido primeiro</span>
                      </>
                    ) : (
                      <select
                        className={styles.input}
                        value={itemModal.tecido_id}
                        onChange={(e) => setItemModal((m) => ({ ...m, tecido_id: e.target.value }))}
                      >
                        <option value="">— Selecionar tecido —</option>
                        {tecidos.map((t) => (
                          <option key={t._id} value={t._id}>
                            {t.modelo_nome} — {t.cor_nome} ({t.lote_codigo})
                          </option>
                        ))}
                      </select>
                    )}
                  </label>

                  <div className={styles.tamSection}>
                    <p className={styles.tamLabel}>Quantidades por tamanho</p>
                    <div className={styles.tamGrid}>
                      {tamForm.map((tam) => (
                        <label key={tam} className={styles.tamItem}>
                          <span>{tam}</span>
                          <input
                            type="number"
                            min="0"
                            className={styles.tamInput}
                            value={itemModal[TAM_KEY[tam]]}
                            onChange={(e) =>
                              setItemModal((m) => ({ ...m, [TAM_KEY[tam]]: e.target.value }))
                            }
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {erroModal && <p className={styles.erroModal}>{erroModal}</p>}
            </div>

            <div className={styles.modalActions}>
              <button
                className={styles.btnSecondary}
                onClick={() => {
                  setItemModal(null);
                  setErroModal(null);
                }}
              >
                Cancelar
              </button>
              <button
                className={styles.btnPrimary}
                onClick={handleConfirmarItem}
                disabled={!itemModal.selectedGrupo}
              >
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Resultado: totais, mesas por enfesto (cards com a linha de moldes) ─────────

function ResultadoRapido({ resultado, avisos, nome, onTentar, onNovo, onVer }) {
  const { encaixes } = resultado;
  const t = totaisResultado(encaixes);
  const enfestos = agruparEnfestos(encaixes);

  if (t.aproveitamento != null && t.aproveitamento <= 0)
    return (
      <div className={styles.warningState}>
        {avisos.length > 0 ? (
          avisos.map((aviso, i) => (
            <p key={i} className={styles.warningText}>
              {aviso}
            </p>
          ))
        ) : (
          <p className={styles.warningText}>
            Nenhuma peça foi posicionada no tecido. Verifique a largura útil do tecido selecionado.
          </p>
        )}
        <button className={styles.btnPrimary} onClick={onTentar}>
          Tentar novamente
        </button>
      </div>
    );

  const baixarPdf = async () => {
    try {
      const blob = await getPdfEncaixe(resultado.pedido_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `corte-encaixe.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {}
  };

  return (
    <div className={styles.resultCard}>
      <div className={styles.resultHeader}>
        <p className={styles.resultTitle}>Encaixe gerado com sucesso</p>
        <p className={styles.resultSub}>
          {nome || "Encaixe rápido"} · {encaixes.length} {encaixes.length === 1 ? "mesa" : "mesas"}{" "}
          de até {resultado.comprimento_max_cm} cm
        </p>
        <RotuloMotor encaixes={encaixes} />
      </div>

      <div className={styles.resultGrid}>
        <div className={styles.resultMetric}>
          <span className={styles.resultMetricLabel}>Aproveitamento médio</span>
          <span
            className={styles.resultMetricValue}
            data-nivel={nivelAproveitamento(t.aproveitamento)}
          >
            {t.aproveitamento != null ? `${t.aproveitamento.toFixed(1)}%` : "—"}
          </span>
        </div>
        <div className={styles.resultMetric}>
          <span
            className={styles.resultMetricLabel}
            title="Soma do comprimento de uma camada de cada mesa"
          >
            Comprimento dos riscos
          </span>
          <span className={styles.resultMetricValue}>{t.metros.toFixed(2)} m</span>
        </div>
        <div className={styles.resultMetric}>
          <span className={styles.resultMetricLabel}>Peso total</span>
          <span className={styles.resultMetricValue}>{t.peso.toFixed(3)} kg</span>
        </div>
        <div className={styles.resultMetric}>
          <span className={styles.resultMetricLabel}>Custo total</span>
          <span className={styles.resultMetricValue}>{moeda(t.custo)}</span>
        </div>
      </div>

      <DecisaoEnfesto decisoes={resultado.decisoes} />

      {enfestos.map((g) => (
        <section key={g.chave}>
          <ResumoEnfesto grupo={g} />
          <div className={cardsGridClass}>
            {g.mesas.map((e) => (
              <CardMesa key={e.id} encaixe={e} />
            ))}
          </div>
        </section>
      ))}

      <div className={styles.resultActions}>
        <button className={styles.btnPrimary} onClick={() => onVer(encaixes[0].id)}>
          Ver encaixe completo →
        </button>
        <button className={styles.btnDownload} onClick={baixarPdf}>
          ↓ Baixar PDF de Corte
        </button>
        <button className={styles.btnSecondary} onClick={onNovo}>
          Novo encaixe
        </button>
      </div>

      {avisos.length > 0 && (
        <div className={styles.avisoBanner}>
          {avisos.map((aviso, i) => (
            <p key={i}>{aviso}</p>
          ))}
        </div>
      )}
    </div>
  );
}
