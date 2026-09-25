import { useState } from "react";


// 兼容早期只存了字符串的来源格式
function normalize(source) {

  if (typeof source === "string") {

    return { filename: null, chunk_index: null, chunk: source };
  }

  return {
    filename: source.filename,
    chunk_index: source.chunk_index,
    chunk: source.chunk
  };
}


function Sources({ sources }) {

  // 一次只展开一条，避免整屏都被原文占满
  const [openIndex, setOpenIndex] = useState(null);

  if (!sources || sources.length === 0) {

    return null;
  }

  const items = sources.map(normalize);

  const opened = openIndex === null ? null : items[openIndex];

  return (

    <div className="sources">

      <div className="sources-label">参考来源</div>

      <div className="source-chips">

        {
          items.map((item, index) => (

            <button
              key={index}
              type="button"
              className={
                "source-chip" + (openIndex === index ? " active" : "")
              }
              onClick={() =>
                setOpenIndex(openIndex === index ? null : index)
              }
              title={item.filename || "来源片段"}
            >

              <span className="source-chip-name">
                {item.filename || `来源 ${index + 1}`}
              </span>

              {
                typeof item.chunk_index === "number" && (
                  <span className="source-chip-idx">
                    #{item.chunk_index + 1}
                  </span>
                )
              }

            </button>
          ))
        }

      </div>

      {
        opened && opened.chunk && (
          <div className="source-excerpt">
            {opened.chunk}
          </div>
        )
      }

    </div>
  );
}


export default Sources;
