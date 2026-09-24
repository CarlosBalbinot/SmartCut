import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getPedidosVenda } from "../api/pedidos";
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

function classeAproveitamento(aprov) {
  if (aprov == null) return null;
  if (aprov >= 80) return "bom";
  if (aprov >= 65) return "medio";
  return "ruim";
}

export default function EncaixesPage() {
  const { hasPermission } = useAuth();
  const navigate = useNavigate();
  const [pedidos, setPedidos] = useState([]);
  const [encaixes, setEncaixes] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [excluindo, setExcluindo] = useState(null); // encaixe obj

  const [busca, setBusca] = useState("");
  const [dataDe, setDataDe] = useState("");
  const [dataAte, setDataAte] = useState("");

  useEffect(() => {
    Promise.all([getPedidosVenda(), getEncaixes()])
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
      await deleteEncaixe(enc.id);
      setEncaixes((prev) => prev.filter((e) => e.id !== enc.id));
    } catch (ex) {
      setErro(ex.message);
    }
  }

  // pedido.numero/cliente_razao_social/data_emissao/tipo são os campos
  // reais de PedidoVendaOut — não num_pedido/cliente/data_pedido.
  const pedidoMap = Object.fromEntries(pedidos.map((p) => [p.id, p]));

  const termoBusca = busca.trim().toLowerCase();
  const filtroAtivo = !!(termoBusca || dataDe || dataAte);

  const encaixesFiltrados = encaixes
    .filter((enc) => {
      if (termoBusca) {
        const descricao = (enc.descricao ?? "").toLowerCase();
        const numeroFmt = formatarNumeroEnc(enc.numero_enc).toLowerCase();
        if (!descricao.includes(termoBusca) && !numeroFmt.includes(termoBusca)) {
          return false;
        }
      }
      const dataEnc = (enc.criado_em ?? "").slice(0, 10);
      if (dataDe && dataEnc < dataDe) return false;
      if (dataAte && dataEnc > dataAte) return false;
      return true;
    })
    .sort((a, b) => (b.criado_em ?? "").localeCompare(a.criado_em ?? ""));

  const totalEncaixes = encaixes.length;

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
        encaixesFiltrados.map((enc) => {
          const ped = pedidoMap[enc.pedido_id];
          const ehRapido = ped?.tipo === "encaixe_rapido";
          const mapa = enc.mapa_json ?? {};
          const aprov = enc.desperdicio_pct != null ? 100 - enc.desperdicio_pct : null;
          const classeAprov = classeAproveitamento(aprov);

          const metricas = [
            enc.comp_metros != null ? `${Number(enc.comp_metros).toFixed(2)} m` : null,
            enc.peso_kg != null ? `${Number(enc.peso_kg).toFixed(3)} kg` : null,
            enc.custo_total != null
              ? `R$ ${Number(enc.custo_total).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
              : null,
            enc.num_camadas != null
              ? `${enc.num_camadas} camada${enc.num_camadas !== 1 ? "s" : ""}`
              : null,
          ]
            .filter(Boolean)
            .join(" · ");

          return (
            <div key={enc.id} className={es.encaixeCard}>
              <div className={es.cardHeader}>
                <div className={es.cardHeaderLeft}>
                  <span className={es.numeroEnc}>{formatarNumeroEnc(enc.numero_enc)}</span>
                  {enc.descricao && (
                    <span className={es.descricaoEnc}>{enc.descricao}</span>
                  )}
                  <span className={es.dataEnc}>{formatarData(enc.criado_em)}</span>
                </div>
                {ehRapido && (
                  <span className={es.pillEncaixeRapido}>Encaixe Rápido</span>
                )}
              </div>

              <div className={es.cardBody}>
                <div className={es.cardBodyLeft}>
                  {mapa.tecido_nome && (
                    <span className={es.tecidoBadge}>{mapa.tecido_nome}</span>
                  )}
                  {metricas && <div className={es.metricas}>{metricas}</div>}
                </div>

                <div className={es.cardBodyRight}>
                  {classeAprov && (
                    <span
                      className={`${es.aprovBadge} ${es[`aprovBadge_${classeAprov}`]}`}
                    >
                      {aprov.toFixed(1)}%
                    </span>
                  )}
                  <button
                    type="button"
                    className={es.btnPrimCompacto}
                    onClick={() => navigate(`/producao/encaixes/${enc.pedido_id}`)}
                  >
                    Ver encaixe
                  </button>
                  {!ehRapido && (
                    <button
                      type="button"
                      className={es.btnSecCompacto}
                      onClick={() => navigate(`/vendas/pedidos/${enc.pedido_id}`)}
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
        })
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
