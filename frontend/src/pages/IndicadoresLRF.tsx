import { useMemo, useState } from "react";
import { useExerciciosOrcamento, useIndicadoresFiscais } from "@/api/hooks";
import type { IndicadorFiscal, SituacaoIndicador } from "@/api/types";
import {
  DataSourceStrip,
  EmptyState,
  PageHeader,
} from "@/components/PageChrome";
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
  LIMITE_ALERTA_PESSOAL: {
    ordem: 3,
    tipoLimite: "MAXIMO",
    referencia: "LRF Art. 59 §1º IV",
  },
  DIVIDA_CONSOLIDADA_PCT_RCL: {
    ordem: 4,
    tipoLimite: "MAXIMO",
    referencia: "Res. Senado 40/2001",
  },
  OP_CREDITO_PCT_RCL: {
    ordem: 5,
    tipoLimite: "MAXIMO",
    referencia: "Res. Senado 43/2001",
  },
  GARANTIAS_PCT_RCL: {
    ordem: 6,
    tipoLimite: "MAXIMO",
    referencia: "Res. Senado 43/2001",
  },
  RESULTADO_PRIMARIO: {
    ordem: 7,
    tipoLimite: "MINIMO",
    referencia: "LRF Art. 4º §1º I e Art. 9º",
  },
  RESULTADO_NOMINAL: {
    ordem: 8,
    tipoLimite: "MINIMO",
    referencia: "LRF Art. 4º §1º I e Art. 9º",
  },
  SUFICIENCIA_FINANCEIRA_RP: {
    ordem: 9,
    tipoLimite: "MINIMO",
    referencia: "LRF Art. 42",
  },
  APLIC_MIN_SAUDE_PCT: {
    ordem: 10,
    tipoLimite: "MINIMO",
    referencia: "CF Art. 198 §2º",
  },
  APLIC_MIN_EDUCACAO_PCT: {
    ordem: 11,
    tipoLimite: "MINIMO",
    referencia: "CF Art. 212",
  },
};

const SITUACAO_RESUMO: Record<
  SituacaoIndicador,
  { label: string; tom: string; bar: string; panel: string }
> = {
  OK: {
    label: "Dentro dos limites",
    tom: "text-success-500",
    bar: "bg-success-500",
    panel: "border-success-500/25 bg-success-500/[0.045]",
  },
  ALERTA: {
    label: "Atenção — próximo do limite",
    tom: "text-warning-500",
    bar: "bg-warning-500",
    panel: "border-warning-500/30 bg-warning-500/[0.05]",
  },
  EXCEDIDO: {
    label: "Limite ultrapassado",
    tom: "text-danger-500",
    bar: "bg-danger-500",
    panel: "border-danger-500/30 bg-danger-500/[0.05]",
  },
  ABAIXO_MINIMO: {
    label: "Abaixo do mínimo legal",
    tom: "text-danger-500",
    bar: "bg-danger-500",
    panel: "border-danger-500/30 bg-danger-500/[0.05]",
  },
  SEM_DADO: {
    label: "Sem dado publicado",
    tom: "text-text-muted",
    bar: "bg-text-muted",
    panel: "border-border bg-surface-raised",
  },
};

function IndicadorCard({ indicador }: { indicador: IndicadorFiscal }) {
  const meta = METADATA[indicador.codigo];
  const resumo = SITUACAO_RESUMO[indicador.situacao];

  return (
    <article
      className={`group relative overflow-hidden rounded-xl border p-6 space-y-5 transition-colors hover:border-accent-500/40 ${resumo.panel}`}
    >
      <span
        className={`absolute inset-x-0 top-0 h-[2px] ${resumo.bar}`}
        aria-hidden
      />
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
        unidade={
          indicador.unidade === "MONETARIO" ? "MONETARIO" : "PERCENTUAL"
        }
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
      <PageHeader
        eyebrow="Responsabilidade fiscal"
        title="Indicadores LRF"
        description="Cumprimento da Lei de Responsabilidade Fiscal, limites de endividamento e mínimos constitucionais calculados a partir dos relatórios fiscais ingeridos."
        actions={
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
        }
      />

      <DataSourceStrip
        items={["RGF", "RREO", "Constituição Federal", "LRF"]}
        note="Cada cartão mostra valor apurado, referência legal e situação derivada pelo backend."
      />

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
        <EmptyState
          title="Nenhum indicador derivado"
          description={`Não há indicadores fiscais para ${anoSelecionado ?? "—"}. Verifique se os relatórios RGF/RREO desse exercício foram ingeridos no backend.`}
        />
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
