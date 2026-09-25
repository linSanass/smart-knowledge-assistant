import Message from "./Message";


function Typing() {

  return (

    <div className="msg msg-ai">

      <div className="msg-ai-body">

        <div className="typing" aria-label="正在生成回答">
          <span />
          <span />
          <span />
        </div>

      </div>

    </div>
  );
}


function EmptyState({ hasIndex, onSuggestion }) {

  // 固定四条，正好铺满两列网格，不留落单的第三张
  const suggestions = hasIndex
    ? [
        "总结一下知识库里的主要内容",
        "把文档里的关键概念列成表格",
        "知识库里对这个问题是怎么说的？",
        "这份文档适合谁看？"
      ]
    : [
        "上传 PDF / TXT / Markdown 后，我就能基于它回答问题",
        "没有知识库也可以直接提问",
        "解释一下什么是 RAG",
        "用表格对比几个常见的技术概念"
      ];

  return (

    <div className="empty">

      <div className="empty-inner">

        <div className="empty-mark">S</div>

        <h1 className="empty-title">
          {hasIndex ? "知识库已就绪" : "开始一段对话"}
        </h1>

        <p className="empty-sub">
          {
            hasIndex
              ? "提问会基于你的知识库回答，并在底部给出来源"
              : "上传 PDF / TXT / Markdown 建立知识库，或直接提问"
          }
        </p>

        <div className="suggestions">

          {
            suggestions.map((text) => (

              <button
                key={text}
                type="button"
                className="suggestion"
                onClick={() => onSuggestion(text)}
              >
                {text}
              </button>
            ))
          }

        </div>

      </div>

    </div>
  );
}


function ChatArea({

  messages,
  loading,
  scrollRef,
  hasIndex,
  onSuggestion

}) {

  if (messages.length === 0 && !loading) {

    return (
      <div className="messages" ref={scrollRef}>
        <EmptyState hasIndex={hasIndex} onSuggestion={onSuggestion} />
      </div>
    );
  }

  return (

    <div className="messages" ref={scrollRef}>

      <div className="messages-inner">

        {
          messages.map((message, index) => (

            <Message
              key={message.id || index}
              message={message}
            />
          ))
        }

        {loading && <Typing />}

      </div>

    </div>
  );
}


export default ChatArea;
