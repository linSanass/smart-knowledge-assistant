import { useEffect, useRef } from "react";


function PaperclipIcon() {

  return (

    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >

      <path
        d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"
      />

    </svg>
  );
}


function SendIcon() {

  return (

    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >

      <line x1="12" y1="19" x2="12" y2="5" />

      <polyline points="5 12 12 5 19 12" />

    </svg>
  );
}


function Composer({

  value,
  onChange,
  onSend,
  loading,

  onUploadFiles,
  uploading,

  note,
  noteError

}) {

  const textareaRef = useRef(null);

  const fileRef = useRef(null);

  // 跟随内容长高，超过 CSS 的 max-height 后由它接管滚动
  useEffect(() => {

    const el = textareaRef.current;

    if (!el) return;

    el.style.height = "auto";

    el.style.height = el.scrollHeight + "px";

  }, [value]);

  const canSend = value.trim().length > 0 && !loading;

  const handleKeyDown = (event) => {

    // Enter 发送，Shift+Enter 换行
    if (event.key === "Enter" && !event.shiftKey) {

      event.preventDefault();

      if (canSend) onSend();
    }
  };

  return (

    <div className="composer-wrap">

      <div className="composer">

        <textarea
          ref={textareaRef}
          className="composer-input"
          rows={1}
          value={value}
          placeholder="问点什么，或上传 PDF 建立知识库…"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
        />

        <div className="composer-row">

          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            multiple
            hidden
            onChange={(event) => {

              const files = Array.from(event.target.files || []);

              // 清空 value，否则同一个文件选第二次不会触发 change
              event.target.value = "";

              if (files.length > 0) onUploadFiles(files);
            }}
          />

          <button
            type="button"
            className="btn btn-icon"
            title="上传 PDF"
            disabled={uploading}
            onClick={() => fileRef.current?.click()}
          >

            <PaperclipIcon />

          </button>

          <span className="composer-hint">

            {
              uploading
                ? "上传中…"
                : "Enter 发送 · Shift + Enter 换行"
            }

          </span>

          <button
            type="button"
            className="btn btn-send"
            title="发送"
            disabled={!canSend}
            onClick={onSend}
          >

            <SendIcon />

          </button>

        </div>

      </div>

      {
        note && (
          <div
            className={
              "composer-note" + (noteError ? " error" : "")
            }
          >
            {note}
          </div>
        )
      }

    </div>
  );
}


export default Composer;
