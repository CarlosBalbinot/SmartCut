import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  getConfigPrecificacao,
  getCustosFixos,
  updateConfigPrecificacao,
  updateCustosFixos,
} from "../api/precificacoes";
import * as configuracaoGradeApi from "../api/configuracaoGrade";
import { useAuth } from "../auth/useAuth";
import styles from "./UsuarioConfiguracoesGeraisPage.module.css";

const MODULO = "configuracoes_editar";

const GRADE_VAZIO = { mascara: "", separador: "-", tamanho_seq: 4 };
const PREVIEW_EXEMPLO = { grupo_prefixo: "LG", seq_exemplo: 21, cor_codigo: "AZU", tam_codigo: "M" };

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

  const [formGrade, setFormGrade]       = useState(GRADE_VAZIO);
  const [savingGrade, setSavingGrade]   = useState(false);
  const [erroGrade, setErroGrade]       = useState(null);
  const [sucessoGrade, setSucessoGrade] = useState(false);
  const [previewCodigo, setPreviewCodigo]   = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewTimer = useRef(null);

  useEffect(() => {
    Promise.all([
      getConfigPrecificacao(),
      getCustosFixos(),
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

    configuracaoGradeApi.obter().then((cfg) => {
      if (cfg) setFormGrade({ mascara: cfg.mascara, separador: cfg.separador, tamanho_seq: cfg.tamanho_seq });
    }).catch(() => {});
  }, []);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const setGrade = (key) => (e) => setFormGrade((f) => ({ ...f, [key]: e.target.value }));

  // ── Preview do código de produto — debounce 400ms ──────────────────────
  useEffect(() => {
    clearTimeout(previewTimer.current);
    if (!formGrade.mascara.trim()) { setPreviewCodigo(""); return; }
    previewTimer.current = setTimeout(async () => {
      setPreviewLoading(true);
      try {
        const resp = await configuracaoGradeApi.preview({
          mascara: formGrade.mascara,
          separador: formGrade.separador,
          tamanho_seq: Number(formGrade.tamanho_seq) || 4,
          ...PREVIEW_EXEMPLO,
        });
        setPreviewCodigo(resp.codigo_gerado);
      } catch {
        setPreviewCodigo("");
      } finally {
        setPreviewLoading(false);
      }
    }, 400);
    return () => clearTimeout(previewTimer.current);
  }, [formGrade.mascara, formGrade.separador, formGrade.tamanho_seq]);

  const handleSaveGrade = async () => {
    setSavingGrade(true); setErroGrade(null); setSucessoGrade(false);
    try {
      await configuracaoGradeApi.atualizar({
        mascara: formGrade.mascara,
        separador: formGrade.separador,
        tamanho_seq: Number(formGrade.tamanho_seq),
      });
      setSucessoGrade(true);
    } catch (e) {
      setErroGrade(e.message);
    } finally {
      setSavingGrade(false);
    }
  };

  const handleSave = async () => {
    setSaving(true); setErro(null); setSucesso(false);
    try {
      await Promise.all([
        updateConfigPrecificacao({
          aliquota_simples: n(form.aliquota_simples),
          custo_etiqueta:   n(form.custo_etiqueta),
        }),
        updateCustosFixos(
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
        <div className={styles.secao}>
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

        {/* GERAÇÃO DE CÓDIGO DE PRODUTO */}
        <div className={`${styles.secao} ${styles.secaoLast}`}>
          <p className={styles.secLabel}>Geração de Código de Produto</p>

          <div className={styles.grid2}>
            <label className={`${styles.field} ${styles.fieldFull}`}>
              <span>Máscara</span>
              <input className={styles.input} value={formGrade.mascara} onChange={setGrade("mascara")} />
              <span className={styles.hint}>
                Variáveis disponíveis: {"{GRUPO}"} = prefixo do grupo, {"{SEQ}"} = sequencial numérico,
                {" "}{"{COR}"} = código da cor, {"{TAM}"} = código do tamanho
              </span>
            </label>

            <label className={styles.field}>
              <span>Separador padrão</span>
              <input className={styles.input} value={formGrade.separador} maxLength={3} onChange={setGrade("separador")} />
            </label>

            <label className={styles.field}>
              <span>Dígitos do sequencial</span>
              <select
                className={styles.input}
                value={formGrade.tamanho_seq}
                onChange={(e) => setFormGrade((f) => ({ ...f, tamanho_seq: Number(e.target.value) }))}
              >
                <option value={3}>3 dígitos (001)</option>
                <option value={4}>4 dígitos (0001)</option>
                <option value={5}>5 dígitos (00001)</option>
              </select>
            </label>
          </div>

          <div className={styles.previewCard}>
            <span className={styles.previewLabel}>Exemplo de código gerado:</span>
            <span className={styles.previewCodigo}>
              {previewLoading ? "…" : previewCodigo || "—"}
            </span>
          </div>

          {erroGrade && <p className={styles.erro}>{erroGrade}</p>}
          {sucessoGrade && <p className={styles.sucesso}>Configuração de código salva.</p>}

          {podeEditar && (
            <div className={styles.actions}>
              <button className={styles.btnNovo} onClick={handleSaveGrade} disabled={savingGrade}>
                {savingGrade ? "Salvando…" : "Salvar"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
