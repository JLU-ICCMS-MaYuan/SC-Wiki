/** 只判断实际空值；0、false和unknown都有内容。合法性由服务器字段规则判断。 */
export const isEmptyFieldValue = (value: unknown): boolean => value == null
  || typeof value === 'string' && value.trim() === ''
  || Array.isArray(value) && value.length === 0
  || typeof value === 'object' && value !== null && !Array.isArray(value) && Object.keys(value).length === 0
