import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { Dre } from "../types/dre";
import { DrePage } from "./DrePage";

vi.mock("../api/client", () => ({
  api: {
    getDre: vi.fn(),
    getCompetencias: vi.fn(),
    salvarDespesaDre: vi.fn(),
    urlExportDre: vi.fn(() => "#"),
  },
}));

const mockApi = vi.mocked(api);

const DRE: Dre = {
  competencia: { ano: 2026, mes: 1 },
  marketplace: "todos",
  unidades: "15",
  receitas: {
    mercado_livre: "1000.00",
    shopee: "250.00",
    receita_bruta: "1250.00",
    deducoes: { itens: { Cancelamentos: "0.00", Devoluções: "0.00", Reembolsos: "0.00" }, total: "0.00" },
    receita_liquida: "1250.00",
  },
  cmv: "700.00",
  lucro_bruto: "550.00",
  despesas_operacionais: {
    mercado_livre: { itens: { Comissão: "0.00" }, total: "0.00" },
    shopee: { itens: { Comissão: "0.00" }, total: "0.00" },
    total: "0.00",
  },
  lucro_operacional: "550.00",
  despesas_gerais: { itens: { Salários: "0.00" }, total: "0.00" },
  lucro_liquido: "550.00",
  ebitda: "550.00",
  margens: { bruta: "44.00", operacional: "44.00", liquida: "44.00" },
};

describe("DrePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.getDre.mockResolvedValue(DRE);
    mockApi.getCompetencias.mockResolvedValue([{ ano: 2026, mes: 1 }]);
    mockApi.salvarDespesaDre.mockResolvedValue({
      ano: 2026, mes: 1, grupo: "geral", categoria: "Salários", valor: "80",
    });
  });

  it("mostra receitas, CMV, lucro e margens", async () => {
    render(<DrePage />);
    expect((await screen.findAllByText(/1\.250,00/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/700,00/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/44%/).length).toBeGreaterThan(0);
  });

  it("salva uma despesa ao editar e sair do campo", async () => {
    render(<DrePage />);
    await screen.findAllByText(/1\.250,00/);

    const inputs = screen.getAllByRole("spinbutton");
    const salario = inputs[inputs.length - 1];
    await userEvent.clear(salario);
    await userEvent.type(salario, "80");
    salario.blur();

    await waitFor(() =>
      expect(mockApi.salvarDespesaDre).toHaveBeenCalledWith(
        expect.objectContaining({ grupo: "geral", categoria: "Salários", valor: "80" }),
      ),
    );
  });
});
