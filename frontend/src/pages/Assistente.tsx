import { useMemo, useRef, useState } from "react";
import { type ChatResponse, type FonteCitada, useChat } from "@/api/chat";
import { DataSourceStrip, PageHeader } from "@/components/PageChrome";

/**
 * Linha de mensagem: pergunta do usuário ou resposta do assistente.
 * Mantida em memória do browser — zero persistência.
 */
interface Mensagem {
  id: string;
  autor: "usuario" | "assistente";
  texto: string;
  criadaEm: Date;
  fontes?: FonteCitada[];
  recusou?: boolean;
  latenciaMs?: number;
}

const formatadorHora = new Intl.DateTimeFormat("pt-BR", {
  hour: "2-digit",
  minute: "2-digit",
});

/**
 * Divide o texto da resposta em segmentos: trechos de texto puro e
 * chips `[n]`. Retorna tokens consumíveis pelo render.
 */
function segmentar(texto: string): Array<
  | { tipo: "texto"; valor: string }
  | { tipo: "chip"; indice: number }
> {
  const segmentos: Array<
    | { tipo: "texto"; valor: string }
    | { tipo: "chip"; indice: number }
  > = [];
  const regex = /\[(\d{1,2})\]/g;
  let ultimo = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(texto)) !== null) {
    if (m.index > ultimo) {
      segmentos.push({ tipo: "texto", valor: texto.slice(ultimo, m.index) });
    }
    segmentos.push({ tipo: "chip", indice: Number(m[1]) });
    ultimo = m.index + m[0].length;
  }
  if (ultimo < texto.length) {
    segmentos.push({ tipo: "texto", valor: texto.slice(ultimo) });
  }
  return segmentos;
}

const ROTULO_FONTE: Record<string, string> = {
  CONTRATO: "Contrato",
  INDICADOR_FISCAL: "Indicador fiscal",
  RESUMO_FUNCAO: "Execução por função",
  RESUMO_PCA: "PCA por função",
};

function rotuloFonte(fonte: string): string {
  return ROTULO_FONTE[fonte] ?? fonte;
}

function FonteDrawer({
  fonte,
  onClose,
}: {
  fonte: FonteCitada;
  onClose: () => void;
}) {
  const linkOrigem = (() => {
    switch (fonte.referencia_tipo) {
      case "contrato":
        return fonte.referencia_id ? "/contratos" : null;
      case "indicador_fiscal":
        return "/lrf";
      case "resumo_funcao":
        return "/orcamento";
      case "resumo_pca":
        return "/orcamento";
      default:
        return null;
    }
  })();

  return (
    <div className="fixed inset-0 z-50 flex">
      <div
        className="flex-1 bg-surface/80 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <aside
        className="w-full max-w-md overflow-y-auto bg-surface-raised border-l border-border p-6 animate-fade-up shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-label="Detalhes da fonte"
      >
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent-ink">
              Fonte [{fonte.indice}] · {rotuloFonte(fonte.fonte)}
            </p>
            <h3 className="font-display text-lg text-text-primary mt-1 leading-tight">
              {fonte.titulo}
            </h3>
            <p className="font-mono text-[11px] text-text-muted mt-1">
              relevância {(fonte.score * 100).toFixed(1)}%
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-text-muted hover:text-text-primary hover:bg-surface-overlay transition-colors text-xl leading-none"
            aria-label="Fechar"
          >
            ×
          </button>
        </div>

        <div className="space-y-4">
          {Object.keys(fonte.metadados).length > 0 && (
            <section>
              <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted mb-2">
                Metadados
              </p>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                {Object.entries(fonte.metadados).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="font-mono text-[11px] text-text-muted">
                      {k}
                    </dt>
                    <dd className="text-text-secondary break-words">
                      {v == null ? "—" : String(v)}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          {linkOrigem && (
            <a
              href={linkOrigem}
              className="inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-wider text-accent-ink hover:text-accent-500 transition-colors"
            >
              abrir página de origem →
            </a>
          )}
        </div>
      </aside>
    </div>
  );
}

function Chip({
  fonte,
  onClick,
}: {
  fonte: FonteCitada;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center justify-center h-5 min-w-[22px] px-1.5 mx-0.5 rounded-md bg-accent-500/15 border border-accent-500/45 text-[11px] font-mono text-accent-ink hover:bg-accent-500/25 hover:text-accent-500 transition-colors align-baseline"
      title={fonte.titulo}
    >
      {fonte.indice}
    </button>
  );
}

function MensagemUsuario({
  texto,
  criadaEm,
}: {
  texto: string;
  criadaEm: Date;
}) {
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="max-w-[80%] bg-accent-500/12 border border-accent-500/40 rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm text-text-primary whitespace-pre-wrap">
        {texto}
      </div>
      <span className="text-[10px] font-mono text-text-muted mr-2">
        {formatadorHora.format(criadaEm)}
      </span>
    </div>
  );
}

function MensagemAssistente({
  mensagem,
  onAbrirFonte,
}: {
  mensagem: Mensagem;
  onAbrirFonte: (f: FonteCitada) => void;
}) {
  if (mensagem.recusou) {
    return (
      <div className="flex flex-col items-start gap-1">
        <div className="max-w-[80%] bg-warning-500/[0.06] border border-warning-500/30 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-warning-500">
          <p className="font-medium">
            Não tenho dados suficientes para responder com confiança.
          </p>
          <p className="text-xs text-text-secondary mt-1">
            Experimente reformular a pergunta, ou verifique se os dados
            correspondentes foram ingeridos.
          </p>
        </div>
        <span className="text-[10px] font-mono text-text-muted ml-2">
          {formatadorHora.format(mensagem.criadaEm)}
          {mensagem.latenciaMs != null
            ? ` · ${(mensagem.latenciaMs / 1000).toFixed(1)}s`
            : ""}
        </span>
      </div>
    );
  }

  const fontesPorIndice = new Map(
    (mensagem.fontes ?? []).map((f) => [f.indice, f]),
  );
  const segmentos = segmentar(mensagem.texto);

  return (
    <div className="flex flex-col items-start gap-1">
      <div className="max-w-[85%] bg-surface-raised border border-border rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-text-primary leading-relaxed">
        <p className="whitespace-pre-wrap">
          {segmentos.map((s, i) =>
            s.tipo === "texto" ? (
              <span key={i}>{s.valor}</span>
            ) : (() => {
              const fonte = fontesPorIndice.get(s.indice);
              if (!fonte) {
                return <span key={i}>[{s.indice}]</span>;
              }
              return (
                <Chip
                  key={i}
                  fonte={fonte}
                  onClick={() => onAbrirFonte(fonte)}
                />
              );
            })(),
          )}
        </p>

        {mensagem.fontes && mensagem.fontes.length > 0 && (
          <div className="mt-4 pt-3 border-t border-border">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono uppercase tracking-[0.22em] text-accent-ink">
                Fontes citadas
              </span>
              <span className="text-[10px] font-mono text-text-muted">
                {mensagem.fontes.length}{" "}
                {mensagem.fontes.length === 1 ? "documento" : "documentos"}
              </span>
            </div>
            <ul className="space-y-1.5">
              {mensagem.fontes.map((f) => (
                <li key={f.indice}>
                  <button
                    type="button"
                    onClick={() => onAbrirFonte(f)}
                    className="group w-full flex items-start gap-2.5 rounded-lg border border-border bg-surface-overlay/50 px-3 py-2 text-left transition-colors hover:border-accent-500/45 hover:bg-surface-overlay"
                  >
                    <span className="mt-0.5 shrink-0 inline-flex items-center justify-center h-5 min-w-[22px] px-1.5 rounded-md bg-accent-500/15 border border-accent-500/45 text-[10.5px] font-mono text-accent-ink">
                      {f.indice}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[12.5px] text-text-primary group-hover:text-accent-ink transition-colors leading-snug">
                        {f.titulo}
                      </span>
                      <span className="block text-[10.5px] font-mono text-text-muted mt-0.5">
                        {rotuloFonte(f.fonte)} · {(f.score * 100).toFixed(0)}% relevância
                      </span>
                    </span>
                    <span
                      className="shrink-0 self-center text-text-muted group-hover:text-accent-ink group-hover:translate-x-0.5 transition-all"
                      aria-hidden
                    >
                      →
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <span className="text-[10px] font-mono text-text-muted ml-2">
        {formatadorHora.format(mensagem.criadaEm)}
        {mensagem.latenciaMs != null
          ? ` · ${(mensagem.latenciaMs / 1000).toFixed(1)}s`
          : ""}
      </span>
    </div>
  );
}

export default function Assistente() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [entrada, setEntrada] = useState("");
  const [fonteAberta, setFonteAberta] = useState<FonteCitada | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const chat = useChat();

  const desabilitado = chat.isPending || entrada.trim().length < 3;

  const enviar = () => {
    const pergunta = entrada.trim();
    if (pergunta.length < 3) return;

    const idUsuario = crypto.randomUUID();
    const idAssistente = crypto.randomUUID();

    setMensagens((prev) => [
      ...prev,
      {
        id: idUsuario,
        autor: "usuario",
        texto: pergunta,
        criadaEm: new Date(),
      },
    ]);
    setEntrada("");

    chat.mutate(pergunta, {
      onSuccess: (resp: ChatResponse) => {
        setMensagens((prev) => [
          ...prev,
          {
            id: idAssistente,
            autor: "assistente",
            texto: resp.texto,
            criadaEm: new Date(),
            fontes: resp.fontes,
            recusou: resp.recusou,
            latenciaMs: resp.latencia_ms,
          },
        ]);
        requestAnimationFrame(() => {
          scrollRef.current?.scrollTo({
            top: scrollRef.current.scrollHeight,
            behavior: "smooth",
          });
        });
      },
      onError: (err) => {
        setMensagens((prev) => [
          ...prev,
          {
            id: idAssistente,
            autor: "assistente",
            texto: `Erro ao consultar o assistente: ${err.message}`,
            criadaEm: new Date(),
            recusou: false,
            fontes: [],
          },
        ]);
      },
    });
  };

  const placeholderSugestoes = useMemo(
    () => [
      "Por que Saúde está acima do orçamento previsto no PCA em 2024?",
      "Jequié está dentro do limite de despesa com pessoal da LRF?",
      "Quais contratos de tecnologia estão vencendo nos próximos 90 dias?",
    ],
    [],
  );

  return (
    <div className="h-full flex flex-col animate-fade-up">
      <div className="space-y-4 pb-6">
        <PageHeader
          eyebrow="Assistente"
          title="Pergunte à sua base"
          description={
            <>
              Respostas em linguagem natural sobre orçamento, indicadores
              fiscais e contratos de Jequié —{" "}
              <span className="text-text-primary">
                sempre com citação à fonte
              </span>
              . Se o dado não está na base, o assistente recusa em vez de
              inventar.
            </>
          }
        />

        <DataSourceStrip
          items={["RAG", "pgvector", "RREO/RGF", "PNCP"]}
          note="As fontes citadas abrem metadados e apontam para a página de origem quando possível."
        />
      </div>

      {/* Área de mensagens */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto py-6 space-y-4 min-h-0"
      >
        {mensagens.length === 0 && (
          <div className="flex flex-col items-start gap-2">
            <p className="text-text-muted text-sm">Experimente perguntar:</p>
            <div className="flex flex-col gap-2 w-full max-w-xl">
              {placeholderSugestoes.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setEntrada(s)}
                  className="text-left text-sm text-text-secondary bg-surface-raised border border-border hover:border-accent-500/45 hover:bg-surface-overlay hover:text-text-primary transition-colors rounded-lg px-4 py-2.5"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {mensagens.map((m) =>
          m.autor === "usuario" ? (
            <MensagemUsuario
              key={m.id}
              texto={m.texto}
              criadaEm={m.criadaEm}
            />
          ) : (
            <MensagemAssistente
              key={m.id}
              mensagem={m}
              onAbrirFonte={setFonteAberta}
            />
          ),
        )}

        {chat.isPending && (
          <div className="flex justify-start" role="status" aria-live="polite">
            <div className="bg-surface-raised border border-border rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-text-muted flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-accent-500 animate-pulse" />
              pensando…
            </div>
          </div>
        )}
      </div>

      {/* Input fixo embaixo */}
      <div className="pt-4 border-t border-border">
        <div className="flex items-stretch gap-3">
          <textarea
            value={entrada}
            onChange={(e) => setEntrada(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                enviar();
              }
            }}
            aria-label="Pergunta para o assistente"
            placeholder="Faça uma pergunta sobre orçamento, LRF, PCA ou contratos…"
            rows={2}
            className="field-input resize-none flex-1"
          />
          <button
            type="button"
            onClick={enviar}
            disabled={desabilitado}
            className="shrink-0 w-28 rounded-lg bg-accent-500 text-lente-900 font-semibold text-sm tracking-wide hover:bg-accent-400 disabled:bg-surface-overlay disabled:text-text-muted disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-1.5"
          >
            <span>Enviar</span>
            <span aria-hidden>→</span>
          </button>
        </div>
        <p className="mt-2 text-[10px] font-mono uppercase tracking-wider text-text-muted">
          Gemini 3.1 Flash Lite + pgvector · citação obrigatória · Enter envia, Shift+Enter quebra linha · 20 req/min
        </p>
      </div>

      {fonteAberta && (
        <FonteDrawer fonte={fonteAberta} onClose={() => setFonteAberta(null)} />
      )}
    </div>
  );
}
