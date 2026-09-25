import { STATUS_COLOR, STATUS_TEXT } from "../format";


// 与后端 chat_service.roles 的键一一对应。
// 只在本文件使用，所以不作 export —— 组件文件里导出常量会破坏 Fast Refresh
const ROLE_OPTIONS = [
  { value: "general", label: "通用助手" },
  { value: "coding", label: "编程助手" },
  { value: "translation", label: "翻译助手" },
  { value: "writing", label: "写作助手" },
  { value: "tutor", label: "学习导师" }
];


// PDF 与笔记用不同图标区分，其余展示完全一致
const KIND_ICON = {

  pdf: "📄",

  note: "📝"
};


function Sidebar({

  conversations,
  currentId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,

  role,
  onRoleChange,

  documents,
  onDeleteDocument,
  onOpenDocument,
  onNewNote,

  indexStatus,
  onRebuild,
  building

}) {

  const rebuildable = !building && documents.length > 0;

  // 构建失败时把原因露出来，而不是只躺在接口里
  const buildFailed = !building && Boolean(indexStatus.last_error);

  const footDot = building
    ? "var(--warn)"
    : buildFailed
      ? "var(--danger)"
      : indexStatus.built
        ? "var(--ok)"
        : "var(--text-faint)";

  const footText = building
    ? "知识库构建中…"
    : buildFailed
      ? "上次构建失败，可重试"
      : indexStatus.built
        ? "知识库已就绪"
        : "尚未构建知识库";

  return (

    <aside className="sidebar">

      <div className="sidebar-head">

        <div className="logo">

          <div className="logo-mark">S</div>

          <div className="logo-text">
            <div className="logo-name">Smart Assistant</div>
            <div className="logo-sub">知识库问答</div>
          </div>

        </div>

        <button
          type="button"
          className="btn btn-primary btn-block"
          onClick={onNewConversation}
        >
          新建会话
        </button>

      </div>


      {/* 会话列表 */}
      <div className="sidebar-label">
        会话
      </div>

      <div className="conv-list">

        {
          conversations.map((conversation) => (

            <div
              key={conversation.id}
              className={
                "conv-item"
                + (conversation.id === currentId ? " active" : "")
              }
              onClick={() => onSelectConversation(conversation.id)}
            >

              <span className="conv-title">
                {conversation.title || "新会话"}
              </span>

              <button
                type="button"
                className="btn btn-icon conv-del"
                title="删除会话"
                onClick={(event) => {

                  // 别让点击冒泡到外层的选中逻辑
                  event.stopPropagation();

                  onDeleteConversation(conversation.id);
                }}
              >
                ×
              </button>

            </div>
          ))
        }

        {
          conversations.length === 0 && (
            <div className="empty-hint">
              还没有会话
            </div>
          )
        }

      </div>


      {/* 助手选择 */}
      <div className="sidebar-label">助手</div>

      <div className="sidebar-select-wrap">

        <select
          className="select"
          value={role}
          onChange={(event) => onRoleChange(event.target.value)}
        >

          {
            ROLE_OPTIONS.map((option) => (

              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))
          }

        </select>

      </div>


      {/* 知识库：PDF 与手写知识统一展示在同一个列表里 */}
      <div className="sidebar-label">

        <span>知识库</span>

        <span className="sidebar-label-actions">

          <button
            type="button"
            className="sidebar-label-action"
            onClick={onNewNote}
          >
            新建知识
          </button>

          {
            rebuildable && (
              <button
                type="button"
                className="sidebar-label-action"
                onClick={onRebuild}
              >
                重建
              </button>
            )
          }

        </span>

      </div>

      <div className="doc-list">

        {
          documents.map((doc) => (

            <div
              className="doc-item"
              key={doc.id}
              onClick={() => onOpenDocument(doc)}
              title={doc.filename}
            >

              <span className="doc-icon">
                {KIND_ICON[doc.kind] || KIND_ICON.pdf}
              </span>

              <span className="doc-name">
                {doc.filename}
              </span>

              <span
                className="doc-status"
                style={{
                  color:
                    STATUS_COLOR[doc.status] || "var(--text-faint)"
                }}
              >
                {STATUS_TEXT[doc.status] || doc.status}
              </span>

              <button
                type="button"
                className="btn btn-icon conv-del"
                title="删除"
                onClick={(event) => {

                  // 别让点击冒泡到「打开详情」
                  event.stopPropagation();

                  onDeleteDocument(doc.id, doc.filename);
                }}
              >
                ×
              </button>

            </div>
          ))
        }

        {
          documents.length === 0 && (
            <div className="empty-hint">
              还没有内容。用输入框左侧的按钮上传 PDF / TXT / Markdown，
              或点上方「新建知识」手写一条
            </div>
          )
        }

      </div>


      {/* 索引状态：只说状态，不暴露 chunk / 向量数量 */}
      <div
        className="sidebar-foot"
        title={buildFailed ? indexStatus.last_error : undefined}
      >

        <span className="doc-dot" style={{ background: footDot }} />

        <span>{footText}</span>

      </div>

    </aside>
  );
}


export default Sidebar;
