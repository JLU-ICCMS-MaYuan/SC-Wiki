// 确定性隔离性能数据，不是任何论文或用户草稿。
export function makeWorkdraft(stateCount = 40, quoteSize = 1200) {
  const quote = 'Synthetic performance evidence. '.repeat(Math.ceil(quoteSize / 32)).slice(0, quoteSize)
  return { paper: { id: 186, title: 'Isolated workdraft benchmark', knowledge_graph_title: 'Workdraft benchmark',
    year: 2026, authors: [], paper_type: 'theoretical', theoretical_subtype: 'calculation',
    superconductor_kind: 'conventional', material_families: [{ id: 1, name: '隔离性能材料' }], research_materials: ['Sn'] },
    material_states: Array.from({ length: stateCount }, (_, si) => ({
      state_key: 'state-' + si, material: 'Sn', material_name: 'State ' + si, state_kind: 'theoretical',
      pressure_value_gpa: 100 + si, structure_optimization: 'classical_static', crystal_system: 'unknown',
      material_dimensionality: 'three_dimensional', structure_families: [], schema_version: 2,
      property_modules: [{ module_key: 'module-' + si, module_code: 'superconductive_properties',
        definition_key: 'module.superconductive_properties', definition_version: 1, display_order: 0,
        records: Array.from({ length: 6 }, (_, pi) => {
          const method = pi < 3 ? 'isotropic_eliashberg' : 'allen_dynes'
          return { record_key: 'record-' + si + '-' + pi, module_code: 'superconductive_properties',
            record_type: 'predicted_tc', property_code: 'tc', method_code: method,
            definition_key: 'record.superconductive_properties.predicted_tc.' + method, definition_version: 1,
            name_raw: 'Tc', value_kind: 'number', value_number: 230 - pi * 10, value_raw: String(230 - pi * 10),
            unit_raw: 'K', canonical_unit: 'K', is_representative: false, evidences: [{ file_id: 'main', quote }],
            payload: { parameters: { lambda_ep: 2.69, omega_log: 800, mu_star: 0.10 + (pi % 3) * .03 },
              calculation_conditions: { calculation_code: 'Quantum ESPRESSO', electronic_method: 'DFT',
                k_grid: '24x24x24', extensions: [] },
              tc_group: { version: 1, group_key: 'group-' + si, method_key: 'method-' + method, point_key: 'point-' + pi },
              source_associations: Array.from({ length: 6 }, (_, j) => ({
                version: 1, target_path: '/payload/calculation_conditions/k_grid', stage: 'electron_phonon',
                basis_kind: 'paper_inference', explanation: 'Synthetic common scope ' + j,
                scope: { material: 'Sn', pressure_value_gpa: 100 + si },
                source_fingerprint: 'a'.repeat(64), target_fingerprint: 'b'.repeat(64),
                fact_evidences: [{ file_id: 'main', quote }], scope_evidences: [{ file_id: 'main', quote }],
              })),
            },
          }
        }),
      }],
    })),
    structure_candidates: [],
  }
}
