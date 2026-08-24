import { beforeEach, describe, expect, it, vi } from "vitest";
import { SESSAO_EXPIRADA, api, baixarArquivo } from "./client";
import { guardarSessao, tokenAtual } from "./sessao";

const USUARIO = { id: 1, email: "admin@erp.local", nome: "Admin", perfil: "admin" };

function resposta(corpo: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => corpo,
    text: async () => JSON.stringify(corpo),
    blob: async () => new Blob(["conteudo"]),
    statusText: "",
  } as unknown as Response;
}

function cabecalhos(chamada: unknown): Record<string, string> {
  return ((chamada as RequestInit).headers ?? {}) as Record<string, string>;
}

describe("client", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("não manda Authorization quando não há sessão", async () => {
    const buscar = vi.spyOn(globalThis, "fetch").mockResolvedValue(resposta({}));
    await api.getDashboard();
    expect(cabecalhos(buscar.mock.calls[0][1])).not.toHaveProperty("Authorization");
  });

  it("manda o token em toda requisição depois do login", async () => {
    guardarSessao("abc123", USUARIO);
    const buscar = vi.spyOn(globalThis, "fetch").mockResolvedValue(resposta({}));
    await api.getDashboard();
    expect(cabecalhos(buscar.mock.calls[0][1]).Authorization).toBe("Bearer abc123");
  });

  it("manda o token também no upload de planilha", async () => {
    guardarSessao("abc123", USUARIO);
    const buscar = vi.spyOn(globalThis, "fetch").mockResolvedValue(resposta({}));
    await api.importarML(new File(["x"], "ml.xlsx"));
    const enviado = cabecalhos(buscar.mock.calls[0][1]);
    expect(enviado.Authorization).toBe("Bearer abc123");
    // O boundary do multipart é montado pelo navegador — definir Content-Type
    // aqui quebraria o parsing no servidor.
    expect(enviado).not.toHaveProperty("Content-Type");
  });

  it("401 encerra a sessão e avisa que expirou", async () => {
    guardarSessao("abc123", USUARIO);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(resposta({}, 401));
    await expect(api.getDashboard()).rejects.toThrow(SESSAO_EXPIRADA);
    expect(tokenAtual()).toBeNull();
  });

  it("outros erros não derrubam a sessão", async () => {
    guardarSessao("abc123", USUARIO);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(resposta({ detail: "boom" }, 500));
    await expect(api.getDashboard()).rejects.toThrow(/500/);
    expect(tokenAtual()).toBe("abc123");
  });

  it("204 sem corpo não estoura no json()", async () => {
    guardarSessao("abc123", USUARIO);
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => {
        throw new Error("corpo vazio");
      },
      text: async () => "",
    } as unknown as Response);
    await expect(api.excluirAds(1)).resolves.toBeUndefined();
  });

  it("download de arquivo protegido vai com token", async () => {
    guardarSessao("abc123", USUARIO);
    const buscar = vi.spyOn(globalThis, "fetch").mockResolvedValue(resposta({}));
    globalThis.URL.createObjectURL = vi.fn(() => "blob:fake");
    globalThis.URL.revokeObjectURL = vi.fn();

    await baixarArquivo("/api/vendas/analise/export?formato=excel", "analise.xlsx");

    expect(cabecalhos(buscar.mock.calls[0][1]).Authorization).toBe("Bearer abc123");
    expect(globalThis.URL.createObjectURL).toHaveBeenCalled();
    // O link temporário não pode ficar no documento depois do clique.
    expect(document.querySelector("a[download]")).toBeNull();
    expect(globalThis.URL.revokeObjectURL).toHaveBeenCalledWith("blob:fake");
  });

  it("login guarda a sessão a partir da resposta", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      resposta({ access_token: "novo", token_type: "bearer", usuario: USUARIO }),
    );
    const r = await api.login("admin@erp.local", "senha");
    expect(r.access_token).toBe("novo");
    expect(r.usuario.email).toBe("admin@erp.local");
  });
});
