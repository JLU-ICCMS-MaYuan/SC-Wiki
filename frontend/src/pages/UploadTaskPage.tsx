import React from 'react'
import { useParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import UploadPage from './UploadPage'

// 地址决定任务；账号或目标变化时重建工作区，防止旧请求及草稿串入新任务。
const UploadTaskPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>()
  const { user } = useAuth()
  return <UploadPage key={`${user?.id ?? 'guest'}:${taskId}`} taskId={taskId} />
}

export default UploadTaskPage
