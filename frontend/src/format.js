// 展示层的格式化工具。
// 单独放一个非组件文件：从组件文件里导出常量会破坏 Fast Refresh

export const STATUS_TEXT = {

  ready: "已索引",

  processing: "索引中",

  pending: "待索引",

  failed: "失败"
};


export const STATUS_COLOR = {

  ready: "var(--ok)",

  processing: "var(--warn)",

  failed: "var(--danger)",

  pending: "var(--text-faint)"
};


export function formatSize(bytes) {

  if (bytes === null || bytes === undefined) return "—";

  if (bytes < 1024) return `${bytes} B`;

  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;

  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}


export function formatTime(iso) {

  if (!iso) return "—";

  // 后端存的是 naive UTC，补上 Z 让浏览器按本地时区换算
  const date = new Date(iso.endsWith("Z") ? iso : iso + "Z");

  if (Number.isNaN(date.getTime())) return iso;

  const pad = (n) => String(n).padStart(2, "0");

  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
    + ` ${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}
