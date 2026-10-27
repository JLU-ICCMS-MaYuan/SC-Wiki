import React from 'react'
import { beforeAll, afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { ThemeProvider } from '@mui/material/styles'
import theme from '../../frontend/src/theme'
import Editor from '../../frontend/src/components/spectrumEditor/SpectrumManualEditor'
import type { Document } from '../../frontend/src/components/spectrumEditor/engine'

beforeAll(()=>{
 vi.stubGlobal('ResizeObserver',class {observe(){} disconnect(){}})
 Object.defineProperty(SVGElement.prototype,'getScreenCTM',{configurable:true,value:()=>({a:1})})
 Element.prototype.scrollTo=()=>{}
})
afterEach(cleanup)
function docs():Document[]{
 return ['H','Sc','La'].map(name=>({schemaVersion:1,id:'doc-'+name,title:name,description:'',
 source:{id:'collection',sha256:'source',image:'',width:101,height:101,plot:[0,0,100,100],viewport:[0,0,100,100]},
 calibration:{direction:'x',frequency:{pixels:[0,100],values:[0,10],unit:'THz'},amplitude:{pixels:[100,0],values:[0,100],unit:'pixel'}},
 curves:[{id:name,name,color:'green',pathOrdered:true,points:[{id:name+':p0',x:0,y:100,status:'原点',segment:'s',breakBefore:true},{id:name+':p1',x:50,y:50,status:'原点',segment:'s'}]}],
 zero:{pixel:0,pointIds:[name+':p0']},operations:[]}))
}
function setup(save?: (doc:Document)=>Promise<Document[]|void>){
 let stored=docs()
 const onSave=vi.fn(save|| (async (doc:Document)=>{stored=stored.map(d=>d.id===doc.id?structuredClone(doc):d);return stored})),onClose=vi.fn()
 render(<ThemeProvider theme={theme}><Editor documents={stored} onSave={onSave} onClose={onClose} kind="phonon_dos" imageOpacity={100} onOpacityChange={()=>{}}/></ThemeProvider>)
 return {onSave,onClose}
}
const button=(name:string)=>screen.getByRole('button',{name,exact:true})
const modal=()=>screen.getByRole('dialog',{name:'保留这次调整吗？'})
function select(name:string){fireEvent.click(document.querySelector('[data-row="'+name+':p1"]')!)}
function edit(name:string,amplitude:number){select(name);fireEvent.change(screen.getByLabelText('选中点幅值'),{target:{value:String(amplitude)}});fireEvent.click(button('应用坐标到此点'))}
async function saveAndSwitch(name:string){
 fireEvent.click(button(name));expect(within(modal()).getByText(/保存后将继续编辑/)).toBeVisible()
 fireEvent.click(button('保存并继续编辑'))
 await waitFor(()=>expect(screen.queryByRole('dialog',{name:'保留这次调整吗？'})).toBeNull())
}
it('连续保存H/Sc后直接编辑目标元素，回切仍是新保存坐标',async()=>{
 const {onSave,onClose}=setup()
 edit('H',55);await saveAndSwitch('Sc')
 expect(button('Sc')).toHaveClass('active');expect(screen.getByRole('application')).toBeVisible()
 edit('Sc',66);await saveAndSwitch('La')
 expect(button('La')).toHaveClass('active')
 fireEvent.click(button('H'));select('H');expect(screen.getByLabelText('选中点幅值')).toHaveValue(55)
 fireEvent.click(button('Sc'));select('Sc');expect(screen.getByLabelText('选中点幅值')).toHaveValue(66)
 expect(onSave).toHaveBeenCalledTimes(2);expect(onClose).not.toHaveBeenCalled()
 expect(onSave.mock.calls.map(c=>c[0].curves[0].id)).toEqual(['H','Sc'])
})
it('保存失败保留当前元素与输入，弹窗展示失败并可重试',async()=>{
 const {onSave,onClose}=setup(async()=>{throw Error('版本冲突')})
 edit('H',55);fireEvent.click(button('Sc'));fireEvent.click(button('保存并继续编辑'))
 expect(await within(modal()).findByRole('alert')).toHaveTextContent('版本冲突')
 expect(button('H')).toHaveClass('active');expect(screen.getByLabelText('选中点幅值')).toHaveValue(55)
 expect(onClose).not.toHaveBeenCalled()
 onSave.mockResolvedValueOnce(undefined)
 fireEvent.click(button('保存并继续编辑'))
 await waitFor(()=>expect(button('Sc')).toHaveClass('active'))
 fireEvent.click(button('H'));select('H');expect(screen.getByLabelText('选中点幅值')).toHaveValue(55)
})
it('取消留在当前元素，放弃只丢弃当前未保存修改而不写库',()=>{
 const {onSave,onClose}=setup()
 edit('H',55);fireEvent.click(button('Sc'));fireEvent.click(button('留在当前元素'))
 expect(button('H')).toHaveClass('active');expect(screen.getByLabelText('选中点幅值')).toHaveValue(55)
 fireEvent.click(button('Sc'));fireEvent.click(button('放弃修改'))
 expect(button('Sc')).toHaveClass('active')
 fireEvent.click(button('H'));select('H');expect(screen.getByLabelText('选中点幅值')).toHaveValue(50)
 expect(onSave).not.toHaveBeenCalled();expect(onClose).not.toHaveBeenCalled()
})
it('保存中不重复提交、不允许改选或放弃，成功后再切换',async()=>{
 let finish!:(value:void)=>void
 const {onSave,onClose}=setup(()=>new Promise<void>(resolve=>{finish=resolve}))
 edit('H',55);fireEvent.click(button('Sc'))
 const save=button('保存并继续编辑');fireEvent.click(save);fireEvent.click(save)
 expect(save).toBeDisabled();expect(button('放弃修改')).toBeDisabled();expect(button('留在当前元素')).toBeDisabled()
 expect(button('H')).toHaveClass('active');expect(onSave).toHaveBeenCalledTimes(1)
 finish();await waitFor(()=>expect(button('Sc')).toHaveClass('active'))
 expect(onClose).not.toHaveBeenCalled()
})
it('真正返回详情仍保存并返回，点击当前元素不会产生离开弹窗',async()=>{
 const {onSave,onClose}=setup();edit('H',55)
 fireEvent.click(button('H'));expect(screen.queryByRole('dialog')).toBeNull()
 fireEvent.click(button('← 返回详情'));expect(button('继续编辑')).toBeVisible()
 expect(screen.queryByRole('button',{name:'保存并继续编辑'})).toBeNull()
 fireEvent.click(button('保存并返回'));await waitFor(()=>expect(onClose).toHaveBeenCalledTimes(1))
 expect(onSave).toHaveBeenCalledTimes(1)
})
it('未应用标定不保存也不切换，错误留在弹窗内',async()=>{
 const {onSave}=setup()
 fireEvent.click(screen.getByText(/坐标标定/,{selector:'summary'}))
 fireEvent.change(screen.getByLabelText('frequency-1-value'),{target:{value:'11'}})
 fireEvent.click(button('Sc'));fireEvent.click(button('保存并继续编辑'))
 expect(await within(modal()).findByRole('alert')).toHaveTextContent('先应用标定')
 expect(button('H')).toHaveClass('active');expect(onSave).not.toHaveBeenCalled()
})
