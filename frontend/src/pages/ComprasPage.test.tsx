import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { ComprasPage } from "./ComprasPage";

vi.mock("../api/client", () => ({
  api: {
    listarCompras: vi.fn(),
    sugestaoCompra: vi.fn(),
    listarFornecedores: vi.fn(),
    listarProdutosCadastro: vi.fn(),
    aprovarCompra: vi.fn(),
    receberCompra: vi.fn(),
    criarCompra: vi.fn(),
  },
}));

const mockApi = vi.mocked(api);

describe("ComprasPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.listarFornecedores.mockResolvedValue([]);
    mockApi.listarProdutosCadastro.mockResolvedValue([]);
    mockApi.sugestaoCompra.mockResolvedValue([
      {
        produto_id: 1,
        sku_base: "5338",
        nome: "Retentor",
        media_mensal: "5",
        estoque_minimo: "10",
        qtd_pendente: "0",
        qtd_atual: "0",
        qtd_sugerida: "15",
        repor: true,
      },
    ]);
    mockApi.listarCompras.mockResolvedValue([
      {
        id: 7,
        fornecedor_id: 1,
        status: "rascunho",
        total: "100.00",
        itens: [
          { id: 1, produto_id: 1, qtd: "10", custo_unitario: "5.00", subtotal: "50.00" },
        ],
      },
    ]);
  });

  it("mostra sugestão (repor em destaque) e pedidos", async () => {
    render(<ComprasPage />);
    expect(await screen.findByText("5338")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument(); // qtd sugerida
    expect(screen.getByText("#7")).toBeInTheDocument();
    expect(screen.getByText("rascunho")).toBeInTheDocument();
  });

  it("aprova um pedido em rascunho", async () => {
    const user = userEvent.setup();
    mockApi.aprovarCompra.mockResolvedValue({} as never);
    render(<ComprasPage />);
    await screen.findByText("#7");

    await user.click(screen.getByRole("button", { name: "Aprovar" }));
    await waitFor(() => {
      expect(mockApi.aprovarCompra).toHaveBeenCalledWith(7);
    });
  });
});
