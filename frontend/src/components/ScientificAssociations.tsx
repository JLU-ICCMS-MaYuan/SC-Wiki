import { Alert, Box, Typography } from '@mui/material'
import { useLanguage } from '../context/LanguageContext'
import { EvidenceRegion } from './EvidenceRegion'
import type { EvidenceSource, EvidenceTarget } from './EvidenceWorkflow'

export interface ScientificAssociation {
  target_path: string
  stage: string
  basis_kind: 'paper_quote' | 'paper_inference'
  explanation: string
  reported_value_raw?: string
  stale?: boolean
  fact_evidences: EvidenceSource[]
  scope_evidences: EvidenceSource[]
}

/** 沿用证据抽屉的理由和原文入口，分别展示值与适用范围。 */
export default function ScientificAssociations({ associations, target }: { associations?: ScientificAssociation[]; target?: EvidenceTarget }) {
  const { lang } = useLanguage()
  const zh = lang === 'zh'
  const stages: Record<string, string> = zh ? { electron_phonon:'声子／电声耦合', structural_relaxation:'结构优化',
    electronic_structure:'电子结构', sscha:'SSCHA 非谐计算', aimd:'分子动力学', superconductivity:'超导计算' } : {}
  const fields: Record<string, string> = zh ? { k_grid:'k 网格', q_grid:'q 网格', calculation_code:'计算软件',
    electronic_method:'电子结构方法', exchange_correlation_functional:'交换关联泛函', k_broadening:'k 展宽', q_broadening:'q 展宽',
    lambda_ep:'电声耦合强度 λ', omega_log:'ωlog', mu_star:'μ*' } : {}
  return <>{(associations || []).map((a, index) => <Box key={a.target_path + ':' + index} sx={{ my: 1 }}>
    <Alert severity={a.stale ? 'warning' : 'info'}>
      {a.stale ? (zh ? '旧关联已失效，请重新核对' : 'Association is stale; review again') :
        a.basis_kind === 'paper_inference' ? (zh ? '由本文推断共用范围，待人工核对' : 'Shared scope inferred from this paper; review required') :
          (zh ? '作者明确报告的共用范围' : 'Shared scope explicitly reported by the authors')}
    </Alert>
    <Typography variant="body2">{stages[a.stage] || a.stage} · {fields[a.target_path.split('/').at(-1) || ''] ||
      (zh ? '补充参数' : 'Additional setting')}{a.reported_value_raw ? ' — ' + a.reported_value_raw : ''}</Typography>
    <Typography sx={{ whiteSpace: 'pre-wrap' }}>{a.explanation}</Typography>
    <Box component="details"><Typography component="summary">{zh ? '参数值与适用范围的原文' : 'Sources for the value and scope'}</Typography>
      {([['fact_evidences', zh ? '参数值来源' : 'Value sources'], ['scope_evidences', zh ? '适用范围来源' : 'Scope sources']] as const).map(([key, label]) => <Box key={key}>
        <Typography fontWeight={600}>{label}</Typography>
        {a[key].map((source, i) => <EvidenceRegion key={key + i} source={source} target={target} />)}
      </Box>)}
    </Box>
  </Box>)}</>
}
