import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { encerrarSessao, guardarSessao, tokenAtual } from "./api/sessao";

vi.mock("./api/client", () => ({
  api: { login: vi.fn(), getDashboard: vi.fn().mockResolvedValue({}) },
  baixarArquivo: vi.fn(),
  SESSAO_EXPIRADA: "Sessão expirada. Entre novamente.",
}));

// As páginas internas não são o objeto deste teste — só se elas aparecem.
vi.mock("./pages/DashboardPage", () => ({ DashboardPage: () => <p>painel</p> }));

const USUARIO = { id: 1, email: "admin@erp.local", nome: "Matheus", perfil: "admin" };

function montar() {
  return render(
    <MemoryRouter>
      <App />
    </MemoryRouter>,
  );
}

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("sem sessão mostra o login e nenhuma tela interna", () => {
    montar();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByText("painel")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Financeiro" })).not.toBeInTheDocument();
  });

  it("com sessão mostra o painel e o menu", () => {
    guardarSessao("abc123", USUARIO);
    montar();
    expect(screen.getByText("painel")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Análise de Vendas" })).toBeInTheDocument();
  });

  it("mostra quem está logado", () => {
    guardarSessao("abc123", USUARIO);
    montar();
    expect(screen.getByRole("link", { name: "Matheus" })).toBeInTheDocument();
  });

  it("sair limpa a sessão e volta para o login", async () => {
    const user = userEvent.setup();
    guardarSessao("abc123", USUARIO);
    montar();
    await user.click(screen.getByRole("button", { name: "Sair" }));

    expect(tokenAtual()).toBeNull();
    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
  });

  it("token descartado pela API derruba a tela para o login sozinho", async () => {
    guardarSessao("abc123", USUARIO);
    montar();
    expect(screen.getByText("painel")).toBeInTheDocument();

    // É o que o cliente HTTP faz ao receber 401 no meio do uso.
    encerrarSessao();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument(),
    );
    expect(screen.queryByText("painel")).not.toBeInTheDocument();
  });
});
