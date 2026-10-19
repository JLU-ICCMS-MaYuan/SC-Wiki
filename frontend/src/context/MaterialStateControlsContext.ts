import { createContext } from 'react'

/** 上传任务页提供顶部容器；其他编辑入口继续在材料状态标题旁显示按钮。 */
export const MaterialStateControlsContext = createContext<HTMLElement | null>(null)
