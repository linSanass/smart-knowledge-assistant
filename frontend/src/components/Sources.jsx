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


// 按文件归并来源。
//
// 检索取的是最相近的若干 chunk，同一个文件命中多个片段时会把来源位占满，
// 看上去就像只引了一份文档。这里按文件名合并，一个文件只出一个 chip，
// 点开再看它命中的全部片段。
function groupByFile(sources) {

  const groups = [];

  const byName = new Map();

  sources.map(normalize).forEach((item, index) => {

    // 老格式没有文件名，各自单独成组，避免被错误地合到一起
    const key = item.filename || `__anon_${index}`;

    let group = byName.get(key);

    if (!group) {

      group = { filename: item.filename, chunks: [] };

      byName.set(key, group);

      groups.push(group);
    }

    if (item.chunk) {

      group.chunks.push({
        chunk_index: item.chunk_index,
        chunk: item.chunk
      });
    }
  });

  // 组内按在原文中的先后排。
  //
  // 检索结果本身是按相关性距离返回的，直接渲染会出现
  // 「第 2 块」排在「第 1 块」前面 —— 读起来像顺序错了。
  // 文件之间仍然保持相关性顺序（最相关的文件排最前），
  // 只把同一个文件内部的片段排回文档顺序
  groups.forEach((group) => {

    group.chunks.sort((a, b) => {

      const left = typeof a.chunk_index === "number"
        ? a.chunk_index
        : Number.MAX_SAFE_INTEGER;

      const right = typeof b.chunk_index === "number"
        ? b.chunk_index
        : Number.MAX_SAFE_INTEGER;

      return left - right;
    });
  });

  return groups;
}


function Sources({ sources }) {

  // 同时只展开一个文件，避免整屏都被原文占满
  const [openIndex, setOpenIndex] = useState(null);

  if (!sources || sources.length === 0) {

    return null;
  }

  const groups = groupByFile(sources);

  const opened = openIndex === null ? null : groups[openIndex];

  return (

    <div className="sources">

      <div className="sources-label">参考来源</div>

      <div className="source-chips">

        {
          groups.map((group, index) => (

            <button
              key={group.filename || index}
              type="button"
              className={
                "source-chip" + (openIndex === index ? " active" : "")
              }
              onClick={() =>
                setOpenIndex(openIndex === index ? null : index)
              }
              title={group.filename || "来源片段"}
            >

              <span className="source-chip-name">
                {group.filename || `来源 ${index + 1}`}
              </span>

              {/* 命中多个片段时显示数量，比只报一个块号更有信息量 */}
              <span className="source-chip-idx">
                {
                  group.chunks.length > 1
                    ? `${group.chunks.length} 段`
                    : typeof group.chunks[0]?.chunk_index === "number"
                      ? `#${group.chunks[0].chunk_index + 1}`
                      : ""
                }
              </span>

            </button>
          ))
        }

      </div>

      {
        opened && (
          <div className="source-detail">

            {
              opened.chunks.map((item, index) => (

                <div className="source-excerpt" key={index}>

                  {
                    opened.chunks.length > 1 && (
                      <span className="source-excerpt-idx">
                        {
                          typeof item.chunk_index === "number"
                            ? `第 ${item.chunk_index + 1} 块`
                            : `片段 ${index + 1}`
                        }
                      </span>
                    )
                  }

                  {item.chunk}

                </div>
              ))
            }

          </div>
        )
      }

    </div>
  );
}


export default Sources;
