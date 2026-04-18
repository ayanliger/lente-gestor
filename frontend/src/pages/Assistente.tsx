import { useMemo, useRef, useState } from "react";
import { type ChatResponse, type FonteCitada, useChat } from "@/api/chat";

/**
 * Linha de mensagem: pergunta do usuário ou resposta do assistente.
 * Mantida em memória do browser — zero persistência.
 */
interface Mensagem {
  id: string;
  autor: "usuario" | "assistente";
  texto: string;
  fontes?: FonteCitada[];
  recusou?: boolean;
  latenciaMs?: number;
}

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
        className="flex-1 bg-surface/70 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <aside
        className="w-full max-w-md overflow-y-auto bg-surface-raised border-l border-border p-6 animate-fade-up"
        role="dialog"
        aria-label="Detalhes da fonte"
      >
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-accent-400/80">
              Fonte [{fonte.indice}]
            </p>
            <h3 className="font-display text-lg text-text-primary mt-1 leading-tight">
              {fonte.titulo}
            </h3>
            <p className="font-mono text-[11px] text-text-muted mt-1">
              {fonte.fonte} · score {(fonte.score * 100).toFixed(1)}%
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-text-muted hover:text-text-primary transition-colors text-xl leading-none"
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
              className="inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-wider text-accent-400 hover:text-accent-300 transition-colors"
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
      className="inline-flex items-center justify-center h-5 min-w-[22px] px-1.5 mx-0.5 rounded-md bg-accent-500/20 border border-accent-500/40 text-[11px] font-mono text-accent-300 hover:bg-accent-500/30 hover:text-accent-200 transition-colors align-baseline"
      title={fonte.titulo}
    >
      {fonte.indice}
    </button>
  );
}

function MensagemUsuario({ texto }: { texto: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] bg-lente-700/70 border border-lente-500/40 rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm text-text-primary whitespace-pre-wrap">
        {texto}
      </div>
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
      <div className="flex justify-start">
        <div className="max-w-[80%] bg-warning-500/[0.06] border border-warning-500/30 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-warning-500">
          <p className="font-medium">Não tenho dados suficientes para responder com confiança.</p>
          <p className="text-xs text-text-secondary mt-1">
            Experimente reformular a pergunta, ou verifique se os dados
            correspondentes foram ingeridos.
          </p>
        </div>
      </div>
    );
  }

  const fontesPorIndice = new Map(
    (mensagem.fontes ?? []).map((f) => [f.indice, f]),
  );
  const segmentos = segmentar(mensagem.texto);

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] bg-surface-raised/70 border border-border rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-text-primary leading-relaxed">
        <p className="whitespace-pre-wrap">
          {segmentos.map((s, i) =>
            s.tipo === "texto" ? (
              <span key={i}>{s.valor}</span>
            ) : (() => {
              const fonte = fontesPorIndice.get(s.indice);
              if (!fonte) {
                // Índice que não veio no array de fontes — renderiza como texto plano
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
          <div className="mt-3 pt-2 border-t border-border/60 flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted">
              fontes:
            </span>
            {mensagem.fontes.map((f) => (
              <button
                key={f.indice}
                type="button"
                onClick={() => onAbrirFonte(f)}
                className="text-[11px] font-mono text-text-secondary hover:text-accent-400 transition-colors"
              >
                [{f.indice}] {f.titulo.length > 42 ? f.titulo.slice(0, 40) + "…" : f.titulo}
              </button>
            ))}
          </div>
        )}
        {mensagem.latenciaMs != null && (
          <p className="mt-2 text-[10px] font-mono text-text-muted">
            {(mensagem.latenciaMs / 1000).toFixed(1)}s
          </p>
        )}
      </div>
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
      { id: idUsuario, autor: "usuario", texto: pergunta },
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
      <header className="pb-6 border-b border-border/60">
        <p className="text-[11px] font-mono uppercase tracking-[0.28em] text-accent-400/80 mb-2">
          Assistente
        </p>
        <h1 className="font-display text-3xl md:text-4xl tracking-tight text-text-primary leading-[1.05]">
          Pergunte à sua base
        </h1>
        <p className="text-text-secondary text-sm mt-3 max-w-2xl">
          Respostas em linguagem natural sobre orçamento, indicadores fiscais
          e contratos de Jequié — <span className="text-text-primary">sempre com citação à fonte</span>.
          Se o dado não está na base, o assistente recusa em vez de inventar.
        </p>
      </header>

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
                  className="text-left text-sm text-text-secondary bg-surface-raised/40 border border-border hover:border-lente-500/40 hover:bg-lente-800/20 hover:text-text-primary transition-all rounded-lg px-4 py-2.5"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {mensagens.map((m) =>
          m.autor === "usuario" ? (
            <MensagemUsuario key={m.id} texto={m.texto} />
          ) : (
            <MensagemAssistente
              key={m.id}
              mensagem={m}
              onAbrirFonte={setFonteAberta}
            />
          ),
        )}

        {chat.isPending && (
          <div className="flex justify-start">
            <div className="bg-surface-raised/60 border border-border rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-text-muted flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-accent-500 animate-pulse" />
              pensando…
            </div>
          </div>
        )}
      </div>

      {/* Input fixo embaixo */}
      <div className="pt-4 border-t border-border/60">
        <div className="relative">
          <textarea
            value={entrada}
            onChange={(e) => setEntrada(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                enviar();
              }
            }}
            placeholder="Faça uma pergunta sobre orçamento, LRF, PCA ou contratos…"
            rows={2}
            className="field-input resize-none pr-24"
          />
          <button
            type="button"
            onClick={enviar}
            disabled={desabilitado}
            className="absolute right-2 bottom-2 px-4 py-1.5 rounded-md bg-accent-500 text-surface font-medium text-sm hover:bg-accent-400 disabled:bg-surface-overlay disabled:text-text-muted disabled:cursor-not-allowed transition-colors"
          >
            Enviar
          </button>
        </div>
        <p className="mt-2 text-[10px] font-mono uppercase tracking-wider text-text-muted">
          Gemini 3.1 Pro + pgvector · respostas com citação obrigatória · 20 req/min
        </p>
      </div>

      {fonteAberta && (
        <FonteDrawer fonte={fonteAberta} onClose={() => setFonteAberta(null)} />
      )}
    </div>
  );
}
