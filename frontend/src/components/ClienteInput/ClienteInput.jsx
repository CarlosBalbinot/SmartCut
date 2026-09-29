import { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { validarCliente, buscarClientes } from "../../api/clientes";
import { useAuth } from "../../auth/useAuth";
import ClienteFormModal from "../ClienteFormModal/ClienteFormModal";
import useOverlayDismiss from "../../hooks/useOverlayDismiss";
import styles from "./ClienteInput.module.css";

// "05522680000127" → "05.522.680/0001-27"; CPF idem; outro formato fica como veio.
function formatarDocumento(doc) {
  const d = (doc || "").replace(/\D/g, "");
  if (d.length === 14) return d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
  if (d.length === 11) return d.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4");
  return doc || "";
}

// "CNPJ 05.522.680/0001-27 — GUAPORE/RS" (partes ausentes são omitidas).
function resumoCliente(c) {
  if (!c) return "";
  const d = (c.cnpj || "").replace(/\D/g, "");
  const doc = c.cnpj ? `${d.length === 11 ? "CPF" : "CNPJ"} ${formatarDocumento(c.cnpj)}` : "";
  const local = [c.cidade, c.uf].filter(Boolean).join("/");
  return [doc, local].filter(Boolean).join(" — ");
}

/**
 * Campo Cliente do pedido: [código] [razão social] [lupa].
 * Código ou CNPJ/CPF valida no blur/Enter (GET /clientes/validar). Lupa ou
 * F2 abre o modal: cliente atual no topo (com "Editar cadastro") e, abaixo,
 * busca para trocar. Só leitura: a lupa abre direto o cadastro do cliente.
 * Erro: campo vermelho claro + tooltip.
 *
 * Props:
 *   cliente       — { id, codigo, razao_social, cnpj, cidade, uf } ou null
 *   readOnly      — pedido fora de Aberto / sem permissão: não troca cliente
 *   onChange      — (cliente) => void | Promise; rejeitar mostra o erro no campo
 *   onVerCadastro — (cliente, { somenteLeitura }) => void: quem abre o cadastro
 *                   é a página (ex.: pedido ressincroniza a cópia ao salvar).
 *                   null = sem acesso ao cadastro. Omitido = o próprio campo
 *                   abre o ClienteFormModal (se o usuário pode ver cadastros).
 *
 * "+ Novo cliente" no rodapé da busca abre o cadastro vazio (com o CNPJ/CPF
 * buscado já preenchido); salvar seleciona o cliente criado.
 */
export default function ClienteInput({ cliente, readOnly = false, onChange, onVerCadastro }) {
  const codigoAtual = cliente?.codigo || "";
  // null = sem edição em andamento: o campo mostra o código do cliente atual.
  const [texto, setTexto] = useState(null);
  const [erro, setErro] = useState(null);
  const [validando, setValidando] = useState(false);
  const [modalAberto, setModalAberto] = useState(false);
  // Cadastro de cliente novo aberto pela busca: { cnpj?, cpf? } pré-preenchidos.
  const [novoCadastro, setNovoCadastro] = useState(null);
  // Cadastro do cliente atual aberto pelo próprio campo (sem onVerCadastro):
  // { id, somenteLeitura }.
  const [cadastroAtual, setCadastroAtual] = useState(null);
  const { hasPermission } = useAuth();
  const podeCriarCliente = hasPermission("cadastros_clientes", "criar");
  const podeVerCadastro =
    onVerCadastro !== undefined ? !!onVerCadastro : hasPermission("cadastros_clientes", "ver");
  const inputRef = useRef(null);

  // Cliente trocado por fora (seleção confirmada, recarga) — descarta edição.
  useEffect(() => {
    setTexto(null);
    setErro(null);
  }, [cliente?.id]);

  const aplicar = async (novo) => {
    try {
      await onChange?.(novo);
      setTexto(null);
      setErro(null);
      return true;
    } catch (e) {
      setErro(e.message || "Não foi possível alterar o cliente.");
      return false;
    }
  };

  const validar = async () => {
    if (texto === null) return true;
    const valor = texto.trim().toUpperCase();
    if (!valor || valor === codigoAtual.toUpperCase()) {
      setTexto(null);
      setErro(null);
      return true;
    }
    setValidando(true);
    let encontrado;
    try {
      encontrado = await validarCliente(valor);
    } catch (e) {
      // Não altera o pedido: o texto digitado fica, com o erro no tooltip.
      setErro(e.message || "Cliente não encontrado");
      return false;
    } finally {
      setValidando(false);
    }
    if (encontrado.id === cliente?.id) {
      setTexto(null);
      setErro(null);
      return true;
    }
    return aplicar(encontrado);
  };

  const handleKeyDown = async (e) => {
    if (readOnly || validando) return;
    if (e.key === "F2") {
      e.preventDefault();
      setModalAberto(true);
    } else if (e.key === "Enter") {
      e.preventDefault();
      await validar();
    } else if (e.key === "Escape") {
      e.preventDefault();
      setTexto(null);
      setErro(null);
    }
  };

  const handleBlur = () => {
    // Blur causado pela abertura do modal não valida o texto parcial.
    if (!readOnly && !modalAberto) validar();
  };

  const selecionarNoModal = async (novo) => {
    setModalAberto(false);
    if (novo.id !== cliente?.id) await aplicar(novo);
    inputRef.current?.focus();
  };

  // Busca → cadastro novo: fecha a busca antes (os dois modais usam o mesmo
  // nível de sobreposição).
  const abrirNovoCadastro = (buscaTexto) => {
    const digitos = (buscaTexto || "").replace(/\D/g, "");
    setModalAberto(false);
    setNovoCadastro(
      digitos.length === 14
        ? { cnpj: digitos }
        : digitos.length === 11
          ? { cpf: digitos, tipo_pessoa: "fisica" }
          : {}
    );
  };

  const novoCadastroSalvo = async (salvo) => {
    setNovoCadastro(null);
    await aplicar({
      id: salvo.id,
      codigo: salvo.codigo,
      razao_social: salvo.razao_social,
      cnpj: salvo.cnpj || salvo.cpf,
      cidade: salvo.cidade,
      uf: salvo.estado,
    });
    inputRef.current?.focus();
  };

  // "Editar cadastro" (modal) ou lupa em modo leitura.
  const abrirCadastro = (somenteLeitura) => {
    if (!cliente?.id || !podeVerCadastro) return;
    setModalAberto(false);
    if (onVerCadastro) onVerCadastro(cliente, { somenteLeitura });
    else setCadastroAtual({ id: cliente.id, somenteLeitura });
  };

  // Cadastro editado pelo próprio campo: atualiza a cópia exibida.
  const cadastroAtualSalvo = async (salvo) => {
    setCadastroAtual(null);
    await aplicar({
      id: salvo.id,
      codigo: salvo.codigo,
      razao_social: salvo.razao_social,
      cnpj: salvo.cnpj || salvo.cpf,
      cidade: salvo.cidade,
      uf: salvo.estado,
    });
  };

  const resumo = resumoCliente(cliente);
  // Tooltip da razão social: nome completo + CNPJ + cidade/UF.
  const tituloRazao = [cliente?.razao_social, resumo].filter(Boolean).join(" — ");
  const lupaVisivel = !readOnly || (cliente?.id && podeVerCadastro);

  return (
    <div className={styles.linha}>
      <div className={`${styles.campo} ${readOnly ? styles.campoLeitura : ""}`}>
        <input
          ref={inputRef}
          className={`${styles.codigo} ${erro ? styles.campoErro : ""} sc-upper`}
          value={texto ?? codigoAtual}
          readOnly={readOnly || validando}
          tabIndex={readOnly ? -1 : 0}
          title={erro || (readOnly ? "" : "Código ou CNPJ/CPF do cliente — F2 para buscar")}
          placeholder={readOnly ? "" : "CÓDIGO"}
          onChange={(e) => {
            setTexto(e.target.value.toUpperCase());
            setErro(null);
          }}
          onFocus={(e) => {
            if (texto === null) setTexto(codigoAtual);
            e.target.select();
          }}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
        />
        <input
          className={styles.razao}
          value={cliente?.razao_social || ""}
          placeholder={readOnly ? "—" : "Nenhum cliente selecionado"}
          title={tituloRazao}
          readOnly
          tabIndex={-1}
        />
        {lupaVisivel && (
          <button
            type="button"
            className={styles.lupa}
            tabIndex={-1}
            title={readOnly ? "Ver cadastro do cliente" : "Cliente atual e busca (F2)"}
            aria-label={readOnly ? "Ver cadastro do cliente" : "Buscar cliente"}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => (readOnly ? abrirCadastro(true) : setModalAberto(true))}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <circle cx="7" cy="7" r="4.5" />
              <line x1="10.5" y1="10.5" x2="14" y2="14" />
            </svg>
          </button>
        )}
      </div>

      {modalAberto && (
        <ClienteModal
          clienteAtual={cliente?.id ? cliente : null}
          onEditar={cliente?.id && podeVerCadastro ? () => abrirCadastro(false) : null}
          selecionadoId={cliente?.id}
          onSelecionar={selecionarNoModal}
          onNovo={podeCriarCliente ? abrirNovoCadastro : null}
          onFechar={() => {
            setModalAberto(false);
            inputRef.current?.focus();
          }}
        />
      )}

      {novoCadastro && (
        <ClienteFormModal
          clienteId={null}
          valoresIniciais={novoCadastro}
          onClose={() => {
            setNovoCadastro(null);
            inputRef.current?.focus();
          }}
          onSaved={novoCadastroSalvo}
        />
      )}

      {cadastroAtual && (
        <ClienteFormModal
          clienteId={cadastroAtual.id}
          somenteLeitura={cadastroAtual.somenteLeitura}
          onClose={() => setCadastroAtual(null)}
          onSaved={cadastroAtualSalvo}
        />
      )}
    </div>
  );
}

const POR_PAGINA = 50;

function ClienteModal({ clienteAtual, onEditar, selecionadoId, onSelecionar, onNovo, onFechar }) {
  const [busca, setBusca] = useState("");
  const [lista, setLista] = useState([]);
  const [temMais, setTemMais] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [ativo, setAtivo] = useState(0);
  const overlayProps = useOverlayDismiss(() => onFechar());
  const listaRef = useRef(null);
  const buscaAtual = useRef("");

  // Busca no backend (tipo cliente/ambos), 300ms após parar de digitar.
  // O campo mostra o que foi digitado; o termo vai em maiúsculo porque o
  // ilike do SQLite só ignora caixa em ASCII (acentos: "ç" ≠ "Ç").
  useEffect(() => {
    let cancelado = false;
    buscaAtual.current = busca;
    setCarregando(true);
    const t = setTimeout(() => {
      buscarClientes(busca.trim().toUpperCase(), 0, POR_PAGINA)
        .then((d) => {
          if (cancelado) return;
          const itens = d || [];
          setLista(itens);
          setTemMais(itens.length === POR_PAGINA);
          setErro(null);
          const idx = itens.findIndex((c) => c.id === selecionadoId);
          setAtivo(idx >= 0 && !busca.trim() ? idx : 0);
        })
        .catch((e) => {
          if (!cancelado) {
            setLista([]);
            setTemMais(false);
            setErro(e.message);
          }
        })
        .finally(() => {
          if (!cancelado) setCarregando(false);
        });
    }, 300);
    return () => {
      cancelado = true;
      clearTimeout(t);
    };
  }, [busca]);

  useEffect(() => {
    listaRef.current?.querySelector(`[data-idx="${ativo}"]`)?.scrollIntoView({ block: "nearest" });
  }, [ativo]);

  const carregarMais = async () => {
    const termo = buscaAtual.current;
    setCarregando(true);
    try {
      const d = (await buscarClientes(termo.trim().toUpperCase(), lista.length, POR_PAGINA)) || [];
      if (termo !== buscaAtual.current) return;
      setLista((l) => [...l, ...d]);
      setTemMais(d.length === POR_PAGINA);
    } catch (e) {
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      onFechar();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setAtivo((i) => Math.min(i + 1, lista.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAtivo((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (lista[ativo]) onSelecionar(paraLookup(lista[ativo]));
    }
  };

  return ReactDOM.createPortal(
    <div className={styles.overlay} {...overlayProps} onKeyDown={handleKeyDown}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.modalHead}>
          <h2 className={styles.modalTitle}>{clienteAtual ? "Cliente" : "Selecionar cliente"}</h2>
          <button className={styles.btnClose} onClick={onFechar} aria-label="Fechar">
            ×
          </button>
        </div>

        <div className={styles.modalScroll}>
          {/* Cliente atual no topo; a busca abaixo é para trocar de cliente. */}
          {clienteAtual && (
            <div className={styles.atual}>
              <div className={styles.atualInfo}>
                <span className={styles.atualRotulo}>Cliente atual</span>
                <span className={styles.atualNome} title={clienteAtual.razao_social}>
                  {clienteAtual.razao_social}
                </span>
                <span className={styles.atualDetalhe}>
                  {[clienteAtual.codigo, resumoCliente(clienteAtual)].filter(Boolean).join(" · ")}
                </span>
              </div>
              {onEditar && (
                <button type="button" className={styles.btnSecondary} onClick={onEditar}>
                  Editar cadastro
                </button>
              )}
            </div>
          )}

          {clienteAtual && <p className={styles.trocarRotulo}>Trocar cliente</p>}
          <input
            className={styles.busca}
            placeholder="BUSCAR POR RAZÃO SOCIAL, FANTASIA, CÓDIGO, CNPJ OU CIDADE..."
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            autoFocus
          />

          <div className={styles.lista} ref={listaRef}>
            <table className={styles.tabela}>
              <thead>
                <tr>
                  <th className={styles.colCodigo}>Código</th>
                  <th>Razão social</th>
                  <th className={styles.colDoc}>CNPJ</th>
                  <th className={styles.colCidade}>Cidade/UF</th>
                </tr>
              </thead>
              <tbody>
                {erro ? (
                  <tr>
                    <td colSpan={4} className={styles.vazio} title={erro}>
                      Não foi possível carregar os clientes.
                    </td>
                  </tr>
                ) : lista.length === 0 ? (
                  <tr>
                    <td colSpan={4} className={styles.vazio}>
                      {carregando ? "Carregando…" : "Nenhum cliente encontrado."}
                    </td>
                  </tr>
                ) : (
                  lista.map((c, idx) => {
                    const doc = formatarDocumento(c.cnpj || c.cpf);
                    const local = [c.cidade, c.estado].filter(Boolean).join("/");
                    return (
                      <tr
                        key={c.id}
                        data-idx={idx}
                        className={`${idx === ativo ? styles.linhaAtiva : ""} ${c.id === selecionadoId ? styles.linhaSelecionada : ""}`}
                        onClick={() => setAtivo(idx)}
                        onDoubleClick={() => onSelecionar(paraLookup(c))}
                      >
                        <td title={c.codigo || ""}>{c.codigo || "—"}</td>
                        <td title={c.razao_social}>{c.razao_social}</td>
                        <td title={doc}>{doc || "—"}</td>
                        <td title={local}>{local || "—"}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          <div className={styles.rodapeLista}>
            <p className={styles.dica}>
              Setas para navegar, Enter ou duplo clique para selecionar.
            </p>
            {temMais && !erro && (
              <button
                type="button"
                className={styles.btnMais}
                onClick={carregarMais}
                disabled={carregando}
              >
                {carregando ? "Carregando…" : "Carregar mais"}
              </button>
            )}
          </div>
        </div>

        <div className={styles.modalActions}>
          {onNovo && (
            <button
              type="button"
              className={styles.btnSecondary}
              style={{ marginRight: "auto" }}
              onClick={() => onNovo(busca)}
            >
              + Novo cliente
            </button>
          )}
          <button className={styles.btnSecondary} onClick={onFechar}>
            Cancelar
          </button>
          <button
            className={styles.btnPrimary}
            disabled={!lista[ativo]}
            onClick={() => lista[ativo] && onSelecionar(paraLookup(lista[ativo]))}
          >
            Selecionar
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

// Cliente completo da listagem → mesmo formato do /clientes/validar.
function paraLookup(c) {
  return {
    id: c.id,
    codigo: c.codigo,
    razao_social: c.razao_social,
    cnpj: c.cnpj || c.cpf,
    cidade: c.cidade,
    uf: c.estado,
  };
}
