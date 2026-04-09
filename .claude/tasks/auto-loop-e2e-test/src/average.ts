/**
 * 计算数字数组的算术平均值。
 *
 * 功能规格（详见本 task 的 README.md）：
 * - 返回数组所有元素的算术平均值
 * - 空数组必须返回 0（不能抛异常、不能返回 NaN 或 Infinity）
 * - 只有一个元素时返回该元素本身
 * - 所有元素都是 0 时返回 0
 */
export function average(numbers: number[]): number {
  if (numbers.length === 0) return 0;
  return numbers.reduce((a, b) => a + b, 0) / numbers.length;
}
