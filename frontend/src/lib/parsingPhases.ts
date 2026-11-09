// 运行阶段与科学字段分开；只表达服务端实际报告的动作。
const labels: Record<string, [string, string]> = {
  paper_extracting: ['读取论文级信息', 'Reading paper information'],
  paper_filling: ['填写论文级字段', 'Filling paper fields'],
  paper_reviewing: ['核对并保存论文级字段', 'Reviewing and saving paper fields'],
  paper_reviewed: ['论文级核对已保存', 'Paper review saved'],
  chart_reading: ['逐页找图并读取科学数据', 'Finding figures and reading scientific data'],
  workflow_selection: ['判断材料状态适用流程', 'Selecting material workflow'],
  material_extracting: ['并发提取材料状态与科学结果', 'Extracting material states and results'],
  material_identifying: ['规划材料状态及其归属', 'Organizing material states'],
  material_filling: ['填写材料状态字段', 'Filling material fields'],
  material_reviewing: ['核对并保存材料状态字段', 'Reviewing and saving material fields'],
  material_saving: ['保存本组材料状态', 'Saving this material group'],
}

export function parsingPhaseLabel(phase: string | undefined, lang: string): string | undefined {
  return phase ? labels[phase]?.[lang === 'zh' ? 0 : 1] : undefined
}
