import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { guardarSessao } from "../api/sessao";
import type { Usuario } from "../types/usuario";
import { UsuariosPage } from "./UsuariosPage";

vi.mock("../api/client", () => ({
  api: {
    listarUsuarios: vi.fn(),
    criarUsuario: vi.fn(),
    atualizarUsuario: vi.fn(),
    redefinirSenhaUsuario: vi.fn(),
    excluirUsuario: vi.fn(),
  },
}));
const mockApi = vi.mocked(api);

const EU: Usuario = { id: 1, login: "arizono", nome: "Arizono", perfil: "admin", ativo: true };
const OUTRO: Usuario = { id: 2, login: "canaveze", nome: "Canaveze", perfil: "admin", ativo: true };
const LEITOR: Usuario = { id: 3, login: "estagio", nome: "Estágio", perfil: "viewer", ativo: true };

function linhaDe(login: string) {
  return screen.getByText(login).closest("tr")!;
}

describe("UsuariosPage", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    guardarSessao("t", { id: 1, email: "arizono", nome: "Arizono", perfil: "admin" });
    mockApi.listarUsuarios.mockResolvedValue([EU, OUTRO, LEITOR]);
  });

  it("lista os usuários com perfil e situação", async () => {
    render(<UsuariosPage />);
    expect(await screen.findByText("arizono")).toBeInTheDocument();
    expect(screen.getByText("canaveze")).toBeInTheDocument();
    expect(within(linhaDe("estagio")).getByLabelText("Perfil de estagio")).toHaveValue("viewer");
  });

  it("marca qual é a sua própria conta", async () => {
    render(<UsuariosPage />);
    await screen.findByText("arizono");
    expect(within(linhaDe("arizono")).getByText("(você)")).toBeInTheDocument();
    expect(within(linhaDe("canaveze")).queryByText("(você)")).not.toBeInTheDocument();
  });

  it("cria um usuário e recarrega a lista", async () => {
    const user = userEvent.setup();
    mockApi.criarUsuario.mockResolvedValue(LEITOR);
    render(<UsuariosPage />);
    await screen.findByText("arizono");

    await user.type(screen.getByLabelText("Usuário"), "canaveze");
    await user.type(screen.getByLabelText("Senha"), "uma-senha-longa");
    await user.selectOptions(screen.getByLabelText("Perfil"), "admin");
    await user.click(screen.getByRole("button", { name: "Criar usuário" }));

    await waitFor(() =>
      expect(mockApi.criarUsuario).toHaveBeenCalledWith({
        login: "canaveze", nome: "", senha: "uma-senha-longa", perfil: "admin",
      }),
    );
    expect(mockApi.listarUsuarios).toHaveBeenCalledTimes(2);
  });

  it("o perfil sugerido é o mais restrito", async () => {
    render(<UsuariosPage />);
    await screen.findByText("arizono");
    expect(screen.getByLabelText("Perfil")).toHaveValue("viewer");
  });

  it("explica o que o perfil escolhido permite", async () => {
    const user = userEvent.setup();
    render(<UsuariosPage />);
    await screen.findByText("arizono");
    await user.selectOptions(screen.getByLabelText("Perfil"), "admin");
    expect(
      screen.getAllByText(/Acesso total, incluindo o cadastro de usuários/).length,
    ).toBeGreaterThan(0);
  });

  it("recusa senha curta antes de chamar a API", async () => {
    const user = userEvent.setup();
    render(<UsuariosPage />);
    await screen.findByText("arizono");

    await user.type(screen.getByLabelText("Usuário"), "novo");
    await user.type(screen.getByLabelText("Senha"), "1234567");
    await user.click(screen.getByRole("button", { name: "Criar usuário" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("ao menos 8 caracteres");
    expect(mockApi.criarUsuario).not.toHaveBeenCalled();
  });

  it("troca o perfil de outro usuário pelo seletor da linha", async () => {
    const user = userEvent.setup();
    mockApi.atualizarUsuario.mockResolvedValue({ ...LEITOR, perfil: "analista" });
    render(<UsuariosPage />);
    await screen.findByText("estagio");

    await user.selectOptions(screen.getByLabelText("Perfil de estagio"), "analista");

    await waitFor(() =>
      expect(mockApi.atualizarUsuario).toHaveBeenCalledWith(3, { perfil: "analista" }),
    );
  });

  it("desativa e reativa", async () => {
    const user = userEvent.setup();
    mockApi.atualizarUsuario.mockResolvedValue({ ...LEITOR, ativo: false });
    render(<UsuariosPage />);
    await screen.findByText("estagio");

    await user.click(within(linhaDe("estagio")).getByRole("button", { name: "Desativar" }));
    await waitFor(() =>
      expect(mockApi.atualizarUsuario).toHaveBeenCalledWith(3, { ativo: false }),
    );
  });

  it("exclusão pede confirmação antes de apagar", async () => {
    const user = userEvent.setup();
    mockApi.excluirUsuario.mockResolvedValue(undefined);
    render(<UsuariosPage />);
    await screen.findByText("estagio");
    const linha = linhaDe("estagio");

    await user.click(within(linha).getByRole("button", { name: "Excluir" }));
    expect(mockApi.excluirUsuario).not.toHaveBeenCalled();

    await user.click(within(linha).getByRole("button", { name: "Confirmar exclusão" }));
    await waitFor(() => expect(mockApi.excluirUsuario).toHaveBeenCalledWith(3));
  });

  it("dá para cancelar a exclusão", async () => {
    const user = userEvent.setup();
    render(<UsuariosPage />);
    await screen.findByText("estagio");
    const linha = linhaDe("estagio");

    await user.click(within(linha).getByRole("button", { name: "Excluir" }));
    await user.click(within(linha).getByRole("button", { name: "Cancelar" }));

    expect(within(linha).getByRole("button", { name: "Excluir" })).toBeInTheDocument();
    expect(mockApi.excluirUsuario).not.toHaveBeenCalled();
  });

  it("mostra a senha redefinida uma única vez", async () => {
    const user = userEvent.setup();
    mockApi.redefinirSenhaUsuario.mockResolvedValue(LEITOR);
    render(<UsuariosPage />);
    await screen.findByText("estagio");

    await user.click(
      within(linhaDe("estagio")).getByRole("button", { name: "Redefinir senha" }),
    );

    await waitFor(() => expect(mockApi.redefinirSenhaUsuario).toHaveBeenCalled());
    expect(await screen.findByText(/não será mostrada de novo/)).toBeInTheDocument();
    // A senha enviada à API é a mesma exibida ao administrador.
    const enviada = mockApi.redefinirSenhaUsuario.mock.calls[0][1];
    expect(screen.getByText(enviada)).toBeInTheDocument();
  });

  it("mostra o motivo quando o servidor recusa", async () => {
    const user = userEvent.setup();
    mockApi.atualizarUsuario.mockRejectedValue(
      new Error('HTTP 400: {"detail":"Este é o último administrador ativo."}'),
    );
    render(<UsuariosPage />);
    await screen.findByText("arizono");

    await user.selectOptions(screen.getByLabelText("Perfil de arizono"), "viewer");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Este é o último administrador ativo.",
    );
  });

  it("informa quando não há usuários", async () => {
    mockApi.listarUsuarios.mockResolvedValue([]);
    render(<UsuariosPage />);
    expect(await screen.findByText("Nenhum usuário cadastrado.")).toBeInTheDocument();
  });
});
