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

import SourceCard from "./SourceCard";

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

  toolCall: {
    display: "inline-block",
    textAlign: "left",
    width: "90%",
    borderWidth: "1px",
    borderStyle: "solid",
    borderColor: "#5b4b8a",
    borderRadius: "4px",
    padding: "8px",
    marginTop: "6px",
    fontSize: "12px",
    color: "#cbb8ff"
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
    documents: 0,
    building: false,
    finished_at: null
  });

  // 非 null 表示「已经触发构建、正等它结束」，from 是触发时的 finished_at
  const [buildWatch, setBuildWatch] = useState(null);

  const messageBoxRef = useRef(null);

  // 并发请求的序号，用来丢弃过期响应
  const conversationsSeq = useRef(0);

  const knowledgeSeq = useRef(0);

  // 轮询次数，防止文档一直卡在 pending 时无限轮询
  const pollCount = useRef(0);

  // 加载会话列表
  const refreshConversations = async () => {

    const seq = ++conversationsSeq.current;

    const data = await listConversations();

    // 已经有更新的请求发出，这次结果作废
    if (seq !== conversationsSeq.current) return data;

    setConversations(data);

    return data;
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

  // 后台构建期间需要轮询：索引状态和每个文档的状态都在变
  const hasUnsettledDocs = documents.some(
    (doc) => doc.status === "pending" || doc.status === "processing"
  );

  // 盯梢中：构建已触发，但还没观测到「新一轮真的跑完了」。
  // 不能只看 building 字段——请求返回时后台任务可能还没开始，
  // 服务端会返回 building=false，那会让轮询立刻停掉、界面卡住不动。
  // 所以用触发时的 finished_at 做判据：它变了才说明这一轮结束了
  const watchingBuild =
    buildWatch !== null &&
    (
      indexStatus.building ||
      indexStatus.finished_at === buildWatch.from
    );

  const shouldPoll =
    indexStatus.building || hasUnsettledDocs || watchingBuild;

  useEffect(() => {

    if (!shouldPoll) {

      pollCount.current = 0;

      return;
    }

    const timer = setInterval(() => {

      // 兜底：文档一直卡在 pending（例如旧 /upload 接口建的）时不要无限轮询
      if (++pollCount.current > 40) {

        clearInterval(timer);

        return;
      }

      refreshKnowledge().catch(() => {});

    }, 1500);

    return () => clearInterval(timer);

  }, [shouldPoll]);

  // 触发构建前调用：记下当前收尾时间
  const watchBuild = () => {

    setBuildWatch({ from: indexStatus.finished_at });

    pollCount.current = 0;
  };

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

      // 上传已经自动排队构建，进入盯梢状态
      watchBuild();

      await refreshKnowledge();

      alert(`成功上传 ${uploaded} 个PDF，正在后台构建知识库`);

    } catch (error) {

      alert("上传失败: " + error.message);
    }
  };

  // 删除PDF
  const handleDeleteDocument = async (id, filename) => {

    if (!window.confirm(`确认删除 ${filename}?`)) return;

    try {

      const data = await deleteDocument(id);

      // 删除会触发后台重建索引，跟着轮询
      if (data.index_rebuild_scheduled) watchBuild();

      await refreshKnowledge();

    } catch (error) {

      alert("删除失败: " + error.message);
    }
  };

  // 构建 / 重建知识库：只负责排队，结果靠轮询观察
  const handleBuildRag = async () => {

    try {

      await buildRag();

      watchBuild();

    } catch (error) {

      alert(error.message);

      // 409 = 已经有一次构建在跑，跟着它一起轮询，
      // 而不是让用户以为这次点击彻底失败了
      if (error.status === 409) {

        watchBuild();

        await refreshKnowledge().catch(() => {});
      }
    }
  };

  // 发送消息：mode 为 chat / rag / tools / agent
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
          sources: data.sources || [],
          tool_calls: data.tool_calls || []
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
                disabled={indexStatus.building}
                style={{ marginLeft: "10px" }}
              >
                {indexStatus.building ? "构建中..." : "构建知识库"}
              </button>
            </div>

            <div
              style={{
                marginTop: "8px",
                fontSize: "13px",
                color: indexStatus.building
                  ? "#ffd479"
                  : indexStatus.built
                    ? "#7ddc7d"
                    : "#999"
              }}
            >
              {
                indexStatus.building
                  ? "索引构建中..."
                  : indexStatus.built
                    ? `索引已构建：${indexStatus.documents} 个文档 / ${indexStatus.chunk_count} 个 Chunk`
                    : "索引未构建"
              }

              {
                indexStatus.last_error && (
                  <span
                    style={{
                      color: "#ff7b7b",
                      marginLeft: "8px"
                    }}
                  >
                    上次构建失败：{indexStatus.last_error}
                  </span>
                )
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
                              : doc.status === "processing"
                                ? "#ffd479"
                                : "#ddd"
                      }}
                    >
                      {
                        doc.status === "ready"
                          ? `${doc.chunk_count} chunks`
                          : doc.status === "failed"
                            ? `失败: ${doc.error || ""}`
                            : doc.status === "processing"
                              ? "处理中..."
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

                  {/* Function Calling 轨迹 */}
                  {
                    (msg.tool_calls || []).map((call, i) => (

                      <div
                        key={i}
                        style={styles.toolCall}
                      >
                        <b>
                          {
                            typeof call.step === "number"
                              ? `第 ${call.step} 步 · `
                              : ""
                          }
                          🔧 {call.name}
                        </b>

                        <div style={{ color: "#aaa" }}>
                          参数：{JSON.stringify(call.arguments)}
                        </div>

                        <div
                          style={{
                            whiteSpace: "pre-wrap",
                            maxHeight: "80px",
                            overflowY: "auto"
                          }}
                        >
                          结果：{
                            String(call.result).slice(0, 300)
                          }
                        </div>
                      </div>
                    ))
                  }

                  {/* 参考资料 */}
                  {
                    (msg.sources || []).length > 0 && (

                      <div
                        style={{
                          display: "inline-block",
                          textAlign: "left",
                          width: "90%"
                        }}
                      >

                        <div
                          style={{
                            fontSize: "12px",
                            color: "#888",
                            marginTop: "8px"
                          }}
                        >
                          参考资料（{msg.sources.length}）
                        </div>

                        {
                          msg.sources.map((source, i) => (

                            <SourceCard
                              key={i}
                              index={i}
                              source={source}
                            />
                          ))
                        }

                      </div>
                    )
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

          <button
            onClick={() => handleSend("tools")}
            disabled={loading}
            style={{ marginLeft: "10px" }}
          >
            工具模式
          </button>

          <button
            onClick={() => handleSend("agent")}
            disabled={loading}
            style={{ marginLeft: "10px" }}
          >
            Agent
          </button>

        </div>

      </div>

    </div>
  );
}

export default App;
