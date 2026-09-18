import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import UploadTaskEditor from '../../frontend/src/components/UploadTaskEditor'
import { api } from '../../frontend/src/lib/api'
import type { ApiError } from '../../frontend/src/lib/api'
import type { DraftMaterialState, UploadDraft } from '../../frontend/src/lib/paperProcessing'

vi.mock('../../frontend/src/lib/api', () => ({
  api: { get: vi.fn(), put: vi.fn(), post: vi.fn() },
}))

vi.mock('../../frontend/src/lib/classifications', async importOriginal => {
  const actual = await importOriginal<typeof import('../../frontend/src/lib/classifications')>()
  return {
    ...actual,
    loadClassificationCatalogs: vi.fn(async () => ({
      material_families: [{ id: 1, name: '氢基超导体', aliases: ['hydride'] }],
      structure_families: [{ id: 10, name: '笼状结构', aliases: ['clathrate'] }],
      material_dimensionalities: [{ value: 'unknown', name: '未知' }],
    })),
  }
})

vi.mock('../../frontend/src/components/StructureCandidatePanel', () => ({
  default: () => <div data-testid="structure-candidate-panel" />,
}))

const mockedApi = vi.mocked(api)
// 预检与最终提交是两个不同端点；错误用例只控制最终提交响应。
const submitRequest = vi.fn()

const makeState = (overrides: Partial<DraftMaterialState> = {}): DraftMaterialState => ({
  material: 'LaH10',
  structure_families: [],
  element_count: 2,
  material_dimensionality: 'unknown',
  tc_results: [],
  properties: [],
  ...overrides,
})

const makeDraft = (states: DraftMaterialState[], paper: Record<string, unknown> = {}) => ({
  paper: {
    title: '测试论文', authors: [], paper_type: 'experimental',
    material_families: [{ id: 1, name: '氢基超导体', status: 'confirmed' }],
    keywords_tags: ['超导'], methodology: ['高压合成'],
    ...paper,
  },
  material_states: states,
  structure_candidates: [], classification_evidence: [], field_evidence: {},
} as UploadDraft)

const collapseContent = (index: number) => document.getElementById(`material-state-${index}-content`)
const collapseState = async (index: number) => {
  fireEvent.click(document.querySelector(`[data-material-state-index="${index}"] [data-state-toggle]`)!)
  await waitFor(() => expect(collapseContent(index)).not.toHaveClass('MuiCollapse-entered'))
}

const clickSubmit = async () => {
  fireEvent.click(await screen.findByRole('button', { name: '提交审核' }))
}

beforeEach(() => {
  mockedApi.get.mockImplementation((url: string) => {
    if (String(url).includes('/space-groups')) {
      return Promise.resolve({ space_groups: [{ number: 139, symbol: 'I4/mmm' }] } as never)
    }
    return Promise.resolve({ ok: true, data: makeDraft([makeState()]) } as never)
  })
  mockedApi.put.mockResolvedValue({ ok: true } as never)
  submitRequest.mockReset().mockResolvedValue({ ok: true, paper_id: 99, review_status: 'pending' })
  mockedApi.post.mockImplementation(async (path, body) => {
    if (path === '/api/rag/evidence/preflight') {
      return { version: 'checked-version', needs_check: false, records: [], sources: [] } as never
    }
    if (path === '/api/rag/evidence/proposals/prepare') return { preparation_id: null, patches: [] } as never
    if (path.endsWith('/submit')) return submitRequest(body)
    throw new Error(`unexpected POST ${path}`)
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('提交失败的必填定位与原因展示（Issue #58）', () => {
  it('模块化物性错误汇总具体消息并展开定位到对应记录', async () => {
    const failure = Object.assign(new Error('科学数据校验失败'), {
      status: 400,
      code: 'schema_validation_failed',
      detail: '科学数据校验失败',
      issues: [{
        field: 'material_states[0].property_modules[0].records[0].custom_property_key',
        code: 'schema_validation_failed',
        message: '规范性质不能携带自定义键',
      }],
    }) as ApiError
    submitRequest.mockRejectedValue(failure)
    const record = {
      record_key: 'tc-1', module_code: 'superconductive_properties', record_type: 'measured_tc', property_code: 'tc',
      custom_property_key: 'stale-key', definition_key: 'record.superconductive_properties.measured_tc.resistivity',
      definition_version: 1, name_raw: 'Tc', value_kind: 'number', value_raw: '203 K', value_number: 203,
      canonical_unit: 'K', method_code: 'resistivity', payload: { experimental_conditions: {} },
    }
    render(<UploadTaskEditor
      taskId={'7'.repeat(32)}
      onSubmitted={vi.fn()}
      draftOverride={makeDraft([makeState({ property_modules: [{
        module_key: 'module-superconductive_properties', module_code: 'superconductive_properties',
        definition_key: 'module.superconductive_properties', definition_version: 1, display_order: 0, records: [record],
      }] })])}
    />)

    await clickSubmit()

    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent('规范性质不能携带自定义键')
    await waitFor(() => expect(document.querySelector('[data-issue-field="material_states.0.property_modules.0.records.0.custom_property_key"]')).not.toBeNull())
  })

  it('多处缺失时横幅汇总全部项而不是只报第一条，且不发起提交请求', async () => {
    render(<UploadTaskEditor
      taskId={'a'.repeat(32)}
      onSubmitted={vi.fn()}
      draftOverride={makeDraft(
        [makeState({ material: 'LaH10' }), makeState({ material: 'H3S' }), makeState({ material: '' })],
        { title: '' },
      )}
    />)

    await clickSubmit()

    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent('标题不能为空')
    expect(banner).toHaveTextContent('第 3 个材料状态至少需要材料名或化学式')
    expect(submitRequest).not.toHaveBeenCalled()
    expect(mockedApi.put).not.toHaveBeenCalled()
    expect(mockedApi.post.mock.calls.every(([path]) => path === '/api/rag/evidence/preflight')).toBe(true)
  })

  it('出错字段位于手动折叠的卡片内时展开该卡片并显示字段错误提示', async () => {
    render(<UploadTaskEditor
      taskId={'b'.repeat(32)}
      onSubmitted={vi.fn()}
      draftOverride={makeDraft([
        makeState({ material: 'LaH10' }),
        makeState({ material: 'H3S' }),
        makeState({ material: '' }),
      ])}
    />)

    await screen.findByText('材料状态 #1')
    await collapseState(2)

    await clickSubmit()

    await waitFor(() => {
      expect(collapseContent(2)).toHaveClass('MuiCollapse-entered')
    })
    const anchor = document.querySelector('[data-issue-field="material_states[2].material_name"]')
    expect(anchor).not.toBeNull()
    expect(anchor).toHaveTextContent('第 3 个材料状态至少需要材料名或化学式')
  })

  it('空间群号越界时定位到该字段并展示区间提示', async () => {
    render(<UploadTaskEditor
      taskId={'c'.repeat(32)}
      onSubmitted={vi.fn()}
      draftOverride={makeDraft([makeState({ reported_space_group_number: 999 })])}
    />)

    await clickSubmit()

    const anchor = document.querySelector('[data-issue-field="material_states[0].reported_space_group_number"]')
    expect(anchor).not.toBeNull()
    await waitFor(() => {
      expect(anchor).toHaveTextContent('空间群号必须在 1–230 之间')
    })
  })

  it('后端专属校验错误按 message 中的序号定位到对应卡片', async () => {
    const failure = Object.assign(new Error('压强区间无效'), {
      status: 400,
      code: 'invalid_pressure_range',
      detail: { code: 'invalid_pressure_range', message: '第 2 个材料状态的压强区间 min 不能大于 max' },
    }) as ApiError
    submitRequest.mockRejectedValue(failure)

    render(<UploadTaskEditor
      taskId={'d'.repeat(32)}
      onSubmitted={vi.fn()}
      draftOverride={makeDraft([
        makeState({ material: 'LaH10' }),
        makeState({ material: 'H3S' }),
        makeState({ material: 'MgB2' }),
      ])}
    />)

    await screen.findByText('材料状态 #1')
    await collapseState(1)

    await clickSubmit()

    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent('第 2 个材料状态的压强区间 min 不能大于 max')
    expect(banner).toHaveTextContent('invalid_pressure_range')
    await waitFor(() => {
      expect(collapseContent(1)).toHaveClass('MuiCollapse-entered')
    })
  })

  it('后端错误 message 中没有材料状态序号时只展示横幅，不做定位也不报错', async () => {
    const failure = Object.assign(new Error('论文标题不能为空'), {
      status: 400,
      code: 'title_required',
      detail: { code: 'title_required', message: '论文标题不能为空' },
    }) as ApiError
    submitRequest.mockRejectedValue(failure)

    render(<UploadTaskEditor
      taskId={'e'.repeat(32)}
      onSubmitted={vi.fn()}
      draftOverride={makeDraft([makeState()])}
    />)

    await clickSubmit()

    expect(await screen.findByText(/论文标题不能为空/)).toBeInTheDocument()
  })

  it('未捕获异常返回结构化 detail 时展示后端原因而非通用文案', async () => {
    const failure = Object.assign(new Error('internal'), {
      status: 500,
      code: 'internal_error',
      detail: { code: 'internal_error', message: '服务器内部错误，请稍后重试' },
    }) as ApiError
    submitRequest.mockRejectedValue(failure)

    render(<UploadTaskEditor
      taskId={'f'.repeat(32)}
      onSubmitted={vi.fn()}
      draftOverride={makeDraft([makeState()])}
    />)

    await clickSubmit()

    expect(await screen.findByText(/服务器内部错误/)).toBeInTheDocument()
    expect(screen.queryByText('提交审核失败')).not.toBeInTheDocument()
  })

  it('修正缺失项后重新提交成功，错误态与横幅被清除', async () => {
    const onSubmitted = vi.fn()
    render(<UploadTaskEditor
      taskId={'0'.repeat(32)}
      onSubmitted={onSubmitted}
      draftOverride={makeDraft([makeState({ material: '' })])}
    />)

    await clickSubmit()
    expect(await screen.findByRole('alert')).toHaveTextContent('第 1 个材料状态至少需要材料名或化学式')

    fireEvent.change(screen.getByLabelText('化学式'), { target: { value: 'LaH10' } })
    await clickSubmit()

    await waitFor(() => {
      expect(onSubmitted).toHaveBeenCalledWith(99)
      expect(submitRequest).toHaveBeenCalledTimes(1)
      expect(submitRequest).toHaveBeenCalledWith(expect.objectContaining({
        expected_evidence_version: 'checked-version',
      }))
    })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('后端返回「第 N 个材料状态缺少化学式」时仍能解析序号并定位到出错卡片', async () => {
    const failure = Object.assign(new Error('第 2 个材料状态缺少化学式'), {
      status: 400,
      code: 'state_material_required',
      detail: { code: 'state_material_required', message: '第 2 个材料状态缺少化学式' },
    }) as ApiError
    submitRequest.mockRejectedValue(failure)

    render(<UploadTaskEditor
      taskId={'9'.repeat(32)}
      onSubmitted={vi.fn()}
      draftOverride={makeDraft([makeState({ material: 'LaH10' }), makeState({ material: 'H3S' })])}
    />)

    await screen.findByText('材料状态 #1')
    await collapseState(1)
    await clickSubmit()

    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent('第 2 个材料状态缺少化学式')
    expect(submitRequest).toHaveBeenCalledTimes(1)

    // 序号前缀仍被解析：第二张卡片展开并挂上字段错误锚点
    await waitFor(() => {
      expect(collapseContent(1)).toHaveClass('MuiCollapse-entered')
    })
    const anchor = document.querySelector('[data-issue-field="material_states[1].material"]')
    expect(anchor).not.toBeNull()
    expect(anchor).toHaveTextContent('第 2 个材料状态缺少化学式')
  })
})
