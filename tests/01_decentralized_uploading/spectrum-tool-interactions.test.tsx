import React from 'react'
import { beforeAll, afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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
it('两个并列按钮直接激活，默认/退出后只选点不拖动，不产生编辑历史',()=>{
 const {canvas,save}=setup(),before=positions()
 const linked=button('联动选点／拖动'),single=button('单点选点／拖动')
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
 fireEvent.click(button('单点选点／拖动'));drag(canvas,90,120,5,-3)
 expect(positions().filter(p=>p.id!=='p3')).toEqual(before.filter(p=>p.id!=='p3'))
 expect(positions().find(p=>p.id==='p3')).toEqual({id:'p3',x:95,y:117})
 fireEvent.click(button('↶ 撤销'));expect(positions()).toEqual(before)
 fireEvent.click(button('联动选点／拖动'));drag(canvas,90,120,5,-3)
 expect(positions().find(p=>p.id==='p2')).not.toEqual(before[2])
 fireEvent.click(button('↶ 撤销'));expect(positions()).toEqual(before)
})
it('先选增加点，未命中不创建点，首次吸附只选择起点，后续增加且退出保留',()=>{
 const {canvas}=setup(),before=positions(),add=button('＋ 增加点')
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
 fireEvent.click(button('联动选点／拖动'));drag(canvas,90,120,7,-6,false)
 expect(positions()).not.toEqual(before)
 fireEvent.click(button('✥ 平移'));expect(positions()).toEqual(before)
 fireEvent.pointerUp(canvas,{pointerId:1});expect(button('↶ 撤销')).toBeDisabled()
 fireEvent.click(button('单点选点／拖动'));drag(canvas,90,120,7,-6,false)
 fireEvent.keyDown(document.body,{key:'Escape'});expect(positions()).toEqual(before)
 expect(button('单点选点／拖动')).toHaveAttribute('aria-pressed','false')
})
it('所有持续工具可反选，标定同槽退出/异槽切换，主题颜色来自站点',()=>{
 setup()
 for(const name of ['联动选点／拖动','单点选点／拖动','＋ 增加点','✥ 平移','▣ 框选','1 · 标记原图 0 频率位置','2 · 补选曲线零频点']){
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

it('多选时增加点需重新点选唯一锚点，切曲线不会带入旧锚点',()=>{
 const doc=data();doc.curves.push({...structuredClone(doc.curves[0]),id:'b',name:'H',points:doc.curves[0].points.map(p=>({...p,id:'b'+p.id,y:p.y+30}))})
 const {canvas}=setup(doc)
 fireEvent.click(button('▣ 框选'));drag(canvas,25,125,40,20)
 expect(screen.getByText('2 个',{selector:'span.badge'})).toBeVisible()
 const before=positions();fireEvent.click(button('＋ 增加点'))
 clickPoint(canvas,90,120);expect(positions()).toEqual(before)
 expect(screen.getByText('1 个',{selector:'span.badge'})).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:/^H/}))
 expect(button('＋ 增加点')).toHaveAttribute('aria-pressed','false')
 fireEvent.click(button('＋ 增加点'))
 clickPoint(canvas,90,120) // 旧曲线位置，与当前H点相距30像素。
 expect(document.querySelectorAll('[data-point]')).toHaveLength(7)
 expect(screen.getByText('0 个',{selector:'span.badge'})).toBeVisible()
})
it('退出后重新进入不沿用旧描线会话；输入框中的Esc也退出工具',()=>{
 const {canvas}=setup(),before=positions()
 fireEvent.click(button('＋ 增加点'));clickPoint(canvas,90,120);clickPoint(canvas,105,90)
 fireEvent.click(button('＋ 增加点'))
 fireEvent.click(button('＋ 增加点'));clickPoint(canvas,115,70)
 expect(positions()).toHaveLength(before.length+2)
 fireEvent.keyDown(screen.getByLabelText('选中点频率'),{key:'Escape'})
 expect(button('＋ 增加点')).toHaveAttribute('aria-pressed','false')
 expect(positions()).toHaveLength(before.length+2)
})
it('相邻原点之间插点完成后退出，仍可撤销原连接修改',()=>{
 const {canvas}=setup(),before=positions()
 fireEvent.click(button('＋ 增加点'));clickPoint(canvas,90,120);clickPoint(canvas,105,110);clickPoint(canvas,120,110)
 expect(positions()).toHaveLength(before.length+1)
 expect(button('＋ 增加点')).toHaveAttribute('aria-pressed','false')
 expect(screen.getByText(/已在原线段中插入 1 个点/)).toBeVisible()
 fireEvent.click(button('↶ 撤销'));expect(positions()).toHaveLength(before.length+1)
 fireEvent.click(button('↶ 撤销'));expect(positions()).toEqual(before)
})
it('空曲线不会凭空新增起点，已有有效单选点可直接新增',()=>{
 const doc=data();doc.curves[0].points=[];doc.zero=null
 const {canvas}=setup(doc);fireEvent.click(button('＋ 增加点'));clickPoint(canvas,90,100)
 expect(positions()).toHaveLength(0);expect(button('↶ 撤销')).toBeDisabled()
 cleanup()
 const ready=setup();clickPoint(ready.canvas,90,120)
 fireEvent.click(button('＋ 增加点'));clickPoint(ready.canvas,105,90)
 expect(positions()).toHaveLength(8)
})

it('实际全屏Dialog内按Esc仍退出工具并清空旧选择',()=>{
 render(<ThemeProvider theme={theme}><Dialog fullScreen open transitionDuration={0} onClose={()=>{}}>
  <Editor documents={[data()]} onSave={async()=>{}} onClose={()=>{}} kind="alpha2f" imageOpacity={100} onOpacityChange={()=>{}}/>
 </Dialog></ThemeProvider>)
 const canvas=screen.getByRole('application')
 clickPoint(canvas,90,120);fireEvent.click(button('＋ 增加点'))
 fireEvent.keyDown(button('＋ 增加点'),{key:'Escape'})
 expect(button('＋ 增加点')).toHaveAttribute('aria-pressed','false')
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
