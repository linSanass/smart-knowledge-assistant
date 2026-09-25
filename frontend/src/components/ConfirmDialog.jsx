import { useEffect } from "react";


function ConfirmDialog({

  open,
  title,
  message,
  confirmText = "删除",
  onConfirm,
  onCancel,
  busy

}) {

  useEffect(() => {

    if (!open) return undefined;

    const onKey = (event) => {

      if (event.key === "Escape") onCancel();
    };

    window.addEventListener("keydown", onKey);

    return () => window.removeEventListener("keydown", onKey);

  }, [open, onCancel]);

  if (!open) return null;

  return (

    <div
      className="dialog-backdrop"
      onClick={(event) => {

        if (event.target === event.currentTarget) onCancel();
      }}
    >

      <div
        className="dialog dialog-sm"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >

        <div className="dialog-head">

          <div className="dialog-title">{title}</div>

        </div>

        <div className="dialog-body">

          <p className="confirm-text">{message}</p>

        </div>

        <div className="dialog-foot">

          <div className="dialog-foot-right">

            <button
              type="button"
              className="btn"
              onClick={onCancel}
            >
              取消
            </button>

            <button
              type="button"
              className="btn btn-danger"
              disabled={busy}
              onClick={onConfirm}
            >
              {busy ? "删除中…" : confirmText}
            </button>

          </div>

        </div>

      </div>

    </div>
  );
}


export default ConfirmDialog;
