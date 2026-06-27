import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { FornecedoresPage } from "./FornecedoresPage";
import { ProdutosPage } from "./ProdutosPage";

vi.mock("../api/client", () => ({
  api: {
    listarProdutosCadastro: vi.fn(),
    criarProduto: vi.fn(),
    listarFornecedores: vi.fn(),
    criarFornecedor: vi.fn(),
  },
}));

const mockApi = vi.mocked(api);

describe("ProdutosPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.listarProdutosCadastro.mockResolvedValue([
      {
        id: 1,
        sku_base: "5338",
        nome: "Retentor Volante",
        categoria: "Retentores",
        unidade_medida: "UN",
        estoque_minimo: "10",
        estoque_seguranca: "0",
        preco_venda: "29.90",
        variantes: [],
      },
    ]);
  });

  it("lista produtos", async () => {
    render(<ProdutosPage />);
    expect(await screen.findByText("5338")).toBeInTheDocument();
    expect(screen.getByText("Retentor Volante")).toBeInTheDocument();
    expect(screen.getByText("R$ 29.90")).toBeInTheDocument();
  });

  it("cria um produto pelo formulário", async () => {
    const user = userEvent.setup();
    mockApi.criarProduto.mockResolvedValue({} as never);
    render(<ProdutosPage />);
    await screen.findByText("5338");

    await user.click(screen.getByRole("button", { name: /Novo produto/ }));
    await user.type(screen.getByLabelText(/SKU base/), "8126");
    await user.type(screen.getByLabelText(/Nome/), "Jogo Anel");
    await user.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => {
      expect(mockApi.criarProduto).toHaveBeenCalledWith(
        expect.objectContaining({ sku_base: "8126", nome: "Jogo Anel" }),
      );
    });
  });
});

describe("FornecedoresPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.listarFornecedores.mockResolvedValue([]);
  });

  it("cria fornecedor com contato", async () => {
    const user = userEvent.setup();
    mockApi.criarFornecedor.mockResolvedValue({} as never);
    render(<FornecedoresPage />);
    await waitFor(() => expect(mockApi.listarFornecedores).toHaveBeenCalled());

    await user.click(screen.getByRole("button", { name: /Novo fornecedor/ }));
    await user.type(screen.getByLabelText(/CNPJ/), "11.222.333/0001-81");
    await user.type(screen.getByLabelText(/Razão social/), "Auto Peças BR");

    await user.click(screen.getByRole("button", { name: /Adicionar contato/ }));
    await user.type(screen.getByPlaceholderText("Nome"), "João");

    await user.click(screen.getByRole("button", { name: /Salvar fornecedor/ }));

    await waitFor(() => {
      expect(mockApi.criarFornecedor).toHaveBeenCalledWith(
        expect.objectContaining({
          cnpj: "11.222.333/0001-81",
          razao_social: "Auto Peças BR",
          contatos: [expect.objectContaining({ nome: "João" })],
        }),
      );
    });
  });
});
