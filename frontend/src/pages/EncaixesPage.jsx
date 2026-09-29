import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { deleteEncaixe, getEncaixes } from "../api/encaixes";
import ConfirmModal from "../components/ConfirmModal/ConfirmModal";
import { useAuth } from "../auth/useAuth";
import es from "./EncaixesPage.module.css";

const MODULO = "encaixes";

function formatarData(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  if (!y || !m || !d) return iso;
  return `${d}/${m}/${y}`;
}

function formatarNumeroEnc(numero_enc) {
  return numero_enc != null ? `ENC-${String(numero_enc).padStart(3, "0")}` : "ENC-—";
}

// Títulos de grupo (OC / sem OC) e links usam classes do módulo da página
// (ver .grupoTitulo / .grupoLink em EncaixesPage.module.css).

function classeAproveitamento(aprov) {
  if (aprov == null) return null;
  if (aprov >= 80) return "bom";
  if (aprov >= 65) return "medio";
  return "ruim";
}

export default function EncaixesPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const [encaixes, setEncaixes] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [excluindo, setExcluindo] = useState(null); // encaixe obj

  const [busca, setBusca] = useState("");
  const [dataDe, setDataDe] = useState("");
  const [dataAte, setDataAte] = useState("");

  useEffect(() => {
    // A listagem já traz ordem_corte e pedido de cada encaixe.
    getEncaixes()
      .then(setEncaixes)
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false));
  }, []);

  async function confirmarExclusao() {
    const enc = excluindo;
    setExcluindo(null);
    try {
      await deleteEncaixe(enc.id);
      setEncaixes((prev) => prev.filter((e) => e.id !== enc.id));
    } catch (ex) {
      setErro(ex.message);
    }
  }

  const termoBusca = busca.trim().toLowerCase();
  const filtroAtivo = !!(termoBusca || dataDe || dataAte);

  const encaixesFiltrados = encaixes
    .filter((enc) => {
      if (termoBusca) {
        const alvo = [
          enc.descricao,
          formatarNumeroEnc(enc.numero_enc),
          enc.ordem_corte?.numero_fmt,
          enc.pedido?.numero,
          enc.pedido?.cliente,
        ]
          .join(" ")
          .toLowerCase();
        if (!alvo.includes(termoBusca)) return false;
      }
      const dataEnc = (enc.criado_em ?? "").slice(0, 10);
      if (dataDe && dataEnc < dataDe) return false;
      if (dataAte && dataEnc > dataAte) return false;
      return true;
    })
    .sort((a, b) => (b.criado_em ?? "").localeCompare(a.criado_em ?? ""));

  const totalEncaixes = encaixes.length;

  // Um grupo por OC (mais recente primeiro, encaixes em ordem de número);
  // Encaixe Rápido e encaixes antigos (sem OC) num grupo próprio no fim.
  const grupos = [];
  const porOc = new Map();
  const semOc = [];
  for (const enc of encaixesFiltrados) {
    const oc = enc.ordem_corte;
    if (!oc) {
      semOc.push(enc);
      continue;
    }
    if (!porOc.has(oc.id)) {
      const g = { chave: oc.id, oc, pedido: enc.pedido, encaixes: [] };
      porOc.set(oc.id, g);
      grupos.push(g);
    }
    porOc.get(oc.id).encaixes.push(enc);
  }
  grupos.sort((a, b) => b.oc.numero - a.oc.numero);
  for (const g of grupos) g.encaixes.sort((a, b) => (a.numero_enc ?? 0) - (b.numero_enc ?? 0));
  if (semOc.length) grupos.push({ chave: "sem-oc", oc: null, encaixes: semOc });

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Encaixes</h1>
        {totalEncaixes > 0 && (
          <span className={es.countBadge}>
            {totalEncaixes} encaixe{totalEncaixes !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      <div className={es.toolbar}>
        <div className={es.searchWrap}>
          <input
            type="text"
            className={es.busca}
            placeholder="Buscar por descrição, nº ou data..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </div>
        <div className={es.filtroData}>
          <label>
            <span>De:</span>
            <input
              type="date"
              className={es.inputData}
              value={dataDe}
              onChange={(e) => setDataDe(e.target.value)}
            />
          </label>
          <label>
            <span>Até:</span>
            <input
              type="date"
              className={es.inputData}
              value={dataAte}
              onChange={(e) => setDataAte(e.target.value)}
            />
          </label>
        </div>
      </div>

      {erro && <p className={es.erro}>{erro}</p>}

      {carregando ? (
        <p className={es.loading}>Carregando encaixes…</p>
      ) : encaixesFiltrados.length === 0 ? (
        <div className={es.vazio}>
          <p>Nenhum encaixe encontrado.</p>
          {filtroAtivo && <p>Tente ajustar os filtros.</p>}
        </div>
      ) : (
        grupos.map((g) => (
          <section key={g.chave}>
            <h2 className={es.grupoTitulo}>
              {g.oc ? (
                <>
                  <Link to={`/producao/ordens-corte/${g.oc.id}`} className={es.grupoLink}>
                    {g.oc.numero_fmt}
                  </Link>
                  {g.pedido && (
                    <span className={es.grupoSuave}>
                      Pedido {g.pedido.numero}
                      {g.pedido.cliente ? ` · ${g.pedido.cliente}` : ""}
                    </span>
                  )}
                </>
              ) : (
                "Sem ordem de corte — Encaixe Rápido e anteriores"
              )}
              <span className={`${es.grupoSuave} ${es.grupoContagem}`}>
                {g.encaixes.length} encaixe{g.encaixes.length !== 1 ? "s" : ""}
              </span>
            </h2>
            {g.encaixes.map((enc) => {
              const ped = enc.pedido;
              const ehRapido = ped?.tipo === "encaixe_rapido";
              const mapa = enc.mapa_json ?? {};
              const aprov = enc.desperdicio_pct != null ? 100 - enc.desperdicio_pct : null;
              const classeAprov = classeAproveitamento(aprov);

              // Peso e custo são de TODAS as camadas (peso_total_kg /
              // custo_total_camadas vêm da API, já multiplicados por
              // num_camadas); o comprimento é de UMA camada = comprimento
              // do risco. Mesmo critério da tela do encaixe.
              const numCamadas = enc.num_camadas || 1;
              const pesoTotal = enc.peso_total_kg ?? enc.peso_kg;
              const custoTotal = enc.custo_total_camadas ?? enc.custo_total;
              const metricas = [
                enc.comp_metros != null
                  ? {
                      rotulo: "Comprimento do risco",
                      valor: `${Number(enc.comp_metros).toFixed(2)} m`,
                    }
                  : null,
                pesoTotal != null
                  ? {
                      rotulo: `Peso (${numCamadas} camada${numCamadas !== 1 ? "s" : ""})`,
                      valor: `${Number(pesoTotal).toFixed(3)} kg`,
                    }
                  : null,
                custoTotal != null
                  ? {
                      rotulo: "Custo total",
                      valor: `R$ ${Number(custoTotal).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`,
                    }
                  : null,
              ].filter(Boolean);

              return (
                <div key={enc.id} className={es.encaixeCard}>
                  <div className={es.cardHeader}>
                    <div className={es.cardHeaderLeft}>
                      <span className={es.numeroEnc}>{formatarNumeroEnc(enc.numero_enc)}</span>
                      {enc.descricao && <span className={es.descricaoEnc}>{enc.descricao}</span>}
                      <span className={es.dataEnc}>{formatarData(enc.criado_em)}</span>
                    </div>
                    {/* Coluna OC: pílula com link; sem OC, Encaixe Rápido ou "Sem OC". */}
                    {enc.ordem_corte ? (
                      <Link
                        to={`/producao/ordens-corte/${enc.ordem_corte.id}`}
                        className={`${es.pillEncaixeRapido} ${es.pillSemSublinhado}`}
                        title="Abrir a Ordem de Corte"
                      >
                        {enc.ordem_corte.numero_fmt}
                      </Link>
                    ) : ehRapido ? (
                      <span className={es.pillEncaixeRapido}>Encaixe Rápido</span>
                    ) : (
                      <span className={es.tecidoBadge}>Sem OC</span>
                    )}
                  </div>

                  <div className={es.cardBody}>
                    <div className={es.cardBodyLeft}>
                      {mapa.tecido_nome && (
                        <span className={es.tecidoBadge}>{mapa.tecido_nome}</span>
                      )}
                      {metricas.length > 0 && (
                        <div className={es.metricas}>
                          {metricas.map((m) => (
                            <span key={m.rotulo} className={es.metricaItem}>
                              <span className={es.metricaRotulo}>{m.rotulo}</span>
                              <span className={es.metricaValor}>{m.valor}</span>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className={es.cardBodyRight}>
                      {classeAprov && (
                        <span className={`${es.aprovBadge} ${es[`aprovBadge_${classeAprov}`]}`}>
                          {aprov.toFixed(1)}%
                        </span>
                      )}
                      <button
                        type="button"
                        className={es.btnPrimCompacto}
                        onClick={() => navigate(`/producao/encaixes/${enc.id}`)}
                      >
                        Ver encaixe
                      </button>
                      {ped && !ehRapido && (
                        <button
                          type="button"
                          className={es.btnSecCompacto}
                          onClick={() => navigate(`/vendas/pedidos/${ped.id}?modo=visualizar`)}
                        >
                          Ver pedido
                        </button>
                      )}
                      {hasPermission(MODULO, "excluir") && (
                        <button
                          type="button"
                          className={es.btnDeletarIcon}
                          onClick={() => setExcluindo(enc)}
                          title="Excluir encaixe"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </section>
        ))
      )}

      <ConfirmModal
        isOpen={!!excluindo}
        titulo="Excluir encaixe"
        mensagem="Tem certeza que deseja excluir este encaixe? Esta ação não pode ser desfeita."
        labelConfirmar="Excluir"
        variante="perigo"
        onConfirmar={confirmarExclusao}
        onCancelar={() => setExcluindo(null)}
      />
    </div>
  );
}
