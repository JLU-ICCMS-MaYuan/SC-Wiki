import React, {useState,useEffect} from 'react'
import {Link as RouterLink, Navigate, useLocation, useSearchParams} from 'react-router-dom'
import {Box,Typography,Card,CardContent,Chip,Button,Select,MenuItem,ToggleButton,ToggleButtonGroup} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import PeriodicTable from '../components/PeriodicTable'
import SearchResults from '../components/SearchResults'
import {StructuralResults} from '../components/PaperStructuralCollection'
import {useLanguage} from '../context/LanguageContext'
import {SEARCH_FILTER_DEFAULTS as FILTER_DEFAULTS,searchFilters,updateFilters,searchRequest,searchURL,searchPageNumber,type SearchFilters} from '../lib/searchNavigation'
/* ── Layer 2 筛选侧栏 ── */
// 联排输入壳：聚焦时主色描边 + 浅靛光环
const shellSx = {
  display:'flex',alignItems:'center',minWidth:0,border:'1px solid',borderColor:'divider',borderRadius:2,
  bgcolor:'background.paper',overflow:'hidden',transition:'border-color .15s ease, box-shadow .15s ease',
  '&:focus-within':{ borderColor:'primary.main',boxShadow:'0 0 0 3px rgba(79,70,229,.12)' },
}
const bareInputSx = {
  flex:1,width:'100%',minWidth:0,minHeight:40,border:'none',outline:'none',px:1.25,fontSize:14,fontWeight:650,
  bgcolor:'transparent',color:'text.primary',fontFamily:'inherit',textAlign:'center' as const,
  '&:disabled':{ cursor:'not-allowed',color:'text.disabled' },
}
// MUI Select：嵌入联排壳的无下划线样式
const selectSx = {
  flex:1,minWidth:0,fontSize:14,fontWeight:650,color:'text.primary',
  '& .MuiSelect-select':{ py:1.1,px:1.5,minHeight:'unset !important',display:'flex',alignItems:'center' },
  '&.Mui-disabled':{ cursor:'not-allowed' },
}
// 下拉弹层：圆角卡片 + 浅靛选中态，与主题一致
const selectMenuProps = {
  PaperProps: {
    sx: {
      mt:0.5, borderRadius:2, border:'1px solid', borderColor:'divider',
      boxShadow:'0 8px 24px rgba(15,23,42,.14)',
      '& .MuiMenuItem-root':{ fontSize:14, fontWeight:600, borderRadius:1.5, mx:0.5, my:0.25, minHeight:36 },
      '& .MuiMenuItem-root.Mui-selected':{ bgcolor:'#e0e7ff', color:'#312e81' },
      '& .MuiMenuItem-root.Mui-selected:hover':{ bgcolor:'#e0e7ff' },
    },
  },
}

/* 组标题：该组筛选生效时左侧亮起靛蓝短竖条 */
const FilterGroupLabel: React.FC<{ text:string; unit?:string; active?:boolean; disabled?:boolean }> =
  ({ text, unit, active, disabled }) => (
  <Box sx={{ display:'flex',alignItems:'center',justifyContent:'space-between',mb:0.75 }}>
    <Box sx={{ display:'flex',alignItems:'center',gap:0.75 }}>
      {active && <Box sx={{ width:3,height:12,borderRadius:2,bgcolor:'primary.main' }} />}
      <Typography sx={{ fontSize:11,fontWeight:800,letterSpacing:'.08em',textTransform:'uppercase',
        color: active ? 'primary.main' : disabled ? 'text.disabled' : 'text.secondary' }}>{text}</Typography>
    </Box>
    {unit && <Typography sx={{ fontSize:11,fontWeight:700,color:'text.disabled' }}>{unit}</Typography>}
  </Box>
)

/* min – max 联排范围输入 */
const RangeField: React.FC<{
  label:string; unit?:string; active?:boolean; disabled?:boolean
  lo:number; hi:number; onLo:(v:number)=>void; onHi:(v:number)=>void
}> = ({ label, unit, active, disabled, lo, hi, onLo, onHi }) => (
  <RangeFieldContent label={label} unit={unit} active={active} disabled={disabled} lo={lo} hi={hi} onLo={onLo} onHi={onHi} />
)

const RangeFieldContent: React.FC<{
  label:string; unit?:string; active?:boolean; disabled?:boolean
  lo:number; hi:number; onLo:(v:number)=>void; onHi:(v:number)=>void
}> = ({ label, unit, active, disabled, lo, hi, onLo, onHi }) => {
  const { t } = useLanguage()
  return <Box title={disabled ? t('search.unsupportedFilter') : undefined} sx={{ opacity: disabled ? 0.45 : 1 }}>
    <FilterGroupLabel text={label} unit={unit} active={active} disabled={disabled} />
    <Box sx={shellSx}>
      <Box component="input" type="number" disabled={disabled} value={lo}
        onChange={(e:any)=>onLo(+e.target.value)} sx={bareInputSx} />
      <Typography sx={{ color:'text.disabled',px:0.25,userSelect:'none' }}>–</Typography>
      <Box component="input" type="number" disabled={disabled} value={hi}
        onChange={(e:any)=>onHi(+e.target.value)} sx={bareInputSx} />
    </Box>
  </Box>
}

const SearchPage:React.FC=()=>{
 const {t}=useLanguage(),[params,setParams]=useSearchParams(),location=useLocation()
 const [selected,setSelected]=useState(new Set<string>((params.get('elements')||'').split(',').filter(Boolean))),[formula,setFormula]=useState(params.get('formula')||''),[mode,setMode]=useState(params.get('mode')||'elements_combination_search')
 const elementSearchModes=[
 {value:'elements_combination_search',label:'search.modeCombination',description:'search.modeCombinationDescription'},
 {value:'elements_exact_search',label:'search.modeExact',description:'search.modeExactDescription'},
 {value:'elements_contained_search',label:'search.modeContained',description:'search.modeContainedDescription'}]
 const currentElementSearchMode=elementSearchModes.find(x=>x.value===mode),formulaQuery=formula.trim()
 const entry=params.get('entry')==='1', paramsKey=params.toString()
 useEffect(()=>{if(entry){setSelected(new Set((params.get('elements')||'').split(',').filter(Boolean)));setFormula(params.get('formula')||'');setMode(params.get('mode')||'elements_combination_search')}},[entry,paramsKey])
 const filters=searchFilters(params),setFilters=(next:SearchFilters)=>setParams(updateFilters(params,next),{replace:true})
 if(params.has('paper_id'))return <Navigate replace to={`/papers/${encodeURIComponent(params.get('paper_id')||'')}`} />
 if(entry || (!params.has('elements')&&!params.has('formula'))) {
    return (
      <Box>
        <Box sx={{ display:'flex',alignItems:'center',justifyContent:'space-between',gap:2,mb:3 }}>
          <Box>
            <Typography variant="overline">Layer 1 · SC Explore</Typography>
            <Typography variant="h1">{t('search.heroTitle')}</Typography>
            <Typography variant="body2" sx={{ mt:1 }}>{t('search.heroDescription')}</Typography>
          </Box>
        </Box>

        {/* Formula search card */}
        <Card sx={{ mb:3 }}>
          <CardContent>
            <Typography variant="h2" gutterBottom>{t('search.formulaSearch')}</Typography>
            <Box sx={{ display:'grid',gridTemplateColumns:'minmax(0,1fr) auto',gap:1.5,alignItems:'end' }}>
              <Box sx={{ minHeight:56,border:'1px solid',borderColor:'divider',borderRadius:1,p:'8px 12px',display:'grid',alignContent:'center',bgcolor:'background.paper' }}>
                <Box component="label" sx={{ color:'text.secondary',fontSize:12,fontWeight:700 }}>Formula</Box>
                <Box component="input" value={formula} onChange={e=>setFormula(e.target.value)}
                  sx={{ border:'none',outline:'none',fontSize:15,fontWeight:600,mt:0.5,width:'100%',bgcolor:'transparent',fontFamily:'inherit' }} />
              </Box>
              <Button variant="contained" component={RouterLink} to={searchURL([],mode,formula)} target="_blank" rel="noopener noreferrer" disabled={!formulaQuery}>{t('search.search')}</Button>
            </Box>
          </CardContent>
        </Card>

        {/* Periodic table card */}
        <Card sx={{ boxShadow: 3 }}>
          <CardContent>
            <Box sx={{ fontSize:16,mb:2 }}>
              <Box sx={{ display:'grid',gridTemplateColumns:'auto minmax(0,1fr) auto',alignItems:'center',gap:2,
                '@media (max-width:1599px)':{ gridTemplateColumns:'minmax(0,1fr)' } }}>
                <Typography variant="h2" sx={{ fontSize:'inherit',lineHeight:1.5 }}>{t('search.periodicSearch')}</Typography>
                {currentElementSearchMode && (
                  <Typography id="element-search-mode-description" role="status" aria-live="polite" aria-atomic="true" variant="body2"
                    sx={{ minWidth:0,color:'text.secondary',lineHeight:1.7,overflowWrap:'anywhere' }}>
                    {t(currentElementSearchMode.description)}
                  </Typography>
                )}
                <Box sx={{ display:'flex',alignItems:'center',gap:1,maxWidth:'100%',
                  '& .MuiButton-root':{ fontSize:'inherit' },
                  '@media (max-width:1599px)':{ flexWrap:'wrap' } }}>
                  {/* Mode segments */}
                  <Box sx={{ display:'inline-flex',gap:0.5,maxWidth:'100%',bgcolor:'#e8e8ed',borderRadius:'20px',p:0.5,
                    '@media (max-width:1599px)':{ flexWrap:'wrap' } }}>
                    {elementSearchModes.map(option=>(
                      <Button key={option.value} size="small"
                        aria-pressed={mode===option.value}
                        aria-describedby={mode===option.value ? 'element-search-mode-description' : undefined}
                        sx={{ borderRadius:'16px',px:2.5,py:1,color:mode===option.value?'#fff':'text.primary',bgcolor:mode===option.value?'primary.main':'transparent',minWidth:0,maxWidth:'100%',overflowWrap:'anywhere',textTransform:'none','&:hover':{bgcolor:mode===option.value?'primary.main':'action.hover'} }}
                        onClick={()=>setMode(option.value)}>{t(option.label)}</Button>
                    ))}
                  </Box>
                  <Button variant="contained" disabled={selected.size===0 && !formulaQuery}
                    component={RouterLink} to={searchURL(selected,mode,formula)} target="_blank" rel="noopener noreferrer">{t('search.enterPage')}</Button>
                  <Button variant="outlined" onClick={()=>setSelected(new Set())}>{t('search.clearSelection')}</Button>
                </Box>
              </Box>
              <Box sx={{ display:'flex',flexWrap:'wrap',alignItems:'center',gap:1.5,mt:1.5,minWidth:0 }}>
                <Typography sx={{ fontSize:'inherit' }}>{t('search.selectedElements')}</Typography>
                <Chip label={selected.size ? [...selected].sort().join(', ') : t('search.noneSelected')} color={selected.size ? 'primary' : 'default'}
                  sx={{ fontSize:'inherit',maxWidth:'100%',height:'auto','& .MuiChip-label':{ whiteSpace:'normal',overflowWrap:'anywhere',py:0.75 } }} />
              </Box>
            </Box>
            <Box sx={{ overflowX:'auto',py:2 }}>
              <PeriodicTable selected={selected} onToggle={s=>setSelected(prev=>{const n=new Set(prev);n.has(s)?n.delete(s):n.add(s);return n})} />
            </Box>
          </CardContent>
        </Card>
      </Box>
    )

 }
    const groupActive = {
      formula: !!filters.formula,
      tc: filters.tcMin > 0 || filters.tcMax < 9999,
      pressure: filters.pMin > 0 || filters.pMax < 9999,
      year: filters.yMin > 1900 || filters.yMax < 2030,
      type: filters.type !== 'All',
      review: filters.review !== 'All',
      chart: filters.chartOnly,
    }
    const activeCount = Object.values(groupActive).filter(Boolean).length
 const view=params.get('view')==='states'?'states':'papers',pageKey=view==='papers'?'paper_page':'state_page'
 const request=searchRequest(params),returnTo=location.pathname+location.search
 const {tc_min: _tcMin,tc_max: _tcMax,chart_only: _chartOnly,...structuralQuery}=request
 const setPage=(key:string,page:number)=>{const next=new URLSearchParams(params);next.set(key,String(page));setParams(next)}
 const entryParams=new URLSearchParams(params);entryParams.set('entry','1')
 const system=(params.get('elements')||params.get('formula')||'').split(',').sort().join('-')
 return <Box>
  <Box sx={{display:'flex',justifyContent:'space-between',alignItems:'start',gap:2,mb:3,flexWrap:'wrap'}}>
   <Box><Button component={RouterLink} to={'/search?'+entryParams} startIcon={<ArrowBackIcon/>}>{t('search.backElementSearch')}</Button><Typography variant="h1">{t('search.systemResults',{system})}</Typography><Typography>{t('search.resultHint')}</Typography></Box>
   <ToggleButtonGroup exclusive value={view} aria-label={t('search.viewMode')} onChange={(_,value)=>{if(value){const next=new URLSearchParams(params);next.set('view',value);setParams(next)}}}>
    <ToggleButton value="papers">{t('search.byPapers')}</ToggleButton><ToggleButton value="states">{t('search.byStates')}</ToggleButton>
   </ToggleButtonGroup>
  </Box>
  <Box sx={{display:'grid',gridTemplateColumns:{xs:'minmax(0,1fr)',lg:'280px minmax(0,1fr)'},gap:3,alignItems:'start',minWidth:0}}>
          <Box component="aside" sx={{ minWidth:0, maxWidth:'100%', overflow:'hidden', p:2.5, bgcolor:'background.paper', borderRadius:4, border:'1px solid', borderColor:'divider', boxShadow:1 }}>
            {/* 标题行：生效计数 + 按需出现的重置 */}
            <Box sx={{ display:'flex',alignItems:'center',justifyContent:'space-between',mb:2 }}>
              <Box sx={{ display:'flex',alignItems:'center',gap:1 }}>
                <Typography variant="h2">{t('search.filters')}</Typography>
                {activeCount > 0 && (
                  <Box sx={{ minWidth:20,height:20,px:0.5,borderRadius:'999px',bgcolor:'primary.main',color:'#fff',fontSize:12,fontWeight:800,display:'inline-flex',alignItems:'center',justifyContent:'center' }}>
                    {activeCount}
                  </Box>
                )}
              </Box>
              {activeCount > 0 && (
                <Box component="button" onClick={()=>setFilters({ ...FILTER_DEFAULTS })}
                  sx={{ border:'none',bgcolor:'transparent',color:'primary.main',fontSize:13,fontWeight:700,cursor:'pointer',p:0,'&:hover':{textDecoration:'underline'} }}>
                  {t('search.reset')}
                </Box>
              )}
            </Box>
            {/* minmax(0,1fr)：切断 number input 内在宽度对单列 grid 的撑破 */}
            <Box sx={{ display:'grid',gridTemplateColumns:'minmax(0,1fr)',gap:2 }}>
              {/* Formula 关键词 */}
              <Box>
                <FilterGroupLabel text={t('search.formulaKeyword')} active={groupActive.formula} />
                <Box sx={shellSx}>
                  <Box component="input" placeholder={t('search.formulaExample')}
                    value={filters.formula} onChange={e=>setFilters({...filters,formula:e.target.value})}
                    sx={{ ...bareInputSx, textAlign:'left', px:1.5 }} />
                </Box>
              </Box>
              {/* 数值范围 */}
              <RangeField label={t('search.representativeTc')} unit="K" active={groupActive.tc}
                lo={filters.tcMin} hi={filters.tcMax}
                onLo={v=>setFilters({...filters,tcMin:v})} onHi={v=>setFilters({...filters,tcMax:v})} />
              <RangeField label={t('search.pressure')} unit="GPa" active={groupActive.pressure}
                lo={filters.pMin} hi={filters.pMax}
                onLo={v=>setFilters({...filters,pMin:v})} onHi={v=>setFilters({...filters,pMax:v})} />
              <RangeField label={t('search.year')} active={groupActive.year}
                lo={filters.yMin} hi={filters.yMax}
                onLo={v=>setFilters({...filters,yMin:v})} onHi={v=>setFilters({...filters,yMax:v})} />
              <Box sx={{ height:'1px',bgcolor:'divider' }} />
              {/* 超导类型 */}
              <Box>
                <FilterGroupLabel text={t('search.superconductorType')} active={groupActive.type} />
                <Box sx={shellSx}>
                  <Select variant="standard" disableUnderline MenuProps={selectMenuProps}
                    value={filters.type} onChange={e=>setFilters({...filters,type:e.target.value})} sx={selectSx}>
                    {/* 规范全称，与 backend/sc_types.py 一致 */}
                    {[
                      {v:'All',l:t('search.allTypes')},{v:'hydride',l:t('search.scType.hydride')},{v:'cuprate',l:t('search.scType.cuprate')},
                      {v:'iron_based',l:t('search.scType.iron_based')},{v:'nickel_based',l:t('search.scType.nickel_based')},{v:'carbon',l:t('search.scType.carbon')},
                      {v:'organic',l:t('search.scType.organic')},{v:'others',l:t('search.scType.others')},
                    ].map(o=><MenuItem key={o.v} value={o.v}>{o.l}</MenuItem>)}
                  </Select>
                </Box>
              </Box>
              {/* 审核状态 */}
              <Box>
                <FilterGroupLabel text={t('search.reviewStatus')} active={groupActive.review} />
                <Box sx={shellSx}>
                  <Select variant="standard" disableUnderline MenuProps={selectMenuProps}
                    value={filters.review} onChange={e=>setFilters({...filters,review:e.target.value})} sx={selectSx}>
                    {[
                      {v:'All',l:t('search.allStatuses')},{v:'Approved',l:t('search.status.approved')},{v:'Pending',l:t('search.status.pending')},
                      {v:'Rejected',l:t('search.status.rejected')},
                    ].map(o=><MenuItem key={o.v} value={o.v}>{o.l}</MenuItem>)}
                  </Select>
                </Box>
              </Box>
              {/* 图表记录开关 */}
              <Box component="button"
                onClick={()=>setFilters({...filters,chartOnly:!filters.chartOnly})}
                sx={{ minHeight:32,px:1.5,borderRadius:'999px',display:'inline-flex',alignItems:'center',gap:0.75,border:'1px solid',borderColor:filters.chartOnly?'primary.main':'divider',bgcolor:filters.chartOnly?'#e0e7ff':'grey.50',color:filters.chartOnly?'#312e81':'text.primary',fontSize:12,fontWeight:700,cursor:'pointer',justifySelf:'start',transition:'all .15s ease' }}>
                <Box sx={{ width:8,height:8,borderRadius:'50%',bgcolor:filters.chartOnly?'primary.main':'text.disabled' }} />
                {t('search.chartOnly')}
              </Box>
            </Box>
          </Box>

<Box sx={{minWidth:0}}>
  <SearchResults query={request} view={view} page={searchPageNumber(params,pageKey)} returnTo={returnTo} onPageChange={page=>setPage(pageKey,page)} />
  <StructuralResults query={structuralQuery} page={searchPageNumber(params,'structure_page')-1} onPageChange={page=>setPage('structure_page',page+1)} />
  </Box></Box></Box>
}
export default SearchPage
