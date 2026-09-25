import { useEffect, useRef, useState } from "react";

import {
  buildRag,
  createConversation,
  deleteConversation,
  deleteDocument,
  getConversation,
  getIndexStatus,
  listConversations,
  listDocuments,
  sendMessage,
  uploadDocument
} from "./api";

const styles = {

  page: {
    width: "1100px",
    margin: "0 auto",
    padding: "20px",
    color: "white"
  },

  layout: {
    display: "flex",
    gap: "20px",
    alignItems: "flex-start"
  },

  sidebar: {
    width: "260px",
    flexShrink: 0
  },

  conversation: {
    // 用长写属性，便于下面只覆盖 borderColor 而不混用简写
    borderWidth: "1px",
    borderStyle: "solid",
    borderColor: "#666",
    padding: "10px",
    marginBottom: "8px",
    cursor: "pointer",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "8px"
  },

  conversationActive: {
    borderColor: "#4a9eff",
    background: "#1b3a5c"
  },

  conversationTitle: {
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    fontSize: "14px"
  },

  main: {
    flex: 1,
    minWidth: 0
  },

  messageBox: {
    border: "1px solid #666",
    height: "460px",
    overflowY: "auto",
    padding: "10px"
  },

  bubble: {
    marginBottom: "15px"
  },

  source: {
    border: "1px solid #555",
    padding: "6px 8px",
    marginTop: "6px",
    fontSize: "12px",
    color: "#bbb",
    whiteSpace: "pre-wrap"
  }
};

function App() {

  const [conversations, setConversations] = useState([]);

  const [currentId, setCurrentId] = useState(null);

  const [messages, setMessages] = useState([]);

  const [message, setMessage] = useState("");

  const [role, setRole] = useState("unity");

  const [loading, setLoading] = useState(false);

  const [pdfFiles, setPdfFiles] = useState([]);

  const [documents, setDocuments] = useState([]);

  const [indexStatus, setIndexStatus] = useState({
    built: false,
    chunk_count: 0,
    documents: 0
  });

  const [knowledgeLoading, setKnowledgeLoading] = useState(false);

  const messageBoxRef = useRef(null);

  // 并发请求的序号，用来丢弃过期响应
  const conversationsSeq = useRef(0);

  const knowledgeSeq = useRef(0);

  // 加载会话列表
  const refreshConversations = async () => {

    const seq = ++conversationsSeq.current;

    const data = await listConversations();

    // 已经有更新的请求发出，这次结果作废
    if (seq !== conversationsSeq.current) return data;

    setConversations(data);

    return data;
  };

  useEffect(() => {

    refreshConversations().catch(
      (error) => alert("加载会话失败: " + error.message)
    );

    refreshKnowledge().catch(
      (error) => alert("加载知识库失败: " + error.message)
    );

  }, []);

  // 切换会话时加载历史消息
  useEffect(() => {

    if (currentId === null) {

      setMessages([]);

      return;
    }

    getConversation(currentId)
      .then((data) => setMessages(data.messages || []))
      .catch((error) => alert("加载历史失败: " + error.message));

  }, [currentId]);

  // 新消息自动滚动到底部
  useEffect(() => {

    const box = messageBoxRef.current;

    if (box) box.scrollTop = box.scrollHeight;

  }, [messages]);

  // 新建会话
  const handleNewConversation = async () => {

    try {

      const conversation = await createConversation();

      setConversations(prev => [conversation, ...prev]);

      setCurrentId(conversation.id);

    } catch (error) {

      alert("新建会话失败: " + error.message);
    }
  };

  // 删除会话
  const handleDeleteConversation = async (event, id) => {

    // 点击删除按钮时不要触发切换会话
    event.stopPropagation();

    if (!window.confirm("确认删除该会话?")) return;

    try {

      await deleteConversation(id);

      setConversations(prev =>
        prev.filter(c => c.id !== id)
      );

      if (currentId === id) setCurrentId(null);

    } catch (error) {

      alert("删除失败: " + error.message);
    }
  };

  // 刷新知识库（文档列表 + 索引状态）
  const refreshKnowledge = async () => {

    const seq = ++knowledgeSeq.current;

    const [docs, status] = await Promise.all([
      listDocuments(),
      getIndexStatus()
    ]);

    // 文档列表和索引状态必须来自同一次刷新，
    // 否则并发刷新时会出现「状态行已更新、文档行还是旧的」
    if (seq !== knowledgeSeq.current) return { docs, status };

    setDocuments(docs);

    setIndexStatus(status);

    return { docs, status };
  };

  // 上传PDF（支持多选）
  const handleUpload = async () => {

    if (pdfFiles.length === 0) {

      alert("请选择PDF");

      return;
    }

    try {

      for (const file of pdfFiles) {

        await uploadDocument(file);
      }

      const uploaded = pdfFiles.length;

      setPdfFiles([]);

      await refreshKnowledge();

      alert(`成功上传 ${uploaded} 个PDF，请点击「构建知识库」`);

    } catch (error) {

      alert("上传失败: " + error.message);
    }
  };

  // 删除PDF
  const handleDeleteDocument = async (id, filename) => {

    if (!window.confirm(`确认删除 ${filename}?`)) return;

    try {

      await deleteDocument(id);

      await refreshKnowledge();

    } catch (error) {

      alert("删除失败: " + error.message);
    }
  };

  // 构建 / 重建知识库
  const handleBuildRag = async () => {

    try {

      const data = await buildRag();

      await refreshKnowledge();

      if (data.chunk_count === 0) {

        alert(data.message);

        return;
      }

      alert(
        `知识库构建完成：${data.documents} 个文档，` +
        `共 ${data.chunk_count} 个 Chunk`
      );

    } catch (error) {

      alert("构建失败: " + error.message);
    }
  };

  // 发送消息：mode 为 chat 或 rag
  const handleSend = async (mode) => {

    const text = message.trim();

    if (!text || loading) return;

    setLoading(true);

    setMessage("");

    // 还没有会话时先自动建一个
    let conversationId = currentId;

    try {

      if (conversationId === null) {

        const conversation = await createConversation();

        conversationId = conversation.id;

        setCurrentId(conversationId);

        setConversations(prev => [conversation, ...prev]);
      }

      // 乐观渲染用户消息
      setMessages(prev => [
        ...prev,
        { role: "user", content: text }
      ]);

      const data = await sendMessage(
        conversationId,
        text,
        mode,
        role
      );

      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources || []
        }
      ]);

      // 标题可能刚由首条消息生成，刷新列表
      await refreshConversations();

    } catch (error) {

      alert("发送失败: " + error.message);

    } finally {

      setLoading(false);
    }
  };

  return (

    <div style={styles.page}>

      <h1>
        Smart Knowledge Assistant
      </h1>

      <div style={styles.layout}>

        {/* 左侧：会话管理 */}
        <div style={styles.sidebar}>

          <button
            onClick={handleNewConversation}
            style={{
              width: "100%",
              padding: "8px",
              marginBottom: "10px"
            }}
          >
            + 新建会话
          </button>

          {
            conversations.map((conversation) => (

              <div
                key={conversation.id}
                onClick={() =>
                  setCurrentId(conversation.id)
                }
                style={{
                  ...styles.conversation,

                  ...(conversation.id === currentId
                    ? styles.conversationActive
                    : {})
                }}
              >

                <div style={styles.conversationTitle}>
                  {conversation.title}

                  <div
                    style={{
                      fontSize: "11px",
                      color: "#999"
                    }}
                  >
                    {conversation.message_count} 条消息
                  </div>
                </div>

                <button
                  onClick={(event) =>
                    handleDeleteConversation(
                      event,
                      conversation.id
                    )
                  }
                  title="删除会话"
                >
                  ×
                </button>

              </div>
            ))
          }

          {
            conversations.length === 0 && (
              <p style={{ color: "#888", fontSize: "13px" }}>
                还没有会话，点击上方按钮开始
              </p>
            )
          }

        </div>

        {/* 右侧：聊天区 */}
        <div style={styles.main}>

          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="unity">Unity导师</option>
            <option value="cpp">C++导师</option>
            <option value="ai">AI全栈导师</option>
            <option value="digital">数字孪生专家</option>
          </select>

          <span
            style={{
              marginLeft: "10px",
              fontSize: "13px",
              color: "#999"
            }}
          >
            {
              currentId === null
                ? "未选择会话（发送时自动新建）"
                : `当前会话 #${currentId}`
            }
          </span>

          <hr />

          {/* 知识库 */}
          <div
            style={{
              borderWidth: "1px",
              borderStyle: "solid",
              borderColor: "#666",
              padding: "10px",
              marginBottom: "10px"
            }}
          >

            <b>知识库</b>

            <div style={{ marginTop: "8px" }}>
              <input
                type="file"
                accept=".pdf"
                multiple
                onChange={(e) =>
                  setPdfFiles(Array.from(e.target.files))
                }
              />

              <button
                onClick={handleUpload}
                style={{ marginLeft: "10px" }}
              >
                上传PDF
              </button>

              <button
                onClick={handleBuildRag}
                style={{ marginLeft: "10px" }}
              >
                构建知识库
              </button>
            </div>

            <div
              style={{
                marginTop: "8px",
                fontSize: "13px",
                color: indexStatus.built ? "#7ddc7d" : "#999"
              }}
            >
              {
                indexStatus.built
                  ? `索引已构建：${indexStatus.documents} 个文档 / ${indexStatus.chunk_count} 个 Chunk`
                  : "索引未构建"
              }
            </div>

            {/* 文档列表 */}
            <div style={{ marginTop: "8px" }}>

              {
                documents.length === 0 && (
                  <span style={{ fontSize: "13px", color: "#888" }}>
                    还没有 PDF
                  </span>
                )
              }

              {
                documents.map((doc) => (

                  <div
                    key={doc.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      fontSize: "13px",
                      padding: "4px 0"
                    }}
                  >

                    <span style={{ flex: 1 }}>
                      {doc.filename}
                    </span>

                    <span
                      style={{
                        color:
                          doc.status === "ready"
                            ? "#7ddc7d"
                            : doc.status === "failed"
                              ? "#ff7b7b"
                              : "#ddd"
                      }}
                    >
                      {
                        doc.status === "ready"
                          ? `${doc.chunk_count} chunks`
                          : doc.status === "failed"
                            ? `失败: ${doc.error || ""}`
                            : "待索引"
                      }
                    </span>

                    <button
                      title="删除文档"
                      onClick={() =>
                        handleDeleteDocument(doc.id, doc.filename)
                      }
                    >
                      ×
                    </button>

                  </div>
                ))
              }

            </div>

          </div>

          <hr />

          {/* 消息列表 */}
          <div
            ref={messageBoxRef}
            style={styles.messageBox}
          >

            {
              messages.map((msg, index) => (

                <div
                  key={msg.id || index}
                  style={{
                    ...styles.bubble,
                    textAlign:
                      msg.role === "user"
                        ? "right"
                        : "left"
                  }}
                >

                  <b>
                    {msg.role === "user" ? "你" : "AI"}
                  </b>

                  <div style={{ whiteSpace: "pre-wrap" }}>
                    {msg.content}
                  </div>

                  {/* 参考资料 */}
                  {
                    (msg.sources || []).map((source, i) => (

                      <div
                        key={i}
                        style={{
                          ...styles.source,
                          display: "inline-block",
                          textAlign: "left",
                          maxWidth: "90%"
                        }}
                      >
                        <b>
                          来源 {i + 1}
                          {
                            // 兼容早期只存字符串的来源格式
                            typeof source === "string"
                              ? ""
                              : ` · ${source.filename} 第${source.chunk_index + 1}块`
                          }
                        </b>

                        <div>
                          {
                            typeof source === "string"
                              ? source
                              : source.chunk
                          }
                        </div>
                      </div>
                    ))
                  }

                </div>
              ))
            }

          </div>

          <br />

          <input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSend("chat");
            }}
            placeholder="输入问题..."
            style={{ width: "520px", padding: "10px" }}
          />

          <button
            onClick={() => handleSend("chat")}
            disabled={loading}
            style={{ marginLeft: "10px" }}
          >
            {loading ? "生成中..." : "AI聊天"}
          </button>

          <button
            onClick={() => handleSend("rag")}
            disabled={loading}
            style={{ marginLeft: "10px" }}
          >
            知识库问答
          </button>

        </div>

      </div>

    </div>
  );
}

export default App;
