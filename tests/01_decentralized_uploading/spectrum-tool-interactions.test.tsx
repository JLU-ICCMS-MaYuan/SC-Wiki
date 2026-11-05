import React from 'react'
import { beforeAll, afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import Dialog from '@mui/material/Dialog'
import { ThemeProvider } from '@mui/material/styles'
import theme from '../../frontend/src/theme'
import Editor from '../../frontend/src/components/spectrumEditor/SpectrumManualEditor'
import type { Document } from '../../frontend/src/components/spectrumEditor/engine'

beforeAll(()=>{
  class Point { constructor(public x=0,public y=0){} matrixTransform(){return this} }
  vi.stubGlobal('DOMPoint',Point)
  vi.stubGlobal('PointerEvent',MouseEvent)
  vi.stubGlobal('ResizeObserver',class {observe(){} disconnect(){}})
  Object.defineProperty(SVGElement.prototype,'getScreenCTM',{configurable:true,value:()=>({a:1,inverse:()=>({})})})
  Object.defineProperty(SVGElement.prototype,'setPointerCapture',{configurable:true,value:()=>{}})
  Object.defineProperty(SVGElement.prototype,'releasePointerCapture',{configurable:true,value:()=>{}})
  Object.defineProperty(SVGElement.prototype,'hasPointerCapture',{configurable:true,value:()=>false})
  Element.prototype.scrollTo=()=>{}
})
afterEach(cleanup)
const data=():Document=>({schemaVersion:1,id:'doc',title:'α²F',description:'测试',
 source:{id:'source',sha256:'hash',image:'',width:201,height:201,plot:[0,0,200,200],viewport:[0,0,200,200]},
 calibration:{direction:'x',frequency:{pixels:[0,200],values:[0,20],unit:'THz'},amplitude:{pixels:[200,0],values:[0,2],unit:'dimensionless'}},
 curves:[{id:'a',name:'α²F',color:'red',pathOrdered:true,points:Array.from({length:7},(_,i)=>({id:'p'+i,x:i*30,y:150-i*10,segment:'s',status:'原始点',breakBefore:i===0}))}],
 zero:{pixel:0,pointIds:['p0']},operations:[]})
function setup(doc=data()){
  const save=vi.fn(async()=>{}),close=vi.fn()
  render(<ThemeProvider theme={theme}><Editor documents={[doc]} onSave={save} onClose={close} kind="alpha2f" imageOpacity={100} onOpacityChange={()=>{}}/></ThemeProvider>)
  return {save,close,canvas:screen.getByRole('application'),doc}
}
const button=(name:string)=>screen.getByRole('button',{name,exact:true})
const positions=()=>Array.from(document.querySelectorAll('[data-point]')).map(p=>({id:p.getAttribute('data-point'),x:Number(p.getAttribute('data-x')),y:Number(p.getAttribute('data-y'))}))
function drag(canvas:HTMLElement,x:number,y:number,dx:number,dy:number,up=true){
 fireEvent.pointerDown(canvas,{clientX:x,clientY:y,button:0,pointerId:1})
 fireEvent.pointerMove(canvas,{clientX:x+dx,clientY:y+dy,pointerId:1})
 if(up)fireEvent.pointerUp(canvas,{pointerId:1})
}
function clickPoint(canvas:HTMLElement,x:number,y:number){
 fireEvent.pointerDown(canvas,{clientX:x,clientY:y,button:0,pointerId:1})
 fireEvent.pointerUp(canvas,{pointerId:1})
 fireEvent.click(canvas,{clientX:x,clientY:y,button:0,detail:1})
}
it('批量与单点拖动直接激活，默认/退出后只选点不拖动，不产生编辑历史',()=>{
 const {canvas,save}=setup(),before=positions()
 const linked=button('批量拖动'),single=button('单点拖动')
 expect(linked).toHaveAttribute('aria-pressed','false');expect(single).toHaveAttribute('aria-pressed','false')
 expect(screen.queryByRole('checkbox',{name:'附近点联动'})).toBeNull()
 drag(canvas,90,120,5,-3);expect(positions()).toEqual(before)
 fireEvent.click(linked);expect(linked).toHaveAttribute('aria-pressed','true')
 fireEvent.click(single);expect(linked).toHaveAttribute('aria-pressed','false');expect(single).toHaveAttribute('aria-pressed','true')
 fireEvent.click(single);expect(single).toHaveAttribute('aria-pressed','false')
 drag(canvas,90,120,5,-3);expect(positions()).toEqual(before)
 expect(button('↶ 撤销')).toBeDisabled();expect(save).not.toHaveBeenCalled()
})
it('单点只移动目标，联动影响相连邻点，撤销恢复整次拖动',()=>{
 const {canvas}=setup(),before=positions()
 fireEvent.click(button('单点拖动'));drag(canvas,90,120,5,-3)
 expect(positions().filter(p=>p.id!=='p3')).toEqual(before.filter(p=>p.id!=='p3'))
 expect(positions().find(p=>p.id==='p3')).toEqual({id:'p3',x:95,y:117})
 fireEvent.click(button('↶ 撤销'));expect(positions()).toEqual(before)
 fireEvent.click(button('批量拖动'));drag(canvas,90,120,5,-3)
 expect(positions().find(p=>p.id==='p2')).not.toEqual(before[2])
 fireEvent.click(button('↶ 撤销'));expect(positions()).toEqual(before)
})
it('先选增加点，未命中不创建点，首次吸附只选择起点，后续增加且退出保留',()=>{
 const {canvas}=setup(),before=positions(),add=button('增加新点')
 fireEvent.click(add);expect(add).toHaveAttribute('aria-pressed','true')
 clickPoint(canvas,15,20);expect(positions()).toEqual(before)
 fireEvent.pointerMove(canvas,{clientX:92,clientY:120})
 expect(screen.getByTestId('snap-target')).toHaveAttribute('data-point-id','p3')
 clickPoint(canvas,92,120);expect(positions()).toEqual(before);expect(button('↶ 撤销')).toBeDisabled()
 clickPoint(canvas,105,90);expect(positions()).toHaveLength(before.length+1)
 fireEvent.click(add);expect(add).toHaveAttribute('aria-pressed','false')
 expect(screen.queryByTestId('snap-target')).toBeNull()
 clickPoint(canvas,115,80);expect(positions()).toHaveLength(before.length+1)
 fireEvent.click(button('↶ 撤销'));expect(positions()).toEqual(before)
})
it('切换和Esc取消未完成拖动，清除预览和临时手势',()=>{
 const {canvas}=setup(),before=positions()
 fireEvent.click(button('批量拖动'));drag(canvas,90,120,7,-6,false)
 expect(positions()).not.toEqual(before)
 fireEvent.click(button('移动'));expect(positions()).toEqual(before)
 fireEvent.pointerUp(canvas,{pointerId:1});expect(button('↶ 撤销')).toBeDisabled()
 fireEvent.click(button('单点拖动'));drag(canvas,90,120,7,-6,false)
 fireEvent.keyDown(document.body,{key:'Escape'});expect(positions()).toEqual(before)
 expect(button('单点拖动')).toHaveAttribute('aria-pressed','false')
})
it('所有持续工具可反选，标定同槽退出/异槽切换，主题颜色来自站点',()=>{
 setup()
 for(const name of ['选点','移动','批量拖动','单点拖动','增加新点','批量框选']){
  const b=button(name);fireEvent.click(b);expect(b).toHaveAttribute('aria-pressed','true')
  fireEvent.click(b);expect(b).toHaveAttribute('aria-pressed','false')
 }
 fireEvent.click(screen.getByText(/坐标标定/,{selector:'summary'}))
 const first=button('点选频率刻度1'),second=button('点选频率刻度2')
 fireEvent.click(first);expect(first).toHaveAttribute('aria-pressed','true')
 fireEvent.click(second);expect(first).toHaveAttribute('aria-pressed','false');expect(second).toHaveAttribute('aria-pressed','true')
 fireEvent.click(second);expect(second).toHaveAttribute('aria-pressed','false')
 expect(document.querySelector<HTMLElement>('.editor-app')!.style.getPropertyValue('--tool-active')).toBe(theme.palette.primary.main)
})

it('六工具与Alt数字键顺序一致，Option特殊字符可选中，重复快捷键不退出且不改数据',()=>{
 const {canvas}=setup(),before=positions()
 const names=['选点','移动','批量拖动','单点拖动','增加新点','批量框选']
 expect(within(screen.getByRole('group',{name:'人工调整工具'})).getAllByRole('button').map(b=>b.textContent?.replace(/Alt\+\d/,''))).toEqual(names)
 names.forEach((name,i)=>{
  fireEvent.keyDown(document.body,{key:'¡',code:`Digit${i+1}`,altKey:true})
  expect(button(name)).toHaveAttribute('aria-pressed','true')
  expect(button(name)).toHaveAttribute('aria-keyshortcuts',`Alt+${i+1}`)
  expect(document.querySelectorAll('.tool-strip [aria-pressed=true]')).toHaveLength(1)
  fireEvent.keyDown(document.body,{key:'¡',code:`Digit${i+1}`,altKey:true})
  expect(button(name)).toHaveAttribute('aria-pressed','true')
 })
 fireEvent.keyDown(document.body,{key:'1',code:'Digit1',altKey:true})
 drag(canvas,90,120,15,-15)
 expect(canvas).toHaveClass('tool-select');expect(positions()).toEqual(before)
 expect(screen.getByText('1 个',{selector:'span.badge'})).toBeVisible()
 expect(button('↶ 撤销')).toBeDisabled()
 fireEvent.click(button('选点'));expect(canvas).toHaveClass('tool-idle')
})

it('快捷键在数值输入中可选工具，组合输入、额外修饰键和离开确认时不切换',()=>{
 const {canvas}=setup();clickPoint(canvas,90,120)
 const input=screen.getByLabelText('选中点频率')
 fireEvent.keyDown(input,{key:'2',code:'Digit2',altKey:true})
 expect(canvas).toHaveClass('tool-pan')
 fireEvent.keyDown(input,{key:'3',code:'Digit3',altKey:true,isComposing:true})
 fireEvent.keyDown(input,{key:'3',code:'Digit3',altKey:true,ctrlKey:true})
 expect(canvas).toHaveClass('tool-pan')
 fireEvent.click(button('单点拖动'));drag(canvas,90,120,5,-3)
 fireEvent.click(button('← 返回详情'))
 fireEvent.keyDown(document.body,{key:'2',code:'Digit2',altKey:true})
 expect(canvas).toHaveClass('tool-dragSingle')
 expect(screen.getByRole('dialog')).toBeVisible()
})

it('坐标区仅显示可编辑数值，确认坐标改单点；方向切换仍限制频率',()=>{
 const {canvas}=setup(),before=positions();clickPoint(canvas,90,120)
 expect(screen.queryByText('原图像素 X')).toBeNull()
 expect(screen.queryByText(/频率与幅值按当前标定换算/)).toBeNull()
 expect(screen.queryByText('主要影响区')).toBeNull()
 expect(screen.queryByText('编辑曲线')).toBeNull()
 fireEvent.change(screen.getByLabelText('选中点幅值'),{target:{value:'1'}})
 fireEvent.click(button('确认坐标'))
 expect(positions().find(p=>p.id==='p3')).toEqual({id:'p3',x:90,y:100})
 expect(positions().filter(p=>p.id!=='p3')).toEqual(before.filter(p=>p.id!=='p3'))
 fireEvent.click(button('↶ 撤销'));expect(positions()).toEqual(before)
 fireEvent.click(button('只改幅值'));fireEvent.click(button('单点拖动'))
 drag(canvas,90,120,5,-3)
 expect(positions().find(p=>p.id==='p3')).toEqual({id:'p3',x:90,y:117})
 expect(button('只改幅值')).toHaveAttribute('aria-pressed','true')
 fireEvent.click(button('自由移动（X / Y）'));drag(canvas,90,117,5,-3)
 expect(positions().find(p=>p.id==='p3')).toEqual({id:'p3',x:95,y:114})
})

it('显示开关仍控制参考曲线和原图，并位于适应窗口左侧，滑条在六工具下方',()=>{
 const doc=data();doc.source.image='fixture.png'
 doc.curves.push({...structuredClone(doc.curves[0]),id:'b',name:'H',points:[]})
 setup(doc)
 const controls=button('适应窗口').parentElement!
 expect(within(controls).getByRole('checkbox',{name:'显示其他分波'})).toBeChecked()
 expect(button('隐藏原图').nextElementSibling).toBe(button('适应窗口'))
 expect(document.querySelector('.editor-tool-rail')?.lastElementChild).toBe(screen.getByTestId('image-opacity-control'))
 expect(screen.getByText('编辑曲线')).toBeVisible()
 fireEvent.click(screen.getByRole('checkbox',{name:'显示其他分波'}))
 expect(document.querySelector('[data-curve=b]')).toBeNull()
 fireEvent.click(button('隐藏原图'))
 expect(screen.queryByTestId('source-image')).toBeNull()
 expect(screen.getByRole('slider',{name:'原图不透明度'})).toBeDisabled()
 fireEvent.click(button('显示原图'))
 expect(screen.getByTestId('source-image')).toBeInTheDocument()
 expect(screen.getByRole('slider',{name:'原图不透明度'})).toBeEnabled()
})

it('保存期间忽略快捷键，不改变待保存文档或按钮状态',()=>{
 const save=vi.fn(()=>new Promise<void>(()=>{}))
 render(<ThemeProvider theme={theme}><Editor documents={[data()]} onSave={save} onClose={()=>{}} kind="alpha2f" imageOpacity={100} onOpacityChange={()=>{}}/></ThemeProvider>)
 const canvas=screen.getByRole('application')
 fireEvent.click(button('单点拖动'));drag(canvas,90,120,5,-3)
 fireEvent.click(button('保存调整'))
 expect(save).toHaveBeenCalledTimes(1)
 fireEvent.keyDown(document.body,{key:'2',code:'Digit2',altKey:true})
 expect(canvas).toHaveClass('tool-dragSingle')
 expect(button('移动')).toBeDisabled()
})

it('多选时增加点需重新点选唯一锚点，切曲线不会带入旧锚点',()=>{
 const doc=data();doc.curves.push({...structuredClone(doc.curves[0]),id:'b',name:'H',points:doc.curves[0].points.map(p=>({...p,id:'b'+p.id,y:p.y+30}))})
 const {canvas}=setup(doc)
 fireEvent.click(button('批量框选'));drag(canvas,25,125,40,20)
 expect(screen.getByText('2 个',{selector:'span.badge'})).toBeVisible()
 const before=positions();fireEvent.click(button('增加新点'))
 clickPoint(canvas,90,120);expect(positions()).toEqual(before)
 expect(screen.getByText('1 个',{selector:'span.badge'})).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:/^H/}))
 expect(button('增加新点')).toHaveAttribute('aria-pressed','false')
 fireEvent.click(button('增加新点'))
 clickPoint(canvas,90,120) // 旧曲线位置，与当前H点相距30像素。
 expect(document.querySelectorAll('[data-point]')).toHaveLength(7)
 expect(screen.getByText('0 个',{selector:'span.badge'})).toBeVisible()
})
it('退出后重新进入不沿用旧描线会话；输入框中的Esc也退出工具',()=>{
 const {canvas}=setup(),before=positions()
 fireEvent.click(button('增加新点'));clickPoint(canvas,90,120);clickPoint(canvas,105,90)
 fireEvent.click(button('增加新点'))
 fireEvent.click(button('增加新点'));clickPoint(canvas,115,70)
 expect(positions()).toHaveLength(before.length+2)
 fireEvent.keyDown(screen.getByLabelText('选中点频率'),{key:'Escape'})
 expect(button('增加新点')).toHaveAttribute('aria-pressed','false')
 expect(positions()).toHaveLength(before.length+2)
})
it('相邻原点之间插点完成后退出，仍可撤销原连接修改',()=>{
 const {canvas}=setup(),before=positions()
 fireEvent.click(button('增加新点'));clickPoint(canvas,90,120);clickPoint(canvas,105,110);clickPoint(canvas,120,110)
 expect(positions()).toHaveLength(before.length+1)
 expect(button('增加新点')).toHaveAttribute('aria-pressed','false')
 expect(screen.getByText(/已在原线段中插入 1 个点/)).toBeVisible()
 fireEvent.click(button('↶ 撤销'));expect(positions()).toHaveLength(before.length+1)
 fireEvent.click(button('↶ 撤销'));expect(positions()).toEqual(before)
})
it('空曲线不会凭空新增起点，已有有效单选点可直接新增',()=>{
 const doc=data();doc.curves[0].points=[];doc.zero=null
 const {canvas}=setup(doc);fireEvent.click(button('增加新点'));clickPoint(canvas,90,100)
 expect(positions()).toHaveLength(0);expect(button('↶ 撤销')).toBeDisabled()
 cleanup()
 const ready=setup();clickPoint(ready.canvas,90,120)
 fireEvent.click(button('增加新点'));clickPoint(ready.canvas,105,90)
 expect(positions()).toHaveLength(8)
})

it('实际全屏Dialog内按Esc仍退出工具并清空旧选择',()=>{
 render(<ThemeProvider theme={theme}><Dialog fullScreen open transitionDuration={0} onClose={()=>{}}>
  <Editor documents={[data()]} onSave={async()=>{}} onClose={()=>{}} kind="alpha2f" imageOpacity={100} onOpacityChange={()=>{}}/>
 </Dialog></ThemeProvider>)
 const canvas=screen.getByRole('application')
 clickPoint(canvas,90,120);fireEvent.click(button('增加新点'))
 fireEvent.keyDown(button('增加新点'),{key:'Escape'})
 expect(button('增加新点')).toHaveAttribute('aria-pressed','false')
 expect(screen.getByText('0 个',{selector:'span.badge'})).toBeVisible()
 expect(screen.getByRole('dialog')).toBeVisible()
})

it('撤销标定时退出旧取点工具，避免工具身份与高亮槽失配',()=>{
 setup()
 fireEvent.click(screen.getByText(/坐标标定/,{selector:'summary'}))
 fireEvent.change(screen.getByLabelText('frequency-1-value'),{target:{value:'25'}})
 fireEvent.click(button('应用标定'))
 const pick=button('点选频率刻度1')
 fireEvent.click(pick);expect(pick).toHaveAttribute('aria-pressed','true')
 fireEvent.click(button('↶ 撤销'))
 expect(pick).toHaveAttribute('aria-pressed','false')
 expect(screen.getByRole('application')).toHaveClass('tool-idle')
})
