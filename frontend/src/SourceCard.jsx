const styles = {

  card: {
    borderWidth: "1px",
    borderStyle: "solid",
    borderColor: "#555",
    borderRadius: "4px",
    padding: "8px",
    marginTop: "6px",
    fontSize: "12px",
    color: "#bbb",
    textAlign: "left"
  },

  header: {
    display: "flex",
    justifyContent: "space-between",
    gap: "8px",
    marginBottom: "6px",
    color: "#8ecbff"
  },

  body: {
    whiteSpace: "pre-wrap",
    maxHeight: "140px",
    overflowY: "auto",
    lineHeight: "1.5"
  }
};

function SourceCard({ index, source }) {

  // 兼容早期只存字符串的来源格式
  const legacy = typeof source === "string";

  const text = legacy ? source : source.chunk;

  const filename = legacy ? null : source.filename;

  const chunkIndex = legacy ? null : source.chunk_index;

  return (

    <div style={styles.card}>

      <div style={styles.header}>

        <b>来源 {index + 1}</b>

        {
          filename && (
            <span title={filename}>
              {filename}
              {
                typeof chunkIndex === "number"
                  ? ` · 第 ${chunkIndex + 1} 块`
                  : ""
              }
            </span>
          )
        }

      </div>

      <div style={styles.body}>
        {text}
      </div>

    </div>
  );
}

export default SourceCard;
