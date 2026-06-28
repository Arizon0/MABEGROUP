import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { SkuMapPage } from "./SkuMapPage";

vi.mock("../api/client", () => ({
  api: {
    listarPendencias: vi.fn(),
    listarSkuMap: vi.fn(),
    buscarProdutos: vi.fn(),
    salvarSkuMap: vi.fn(),
  },
}));

const mockApi = vi.mocked(api);

describe("SkuMapPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.listarPendencias.mockResolvedValue([
      {
        id: 1,
        sku_canal: "8126STA",
        canal: "Shopee",
        id_anuncio: null,
        titulo: "Jogo Anel Pistão",
        ocorrencias: 3,
      },
    ]);
    mockApi.listarSkuMap.mockResolvedValue([
      {
        id: 10,
        sku_canal: "5338",
        canal: "Mercado Livre",
        id_anuncio: "MLB6527593792",
        produto_id: 5,
        sku_base: "5338",
      },
    ]);
    mockApi.buscarProdutos.mockResolvedValue([
      { id: 8, sku_base: "8126", nome: "Jogo Anel Pistão STD" },
    ]);
    mockApi.salvarSkuMap.mockResolvedValue({
      id: 99,
      sku_canal: "8126STA",
      canal: "Shopee",
      id_anuncio: null,
      produto_id: 8,
      sku_base: "8126",
    });
  });

  it("lista pendências e de-para configurados", async () => {
    render(<SkuMapPage />);
    expect(await screen.findByText("8126STA")).toBeInTheDocument();
    expect(screen.getByText("Jogo Anel Pistão")).toBeInTheDocument();
    // de-para já configurado (sku_canal "5338" e sku_base "5338" aparecem na linha)
    expect(screen.getAllByText("5338").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("MLB6527593792")).toBeInTheDocument();
  });

  it("mapeia uma pendência buscando e selecionando o produto", async () => {
    const user = userEvent.setup();
    render(<SkuMapPage />);
    await screen.findByText("8126STA");

    const input = screen.getByLabelText("Buscar produto");
    await user.type(input, "8126");

    // resultado do dropdown aparece (após debounce)
    const opcao = await screen.findByRole("button", { name: /8126/ });
    await user.click(opcao);

    await waitFor(() => {
      expect(mockApi.salvarSkuMap).toHaveBeenCalledWith({
        sku_canal: "8126STA",
        canal: "Shopee",
        id_anuncio: null,
        produto_id: 8,
      });
    });
    // recarrega a lista após salvar
    expect(mockApi.listarPendencias).toHaveBeenCalledTimes(2);
  });
});
