import { useEffect, useState } from "react";

import { STATUS_TEXT, formatSize, formatTime } from "../format";


function KnowledgeDialog({

  mode,
  item,
  onClose,
  onCreate,
  onUpdate,
  onEdit,
  onDelete,
  busy

}) {

  // 表单初值直接用 props 算。
  // 切换条目时靠外层给的 key 让本组件重挂载，初值随之刷新，
  // 不必再用 effect 去同步（那会多触发一轮渲染）
  const [title, setTitle] = useState(item?.filename || "");

  const [content, setContent] = useState(item?.content || "");

  // Esc 关闭
  useEffect(() => {

    if (!mode) return undefined;

    const onKey = (event) => {

      if (event.key === "Escape") onClose();
    };

    window.addEventListener("keydown", onKey);

    return () => window.removeEventListener("keydown", onKey);

  }, [mode, onClose]);

  if (!mode) return null;

  const isForm = mode === "create" || mode === "edit";

  const isNote = item?.kind === "note";

  const canSubmit =
    title.trim().length > 0 && content.trim().length > 0 && !busy;

  const heading = mode === "create"
    ? "新建知识"
    : mode === "edit"
      ? "编辑知识"
      : isNote ? "笔记详情" : "文档详情";

  const submit = () => {

    if (!canSubmit) return;

    if (mode === "create") {

      onCreate(title.trim(), content.trim());

    } else {

      onUpdate(item.id, title.trim(), content.trim());
    }
  };

  return (

    <div
      className="dialog-backdrop"
      onClick={(event) => {

        // 只有点在遮罩本身上才关闭，点内容区不关
        if (event.target === event.currentTarget) onClose();
      }}
    >

      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={heading}
      >

        <div className="dialog-head">

          <div className="dialog-title">{heading}</div>

          <button
            type="button"
            className="btn btn-icon"
            onClick={onClose}
            title="关闭"
          >
            ×
          </button>

        </div>

        <div className="dialog-body">

          {
            isForm ? (

              <>

                <label className="field">

                  <span className="field-label">标题</span>

                  <input
                    className="field-input"
                    value={title}
                    autoFocus
                    placeholder="例如：Unity Addressables"
                    onChange={(e) => setTitle(e.target.value)}
                  />

                </label>

                <label className="field">

                  <span className="field-label">内容</span>

                  <textarea
                    className="field-textarea"
                    value={content}
                    rows={7}
                    placeholder="例如：Addressables 用于资源管理与热更新。"
                    onChange={(e) => setContent(e.target.value)}
                  />

                </label>

              </>

            ) : (

              <>

                <div className="detail-row">

                  <span className="detail-label">文件名</span>

                  <span className="detail-value">{item?.filename}</span>

                </div>

                <div className="detail-row">

                  <span className="detail-label">上传时间</span>

                  <span className="detail-value">
                    {formatTime(item?.created_at)}
                  </span>

                </div>

                <div className="detail-row">

                  <span className="detail-label">文件大小</span>

                  <span className="detail-value">
                    {
                      isNote
                        ? "手写知识，无文件"
                        : formatSize(item?.size)
                    }
                  </span>

                </div>

                <div className="detail-row">

                  <span className="detail-label">状态</span>

                  <span className="detail-value">
                    {
                      item?.status === "failed"
                        ? `失败${item?.error ? "：" + item.error : ""}`
                        : STATUS_TEXT[item?.status] || item?.status
                    }
                  </span>

                </div>

                {
                  isNote && item?.content && (
                    <div className="detail-content">
                      {item.content}
                    </div>
                  )
                }

              </>

            )
          }

        </div>

        <div className="dialog-foot">

          {
            mode === "view" && (
              <button
                type="button"
                className="btn btn-danger"
                disabled={busy}
                onClick={() => onDelete(item)}
              >
                删除
              </button>
            )
          }

          <div className="dialog-foot-right">

            {
              mode === "view" ? (

                <>

                  {
                    isNote && (
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => onEdit(item)}
                      >
                        编辑
                      </button>
                    )
                  }

                  <button
                    type="button"
                    className="btn"
                    onClick={onClose}
                  >
                    关闭
                  </button>

                </>

              ) : (

                <>

                  <button
                    type="button"
                    className="btn"
                    onClick={onClose}
                  >
                    取消
                  </button>

                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!canSubmit}
                    onClick={submit}
                  >
                    {busy ? "保存中…" : "保存"}
                  </button>

                </>

              )
            }

          </div>

        </div>

      </div>

    </div>
  );
}


export default KnowledgeDialog;
