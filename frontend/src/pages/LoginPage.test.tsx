import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { tokenAtual, usuarioAtual } from "../api/sessao";
import { LoginPage } from "./LoginPage";

vi.mock("../api/client", () => ({ api: { login: vi.fn() } }));
const mockApi = vi.mocked(api);

const USUARIO = { id: 1, email: "admin@erp.local", nome: "Admin", perfil: "admin" };

async function preencherEEntrar(user: ReturnType<typeof userEvent.setup>, senha = "admin123") {
  await user.type(screen.getByLabelText("Usuário"), "admin@erp.local");
  await user.type(screen.getByLabelText("Senha"), senha);
  await user.click(screen.getByRole("button", { name: "Entrar" }));
}

describe("LoginPage", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("guarda a sessão quando o login dá certo", async () => {
    const user = userEvent.setup();
    mockApi.login.mockResolvedValue({
      access_token: "abc123", token_type: "bearer", usuario: USUARIO,
    });
    render(<LoginPage />);
    await preencherEEntrar(user);

    await waitFor(() => expect(tokenAtual()).toBe("abc123"));
    expect(usuarioAtual()).toEqual(USUARIO);
    expect(mockApi.login).toHaveBeenCalledWith("admin@erp.local", "admin123");
  });

  it("mostra mensagem específica para credencial errada", async () => {
    const user = userEvent.setup();
    mockApi.login.mockRejectedValue(new Error("HTTP 401: nao autorizado"));
    render(<LoginPage />);
    await preencherEEntrar(user, "errada");

    expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou senha incorretos.");
    expect(tokenAtual()).toBeNull();
  });

  it("não revela se o usuário existe", async () => {
    const user = userEvent.setup();
    mockApi.login.mockRejectedValue(new Error("HTTP 401: nao autorizado"));
    render(<LoginPage />);
    await preencherEEntrar(user);

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).not.toMatch(/(usuário|e-mail) não (existe|encontrado)/i);
  });

  it("erro de rede tem mensagem diferente de credencial", async () => {
    const user = userEvent.setup();
    mockApi.login.mockRejectedValue(new Error("Failed to fetch"));
    render(<LoginPage />);
    await preencherEEntrar(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(/conexão/i);
  });

  it("desabilita o botão enquanto envia, para não duplicar o login", async () => {
    const user = userEvent.setup();
    let liberar: (v: unknown) => void = () => {};
    mockApi.login.mockReturnValue(new Promise((r) => { liberar = r; }) as never);
    render(<LoginPage />);
    await preencherEEntrar(user);

    expect(screen.getByRole("button", { name: "Entrando…" })).toBeDisabled();
    liberar({ access_token: "x", token_type: "bearer", usuario: USUARIO });
  });

  it("os campos ajudam o gerenciador de senhas do navegador", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Usuário")).toHaveAttribute("autocomplete", "username");
    expect(screen.getByLabelText("Senha")).toHaveAttribute("autocomplete", "current-password");
  });
});
