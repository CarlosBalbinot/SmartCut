import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { encaixesApi, pedidosApi } from "../services/api";
import ConfirmModal from "../components/ConfirmModal/ConfirmModal";
import styles from "./Page.module.css";
import es from "./EncaixesPage.module.css";

function badgeAproveitamento(desperdicio_pct) {
  const aprov = 100 - (desperdicio_pct ?? 0);
  if (aprov >= 80) return { label: `${aprov.toFixed(1)}%`, classe: "bom" };
  if (aprov >= 60) return { label: `${aprov.toFixed(1)}%`, classe: "medio" };
  return { label: `${aprov.toFixed(1)}%`, classe: "ruim" };
}

export default function EncaixesPage() {
  const navigate = useNavigate();
  const [pedidos, setPedidos] = useState([]);
  const [encaixes, setEncaixes] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [excluindo, setExcluindo] = useState(null); // encaixe obj

  useEffect(() => {
    Promise.all([pedidosApi.listar(), encaixesApi.listar()])
      .then(([peds, encs]) => {
        setPedidos(peds);
        setEncaixes(encs);
      })
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false));
  }, []);

  async function confirmarExclusao() {
    const enc = excluindo;
    setExcluindo(null);
    try {
      await encaixesApi.deletar(enc.id);
      setEncaixes((prev) => prev.filter((e) => e.id !== enc.id));
    } catch (ex) {
      setErro(ex.message);
    }
  }

  // Group encaixes by pedido_id
  const pedidoMap = Object.fromEntries(pedidos.map((p) => [p.id, p]));
  const grupos = {};
  for (const enc of encaixes) {
    const pid = enc.pedido_id;
    if (!grupos[pid]) grupos[pid] = [];
    grupos[pid].push(enc);
  }

  // Order: pedidos that have encaixes, most recent first
  const pedidosComEncaixe = Object.keys(grupos)
    .map((pid) => pedidoMap[pid] ?? { id: pid, num_pedido: pid.slice(0, 8) })
    .sort((a, b) => (b.data_pedido ?? "").localeCompare(a.data_pedido ?? ""));

  const totalEncaixes = encaixes.length;

  return (
    <div>
      <div className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>Encaixes</h1>
        {totalEncaixes > 0 && (
          <span className={es.countBadge}>{totalEncaixes} encaixe{totalEncaixes !== 1 ? "s" : ""}</span>
        )}
      </div>

      {erro && <p className={styles.erro}>{erro}</p>}

      {carregando && (
        <p className={es.loading}>Carregando encaixes…</p>
      )}

      {!carregando && pedidosComEncaixe.length === 0 && (
        <p className={styles.vazio}>Nenhum encaixe gerado ainda.</p>
      )}

      {pedidosComEncaixe.map((ped) => {
        const encsDoGrupo = grupos[ped.id] ?? [];
        return (
          <section key={ped.id} className={es.grupo}>
            {/* Header do pedido */}
            <div className={es.grupoHeader}>
              <div className={es.grupoInfo}>
                <span className={es.numPedido}>{ped.num_pedido}</span>
                {ped.cliente && (
                  <span className={es.cliente}>{ped.cliente}</span>
                )}
                {ped.data_pedido && (
                  <span className={es.dataPedido}>{ped.data_pedido}</span>
                )}
              </div>
              <button
                className={es.btnVerPedido}
                onClick={() => navigate(`/pedidos/${ped.id}`)}
              >
                Ver pedido →
              </button>
            </div>

            {/* Encaixes do pedido */}
            <div className={es.encaixesList}>
              {encsDoGrupo.map((enc) => {
                const mapa = enc.mapa_json ?? {};
                const badge = badgeAproveitamento(enc.desperdicio_pct);
                return (
                  <div key={enc.id} className={es.encaixeCard}>
                    <div className={es.cardLeft}>
                      {mapa.tecido_nome && (
                        <span className={es.tecidoBadge}>{mapa.tecido_nome}</span>
                      )}
                      <div className={es.cardMeta}>
                        {enc.comp_metros != null && (
                          <span>{Number(enc.comp_metros).toFixed(2)} m</span>
                        )}
                        {enc.peso_kg != null && (
                          <span>{Number(enc.peso_kg).toFixed(3)} kg</span>
                        )}
                        {enc.custo_total != null && (
                          <span>
                            R${" "}
                            {Number(enc.custo_total).toLocaleString("pt-BR", {
                              minimumFractionDigits: 2,
                            })}
                          </span>
                        )}
                        {enc.num_camadas != null && (
                          <span>{enc.num_camadas} camada{enc.num_camadas !== 1 ? "s" : ""}</span>
                        )}
                      </div>
                    </div>

                    <div className={es.cardRight}>
                      {enc.desperdicio_pct != null && (
                        <span className={`${es.aprovBadge} ${es[`aprovBadge_${badge.classe}`]}`}>
                          {badge.label} aproveitamento
                        </span>
                      )}
                      <button
                        className={es.btnVer}
                        onClick={() => navigate(`/encaixes/${ped.id}`)}
                      >
                        Ver encaixe
                      </button>
                      <button
                        className={es.btnDeletar}
                        onClick={() => setExcluindo(enc)}
                        title="Excluir encaixe"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}

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
