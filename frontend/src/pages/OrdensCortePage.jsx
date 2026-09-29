import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listarOrdensCorte } from "../api/ordensCorte";
import styles from "./OrdensCortePage.module.css";

// Rótulo e classe da pílula de status (mesmas cores no detalhe da OC).
const STATUS_OC = {
  RASCUNHO: { label: "Rascunho", cls: "stRascunho" },
  ENVIADA: { label: "Enviada", cls: "stEnviada" },
  EM_CORTE: { label: "Em corte", cls: "stEmCorte" },
  CONCLUIDA: { label: "Concluída", cls: "stConcluida" },
  CANCELADA: { label: "Cancelada", cls: "stCancelada" },
};

const FINAIS = ["CONCLUIDA", "CANCELADA"];

const STATUS_FILTRO_OPCOES = [
  { value: "", label: "Todos" },
  ...Object.entries(STATUS_OC).map(([value, { label }]) => ({ value, label })),
];

// "000001" → "1" (mesma exibição da lista de pedidos).
const formatarNumeroPedido = (numero) => {
  const s = String(numero ?? "").trim();
  return /^\d+$/.test(s) ? String(Number(s)) : s;
};

const dataBR = (iso) => (iso ? new Date(iso).toLocaleDateString("pt-BR") : "");

const numBR = (v, casas) =>
  Number(v || 0).toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });

export default function OrdensCortePage() {
  const navigate = useNavigate();
  const [ordens, setOrdens] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [busca, setBusca] = useState("");
  const [statusFiltro, setStatusFiltro] = useState("");

  useEffect(() => {
    listarOrdensCorte()
      .then((d) => setOrdens(d || []))
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false));
  }, []);

  const filtradas = ordens.filter((oc) => {
    if (statusFiltro && oc.status !== statusFiltro) return false;
    const q = busca.trim().toLowerCase();
    if (!q) return true;
    const alvo = [
      oc.numero_fmt,
      oc.numero,
      oc.pedido_numero,
      formatarNumeroPedido(oc.pedido_numero),
      oc.cliente,
    ]
      .join(" ")
      .toLowerCase();
    return alvo.includes(q);
  });

  const abrir = (oc) => navigate(`/producao/ordens-corte/${oc.id}`);

  return (
    <div className="sc-page">
      <div className="sc-page-header">
        <h1>Ordens de Corte</h1>
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <input
            className={styles.busca}
            placeholder="Buscar por OC, pedido ou cliente…"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
        </div>
        <select
          className={styles.statusFiltro}
          value={statusFiltro}
          onChange={(e) => setStatusFiltro(e.target.value)}
        >
          {STATUS_FILTRO_OPCOES.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {erro && <p className={styles.erro}>{erro}</p>}

      <div className={`sc-card ${styles.tableCard}`}>
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Nº</th>
                <th>Pedido</th>
                <th>Cliente</th>
                <th>Data</th>
                <th>Peças</th>
                <th>Metros</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map((oc) => {
                const st = STATUS_OC[oc.status];
                return (
                  <tr key={oc.id} className={styles.linha} onDoubleClick={() => abrir(oc)}>
                    <td className={styles.num}>{oc.numero_fmt}</td>
                    <td title={oc.pedido_numero || ""}>
                      {formatarNumeroPedido(oc.pedido_numero) || "—"}
                    </td>
                    <td title={oc.cliente || ""}>{oc.cliente || "—"}</td>
                    <td>{dataBR(oc.criado_em) || "—"}</td>
                    <td className={styles.valor}>{numBR(oc.pecas_total, 0)}</td>
                    <td className={styles.valor}>{numBR(oc.metros_total, 2)}</td>
                    <td>
                      <div className={styles.pilulas}>
                        <span className={`${styles.badge} ${styles[st?.cls] || ""}`}>
                          {st?.label || oc.status}
                        </span>
                        {oc.desatualizada && !FINAIS.includes(oc.status) && (
                          <span
                            className={`${styles.badge} ${styles.stDesatualizada}`}
                            title="O pedido foi alterado depois desta OC."
                          >
                            Desatualizada
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
              {!carregando && filtradas.length === 0 && (
                <tr>
                  <td colSpan={7} className={styles.empty}>
                    {ordens.length === 0
                      ? "Nenhuma ordem de corte gerada. Gere a partir de um pedido de venda."
                      : "Nenhuma ordem de corte encontrada para o filtro atual."}
                  </td>
                </tr>
              )}
              {carregando && (
                <tr>
                  <td colSpan={7} className={styles.empty}>
                    Carregando…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
