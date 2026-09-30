import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  aplicarSugestaoMesa,
  atualizarOrdemCorte,
  atualizarOrdemCorteDoPedido,
  cancelarOrdemCorte,
  concluirOrdemCorte,
  descartarSugestaoMesa,
  enviarOrdemCorte,
  gerarEncaixesOrdemCorte,
  getJobOrdemCorte,
  getLotesDisponiveis,
  getOrdemCorte,
  iniciarOrdemCorte,
  reabrirOrdemCorte,
  voltarOrdemCorteParaRascunho,
} from "../api/ordensCorte";
import { RELATORIO_FORMULARIO_CORTE, imprimirRelatorio } from "../api/relatorios";
import ConcluirCorteModal from "../components/ConcluirCorteModal/ConcluirCorteModal";
import ConfirmModal from "../components/ConfirmModal/ConfirmModal";
import DecisaoEnfesto, { NOME_TIPO_ENFESTO } from "../components/DecisaoEnfesto/DecisaoEnfesto";
import MenuDropdown from "../components/MenuDropdown/MenuDropdown";
import Modal from "../components/Modal/Modal";
import OrdemCorteAssistente from "../components/OrdemCorteAssistente/OrdemCorteAssistente";
import ProgressoEncaixe, {
  AlertaMesaMaior,
  MoldesMesa,
  ResumoEnfesto,
  RotuloMotor,
  agruparEnfestos,
} from "../components/ProgressoEncaixe/ProgressoEncaixe";
import { useAuth } from "../auth/useAuth";
import styles from "./OrdemCorteDetalhePage.module.css";

// Mesmas pílulas da lista de Ordens de Corte.
const STATUS_OC = {
  RASCUNHO: { label: "Rascunho", cls: "stRascunho" },
  ENVIADA: { label: "Enviada", cls: "stEnviada" },
  EM_CORTE: { label: "Em corte", cls: "stEmCorte" },
  CONCLUIDA: { label: "Concluída", cls: "stConcluida" },
  CANCELADA: { label: "Cancelada", cls: "stCancelada" },
};
const FINAIS = ["CONCLUIDA", "CANCELADA"];

const MODO_LABEL = { SEM_SOBRA: "sem sobra", MENOS_ENFESTOS: "menos enfestos", MISTO: "misto" };
// Enfesto decidido na geração: "Enfesto duplo · sem sobra"; OC gerada antes
// da decisão automática não tem tipo_enfesto (era sempre enfesto simples).
const enfestoLabel = (oc) => {
  if (!oc.encaixes?.length) return "Automático";
  const tipo =
    oc.tipo_enfesto === "MISTO" ? "Misto" : NOME_TIPO_ENFESTO[oc.tipo_enfesto || "MESMA_FACE"];
  return `${tipo} · ${MODO_LABEL[oc.modo_camadas] || oc.modo_camadas}`;
};

// Linha do tempo do cabeçalho: o passo e o campo de data em cada etapa.
const ETAPAS = [
  ["criado_em", "Criada"],
  ["enviada_em", "Enviada"],
  ["iniciada_em", "Iniciada"],
  ["concluida_em", "Concluída"],
];

// Ordem usual de grade; tamanho fora da lista vai depois (numérico em ordem
// crescente, o resto na ordem em que aparece no pedido).
const ORDEM_TAMANHOS = [
  "RN",
  "PP",
  "P",
  "M",
  "G",
  "GG",
  "XG",
  "XGG",
  "EG",
  "EGG",
  "G1",
  "G2",
  "G3",
];

const IconeChevron = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden="true">
    <path
      d="M2 3.5 5 6.5 8 3.5"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);
const IconeMais = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
    <circle cx="3" cy="8" r="1.4" />
    <circle cx="8" cy="8" r="1.4" />
    <circle cx="13" cy="8" r="1.4" />
  </svg>
);
const IconeAlerta = () => (
  <svg
    width="13"
    height="13"
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.6"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M8 2.2 14.2 13H1.8z" />
    <line x1="8" y1="6.5" x2="8" y2="9.3" />
    <line x1="8" y1="11.2" x2="8" y2="11.3" />
  </svg>
);

const numBR = (v, casas = 2) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("pt-BR", {
        minimumFractionDigits: casas,
        maximumFractionDigits: casas,
      });
const moeda = (v) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);
const dataBR = (iso) => (iso ? new Date(iso).toLocaleDateString("pt-BR") : "");
const dataHoraBR = (iso) =>
  iso
    ? new Date(iso).toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";
const fmtEnc = (n) => (n != null ? `ENC-${String(n).padStart(3, "0")}` : "ENC-—");
// "parte 1 de 3" — só para enfesto dividido (encaixes antigos só têm "1/2").
const fmtParte = (e) => {
  if (e.total_partes > 1) return `parte ${e.parte_numero} de ${e.total_partes}`;
  if (!e.parte) return "";
  const [n, total] = String(e.parte).split("/");
  return total ? `parte ${n} de ${total}` : `parte ${e.parte}`;
};
// Comprimento máximo do enfesto (limite da mesa de corte), em cm.
const COMP_MIN = 50;
const COMP_MAX = 2000;
const COMP_PADRAO = 150;
const norm = (s) => (s || "").trim().toUpperCase();

function ordenarTamanhos(tamanhos) {
  const peso = (t, i) => {
    const k = ORDEM_TAMANHOS.indexOf(norm(t));
    if (k >= 0) return [0, k];
    if (/^\d+$/.test(norm(t))) return [1, Number(t)];
    return [2, i];
  };
  return tamanhos
    .map((t, i) => ({ t, p: peso(t, i) }))
    .sort((a, b) => a.p[0] - b.p[0] || a.p[1] - b.p[1])
    .map((x) => x.t);
}

// Uma grade por produto: linhas = cores, colunas = tamanhos (quantidades
// somadas — dois itens do mesmo SKU caem na mesma célula).
function montarGrades(itens) {
  const produtos = new Map();
  for (const i of itens) {
    let g = produtos.get(i.produto_pai_id);
    if (!g) {
      g = {
        id: i.produto_pai_id,
        nome: [i.produto_codigo, i.produto_descricao].filter(Boolean).join(" — "),
        cores: [],
        tamanhos: [],
        qtd: {},
      };
      produtos.set(i.produto_pai_id, g);
    }
    const cor = i.cor || "—";
    const tam = i.tamanho || "—";
    if (!g.cores.includes(cor)) g.cores.push(cor);
    if (!g.tamanhos.includes(tam)) g.tamanhos.push(tam);
    const k = `${cor}|${tam}`;
    g.qtd[k] = (g.qtd[k] || 0) + (i.quantidade || 0);
  }
  return [...produtos.values()].map((g) => ({ ...g, tamanhos: ordenarTamanhos(g.tamanhos) }));
}

export default function OrdemCorteDetalhePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { hasPermission, usuario } = useAuth();
  const podeEditar = hasPermission("encaixes", "editar");
  const podeCriar = hasPermission("encaixes", "criar");
  // A reabertura registra quem desfez a conclusão no histórico do consumo.
  const quemReabertura = (usuario?.nome_completo || usuario?.username || "").trim();

  const [oc, setOc] = useState(null);
  // null = a reserva não veio (falhou); {} = veio e o lote não tem reserva
  // de nenhuma OC. A diferença importa: sem o mapa, "0 reservado" seria
  // mentira e o alerta de estoque ficaria silenciosamente desligado.
  const [estoque, setEstoque] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [acao, setAcao] = useState(null); // ação em andamento (trava os botões)
  const [confirmar, setConfirmar] = useState(null); // chave do ConfirmModal
  const [assistente, setAssistente] = useState(false);
  const [iniciando, setIniciando] = useState(false); // modal "Iniciar corte"
  const [concluindo, setConcluindo] = useState(false); // modal "Concluir corte"
  const [obs, setObs] = useState("");
  const [obsSalva, setObsSalva] = useState(false);
  const [comp, setComp] = useState(String(COMP_PADRAO));
  // Geração em segundo plano (job do backend): enquanto ativa, o progresso
  // fica no lugar do botão e as ações que mudam a OC ficam travadas.
  const [jobAtivo, setJobAtivo] = useState(false);

  const aplicar = (dados) => {
    setOc(dados);
    setObs(dados.observacoes || "");
    setComp(String(dados.comprimento_max_cm ?? COMP_PADRAO));
  };

  // Reserva por lote (kg travados por outras OCs em produção). A OC entra
  // com ?oc_id= para não contar a reserva dela mesma. Lote fora da resposta
  // (arquivado/esgotado) não tem reserva — o `livre_kg` cai no disponível.
  const carregarEstoque = () =>
    getLotesDisponiveis(id)
      .then((lotes) => setEstoque(Object.fromEntries(lotes.map((l) => [l.id, l]))))
      .catch(() => setEstoque(null));

  const carregar = () => {
    setErro(null);
    return getOrdemCorte(id)
      .then((dados) => {
        aplicar(dados);
        return carregarEstoque();
      })
      .catch((e) => setErro(e.status === 404 ? null : e.message))
      .finally(() => setCarregando(false));
  };

  useEffect(() => {
    setCarregando(true);
    setOc(null);
    setJobAtivo(false);
    carregar();
    // Geração iniciada em outra tela (assistente fechado no meio).
    getJobOrdemCorte(id)
      .then((j) => j && ["FILA", "RODANDO"].includes(j.status) && setJobAtivo(true))
      .catch(() => {});
  }, [id]);

  const grades = useMemo(() => montarGrades(oc?.itens || []), [oc]);

  // Ação da barra: trava os botões, mostra o erro da API e recarrega a OC
  // (a resposta de gerar-encaixes não é a OC).
  const executar = async (nome, fn, { recarregar = false } = {}) => {
    setAcao(nome);
    setErro(null);
    try {
      const r = await fn();
      if (recarregar) await carregar();
      else {
        aplicar(r);
        // Entrar/sair de produção muda a reserva dos lotes, e a OC devolvida
        // não traz esses números.
        await carregarEstoque();
      }
    } catch (e) {
      setErro(e.message);
      if (e.status === 409) carregar();
    } finally {
      setAcao(null);
    }
  };

  if (carregando)
    return (
      <div className="sc-page">
        <p className={styles.stateMsg}>Carregando…</p>
      </div>
    );
  if (!oc)
    return (
      <div className="sc-page">
        <button
          type="button"
          className={styles.linkVoltar}
          onClick={() => navigate("/producao/ordens-corte")}
        >
          ← Ordens de Corte
        </button>
        <p className={styles.stateMsg}>{erro || "Ordem de Corte não encontrada."}</p>
      </div>
    );

  const rascunho = oc.status === "RASCUNHO";
  const enviada = oc.status === "ENVIADA";
  const emCorte = oc.status === "EM_CORTE";
  const concluida = oc.status === "CONCLUIDA";
  const final = FINAIS.includes(oc.status);
  const st = STATUS_OC[oc.status];
  const temEncaixes = oc.encaixes.length > 0;
  const bloqueios = (oc.pendencias || []).filter((p) => p.bloqueia);
  const ocupado = !!acao || jobAtivo;
  const enfestos = agruparEnfestos(oc.encaixes);

  // Reserva e livre do lote. `null` nos dois quando o mapa não veio (a
  // seção mostra "—" e não acende alerta). Com o mapa em mãos, um lote fora
  // dele (arquivado/esgotado) não está reservado por ninguém: livre = disponível.
  const estoqueDoLote = (lote) => {
    if (!lote || !estoque) return { reservado: null, livre: null };
    const info = estoque[lote.id];
    return info
      ? { reservado: info.reservado_kg, livre: info.livre_kg }
      : { reservado: 0, livre: lote.peso_disponivel_kg };
  };

  const salvarObs = () => {
    if ((obs || "") === (oc.observacoes || "")) return;
    setObsSalva(false);
    executar("obs", async () => {
      const r = await atualizarOrdemCorte(oc.id, { observacoes: obs });
      setObsSalva(true);
      return r;
    });
  };

  // Comprimento máximo: grava ao sair do campo; mudar deixa os encaixes
  // desatualizados (oc.encaixes_desatualizados) até regerar.
  const salvarComp = () => {
    const cm = Number(comp.trim());
    if (cm === oc.comprimento_max_cm) return;
    if (!Number.isInteger(cm) || cm < COMP_MIN || cm > COMP_MAX) {
      setErro(
        `O comprimento máximo deve ser um número inteiro entre ${COMP_MIN} e ${COMP_MAX} cm.`
      );
      setComp(String(oc.comprimento_max_cm ?? COMP_PADRAO));
      return;
    }
    executar("comp", () => atualizarOrdemCorte(oc.id, { comprimento_max_cm: cm }));
  };

  // Inicia o job; o resultado chega pelo ProgressoEncaixe.
  const gerar = async () => {
    setAcao("gerar");
    setErro(null);
    try {
      await gerarEncaixesOrdemCorte(oc.id);
      setJobAtivo(true);
    } catch (e) {
      setErro(e.message);
      if (e.status === 409) carregar();
    } finally {
      setAcao(null);
    }
  };

  const jobConcluido = () => {
    setJobAtivo(false);
    carregar();
  };

  const jobEncerrado = () => {
    setJobAtivo(false);
    carregar();
  };

  // Alerta de mesa maior: usar troca o limite e já dispara a nova geração.
  const usarMesaMaior = async () => {
    setAcao("mesa");
    setErro(null);
    try {
      const r = await aplicarSugestaoMesa(oc.id);
      aplicar(r.ordem_corte);
      setJobAtivo(true);
    } catch (e) {
      setErro(e.message);
      carregar();
    } finally {
      setAcao(null);
    }
  };

  const confirmacoes = {
    regerar: {
      titulo: "Regerar encaixes",
      mensagem: `Os ${oc.encaixes.length} encaixes atuais desta OC serão substituídos por novos.`,
      label: "Regerar",
      variante: "neutro",
      fn: gerar,
    },
    enviar: {
      titulo: "Enviar à produção",
      mensagem: `Enviar ${oc.numero_fmt} à produção? Depois disso não será possível editar os tecidos nem regerar os encaixes.`,
      label: "Enviar",
      variante: "neutro",
      fn: () => executar("enviar", () => enviarOrdemCorte(oc.id)),
    },
    voltar: {
      titulo: "Voltar para rascunho",
      mensagem: `Devolver ${oc.numero_fmt} para rascunho? O corte ainda não começou e os tecidos voltam a ser editáveis.`,
      label: "Voltar",
      variante: "neutro",
      fn: () => executar("voltar", () => voltarOrdemCorteParaRascunho(oc.id)),
    },
    cancelar: {
      titulo: "Cancelar Ordem de Corte",
      mensagem: `Cancelar ${oc.numero_fmt}? Esta ação não pode ser desfeita; o pedido poderá gerar uma nova OC.`,
      label: "Cancelar OC",
      variante: "perigo",
      fn: () => executar("cancelar", () => cancelarOrdemCorte(oc.id)),
    },
    reabrir: {
      titulo: "Reabrir corte",
      mensagem: `Reabrir ${oc.numero_fmt}? Os consumos de tecido serão estornados e o peso devolvido aos lotes.`,
      label: "Reabrir",
      variante: "neutro",
      fn: () => executar("reabrir", () => reabrirOrdemCorte(oc.id, { quem: quemReabertura })),
    },
  };
  const conf = confirmar && confirmacoes[confirmar];

  // As ações do ⋯ mudam com o status: nada em RASCUNHO, voltar/cancelar em
  // ENVIADA, só cancelar em EM_CORTE e só reabrir em CONCLUIDA.
  const acoesMais = [];
  if (podeEditar && !ocupado) {
    if (enviada)
      acoesMais.push({
        label: "Voltar para rascunho",
        onClick: () => setConfirmar("voltar"),
      });
    if (enviada || emCorte)
      acoesMais.push({
        label: "Cancelar OC",
        danger: true,
        onClick: () => setConfirmar("cancelar"),
      });
    if (concluida)
      acoesMais.push({
        label: "Reabrir corte",
        onClick: () => setConfirmar("reabrir"),
      });
  }

  return (
    <div className={`sc-page ${styles.pagina}`}>
      <ConfirmModal
        isOpen={!!conf}
        titulo={conf?.titulo}
        mensagem={conf?.mensagem}
        labelConfirmar={conf?.label}
        variante={conf?.variante}
        onConfirmar={() => {
          const fn = conf.fn;
          setConfirmar(null);
          fn();
        }}
        onCancelar={() => setConfirmar(null)}
      />

      <div className={`sc-compact ${styles.compacto}`}>
        {/* ── Barra do topo: identificação à esquerda, ações à direita ── */}
        <header className={styles.faixa}>
          <div className={styles.faixaEsq}>
            <button
              type="button"
              className={styles.linkVoltar}
              onClick={() => navigate("/producao/ordens-corte")}
            >
              ← Ordens de Corte
            </button>
            <div className={styles.identificacao}>
              <h1 className={styles.titulo}>{oc.numero_fmt}</h1>
              <span className={`${styles.statusBadge} ${styles[st?.cls] || ""}`}>
                {st?.label || oc.status}
              </span>
              {oc.desatualizada && !final && (
                <span className={`${styles.statusBadge} ${styles.stDesatualizada}`}>
                  Desatualizada
                </span>
              )}
              <RotuloMotor encaixes={oc.encaixes} />
              {obsSalva && <span className={styles.msgSalvo}>Observações salvas.</span>}
            </div>
          </div>

          <div className={styles.actionBar}>
            <MenuDropdown
              className={styles.btnHeaderSecondary}
              trigger={
                <>
                  Imprimir
                  <IconeChevron />
                </>
              }
              items={[
                {
                  // relPro001 (relatorios/producao/relPro001.html)
                  label: "Formulário de corte",
                  onClick: () =>
                    imprimirRelatorio(RELATORIO_FORMULARIO_CORTE, oc.id).catch((e) =>
                      setErro(e.message)
                    ),
                },
              ]}
            />
            {rascunho && podeEditar && (
              <button
                type="button"
                className={styles.btnHeaderSecondary}
                onClick={() => setAssistente(true)}
                disabled={ocupado}
              >
                Editar tecidos
              </button>
            )}
            {rascunho && podeCriar && !jobAtivo && (
              <button
                type="button"
                className={temEncaixes ? styles.btnHeaderSecondary : styles.btnHeaderPrimario}
                onClick={() => (temEncaixes ? setConfirmar("regerar") : gerar())}
                disabled={ocupado || !oc.pode_gerar_encaixes || oc.desatualizada}
                title={
                  oc.desatualizada
                    ? "Atualize a OC do pedido antes de gerar."
                    : bloqueios.length
                      ? bloqueios.map((p) => p.mensagem).join("\n")
                      : ""
                }
              >
                {acao === "gerar"
                  ? "Iniciando…"
                  : temEncaixes
                    ? "Regerar encaixes"
                    : "Gerar encaixes"}
              </button>
            )}
            {rascunho && podeEditar && (
              <button
                type="button"
                className={temEncaixes ? styles.btnHeaderPrimario : styles.btnHeaderSecondary}
                onClick={() => setConfirmar("enviar")}
                disabled={ocupado || !temEncaixes || oc.desatualizada || oc.encaixes_desatualizados}
                title={
                  !temEncaixes
                    ? "Gere os encaixes antes de enviar."
                    : oc.desatualizada
                      ? "Atualize a OC do pedido e regere os encaixes."
                      : oc.encaixes_desatualizados
                        ? "Regere os encaixes para aplicar o novo limite."
                        : ""
                }
              >
                {acao === "enviar" ? "Enviando…" : "Enviar à produção"}
              </button>
            )}
            {enviada && podeEditar && (
              <button
                type="button"
                className={styles.btnHeaderPrimario}
                onClick={() => setIniciando(true)}
                disabled={ocupado}
              >
                Iniciar corte
              </button>
            )}
            {emCorte && podeEditar && (
              <button
                type="button"
                className={styles.btnHeaderPrimario}
                onClick={() => setConcluindo(true)}
                disabled={ocupado}
              >
                Concluir corte
              </button>
            )}
            {acoesMais.length > 0 && (
              <MenuDropdown
                className={`${styles.btnHeaderSecondary} ${styles.btnHeaderIcone}`}
                ariaLabel="Mais ações"
                title="Mais ações"
                trigger={<IconeMais />}
                items={acoesMais}
              />
            )}
          </div>
        </header>

        {/* Linha do tempo: onde a OC parou. Etapa sem data ainda não aconteceu
            (reabrir limpa a conclusão, então Concluída volta a ficar vazia). */}
        <ol className={styles.timeline}>
          {ETAPAS.map(([campo, rotulo]) => {
            const quando = oc[campo];
            return (
              <li
                key={campo}
                className={`${styles.etapa} ${quando ? styles.etapaFeita : ""}`}
                title={
                  quando ? `${rotulo} em ${dataHoraBR(quando)}` : `${rotulo}: ainda não aconteceu`
                }
              >
                <span className={styles.etapaPonto} aria-hidden="true" />
                <span className={styles.etapaRotulo}>{rotulo}</span>
                <span className={styles.etapaData}>{quando ? dataHoraBR(quando) : "—"}</span>
              </li>
            );
          })}
        </ol>

        {erro && <p className={styles.erroInline}>{erro}</p>}

        {jobAtivo && (
          <ProgressoEncaixe ocId={oc.id} onConcluido={jobConcluido} onFim={jobEncerrado} />
        )}

        {rascunho && !jobAtivo && (
          <AlertaMesaMaior
            sugestao={oc.sugestao_mesa}
            limiteAtual={oc.comprimento_max_cm}
            ocupado={ocupado || !podeCriar}
            onUsar={usarMesaMaior}
            onManter={() => executar("manter", () => descartarSugestaoMesa(oc.id))}
          />
        )}

        {oc.desatualizada && !final && (
          <div className={`${styles.avisoWarn} ${styles.avisoLinha}`}>
            <span>
              O pedido foi alterado depois desta OC.
              {!rascunho && " Só uma OC em rascunho pode ser atualizada."}
            </span>
            {rascunho && podeEditar && (
              <button
                type="button"
                className={styles.btnHeaderSecondary}
                onClick={() => executar("atualizar", () => atualizarOrdemCorteDoPedido(oc.id))}
                disabled={ocupado}
              >
                {acao === "atualizar" ? "Atualizando…" : "Atualizar do pedido"}
              </button>
            )}
          </div>
        )}

        {oc.encaixes_desatualizados && !jobAtivo && (
          <div className={`${styles.avisoWarn} ${styles.avisoLinha}`}>
            <span>Regere os encaixes para aplicar o novo limite.</span>
            {podeCriar && (
              <button
                type="button"
                className={styles.btnHeaderSecondary}
                onClick={() => setConfirmar("regerar")}
                disabled={ocupado || !oc.pode_gerar_encaixes || oc.desatualizada}
              >
                {acao === "gerar" ? "Gerando encaixes…" : "Regerar encaixes"}
              </button>
            )}
          </div>
        )}

        {rascunho && bloqueios.length > 0 && (
          <div className={`${styles.avisoWarn} ${styles.avisoLista}`}>
            <IconeAlerta />
            <div>
              <strong>Pendências para gerar os encaixes:</strong>
              <ul>
                {bloqueios.map((p, i) => (
                  <li key={i}>{p.mensagem}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* ══ CARD — Cabeçalho ══ */}
        <section className={`sc-card ${styles.card}`} aria-label="Cabeçalho da Ordem de Corte">
          <div className={styles.linhas}>
            <div className={styles.linha}>
              <div className={`${styles.field} sc-field-s`}>
                <span className={styles.rotulo}>Pedido</span>
                <div className={`${styles.input} sc-readonly ${styles.valorLink}`}>
                  <Link to={`/vendas/pedidos/${oc.pedido_id}?modo=visualizar`}>
                    {oc.pedido_numero || "—"}
                  </Link>
                </div>
              </div>
              <label className={`${styles.field} sc-field-flex`}>
                <span className={styles.rotulo}>Cliente</span>
                <input
                  className={`${styles.input} sc-readonly`}
                  readOnly
                  tabIndex={-1}
                  value={oc.cliente || "—"}
                  title={oc.cliente || ""}
                />
              </label>
              <label className={`${styles.field} sc-field-s`}>
                <span className={styles.rotulo}>Data</span>
                <input
                  className={`${styles.input} sc-readonly`}
                  readOnly
                  tabIndex={-1}
                  value={dataBR(oc.criado_em)}
                />
              </label>
              <label className={`${styles.field} sc-field-m`}>
                <span className={styles.rotulo}>Enfesto</span>
                <input
                  className={`${styles.input} sc-readonly`}
                  readOnly
                  tabIndex={-1}
                  value={enfestoLabel(oc)}
                />
              </label>
              <label
                className={`${styles.field} sc-field-s`}
                title="Limite da mesa. Riscos menores saem com o tamanho real; maiores são divididos em partes."
              >
                <span className={styles.rotulo}>Comprimento máx. (cm)</span>
                {rascunho && podeEditar ? (
                  <input
                    className={styles.input}
                    type="number"
                    inputMode="numeric"
                    min={COMP_MIN}
                    max={COMP_MAX}
                    step={1}
                    value={comp}
                    disabled={ocupado}
                    onChange={(e) => setComp(e.target.value)}
                    onBlur={salvarComp}
                    onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                  />
                ) : (
                  <input
                    className={`${styles.input} sc-readonly`}
                    readOnly
                    tabIndex={-1}
                    value={oc.comprimento_max_cm ?? COMP_PADRAO}
                  />
                )}
              </label>
            </div>

            <div className={styles.linha}>
              <label className={`${styles.field} sc-field-flex`}>
                <span className={styles.rotulo}>Observações</span>
                <textarea
                  className={`${styles.input} ${styles.textarea} ${final || !podeEditar ? "sc-readonly" : ""}`}
                  readOnly={final || !podeEditar}
                  maxLength={2000}
                  value={obs}
                  onChange={(e) => {
                    setObs(e.target.value);
                    setObsSalva(false);
                  }}
                  onBlur={salvarObs}
                  placeholder={final || !podeEditar ? "" : "Observações para o corte…"}
                />
              </label>
            </div>

            {/* Grade de 6 colunas na largura toda (3 abaixo de 900px) — sem
                .sc-field-s, cuja largura fixa deixava a linha pela metade. */}
            <div className={styles.totais}>
              {[
                ["Peças", numBR(oc.pecas_total, 0)],
                ["Enfestos", numBR(oc.enfestos, 0)],
                ["Metros", `${numBR(oc.metros_total, 2)} m`],
                ["Peso total", `${numBR(oc.peso_total_kg, 3)} kg`],
                ["Custo total", moeda(oc.custo_total), true],
                ["Sobra", `${numBR(oc.sobra_total, 0)} pç`],
              ].map(([rotulo, valor, destaque]) => (
                <label key={rotulo} className={styles.field}>
                  <span className={styles.rotulo}>{rotulo}</span>
                  <input
                    className={`${styles.input} sc-readonly ${styles.numero} ${destaque ? styles.destaque : ""}`}
                    readOnly
                    tabIndex={-1}
                    value={valor}
                  />
                </label>
              ))}
            </div>
          </div>
        </section>

        {/* ══ GRADE (cor × tamanho) ══ */}
        <section className={`sc-card ${styles.card}`} aria-label="Grade">
          <h2 className={styles.secaoTitulo}>Grade</h2>
          {grades.length === 0 ? (
            <p className={styles.vazio}>Sem itens.</p>
          ) : (
            <div className={styles.grades}>
              {grades.map((g) => {
                const totalCor = (cor) =>
                  g.tamanhos.reduce((s, t) => s + (g.qtd[`${cor}|${t}`] || 0), 0);
                const totalTam = (t) =>
                  g.cores.reduce((s, cor) => s + (g.qtd[`${cor}|${t}`] || 0), 0);
                const total = g.cores.reduce((s, cor) => s + totalCor(cor), 0);
                return (
                  <div key={g.id} className={styles.gradeBloco}>
                    <div className={styles.gradeProduto}>{g.nome}</div>
                    <div className={styles.tabelaWrap}>
                      <table className={`${styles.tabela} ${styles.tabelaGrade}`}>
                        <thead>
                          <tr>
                            <th>Cor</th>
                            {g.tamanhos.map((t) => (
                              <th key={t} className={styles.num}>
                                {t}
                              </th>
                            ))}
                            <th className={styles.num}>Total</th>
                          </tr>
                        </thead>
                        <tbody>
                          {g.cores.map((cor) => (
                            <tr key={cor}>
                              <td>{cor}</td>
                              {g.tamanhos.map((t) => (
                                <td key={t} className={styles.num}>
                                  {g.qtd[`${cor}|${t}`] || ""}
                                </td>
                              ))}
                              <td className={`${styles.num} ${styles.total}`}>{totalCor(cor)}</td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr>
                            <td>Total</td>
                            {g.tamanhos.map((t) => (
                              <td key={t} className={styles.num}>
                                {totalTam(t)}
                              </td>
                            ))}
                            <td className={styles.num}>{total}</td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* ══ TECIDOS ══ */}
        <section className={`sc-card ${styles.card}`} aria-label="Tecidos">
          <h2 className={styles.secaoTitulo}>Tecidos</h2>
          <div className={styles.tabelaWrap}>
            <table className={styles.tabela}>
              <thead>
                <tr>
                  <th>Produto</th>
                  <th>Cor</th>
                  <th>Lote</th>
                  <th>Modelo</th>
                  <th className={styles.num}>Largura (cm)</th>
                  <th className={styles.num} title="Peso físico do lote.">
                    Disponível (kg)
                  </th>
                  <th className={styles.num} title="Peso travado por outras OCs em produção.">
                    Reservado (kg)
                  </th>
                  <th
                    className={styles.num}
                    title="Disponível menos o reservado — o que dá para planejar agora."
                  >
                    Livre (kg)
                  </th>
                  <th className={styles.num}>Planejado (kg)</th>
                </tr>
              </thead>
              <tbody>
                {oc.tecidos.map((t) => {
                  const lote = t.lote;
                  const planejado = lote ? (oc.planejado_por_lote || {})[lote.id] : null;
                  const { reservado, livre } = estoqueDoLote(lote);
                  // O alerta é contra o LIVRE: o que outra OC já travou não
                  // está disponível para esta, mesmo que o lote tenha peso.
                  const falta = planejado != null && livre != null && planejado > livre;
                  return (
                    <tr key={t.id}>
                      <td>{t.produto_descricao || t.produto_codigo || "—"}</td>
                      <td>{t.cor || "—"}</td>
                      <td>
                        {lote ? lote.codigo_lote : <span className={styles.semLote}>Sem lote</span>}
                      </td>
                      <td>
                        {lote ? [lote.modelo, lote.cor_tecido].filter(Boolean).join(" — ") : "—"}
                      </td>
                      <td className={styles.num}>{lote ? numBR(lote.largura_util_cm, 1) : "—"}</td>
                      <td className={styles.num} title="Peso físico do lote.">
                        {lote ? numBR(lote.peso_disponivel_kg, 3) : "—"}
                      </td>
                      <td className={styles.num} title="Peso travado por outras OCs em produção.">
                        {lote ? numBR(reservado, 3) : "—"}
                      </td>
                      <td className={styles.num}>{lote ? numBR(livre, 3) : "—"}</td>
                      <td
                        className={`${styles.num} ${falta ? styles.alerta : ""}`}
                        title={
                          falta
                            ? `Faltam ${numBR(planejado - livre, 3)} kg livres no lote ${lote.codigo_lote} (disponível ${numBR(lote.peso_disponivel_kg, 3)} kg, reservado por outras OCs ${numBR(reservado, 3)} kg).`
                            : "Consumo planejado pelos encaixes do lote."
                        }
                      >
                        {falta && <IconeAlerta />} {planejado != null ? numBR(planejado, 3) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* ══ ENCAIXES ══ */}
        <section className={`sc-card ${styles.card}`} aria-label="Encaixes">
          <h2 className={styles.secaoTitulo}>Encaixes</h2>
          {!temEncaixes ? (
            <p className={styles.vazio}>
              {rascunho ? "Nenhum encaixe gerado ainda." : "Nenhum encaixe nesta OC."}
            </p>
          ) : (
            <>
              <DecisaoEnfesto decisoes={oc.decisao_enfesto?.lotes} />
              {/* Um bloco por enfesto: a grade por tamanho fica no resumo do
                enfesto; cada card (mesa) lista só os moldes que corta. */}
              {enfestos.map((g) => {
                const lote = oc.tecidos.find((t) => t.lote?.id === g.lote_id)?.lote;
                return (
                  <div key={g.chave}>
                    <ResumoEnfesto grupo={g} loteCodigo={lote?.codigo_lote} />
                    <div className={styles.encaixes}>
                      {g.mesas.map((e) => (
                        <article key={e.id} className={styles.encaixeCard}>
                          <div className={styles.encaixeTopo}>
                            <div className={styles.encaixeId}>
                              <strong>{fmtEnc(e.numero_enc)}</strong>
                              <span className={styles.encaixeParte}>
                                {fmtParte(e) || "mesa única"}
                              </span>
                            </div>
                            <Link className={styles.linkEncaixe} to={`/producao/encaixes/${e.id}`}>
                              Ver encaixe
                            </Link>
                          </div>
                          <dl className={styles.metricas}>
                            <div>
                              <dt title="Comprimento">COMPR.</dt>
                              <dd>{numBR(e.comp_metros, 2)} m</dd>
                            </div>
                            <div>
                              <dt title="Aproveitamento">APROV.</dt>
                              <dd>
                                {e.aproveitamento_pct != null
                                  ? `${numBR(e.aproveitamento_pct, 1)}%`
                                  : "—"}
                              </dd>
                            </div>
                            <div>
                              <dt title="Peso total">PESO</dt>
                              <dd>{numBR(e.peso_total_kg, 3)} kg</dd>
                            </div>
                            <div>
                              <dt title="Camadas">CAMADAS</dt>
                              <dd>{e.num_camadas}</dd>
                            </div>
                          </dl>
                          <MoldesMesa pecas={e.pecas_parte} />
                        </article>
                      ))}
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </section>
      </div>

      {assistente && (
        <OrdemCorteAssistente
          ocId={oc.id}
          passoInicial={2}
          onFechar={() => {
            setAssistente(false);
            carregar();
          }}
        />
      )}
      {iniciando && (
        <ModalIniciarCorte
          cortadorSugerido={oc.cortador}
          enviando={acao === "iniciar"}
          onCancelar={() => setIniciando(false)}
          onConfirmar={(cortador) => {
            setIniciando(false);
            executar("iniciar", () => iniciarOrdemCorte(oc.id, cortador));
          }}
        />
      )}

      {concluindo && (
        <ConcluirCorteModal
          oc={oc}
          enviando={acao === "concluir"}
          onCancelar={() => setConcluindo(false)}
          onConfirmar={(payload) => {
            setConcluindo(false);
            executar("concluir", () => concluirOrdemCorte(oc.id, payload));
          }}
        />
      )}
    </div>
  );
}

/**
 * "Iniciar corte" (ENVIADA → EM_CORTE). Fica nesta página em vez de virar
 * componente próprio: é um campo só, e o `Modal` compartilhado já cuida do
 * overlay (useOverlayDismiss) e do Esc.
 */
function ModalIniciarCorte({ cortadorSugerido, enviando, onCancelar, onConfirmar }) {
  const [cortador, setCortador] = useState(cortadorSugerido || "");
  return (
    <Modal titulo="Iniciar corte" onClose={onCancelar} largura="420px">
      <div className={styles.modalCorpo}>
        <label className={styles.modalCampo}>
          <span className={styles.modalRotulo}>
            Cortador <em>(opcional)</em>
          </span>
          <input
            className={`sc-input sc-upper`}
            value={cortador}
            maxLength={150}
            placeholder="Preencha se já souber quem vai cortar"
            onChange={(e) => setCortador(e.target.value.toUpperCase())}
          />
        </label>
        <p className={styles.modalNota}>
          A OC entra em EM_CORTE e os lotes ficam travados para esta ordem até a conclusão.
        </p>
        <div className={styles.modalAcoes}>
          <button
            type="button"
            className={styles.btnModalSecundario}
            onClick={onCancelar}
            disabled={enviando}
          >
            Cancelar
          </button>
          <button
            type="button"
            className={styles.btnModalPrimario}
            onClick={() => onConfirmar(cortador.trim() || null)}
            disabled={enviando}
            autoFocus
          >
            {enviando ? "Iniciando…" : "Iniciar corte"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
