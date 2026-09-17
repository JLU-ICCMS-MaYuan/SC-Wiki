import React, { useEffect, useRef, useState } from 'react'
import { Box, IconButton, Tooltip, Typography } from '@mui/material'
import RotateRightIcon from '@mui/icons-material/RotateRight'
import ZoomInIcon from '@mui/icons-material/ZoomIn'
import ZoomOutIcon from '@mui/icons-material/ZoomOut'
import CenterFocusStrongIcon from '@mui/icons-material/CenterFocusStrong'
import { crystalStructureData, normalizeCrystalMatrix, type CrystalStructureData } from '../lib/crystalStructure'
import { useLanguage } from '../context/LanguageContext'

/* ── 3D 晶体结构查看器（3Dmol.js，动态加载避免主包膨胀）── */

interface Props {
  data: string          // 结构文本（CIF / POSCAR …）
  format?: string       // 3Dmol 格式名：cif、vasp 等，默认 cif
  height?: number | string
  onStructureData?: (data: CrystalStructureData | null) => void
  controls?: boolean
  showLegend?: boolean
}

interface LegendItem { el: string; color: string }

const StructureViewer3D: React.FC<Props> = ({ data, format = 'cif', height = 320, onStructureData, controls = false, showLegend = true }) => {
  const { t } = useLanguage()
  const ref = useRef<HTMLDivElement>(null)
  const [error, setError] = useState('')
  const [legend, setLegend] = useState<LegendItem[]>([])
  const viewerRef = useRef<any>(null)
  const initialView = useRef<any>(null)
  const parsedRef = useRef(onStructureData)
  parsedRef.current = onStructureData

  useEffect(() => {
    let viewer: any
    let resizeObserver: ResizeObserver | undefined
    let cancelled = false
    setError('')
    setLegend([])
    if (!data || !ref.current) { parsedRef.current?.(null); return }
    import('3dmol').then(($3Dmol: any) => {
      if (cancelled || !ref.current) return
      // orthographic: 正交投影，无近大远小透视变形
      // 切换候选/晶胞时复用 WebGL 上下文，避免反复创建导致浏览器回收旧画布。
      viewer = viewerRef.current || $3Dmol.createViewer(ref.current, { backgroundColor: '#f8fafc', orthographic: true })
      viewerRef.current = viewer
      const model = viewer.addModel(data, format)
      normalizeCrystalMatrix(model, format)
      // 球棍模型（Jmol 元素配色）+ 晶胞线框
      viewer.setStyle({}, { sphere: { scale: 0.32, colorscheme: 'Jmol' }, stick: { radius: 0.12, colorscheme: 'Jmol' } })
      viewer.addUnitCell(model, { box: { color: '#94a3b8' } })
      viewer.zoomTo()
      if (controls) { viewer.rotate(20, 'y'); viewer.rotate(15, 'x') }
      initialView.current = viewer.getView()
      viewer.render()
      parsedRef.current?.(crystalStructureData(model, $3Dmol))
      if (typeof ResizeObserver !== 'undefined') {
        let width = ref.current.clientWidth, height = ref.current.clientHeight
        resizeObserver = new ResizeObserver(() => {
          const nextWidth = ref.current?.clientWidth, nextHeight = ref.current?.clientHeight
          if (!nextWidth || !nextHeight) return
          viewer.resize()
          // 折叠后原尺寸重开不重置缩放；只有有效尺寸改变才重新适配。
          if (nextWidth !== width || nextHeight !== height) viewer.zoomTo()
          width = nextWidth; height = nextHeight
          viewer.render()
        })
        resizeObserver.observe(ref.current)
      }
      // 从模型提取元素集合，与 Jmol 配色对应生成图例
      const jmol = $3Dmol.elementColors?.Jmol || {}
      const els: string[] = Array.from(new Set(model.selectedAtoms({}).map((a: any) => a.elem)))
      setLegend(els.map(el => ({
        el,
        color: '#' + Number(jmol[el] ?? 0x909090).toString(16).padStart(6, '0'),
      })))
    }).catch((e: any) => {
      if (!cancelled) { setError(e?.message || t('paperDetail.renderFailed')); parsedRef.current?.(null) }
    })
    return () => {
      cancelled = true
      resizeObserver?.disconnect()
      if (viewer) { try { viewer.clear() } catch { /* viewer 已销毁 */ } }
    }
  }, [data, format, t, controls])
  return (
    <Box sx={{ minWidth: 0, position: 'relative', ...(controls ? { height } : {}) }}>
      {error && <Typography variant="body2" color="error" sx={controls ? { position: 'absolute', top: 8, left: 8, right: 8, zIndex: 1, overflowWrap: 'anywhere' } : {}}>{t('paperDetail.renderFailedDetail', { error })}</Typography>}
      <Box ref={ref} sx={{
        position:'relative', width:'100%', minWidth:0, height: controls ? '100%' : height,
        overflow:'hidden', ...(controls ? {} : { borderRadius:2, border:'1px solid', borderColor:'divider' }),
        // 3Dmol 内部 canvas 为绝对定位，需要相对定位容器
        '& canvas': { borderRadius: 2 },
      }} />
      {controls && <Box sx={{ position: 'absolute', right: 8, bottom: 8, display: 'flex', gap: 0.5, bgcolor: 'background.paper', borderRadius: 1 }}>
        {[
          { key: 'rotateStructure', icon: <RotateRightIcon />, run: () => viewerRef.current?.rotate(30, 'y') },
          { key: 'zoomInStructure', icon: <ZoomInIcon />, run: () => viewerRef.current?.zoom(1.2) },
          { key: 'zoomOutStructure', icon: <ZoomOutIcon />, run: () => viewerRef.current?.zoom(1 / 1.2) },
          { key: 'resetStructureView', icon: <CenterFocusStrongIcon />, run: () => viewerRef.current?.setView(initialView.current) },
        ].map(item => <Tooltip key={item.key} title={t(`upload.${item.key}`)}><IconButton size="small" aria-label={t(`upload.${item.key}`)} onClick={() => { item.run(); viewerRef.current?.render() }}>{item.icon}</IconButton></Tooltip>)}
      </Box>}
      {showLegend && legend.length > 0 && (
        <Box data-structure-legend sx={{ display:'flex',flexWrap:'wrap',gap:1.5,mt:1.5,alignItems:'center' }}>
          {legend.map(({ el, color }) => (
            <Box key={el} sx={{ display:'inline-flex',alignItems:'center',gap:0.6 }}>
              <Box sx={{ width:14,height:14,borderRadius:'50%',bgcolor:color,border:'1px solid rgba(15,23,42,.25)' }} />
              <Typography variant="body2" fontWeight={700}>{el}</Typography>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  )
}

export default StructureViewer3D
