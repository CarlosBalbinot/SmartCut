// Teste de componente crítico: a tela de login (Parte 8.1 — frontend).
// Cobre o formulário de login (validação de campos vazios, sucesso navegando
// para /, falha exibindo o erro do backend) e o modo de primeiro acesso.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import LoginPage from "../LoginPage";

const { loginMock, navigateMock } = vi.hoisted(() => ({
  loginMock: vi.fn(),
  navigateMock: vi.fn(),
}));

vi.mock("../../auth/useAuth", () => ({
  useAuth: () => ({ login: loginMock }),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
}));

function mockPrimeiroAcesso(primeiroAcesso) {
  globalThis.fetch = vi.fn().mockResolvedValue({
    json: async () => ({ primeiro_acesso: primeiroAcesso }),
  });
}

describe("LoginPage", () => {
  beforeEach(() => {
    loginMock.mockReset();
    navigateMock.mockReset();
    mockPrimeiroAcesso(false);
  });

  it("exibe o formulário de login quando não há primeiro acesso", async () => {
    render(<LoginPage />);

    expect(await screen.findByText("Faça login para continuar")).toBeInTheDocument();
    expect(screen.getByLabelText("Usuário")).toBeInTheDocument();
    expect(screen.getByLabelText("Senha")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
  });

  it("exige usuário e senha preenchidos", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    await screen.findByText("Faça login para continuar");

    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(screen.getByText("Informe usuário e senha.")).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it("login com sucesso chama login() e navega para /", async () => {
    const user = userEvent.setup();
    loginMock.mockResolvedValue(undefined);
    render(<LoginPage />);
    await screen.findByText("Faça login para continuar");

    await user.type(screen.getByLabelText("Usuário"), "admin");
    await user.type(screen.getByLabelText("Senha"), "senha@123");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    await waitFor(() => expect(loginMock).toHaveBeenCalledWith("admin", "senha@123"));
    expect(navigateMock).toHaveBeenCalledWith("/");
  });

  it("login com falha mostra o erro do backend sem navegar", async () => {
    const user = userEvent.setup();
    loginMock.mockRejectedValue(new Error("Usuário ou senha inválidos"));
    render(<LoginPage />);
    await screen.findByText("Faça login para continuar");

    await user.type(screen.getByLabelText("Usuário"), "admin");
    await user.type(screen.getByLabelText("Senha"), "errada");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("Usuário ou senha inválidos")).toBeInTheDocument();
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("primeiro acesso exibe o formulário de configuração do admin", async () => {
    mockPrimeiroAcesso(true);
    render(<LoginPage />);

    expect(
      await screen.findByText("Configure o primeiro administrador do sistema")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Criar administrador" })).toBeInTheDocument();
  });

  it("primeiro acesso valida senhas divergentes", async () => {
    const user = userEvent.setup();
    mockPrimeiroAcesso(true);
    render(<LoginPage />);
    await screen.findByText("Configure o primeiro administrador do sistema");

    await user.type(screen.getByLabelText(/^Usuário$/), "admin");
    await user.type(screen.getByLabelText(/nome completo/i), "Admin Teste");
    await user.type(screen.getByLabelText(/^Senha$/), "senha@123");
    await user.type(screen.getByLabelText(/confirmar senha/i), "outra");
    await user.click(screen.getByRole("button", { name: "Criar administrador" }));

    expect(screen.getByText("As senhas não coincidem.")).toBeInTheDocument();
  });
});
