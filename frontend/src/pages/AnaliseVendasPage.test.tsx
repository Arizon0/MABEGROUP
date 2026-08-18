import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { AnaliseVendas, PedidoAnalisado } from "../types/analiseVendas";
import { AnaliseVendasPage } from "./AnaliseVendasPage";

vi.mock("../api/client", () => ({
  api: {
    getAnaliseVendas: vi.fn(),
    listarAliquotas: vi.fn(),
    listarAds: vi.fn(),
    salvarAliquota: vi.fn(),
    excluirAliquota: vi.fn(),
    salvarAds: vi.fn(),
    excluirAds: vi.fn(),
    salvarNotaFiscal: vi.fn(),
    urlExportAnalise: vi.fn(() => "#"),
  },
}));

const mockApi = vi.mocked(api);

function pedido(over: Partial<PedidoAnalisado> = {}): PedidoAnalisado {
  return {
    canal: "Mercado Livre",
    id_pedido_canal: "V1735",
    numero_nf: "1735",
    data_venda: "2026-07-31T10:00:00",
    titulo: "Retentor Volante",
    skus: ["5338"],
    anuncios: ["MLB1"],
    canal_logistico: "ML Full",
    status_canal: "Entregue",
    linhas: 1,
    is_pacote_multi: false,
    qtd: "1",
    total: "33.87",
    custo: "16.02",
    frete: "7.95",
    comissao: "4.06",
    descontos: "0.00",
    cancelamentos: "0.00",
    liquido_recebido: "21.86",
    ads: "8.79",
    acos_pct: null,
    tacos_pct: "25.95",
    imposto: "2.78",
    aliquota_pct: "8.22",
    margem_valor: "-5.73",
    margem_pct: "-16.92",
    diferenca_liquido: "0.00",
    alertas: [],
    ...over,
  };
}

const RESPOSTA: AnaliseVendas = {
  filtros: {
    data_inicio: null, data_fim: null, canal: null,
    recorte: "todos", ordem: "data", busca: null,
  },
  resumo: {
    pedidos: 709,
    negativos: 248,
    pct_negativos: "35.00",
    para_revisar: 37,
    unidades: "800",
    total: "530.70",
    custo: "268.08",
    frete: "96.00",
    comissao: "62.86",
    ads: "32.11",
    imposto: "43.62",
    liquido_recebido: "371.84",
    margem_valor: "28.03",
    margem_pct: "5.28",
    prejuizo_dos_negativos: "-5.73",
    ads_nao_alocado: "0.00",
  },
  contagem_por_recorte: {
    todos: 709, negativos: 248, "sem-custo": 12, "sem-comissao": 3,
    "sem-frete": 8, pacotes: 20, revisar: 37,
  },
  paginacao: { pagina: 1, tamanho: 50, total: 709, paginas: 15, de: 1, ate: 50 },
  pedidos: [
    pedido(),
    pedido({
      id_pedido_canal: "V1725", numero_nf: "1725", titulo: "Jogo de Anéis",
      skus: ["8126"], total: "135.87", custo: "76.02", frete: "19.25",
      comissao: "16.30", ads: "9.35", acos_pct: "10.49", tacos_pct: "6.88",
      imposto: "11.17", margem_valor: "3.78", margem_pct: "2.78",
    }),
  ],
};

describe("AnaliseVendasPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApi.getAnaliseVendas.mockResolvedValue(RESPOSTA);
    mockApi.listarAliquotas.mockResolvedValue([]);
    mockApi.listarAds.mockResolvedValue([]);
  });

  it("mostra a linha-resumo com pedidos, negativos e a janela exibida", async () => {
    render(<AnaliseVendasPage />);
    const resumo = await screen.findByRole("status");
    expect(resumo).toHaveTextContent("709 pedidos");
    expect(resumo).toHaveTextContent("248 negativos (35%)");
    expect(resumo).toHaveTextContent("37 para revisar");
    expect(resumo).toHaveTextContent("mostrando 1–50");
  });

  it("renderiza cada custo do pedido na sua coluna", async () => {
    render(<AnaliseVendasPage />);
    const linha = (await screen.findByRole("button", { name: "NF 1735" })).closest("tr")!;
    const celulas = within(linha).getAllByRole("cell").map((c) => c.textContent?.trim());
    // Data, Canal, Margem, Total, Custo, Frete, Comissão, Ads, ACOS, TACOS, Imposto
    expect(celulas).toEqual([
      "31/07/26", "ML", "-16,92% ↘-5,73",
      "33,87", "16,02", "7,95", "4,06", "8,79",
      "—", "25,95%", "2,78",
    ]);
  });

  it("mostra ACOS só quando o canal atribuiu receita à publicidade", async () => {
    render(<AnaliseVendasPage />);
    const semAcos = (await screen.findByRole("button", { name: "NF 1735" })).closest("tr")!;
    const comAcos = screen.getByRole("button", { name: "NF 1725" }).closest("tr")!;
    expect(within(semAcos).getAllByRole("cell")[8]).toHaveTextContent("—");
    expect(within(comAcos).getAllByRole("cell")[8]).toHaveTextContent("10,49%");
  });

  it("soma as colunas no rodapé da tabela", async () => {
    render(<AnaliseVendasPage />);
    const rodape = await screen.findByRole("rowheader", { name: /Total do recorte/ });
    expect(rodape).toHaveTextContent("margem 28,03 (5,28%)");
  });

  it("pede um novo recorte ao clicar no chip", async () => {
    const user = userEvent.setup();
    render(<AnaliseVendasPage />);
    await screen.findByRole("button", { name: /Só negativos/ });
    await user.click(screen.getByRole("button", { name: /Só negativos/ }));
    await waitFor(() =>
      expect(mockApi.getAnaliseVendas).toHaveBeenLastCalledWith(
        expect.objectContaining({ recorte: "negativos", pagina: 1 }),
      ),
    );
  });

  it("pede uma nova ordenação ao clicar no chip", async () => {
    const user = userEvent.setup();
    render(<AnaliseVendasPage />);
    await screen.findByRole("button", { name: "Pior margem R$" });
    await user.click(screen.getByRole("button", { name: "Pior margem R$" }));
    await waitFor(() =>
      expect(mockApi.getAnaliseVendas).toHaveBeenLastCalledWith(
        expect.objectContaining({ ordem: "pior-margem-valor" }),
      ),
    );
  });

  it("mostra no chip quantos pedidos cada recorte tem", async () => {
    render(<AnaliseVendasPage />);
    const chip = await screen.findByRole("button", { name: /Só negativos/ });
    expect(chip).toHaveTextContent("248");
  });

  it("marca o recorte ativo para leitores de tela", async () => {
    const user = userEvent.setup();
    render(<AnaliseVendasPage />);
    const todos = await screen.findByRole("button", { name: "Todos" });
    expect(todos).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: /Só negativos/ }));
    expect(screen.getByRole("button", { name: /Só negativos/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("volta para a primeira página ao trocar de recorte", async () => {
    const user = userEvent.setup();
    render(<AnaliseVendasPage />);
    await screen.findByRole("button", { name: "Próxima" });
    await user.click(screen.getByRole("button", { name: "Próxima" }));
    await waitFor(() =>
      expect(mockApi.getAnaliseVendas).toHaveBeenLastCalledWith(
        expect.objectContaining({ pagina: 2 }),
      ),
    );
    await user.click(screen.getByRole("button", { name: /Sem custo/ }));
    await waitFor(() =>
      expect(mockApi.getAnaliseVendas).toHaveBeenLastCalledWith(
        expect.objectContaining({ recorte: "sem-custo", pagina: 1 }),
      ),
    );
  });

  it("avisa quando nenhum imposto está sendo aplicado", async () => {
    mockApi.getAnaliseVendas.mockResolvedValue({
      ...RESPOSTA,
      resumo: { ...RESPOSTA.resumo, imposto: "0.00" },
    });
    render(<AnaliseVendasPage />);
    expect(await screen.findByText(/Cadastre a alíquota da competência/)).toBeInTheDocument();
  });

  it("avisa quando sobra verba de publicidade sem ratear", async () => {
    mockApi.getAnaliseVendas.mockResolvedValue({
      ...RESPOSTA,
      resumo: { ...RESPOSTA.resumo, ads_nao_alocado: "150.00" },
    });
    render(<AnaliseVendasPage />);
    expect(
      await screen.findByText(/150,00 de publicidade não foram rateados/),
    ).toBeInTheDocument();
  });

  it("explica o alerta de líquido divergente", async () => {
    mockApi.getAnaliseVendas.mockResolvedValue({
      ...RESPOSTA,
      pedidos: [pedido({ alertas: ["receber_nao_bate"], diferenca_liquido: "15.00" })],
    });
    render(<AnaliseVendasPage />);
    const marca = await screen.findByText(/receber nao bate/);
    expect(marca).toHaveAttribute("title", expect.stringContaining("não fecha com o líquido"));
  });

  it("grava a nota fiscal editada na linha", async () => {
    const user = userEvent.setup();
    mockApi.salvarNotaFiscal.mockResolvedValue({});
    render(<AnaliseVendasPage />);
    await user.click(await screen.findByRole("button", { name: "NF 1735" }));
    const campo = screen.getByLabelText("Número da nota fiscal");
    await user.clear(campo);
    await user.type(campo, "9999{Enter}");
    await waitFor(() =>
      expect(mockApi.salvarNotaFiscal).toHaveBeenCalledWith(
        "Mercado Livre",
        "V1735",
        "9999",
      ),
    );
  });

  it("mostra travessão quando o pedido não tem margem percentual", async () => {
    mockApi.getAnaliseVendas.mockResolvedValue({
      ...RESPOSTA,
      pedidos: [pedido({ margem_pct: null, margem_valor: "0.00" })],
    });
    render(<AnaliseVendasPage />);
    const linha = (await screen.findByRole("button", { name: "NF 1735" })).closest("tr")!;
    expect(within(linha).getAllByRole("cell")[2]).toHaveTextContent("—");
  });

  it("identifica o pedido pelo id do canal quando não há nota fiscal", async () => {
    mockApi.getAnaliseVendas.mockResolvedValue({
      ...RESPOSTA,
      pedidos: [pedido({ numero_nf: null })],
    });
    render(<AnaliseVendasPage />);
    expect(await screen.findByRole("button", { name: "Pedido V1735" })).toBeInTheDocument();
  });

  it("informa quando o recorte não tem nenhum pedido", async () => {
    mockApi.getAnaliseVendas.mockResolvedValue({
      ...RESPOSTA,
      resumo: { ...RESPOSTA.resumo, pedidos: 0, negativos: 0, para_revisar: 0 },
      paginacao: { pagina: 1, tamanho: 50, total: 0, paginas: 0, de: 0, ate: 0 },
      pedidos: [],
    });
    render(<AnaliseVendasPage />);
    expect(await screen.findByText("Nenhum pedido neste recorte.")).toBeInTheDocument();
  });

  it("mostra o erro quando a API falha", async () => {
    mockApi.getAnaliseVendas.mockRejectedValue(new Error("HTTP 500: boom"));
    render(<AnaliseVendasPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("HTTP 500: boom");
  });

  it("salva a alíquota pelo painel de parâmetros e recarrega a análise", async () => {
    const user = userEvent.setup();
    mockApi.salvarAliquota.mockResolvedValue({
      id: 1, ano: 2026, mes: 7, aliquota_pct: "8.2200", observacao: null,
    });
    render(<AnaliseVendasPage />);
    await user.click(await screen.findByRole("button", { name: /Parâmetros de custo/ }));
    await user.type(screen.getByLabelText(/Alíquota %/), "8,22");
    await user.click(screen.getByRole("button", { name: "Salvar alíquota" }));
    await waitFor(() =>
      expect(mockApi.salvarAliquota).toHaveBeenCalledWith(
        expect.objectContaining({ aliquota_pct: "8.22" }),
      ),
    );
  });

  it("desabilita a referência quando o Ads é do canal inteiro", async () => {
    const user = userEvent.setup();
    render(<AnaliseVendasPage />);
    await user.click(await screen.findByRole("button", { name: /Parâmetros de custo/ }));
    expect(screen.getByLabelText("Referência")).toBeDisabled();
    await user.selectOptions(screen.getByLabelText("Escopo"), "anuncio");
    expect(screen.getByLabelText("Referência")).toBeEnabled();
  });
});
