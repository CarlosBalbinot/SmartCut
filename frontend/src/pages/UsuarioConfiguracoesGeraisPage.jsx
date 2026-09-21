import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { precificacoesApi } from "../services/api";
import { useAuth } from "../auth/useAuth";
import styles from "./UsuarioConfiguracoesGeraisPage.module.css";

const MODULO = "configuracoes_editar";

const CUSTOS_VAZIO = {
  custo_rolo_overlock: "", metros_rolo_overlock: "",
  custo_rolo_reta: "", metros_rolo_reta: "",
  custo_saquinho_lote: "", unidades_saquinho_lote: "",
  custo_caixa: "", pecas_por_caixa: "",
  distancia_costureira_km: "", num_viagens: "",
  consumo_veiculo_km_l: "", preco_combustivel: "",
};

const n = (v) => parseFloat(v) || 0;

const fmtUnit = (v) =>
  v > 0
    ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 4 }).format(v)
    : "—";

const fmtMoeda = (v) =>
  v > 0
    ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v)
    : "—";

function CustoRow({ campos, form, set, resultLabel, resultado, style }) {
  return (
    <div className={styles.custoRow} style={style}>
      {campos.map(({ label, key, step }) => (
        <label key={key} className={styles.field}>
          <span>{label}</span>
          <input type="number" step={step} min="0" className={styles.input}
            value={form[key]} onChange={set(key)} />
        </label>
      ))}
      <div className={styles.custoCalc}>
        <span>{resultLabel}</span>
        <strong>{resultado}</strong>
      </div>
    </div>
  );
}

export default function UsuarioConfiguracoesGeraisPage() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const podeEditar = hasPermission(MODULO, "ver");
  const [form, setForm]       = useState({ aliquota_simples: "", custo_etiqueta: "", ...CUSTOS_VAZIO });
  const [saving, setSaving]   = useState(false);
  const [erro, setErro]       = useState(null);
  const [sucesso, setSucesso] = useState(false);

  useEffect(() => {
    Promise.all([
      precificacoesApi.getConfig(),
      precificacoesApi.getCustos(),
    ]).then(([config, custos]) => {
      setForm((prev) => {
        const next = { ...prev };
        if (config) {
          next.aliquota_simples = config.aliquota_simples ?? "";
          next.custo_etiqueta   = config.custo_etiqueta   ?? "";
        }
        if (custos) {
          Object.keys(CUSTOS_VAZIO).forEach((k) => {
            if (custos[k] !== undefined && custos[k] !== null) next[k] = custos[k];
          });
        }
        return next;
      });
    }).catch(() => {});
  }, []);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const handleSave = async () => {
    setSaving(true); setErro(null); setSucesso(false);
    try {
      await Promise.all([
        precificacoesApi.updateConfig({
          aliquota_simples: n(form.aliquota_simples),
          custo_etiqueta:   n(form.custo_etiqueta),
        }),
        precificacoesApi.updateCustos(
          Object.fromEntries(Object.keys(CUSTOS_VAZIO).map((k) => [k, n(form[k])]))
        ),
      ]);
      setSucesso(true);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSaving(false);
    }
  };

  const custoOverlock  = n(form.metros_rolo_overlock)        ? n(form.custo_rolo_overlock) / n(form.metros_rolo_overlock)        : 0;
  const custoLinhaReta = n(form.metros_rolo_reta)            ? n(form.custo_rolo_reta)     / n(form.metros_rolo_reta)            : 0;
  const custoSaquinho  = n(form.unidades_saquinho_lote)      ? n(form.custo_saquinho_lote) / n(form.unidades_saquinho_lote)      : 0;
  const custoCaixa     = n(form.pecas_por_caixa)             ? n(form.custo_caixa)         / n(form.pecas_por_caixa)             : 0;
  const custoGasolina  = n(form.distancia_costureira_km) > 0 && n(form.consumo_veiculo_km_l) > 0
    ? (n(form.distancia_costureira_km) / n(form.consumo_veiculo_km_l)) *
      n(form.preco_combustivel) * n(form.num_viagens)
    : 0;

  return (
    <div className={styles.page}>
      <button className={styles.btnBack} onClick={() => navigate("/usuario/configuracoes")}>
        Voltar
      </button>

      <h1 className={styles.title}>Configurações Gerais</h1>

      <div className={styles.card}>

        {/* IMPOSTOS */}
        <div className={styles.secao}>
          <p className={styles.secLabel}>Impostos</p>
          <div className={styles.grid2}>
            <label className={styles.field}>
              <span>Alíquota Simples Nacional (%)</span>
              <input type="number" step="0.01" min="0" max="100"
                className={styles.input} value={form.aliquota_simples} onChange={set("aliquota_simples")} />
            </label>
          </div>
        </div>

        {/* INSUMOS */}
        <div className={styles.secao}>
          <p className={styles.secLabel}>Insumos</p>
          <div className={styles.custoRow} style={{ marginBottom: "1rem" }}>
            <label className={styles.field} style={{ flex: 1 }}>
              <span>Etiqueta (R$)</span>
              <input type="number" step="0.01" min="0"
                className={styles.input} value={form.custo_etiqueta} onChange={set("custo_etiqueta")} />
            </label>
          </div>
          <CustoRow
            campos={[
              { label: "Saquinho — preço do pacote (R$)", key: "custo_saquinho_lote",    step: "0.01" },
              { label: "Unidades por pacote",             key: "unidades_saquinho_lote", step: "1"    },
            ]}
            form={form} set={set} resultLabel="R$/unidade" resultado={fmtUnit(custoSaquinho)}
            style={{ marginBottom: "1rem" }}
          />
          <CustoRow
            campos={[
              { label: "Caixa — custo (R$)", key: "custo_caixa",    step: "0.01" },
              { label: "Peças por caixa",    key: "pecas_por_caixa", step: "1"    },
            ]}
            form={form} set={set} resultLabel="R$/peça" resultado={fmtUnit(custoCaixa)}
          />
        </div>

        {/* LOGÍSTICA */}
        <div className={`${styles.secao} ${styles.secaoLast}`}>
          <p className={styles.secLabel}>Logística</p>
          <CustoRow
            campos={[
              { label: "Linha overlock — custo do rolo (R$)", key: "custo_rolo_overlock",  step: "0.01" },
              { label: "Metros por rolo",                     key: "metros_rolo_overlock", step: "1"    },
            ]}
            form={form} set={set} resultLabel="R$/metro" resultado={fmtUnit(custoOverlock)}
            style={{ marginBottom: "1rem" }}
          />
          <CustoRow
            campos={[
              { label: "Linha reta — custo do rolo (R$)", key: "custo_rolo_reta",  step: "0.01" },
              { label: "Metros por rolo",                 key: "metros_rolo_reta", step: "1"    },
            ]}
            form={form} set={set} resultLabel="R$/metro" resultado={fmtUnit(custoLinhaReta)}
            style={{ marginBottom: "1rem" }}
          />

          <p className={styles.custoSubtitulo}>Gasolina</p>
          <div className={styles.gasGrid}>
            {[
              { label: "Distância (km)",           key: "distancia_costureira_km", step: "0.1"  },
              { label: "Nº de viagens",            key: "num_viagens",             step: "1"    },
              { label: "Consumo (km/l)",           key: "consumo_veiculo_km_l",    step: "0.1"  },
              { label: "Preço combustível (R$/l)", key: "preco_combustivel",       step: "0.01" },
            ].map(({ label, key, step }) => (
              <label key={key} className={styles.field}>
                <span>{label}</span>
                <input type="number" step={step} min="0" className={styles.input}
                  value={form[key]} onChange={set(key)} />
              </label>
            ))}
          </div>
          <div className={styles.gasTotal}>
            <span>Custo total estimado</span>
            <strong>{fmtMoeda(custoGasolina)}</strong>
          </div>
        </div>

        {erro && <p className={styles.erro}>{erro}</p>}
        {sucesso && <p className={styles.sucesso}>Configurações salvas.</p>}

        {podeEditar && (
          <div className={styles.actions}>
            <button className={styles.btnNovo} onClick={handleSave} disabled={saving}>
              {saving ? "Salvando…" : "Salvar"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
