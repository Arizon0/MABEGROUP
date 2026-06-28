import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { EstoquePage } from "./EstoquePage";

vi.mock("../api/client", () => ({
  api: {
    listarSaldos: vi.fn(),
    relatorioEstoque: vi.fn(),
  },
}));

const mockApi = vi.mocked(api);

describe("EstoquePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.listarSaldos.mockResolvedValue([
      {
        produto_id: 1,
        sku_base: "5338",
        nome_produto: "Retentor",
        local_id: 2,
        local_nome: "ML Fulfillment",
        qtd_disponivel: "17.000",
        qtd_reservada: "0.000",
        custo_medio: "5.0000",
        valor_total: "85.00",
      },
    ]);
    mockApi.relatorioEstoque.mockResolvedValue({
      valor_total_estoque: "85.00",
      total_alertas: 1,
      alertas: [
        {
          produto_id: 1,
          sku_base: "5338",
          nome: "Retentor",
          disponivel_total: "8",
          estoque_minimo: "10",
        },
      ],
      ranking_skus: [{ sku_base: "5338", unidades: "53", liquido: "4794.58" }],
    });
  });

  it("mostra saldos, valor total e alertas", async () => {
    render(<EstoquePage />);
    expect(await screen.findByText("ML Fulfillment")).toBeInTheDocument();
    // valor total no card e na linha
    expect(screen.getAllByText(/85\.00/).length).toBeGreaterThanOrEqual(1);
    // alerta abaixo do mínimo
    expect(
      screen.getByText("Produtos abaixo do estoque mínimo"),
    ).toBeInTheDocument();
    expect(screen.getByText(/8 \/ mín 10/)).toBeInTheDocument();
  });
});
