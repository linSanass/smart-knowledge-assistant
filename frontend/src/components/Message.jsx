import Markdown from "./Markdown";

import Sources from "./Sources";


function ToolCalls({ calls }) {

  if (!calls || calls.length === 0) {

    return null;
  }

  return (

    <details className="tools">

      <summary>
        工具调用 · {calls.length} 次
      </summary>

      <div className="tools-list">

        {
          calls.map((call, index) => (

            <div className="tool-item" key={index}>

              <div className="tool-item-head">

                {
                  typeof call.step === "number"
                    ? `第 ${call.step} 步 · `
                    : ""
                }

                {call.name}

                {
                  call.ok === false
                    ? " · 失败"
                    : ""
                }

              </div>

              <div className="tool-item-body">

                {JSON.stringify(call.arguments)}

                {"\n"}

                {String(call.result ?? "").slice(0, 400)}

              </div>

            </div>
          ))
        }

      </div>

    </details>
  );
}


function Message({ message }) {

  const isUser = message.role === "user";

  if (isUser) {

    return (

      <div className="msg msg-user">

        <div className="msg-user-body">
          {message.content}
        </div>

      </div>
    );
  }

  return (

    <div className="msg msg-ai">

      <div className="msg-ai-body">

        {/* 助手回答走 Markdown：代码高亮、表格、列表都由它接管 */}
        <Markdown>{message.content || ""}</Markdown>

        {/* 历史会话里可能存有工具调用轨迹，收在折叠区里，
            默认不展开，避免干扰阅读 */}
        <ToolCalls calls={message.tool_calls} />

        {/* 参考来源固定在回答底部 */}
        <Sources sources={message.sources} />

      </div>

    </div>
  );
}


export default Message;
