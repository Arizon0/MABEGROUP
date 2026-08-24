import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  encerrarSessao,
  guardarSessao,
  observarSessao,
  tokenAtual,
  usuarioAtual,
} from "./sessao";

const USUARIO = { id: 1, email: "admin@erp.local", nome: "Admin", perfil: "admin" };

describe("sessao", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("começa sem sessão", () => {
    expect(tokenAtual()).toBeNull();
    expect(usuarioAtual()).toBeNull();
  });

  it("guarda e recupera token e usuário", () => {
    guardarSessao("abc123", USUARIO);
    expect(tokenAtual()).toBe("abc123");
    expect(usuarioAtual()).toEqual(USUARIO);
  });

  it("sobrevive a recarregar a página", () => {
    guardarSessao("abc123", USUARIO);
    // Uma leitura nova, sem estado em memória, ainda enxerga a sessão.
    expect(localStorage.getItem("erp.token")).toBe("abc123");
  });

  it("encerrar limpa tudo", () => {
    guardarSessao("abc123", USUARIO);
    encerrarSessao();
    expect(tokenAtual()).toBeNull();
    expect(usuarioAtual()).toBeNull();
  });

  it("avisa os observadores quando a sessão muda", () => {
    const espiao = vi.fn();
    observarSessao(espiao);
    guardarSessao("abc123", USUARIO);
    expect(espiao).toHaveBeenCalledTimes(1);
    encerrarSessao();
    expect(espiao).toHaveBeenCalledTimes(2);
  });

  it("deixa de avisar depois de cancelar a observação", () => {
    const espiao = vi.fn();
    const cancelar = observarSessao(espiao);
    cancelar();
    guardarSessao("abc123", USUARIO);
    expect(espiao).not.toHaveBeenCalled();
  });

  it("usuário corrompido no storage não derruba a aplicação", () => {
    localStorage.setItem("erp.usuario", "{isso nao e json");
    expect(usuarioAtual()).toBeNull();
  });

  it("storage indisponível não derruba a aplicação", () => {
    // Navegador em modo privado pode lançar no acesso ao localStorage.
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("acesso negado");
    });
    expect(tokenAtual()).toBeNull();
  });
});
