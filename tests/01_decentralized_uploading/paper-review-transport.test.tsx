import {afterEach,it,expect,vi} from 'vitest'
import {api} from '../../frontend/src/lib/api'
import {commitPaperReview} from '../../frontend/src/lib/paperReview'
vi.mock('../../frontend/src/lib/api',()=>({api:{post:vi.fn()}}))
afterEach(()=>vi.clearAllMocks())
it.each([409,403,422,500])('保留业务错误%s，不重试已拒绝的提交',async status=>{
 const error=Object.assign(new Error('真实错误'),{status})
 vi.mocked(api.post).mockRejectedValue(error)
 await expect(commitPaperReview({review_request_id:'same'})).rejects.toBe(error)
 expect(api.post).toHaveBeenCalledTimes(1)
})
it('两次代理失败仍报告最终失败，不无限重试',async()=>{
 const error=Object.assign(new Error('HTTP 502'),{status:502})
 vi.mocked(api.post).mockRejectedValue(error)
 await expect(commitPaperReview({review_request_id:'same'})).rejects.toBe(error)
 expect(api.post).toHaveBeenCalledTimes(2)
})
it('没有操作身份时不能重试未知结果',async()=>{
 const error=Object.assign(new Error('HTTP 504'),{status:504})
 vi.mocked(api.post).mockRejectedValue(error)
 await expect(commitPaperReview({})).rejects.toBe(error)
 expect(api.post).toHaveBeenCalledTimes(1)
})
