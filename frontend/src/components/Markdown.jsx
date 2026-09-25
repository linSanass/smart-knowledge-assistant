import { useState } from "react";

import ReactMarkdown from "react-markdown";

import remarkGfm from "remark-gfm";

import rehypeHighlight from "rehype-highlight";


// 从已经高亮过的 React 节点里把纯文本抠出来，供复制按钮使用。
// rehype-highlight 会把代码拆成一堆 span，直接读 children 拿不到原始文本
function textOf(node) {

  if (node === null || node === undefined || node === false) return "";

  if (typeof node === "string" || typeof node === "number") {

    return String(node);
  }

  if (Array.isArray(node)) {

    return node.map(textOf).join("");
  }

  if (node.props && node.props.children !== undefined) {

    return textOf(node.props.children);
  }

  return "";
}


function CodeBlock({ language, children }) {

  const [copied, setCopied] = useState(false);

  const raw = textOf(children);

  const handleCopy = async () => {

    try {

      await navigator.clipboard.writeText(raw);

      setCopied(true);

      // 只做一次轻微的状态回落，不做动画
      setTimeout(() => setCopied(false), 1600);

    } catch {

      // 浏览器不给剪贴板权限就静默失败，不打断阅读
    }
  };

  return (

    <div className="code-block">

      <div className="code-head">

        <span>{language || "code"}</span>

        <button
          type="button"
          className="code-copy"
          onClick={handleCopy}
        >
          {copied ? "已复制" : "复制"}
        </button>

      </div>

      <pre>{children}</pre>

    </div>
  );
}


function Markdown({ children }) {

  return (

    <div className="md">

      <ReactMarkdown

        remarkPlugins={[remarkGfm]}

        rehypePlugins={[
          // ignoreMissing: 遇到没装的语言不要让整段渲染失败
          [rehypeHighlight, { ignoreMissing: true }]
        ]}

        components={{

          // 代码块交给 CodeBlock 加工具栏；
          // 行内 code 走默认渲染，由 CSS 区分
          pre({ children }) {

            const code = Array.isArray(children)
              ? children[0]
              : children;

            const className = code?.props?.className || "";

            const language = /language-(\w+)/.exec(className)?.[1];

            return (
              <CodeBlock language={language}>
                {code?.props?.children ?? children}
              </CodeBlock>
            );
          },

          // 外链新开窗口，避免把应用自身导航掉
          a({ href, children }) {

            return (
              <a
                href={href}
                target="_blank"
                rel="noreferrer noopener"
              >
                {children}
              </a>
            );
          }
        }}
      >
        {children}
      </ReactMarkdown>

    </div>
  );
}


export default Markdown;
