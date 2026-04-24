import { useMemo, useState } from "react";
import { useExerciciosOrcamento, useIndicadoresFiscais } from "@/api/hooks";
import type { IndicadorFiscal, SituacaoIndicador } from "@/api/types";
import Termometro from "@/components/Termometro";

// Metadata visual por indicador, complementar ao retorno da API.
const METADATA: Record<
  string,
  { ordem: number; tipoLimite: "MAXIMO" | "MINIMO"; referencia: string }
> = {
  DESPESA_PESSOAL_PCT_RCL: {
    ordem: 1,
    tipoLimite: "MAXIMO",
    referencia: "LC 101/2000 Art. 20",
  },
  DESPESA_PESSOAL_PRUDENCIAL: {
    ordem: 2,
    tipoLimite: "MAXIMO",
    referencia: "LRF Art. 22 §único",
  },
  DIVIDA_CONSOLIDADA_PCT_RCL: {
    ordem: 3,
    tipoLimite: "MAXIMO",
    referencia: "Res. Senado 40/2001",
  },
  OP_CREDITO_PCT_RCL: {
    ordem: 4,
    tipoLimite: "MAXIMO",
    referencia: "Res. Senado 43/2001",
  },
  GARANTIAS_PCT_RCL: {
    ordem: 5,
    tipoLimite: "MAXIMO",
    referencia: "Res. Senado 43/2001",
  },
  APLIC_MIN_SAUDE_PCT: {
    ordem: 6,
    tipoLimite: "MINIMO",
    referencia: "CF Art. 198 §2º",
  },
  APLIC_MIN_EDUCACAO_PCT: {
    ordem: 7,
    tipoLimite: "MINIMO",
    referencia: "CF Art. 212",
  },
};

const SITUACAO_RESUMO: Record<
  SituacaoIndicador,
  { label: string; tom: string }
> = {
  OK: { label: "Dentro dos limites", tom: "text-success-500" },
  ALERTA: { label: "Atenção — próximo do limite", tom: "text-warning-500" },
  EXCEDIDO: { label: "Limite ultrapassado", tom: "text-danger-500" },
  ABAIXO_MINIMO: { label: "Abaixo do mínimo legal", tom: "text-danger-500" },
  SEM_DADO: { label: "Sem dado publicado", tom: "text-text-muted" },
};

function IndicadorCard({ indicador }: { indicador: IndicadorFiscal }) {
  const meta = METADATA[indicador.codigo];
  const resumo = SITUACAO_RESUMO[indicador.situacao];

  return (
    <article className="group bg-surface-raised border border-border rounded-xl p-6 space-y-5 hover:border-accent-500/40 transition-colors">
      <header>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-text-primary leading-tight">
              {indicador.descricao}
            </h3>
            <p className="font-mono text-[10px] text-text-muted tracking-wider mt-1 uppercase">
              {indicador.codigo}
            </p>
          </div>
          <span className="shrink-0 text-xs font-mono text-text-muted">
            {indicador.fonte_relatorio}
            {indicador.fonte_periodo != null
              ? ` · P${indicador.fonte_periodo}`
              : ""}
          </span>
        </div>
        <p className={`text-xs mt-2 ${resumo.tom}`}>{resumo.label}</p>
      </header>

      <Termometro
        valor={indicador.valor}
        limite={indicador.limite_legal}
        tipoLimite={meta?.tipoLimite ?? "MAXIMO"}
        situacao={indicador.situacao}
      />

      {meta && (
        <footer className="border-t border-border pt-3 text-[10px] text-text-muted font-mono uppercase tracking-wider">
          {meta.referencia}
        </footer>
      )}
    </article>
  );
}

export default function IndicadoresLRF() {
  const exerciciosQuery = useExerciciosOrcamento();
  const exerciciosDisponiveis = exerciciosQuery.data ?? [];
  const [exercicio, setExercicio] = useState<number | undefined>(undefined);
  const anoSelecionado = exercicio ?? exerciciosDisponiveis[0];
  const { data, isLoading } = useIndicadoresFiscais({
    exercicio: anoSelecionado,
  });

  const indicadoresOrdenados = useMemo(() => {
    if (!data) return [];
    return [...data].sort((a, b) => {
      const oa = METADATA[a.codigo]?.ordem ?? 99;
      const ob = METADATA[b.codigo]?.ordem ?? 99;
      return oa - ob;
    });
  }, [data]);

  const resumoGeral = useMemo(() => {
    if (!data) return null;
    const contagem = data.reduce<Record<SituacaoIndicador, number>>(
      (acc, i) => {
        acc[i.situacao] = (acc[i.situacao] ?? 0) + 1;
        return acc;
      },
      { OK: 0, ALERTA: 0, EXCEDIDO: 0, ABAIXO_MINIMO: 0, SEM_DADO: 0 },
    );
    return contagem;
  }, [data]);

  return (
    <div className="space-y-8 animate-fade-up">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl tracking-tight text-text-primary">
            Indicadores LRF
          </h1>
          <p className="text-text-secondary text-sm mt-2 max-w-xl">
            Cumprimento da Lei de Responsabilidade Fiscal e mínimos
            constitucionais.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-text-muted">
            Exercício
          </span>
          <select
            value={anoSelecionado ?? ""}
            onChange={(e) => setExercicio(Number(e.target.value))}
            className="field-select"
            disabled={exerciciosDisponiveis.length === 0}
          >
            {exerciciosDisponiveis.length === 0 && (
              <option value="">—</option>
            )}
            {exerciciosDisponiveis.map((ano) => (
              <option key={ano} value={ano}>
                {ano}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Resumo geral */}
      {resumoGeral && (
        <div className="flex flex-wrap gap-2">
          {resumoGeral.OK > 0 && (
            <span className="badge badge-success">
              <span className="font-mono tabular-nums">{resumoGeral.OK}</span>
              · OK
            </span>
          )}
          {resumoGeral.ALERTA > 0 && (
            <span className="badge badge-warning">
              <span className="font-mono tabular-nums">
                {resumoGeral.ALERTA}
              </span>
              · em alerta
            </span>
          )}
          {resumoGeral.EXCEDIDO > 0 && (
            <span className="badge badge-danger">
              <span className="font-mono tabular-nums">
                {resumoGeral.EXCEDIDO}
              </span>
              · excedido
            </span>
          )}
          {resumoGeral.ABAIXO_MINIMO > 0 && (
            <span className="badge badge-danger">
              <span className="font-mono tabular-nums">
                {resumoGeral.ABAIXO_MINIMO}
              </span>
              · abaixo do mínimo
            </span>
          )}
          {resumoGeral.SEM_DADO > 0 && (
            <span className="badge badge-muted">
              <span className="font-mono tabular-nums">
                {resumoGeral.SEM_DADO}
              </span>
              · sem dado
            </span>
          )}
        </div>
      )}

      {isLoading ? (
        <p className="text-text-muted text-sm">Carregando indicadores…</p>
      ) : indicadoresOrdenados.length === 0 ? (
        <p className="text-text-muted text-sm">
          Nenhum indicador derivado para {exercicio}. Execute{" "}
          <code className="font-mono text-text-secondary">
            make ingest-rgf ano={exercicio}
          </code>{" "}
          no backend.
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {indicadoresOrdenados.map((i) => (
            <IndicadorCard key={i.id} indicador={i} />
          ))}
        </div>
      )}
    </div>
  );
}
