import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { usuarioAtual } from "../api/sessao";
import {
  DESCRICAO_PERFIL,
  PERFIS,
  type Perfil,
  type Usuario,
} from "../types/usuario";

const SENHA_MINIMA = 8;

function mensagem(e: unknown, padrao: string): string {
  if (!(e instanceof Error)) return padrao;
  // A API manda o motivo em JSON; mostrar o texto cru seria ilegível.
  const detalhe = e.message.match(/"detail":"([^"]+)"/);
  return detalhe ? detalhe[1] : e.message;
}

function Etiqueta({ perfil }: { perfil: Perfil }) {
  const estilo: Record<Perfil, string> = {
    admin: "bg-slate-900 text-white",
    analista: "bg-blue-100 text-blue-900",
    viewer: "bg-slate-100 text-slate-700",
  };
  return (
    <span
      title={DESCRICAO_PERFIL[perfil]}
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${estilo[perfil]}`}
    >
      {perfil}
    </span>
  );
}

function NovoUsuario({ aoCriar }: { aoCriar: () => void }) {
  const [login, setLogin] = useState("");
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [perfil, setPerfil] = useState<Perfil>("viewer");
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  async function criar(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    if (senha.length < SENHA_MINIMA) {
      setErro(`A senha precisa ter ao menos ${SENHA_MINIMA} caracteres.`);
      return;
    }
    setSalvando(true);
    try {
      await api.criarUsuario({ login, nome, senha, perfil });
      setLogin("");
      setNome("");
      setSenha("");
      setPerfil("viewer");
      aoCriar();
    } catch (e) {
      setErro(mensagem(e, "Não foi possível criar o usuário."));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <form onSubmit={criar} className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-900">Novo usuário</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs text-slate-600">
          Usuário
          <input
            required
            minLength={3}
            className="input mt-1 block w-full"
            placeholder="arizono"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
          />
        </label>
        <label className="text-xs text-slate-600">
          Nome
          <input
            className="input mt-1 block w-full"
            placeholder="opcional"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
          />
        </label>
        <label className="text-xs text-slate-600">
          Senha
          <input
            type="password"
            required
            autoComplete="new-password"
            className="input mt-1 block w-full"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
        </label>
        <label className="text-xs text-slate-600">
          Perfil
          <select
            className="input mt-1 block w-full"
            value={perfil}
            onChange={(e) => setPerfil(e.target.value as Perfil)}
          >
            {PERFIS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </label>
      </div>

      <p className="mt-2 text-xs text-slate-500">{DESCRICAO_PERFIL[perfil]}</p>

      {erro && (
        <p role="alert" className="mt-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      <button
        type="submit"
        disabled={salvando}
        className="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
      >
        {salvando ? "Criando…" : "Criar usuário"}
      </button>
    </form>
  );
}

function Linha({
  usuario,
  souEu,
  aoMudar,
  aoFalhar,
}: {
  usuario: Usuario;
  souEu: boolean;
  aoMudar: () => void;
  aoFalhar: (m: string) => void;
}) {
  const [confirmando, setConfirmando] = useState(false);
  const [novaSenha, setNovaSenha] = useState<string | null>(null);

  async function executar(acao: () => Promise<unknown>) {
    try {
      await acao();
      aoMudar();
    } catch (e) {
      aoFalhar(mensagem(e, "Não foi possível concluir a operação."));
    }
  }

  return (
    <tr className="border-b border-slate-100 hover:bg-slate-50">
      <td className="px-3 py-3">
        <span className="font-medium text-slate-900">{usuario.login}</span>
        {souEu && <span className="ml-2 text-xs text-slate-500">(você)</span>}
        <p className="text-xs text-slate-500">{usuario.nome}</p>
      </td>
      <td className="px-3 py-3">
        <select
          aria-label={`Perfil de ${usuario.login}`}
          className="input py-1 text-sm"
          value={usuario.perfil}
          onChange={(e) =>
            void executar(() =>
              api.atualizarUsuario(usuario.id, { perfil: e.target.value as Perfil }),
            )
          }
        >
          {PERFIS.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </td>
      <td className="px-3 py-3">
        {usuario.ativo ? (
          <Etiqueta perfil={usuario.perfil} />
        ) : (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-900">
            desativado
          </span>
        )}
      </td>
      <td className="px-3 py-3 text-right">
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            className="text-xs text-slate-600 hover:underline"
            onClick={() =>
              void executar(() =>
                api.atualizarUsuario(usuario.id, { ativo: !usuario.ativo }),
              )
            }
          >
            {usuario.ativo ? "Desativar" : "Reativar"}
          </button>

          <button
            type="button"
            className="text-xs text-slate-600 hover:underline"
            onClick={() => {
              // Senha gerada aqui e mostrada uma vez: evita o administrador
              // escolher algo fraco por pressa e evita mandá-la por e-mail.
              const gerada = Array.from(crypto.getRandomValues(new Uint8Array(9)))
                .map((b) => b.toString(36).padStart(2, "0"))
                .join("")
                .slice(0, 14);
              void executar(async () => {
                await api.redefinirSenhaUsuario(usuario.id, gerada);
                setNovaSenha(gerada);
              });
            }}
          >
            Redefinir senha
          </button>

          {confirmando ? (
            <>
              <button
                type="button"
                className="text-xs font-medium text-red-700 hover:underline"
                onClick={() => void executar(() => api.excluirUsuario(usuario.id))}
              >
                Confirmar exclusão
              </button>
              <button
                type="button"
                className="text-xs text-slate-500 hover:underline"
                onClick={() => setConfirmando(false)}
              >
                Cancelar
              </button>
            </>
          ) : (
            <button
              type="button"
              className="text-xs text-red-600 hover:underline"
              onClick={() => setConfirmando(true)}
            >
              Excluir
            </button>
          )}
        </div>

        {novaSenha && (
          <p className="mt-2 rounded bg-emerald-50 px-2 py-1 text-left text-xs text-emerald-900">
            Senha nova de <strong>{usuario.login}</strong>:{" "}
            <code className="font-mono">{novaSenha}</code>
            <br />
            Anote agora — ela não será mostrada de novo.
          </p>
        )}
      </td>
    </tr>
  );
}

export function UsuariosPage() {
  const eu = usuarioAtual();
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  const carregar = useCallback(async () => {
    setCarregando(true);
    try {
      setUsuarios(await api.listarUsuarios());
      setErro(null);
    } catch (e) {
      setErro(mensagem(e, "Falha ao carregar os usuários."));
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <div className="mx-auto max-w-5xl p-4 sm:p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Usuários</h1>
        <p className="text-sm text-slate-500">
          Quem entra no sistema e o que cada um pode fazer. As permissões são
          aplicadas no servidor — esconder um menu não protege nada.
        </p>
      </header>

      <NovoUsuario aoCriar={() => void carregar()} />

      {erro && (
        <p role="alert" className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {erro}
        </p>
      )}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead className="bg-slate-900 text-white">
            <tr>
              <th scope="col" className="px-3 py-2.5 text-left font-semibold">Usuário</th>
              <th scope="col" className="px-3 py-2.5 text-left font-semibold">Perfil</th>
              <th scope="col" className="px-3 py-2.5 text-left font-semibold">Situação</th>
              <th scope="col" className="px-3 py-2.5 text-right font-semibold">Ações</th>
            </tr>
          </thead>
          <tbody>
            {usuarios.map((u) => (
              <Linha
                key={u.id}
                usuario={u}
                souEu={u.id === eu?.id}
                aoMudar={() => void carregar()}
                aoFalhar={setErro}
              />
            ))}
            {!carregando && usuarios.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-10 text-center text-slate-500">
                  Nenhum usuário cadastrado.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <section className="mt-6 rounded-lg border border-slate-200 bg-white p-4 text-sm">
        <h2 className="mb-2 font-semibold text-slate-900">O que cada perfil pode</h2>
        <dl className="grid gap-2">
          {PERFIS.map((p) => (
            <div key={p} className="flex gap-3">
              <dt className="w-20 shrink-0">
                <Etiqueta perfil={p} />
              </dt>
              <dd className="text-slate-600">{DESCRICAO_PERFIL[p]}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
