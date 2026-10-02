// Tela da Ordem de Corte (F0 passo 2a): ação recusada porque outra pessoa
// mudou a OC no meio (409 OC_STATUS_MUDOU) mostra a mensagem do backend e
// recarrega a OC — sem a recarga apagar a mensagem.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import OrdemCorteDetalhePage from "../OrdemCorteDetalhePage";

const api = vi.hoisted(() => ({
  getOrdemCorte: vi.fn(),
  getLotesDisponiveis: vi.fn(),
  getJobOrdemCorte: vi.fn(),
  cancelarOrdemCorte: vi.fn(),
}));

vi.mock("../../api/ordensCorte", () => ({
  aplicarSugestaoMesa: vi.fn(),
  atualizarOrdemCorte: vi.fn(),
  atualizarOrdemCorteDoPedido: vi.fn(),
  concluirOrdemCorte: vi.fn(),
  descartarSugestaoMesa: vi.fn(),
  enviarOrdemCorte: vi.fn(),
  gerarEncaixesOrdemCorte: vi.fn(),
  iniciarOrdemCorte: vi.fn(),
  reabrirOrdemCorte: vi.fn(),
  voltarOrdemCorteParaRascunho: vi.fn(),
  ...api,
}));

vi.mock("../../api/relatorios", () => ({
  RELATORIO_FORMULARIO_CORTE: "formulario_corte",
  imprimirRelatorio: vi.fn(),
}));

vi.mock("../../auth/useAuth", () => ({
  useAuth: () => ({ hasPermission: () => true }),
}));

vi.mock("react-router-dom", () => ({
  Link: ({ children }) => <span>{children}</span>,
  useNavigate: () => vi.fn(),
  useParams: () => ({ id: "oc-1" }),
}));

// Componentes pesados (motor, assistente) não entram neste teste.
vi.mock("../../components/OrdemCorteAssistente/OrdemCorteAssistente", () => ({
  default: () => null,
}));
vi.mock("../../components/ProgressoEncaixe/ProgressoEncaixe", () => ({
  default: () => null,
  AlertaMesaMaior: () => null,
  MoldesMesa: () => null,
  ResumoEnfesto: () => null,
  RotuloMotor: () => null,
  agruparEnfestos: () => [],
}));

const MSG = "A Ordem de Corte mudou de situação (agora está CONCLUIDA). Recarregue a tela.";

function ocCom(status) {
  return {
    id: "oc-1",
    numero_fmt: "OC-0007",
    status,
    pedido_id: "pedido-1",
    pedido_numero: "000123",
    cliente: "CLIENTE LTDA",
    criado_em: "2026-10-01T12:00:00Z",
    itens: [],
    tecidos: [],
    encaixes: [],
    enfestos: [],
    pendencias: [],
    desatualizada: false,
    encaixes_desatualizados: false,
    pode_gerar_encaixes: false,
    comprimento_max_cm: 150,
    tipo_enfesto: "AUTOMATICO",
    modo_camadas: "SEM_SOBRA",
  };
}

describe("OrdemCorteDetalhePage — OC mudada por outra pessoa", () => {
  beforeEach(() => {
    Object.values(api).forEach((fn) => fn.mockReset());
    api.getLotesDisponiveis.mockResolvedValue([]);
    api.getJobOrdemCorte.mockResolvedValue(null);
    // Abre em EM_CORTE; na recarga, outra pessoa já concluiu.
    api.getOrdemCorte
      .mockResolvedValueOnce(ocCom("EM_CORTE"))
      .mockResolvedValue(ocCom("CONCLUIDA"));
    const err = Object.assign(new Error(MSG), {
      status: 409,
      codigo: "OC_STATUS_MUDOU",
      params: { status_atual: "CONCLUIDA" },
    });
    api.cancelarOrdemCorte.mockRejectedValue(err);
  });

  it("mostra a mensagem e recarrega a OC", async () => {
    const user = userEvent.setup();
    render(<OrdemCorteDetalhePage />);
    expect(await screen.findByText("Em corte")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Mais ações" }));
    await user.click(screen.getByRole("menuitem", { name: "Cancelar OC" }));
    // Confirmação (o menu já fechou: o único "Cancelar OC" é o do modal).
    expect(screen.getByText(/Cancelar OC-0007\?/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancelar OC" }));

    expect(await screen.findByText(MSG)).toBeInTheDocument();
    await waitFor(() => expect(api.getOrdemCorte).toHaveBeenCalledTimes(2));
    expect((await screen.findAllByText("Concluída")).length).toBeGreaterThan(0);
    // A recarga não apagou a mensagem.
    expect(screen.getByText(MSG)).toBeInTheDocument();
  });
});
