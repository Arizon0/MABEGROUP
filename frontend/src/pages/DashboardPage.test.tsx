import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { DashboardPage } from "./DashboardPage";

vi.mock("../api/client", () => ({
  api: {
    getDashboard: vi.fn(),
    getRelatorio: vi.fn(),
    getCompetencias: vi.fn(),
    getDre: vi.fn(),
  },
}));

const mockApi = vi.mocked(api);

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.getCompetencias.mockResolvedValue([]);
    mockApi.getDre.mockResolvedValue({} as never);
    const mesJunho = {
      mes: "2026-06",
      ano: 2026,
      mes_num: 6,
      pedidos: 678,
      produtos_distintos: 42,
      unidades: "758",
      receita_bruta: "52026.43",
      tarifas_plataforma: "-7901.91",
      frete_liquido: "-9989.47",
      descontos: "664.15",
      cancelamentos: "-1894.76",
      liquido_recebido: "32904.44",
      cmv: "8000.00",
      lucro_bruto: "24904.44",
      margem_liquida: "47.87",
      conferencia: {
        soma_componentes: "32904.44",
        liquido_importado: "32904.44",
        diferenca: "0.00",
        confere: true,
      },
    };
    mockApi.getDashboard.mockResolvedValue({
      faturamento_bruto: "62412.31",
      liquido_total: "40288.14",
      liquido_por_canal: { "Mercado Livre": "32904.44", Shopee: "7383.70" },
      unidades_vendidas: "974",
      qtd_pedidos: 894,
      produtos_distintos: 42,
      entradas: { receita_bruta: "62412.31", descontos_bonus: "664.15" },
      saidas: {
        tarifas_plataforma: "-10904.09",
        frete_liquido: "-9989.47",
        cancelamentos: "-1894.76",
        custo_produtos_vendidos: "10000.00",
        custos_operacionais: "0",
      },
      custo_produtos_vendidos: "10000.00",
      custos_operacionais: "0",
      lucro_estimado: "30288.14",
      projecoes: { "15": "100.00", "30": "200.00", "60": "400.00", "90": "600.00" },
      mes_vigente: mesJunho,
      resumo_mensal: [mesJunho],
    });
    mockApi.getRelatorio.mockImplementation((tipo: string) => {
      if (tipo === "dre") {
        return Promise.resolve({
          receita_bruta: "62412.31",
          tarifas_plataforma: "10904.09",
          frete_liquido: "9989.47",
          descontos: "664.15",
          cancelamentos: "1894.76",
          liquido_recebido: "40288.14",
          custo_produtos_vendidos: "10000.00",
          margem_bruta: "31518.75",
        });
      }
      return Promise.resolve([
        { sku_base: "5338", unidades: "120", liquido: "10058.16" },
      ]);
    });
  });

  it("mostra KPIs e líquido por canal", async () => {
    render(<DashboardPage />);
    // faturamento bruto formatado em BRL (aparece no KPI e no painel DRE)
    expect((await screen.findAllByText(/62\.412,31/)).length).toBeGreaterThan(0);
    expect(screen.getByText("Mercado Livre")).toBeInTheDocument();
    expect(screen.getAllByText(/32\.904,44/).length).toBeGreaterThan(0);
    expect(screen.getByText("974")).toBeInTheDocument();
    // projeções
    expect(screen.getByText("90 dias")).toBeInTheDocument();
    // ranking de produtos
    expect(await screen.findByText("5338")).toBeInTheDocument();
  });

  it("mostra as métricas de quantidade e o resumo mensal com conferência", async () => {
    render(<DashboardPage />);
    // KPIs de contagem
    expect(await screen.findByText("Qtd. de vendas")).toBeInTheDocument();
    expect(screen.getByText("894")).toBeInTheDocument();
    expect(screen.getByText("Produtos distintos")).toBeInTheDocument();
    expect(screen.getByText("CMV do mês vigente")).toBeInTheDocument();
    // Entradas / Saídas
    expect(screen.getByText("Entradas")).toBeInTheDocument();
    expect(screen.getByText("Saídas")).toBeInTheDocument();
    // Resumo mensal detalhado + conferência OK
    expect(screen.getByText("Resumo detalhado por mês")).toBeInTheDocument();
    expect(screen.getAllByText(/Junho 2026/).length).toBeGreaterThan(0);
    expect(screen.getByText("✓ OK")).toBeInTheDocument();
  });
});
