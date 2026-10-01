// Testes da camada de API compartilhada (Parte 8.1 — frontend).
// Cobre apiFetch (token, 401 → limpar sessão + redirect) e mensagemErro
// (detail do backend, lista de validação, 5xx e mensagens com cara de erro
// técnico nunca sobem cruas para a tela).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch, erroDaResposta, mensagemErro } from "../api";

const { obter, limpar } = vi.hoisted(() => ({
  obter: vi.fn(),
  limpar: vi.fn(),
}));

vi.mock("../tokenStore", () => ({
  tokenStore: { obter, salvar: vi.fn(), limpar },
}));

describe("apiFetch", () => {
  beforeEach(() => {
    obter.mockReset();
    limpar.mockReset();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("injeta o Bearer token quando existe", async () => {
    obter.mockResolvedValue("token-x");
    globalThis.fetch.mockResolvedValue({ status: 200, ok: true });

    await apiFetch("/api/v1/pedidos", { method: "GET" });

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/pedidos",
      expect.objectContaining({
        method: "GET",
        headers: { Authorization: "Bearer token-x" },
      })
    );
  });

  it("não injeta header de autorização sem token", async () => {
    obter.mockResolvedValue(null);
    globalThis.fetch.mockResolvedValue({ status: 200, ok: true });

    await apiFetch("/api/v1/pedidos");

    const [, options] = fetch.mock.calls[0];
    expect(options.headers).toEqual({});
    expect(options.headers.Authorization).toBeUndefined();
  });

  it("usa credentials include por padrão (cookie HttpOnly)", async () => {
    obter.mockResolvedValue(null);
    globalThis.fetch.mockResolvedValue({ status: 200, ok: true });

    await apiFetch("/api/v1/me");

    const [, options] = fetch.mock.calls[0];
    expect(options.credentials).toBe("include");
  });

  it("401 limpa o token e redireciona para /login", async () => {
    obter.mockResolvedValue("token-antigo");
    globalThis.fetch.mockResolvedValue({ status: 401, ok: false });

    await apiFetch("/api/v1/segredo");

    expect(limpar).toHaveBeenCalledWith("admin");
    expect(window.location.hash).toBe("#/login");
  });

  it("retorna a resposta para o chamador", async () => {
    obter.mockResolvedValue(null);
    const resposta = { status: 200, ok: true, json: async () => ({}) };
    globalThis.fetch.mockResolvedValue(resposta);

    const retorno = await apiFetch("/api/v1/ping");
    expect(retorno).toBe(resposta);
  });
});

describe("mensagemErro", () => {
  it("passa o detail/error em português do backend diretamente", () => {
    expect(mensagemErro({ detail: "Pedido não encontrado" }, 404)).toBe("Pedido não encontrado");
    expect(mensagemErro({ error: "Não foi possível concluir" }, 400)).toBe(
      "Não foi possível concluir"
    );
  });

  it("respostas 5xx sempre viram mensagem genérica", () => {
    expect(mensagemErro({ detail: "Internal Server Error" }, 500)).toBe(
      "Não foi possível concluir a operação. Tente novamente."
    );
    expect(mensagemErro({ detail: "boom" }, 503)).toMatch(/Tente novamente/);
  });

  it("lista de validação do pydantic vira mensagem genérica", () => {
    const detalhe = [{ loc: ["body", "serie"], msg: "field required" }];
    expect(mensagemErro({ detail: detalhe }, 422)).toBe("Dados inválidos. Verifique os campos.");
  });

  it("mensagem ausente ou vazia usa fallback com o status", () => {
    expect(mensagemErro({}, 403)).toBe("Não foi possível concluir a operação (erro 403).");
    expect(mensagemErro({ detail: "   " }, 400)).toBe(
      "Não foi possível concluir a operação (erro 400)."
    );
  });

  it("mensagem com cara de erro técnico (SQL) nunca sobe crua", () => {
    const tecnico = "sqlalchemy.exc.OperationalError: no such table: tecidos";
    expect(mensagemErro({ detail: tecnico }, 400)).toBe(
      "Não foi possível concluir a operação. Verifique os dados e tente novamente."
    );
  });
});

describe("formato de erro {codigo, params, mensagem} (F0 passo 5a)", () => {
  const corpo = (codigo, mensagem, params = {}) => ({
    data: null,
    error: { codigo, params, mensagem },
    detail: mensagem,
  });

  it("mensagemErro usa a mensagem do erro estruturado", () => {
    expect(mensagemErro(corpo("ERRO", "Pedido não encontrado"), 404)).toBe("Pedido não encontrado");
  });

  it("5xx com mensagem de regra passa; erro interno vira genérica", () => {
    expect(mensagemErro(corpo("ERRO", "Motor de encaixe não instalado."), 500)).toBe(
      "Motor de encaixe não instalado."
    );
    expect(mensagemErro(corpo("ERRO_INTERNO", "Erro interno"), 500)).toBe(
      "Não foi possível concluir a operação. Tente novamente."
    );
  });

  it("validação usa a mensagem do backend, não a lista do pydantic", () => {
    const json = {
      ...corpo("DADOS_INVALIDOS", "Dados inválidos. Verifique os campos.", { campos: ["qtd"] }),
      detail: [{ loc: ["body", "qtd"], msg: "Input should be a valid integer" }],
    };
    expect(mensagemErro(json, 422)).toBe("Dados inválidos. Verifique os campos.");
  });

  it("erroDaResposta preenche status, codigo, params e a mensagem", () => {
    const err = erroDaResposta(
      { status: 409 },
      corpo("OC_STATUS_MUDOU", "A OC mudou de status.", { status_atual: "ENVIADA" })
    );
    expect(err).toBeInstanceOf(Error);
    expect(err.message).toBe("A OC mudou de status.");
    expect(err.status).toBe(409);
    expect(err.codigo).toBe("OC_STATUS_MUDOU");
    expect(err.params).toEqual({ status_atual: "ENVIADA" });
  });

  it("erroDaResposta aceita o formato antigo e corpo vazio", () => {
    const antigo = erroDaResposta({ status: 400 }, { detail: "Status inválido" });
    expect(antigo.message).toBe("Status inválido");
    expect(antigo.codigo).toBeNull();
    expect(antigo.params).toEqual({});

    const vazio = erroDaResposta({ status: 502 }, {});
    expect(vazio.message).toBe("Não foi possível concluir a operação. Tente novamente.");
    expect(vazio.status).toBe(502);
  });

  it("erroDaResposta nunca sobe erro técnico cru", () => {
    const err = erroDaResposta({ status: 400 }, corpo("ERRO", "sqlite3.IntegrityError: UNIQUE"));
    expect(err.message).toBe(
      "Não foi possível concluir a operação. Verifique os dados e tente novamente."
    );
  });
});
