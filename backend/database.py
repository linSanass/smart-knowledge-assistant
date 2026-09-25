import os

from dotenv import load_dotenv

from sqlalchemy import (
    create_engine,
    inspect,
    text
)

from sqlalchemy.orm import (
    declarative_base,
    sessionmaker
)

from sqlalchemy.schema import CreateColumn

load_dotenv()


# =========================
# 数据库连接串
# =========================

# 密码等敏感信息只通过环境变量注入
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:

    raise RuntimeError(
        "缺少 DATABASE_URL 环境变量，请在 backend/.env 中配置，"
        "例如 mysql+pymysql://user:password@127.0.0.1:3306/smart_ai_assistant"
    )


# =========================
# Engine
# =========================

engine = create_engine(
    DATABASE_URL,

    # 连接被 MySQL 回收后自动重连
    pool_pre_ping=True,

    # 避免超过 MySQL wait_timeout 后拿到失效连接
    pool_recycle=3600,

    echo=False
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


Base = declarative_base()


# =========================
# FastAPI 依赖
# =========================

def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()


# =========================
# 建表
# =========================

def init_db():

    # 导入模型，让 Base.metadata 收集到所有表
    from models import Document  # noqa: F401
    from models import Conversation  # noqa: F401
    from models import ChatMessage  # noqa: F401

    Base.metadata.create_all(bind=engine)

    sync_columns()


def sync_columns():
    """
    轻量迁移。

    create_all 只会建缺失的表，不会给已存在的表补列，
    所以这里对比模型与真实表结构，自动 ADD COLUMN。
    """

    inspector = inspect(engine)

    with engine.begin() as conn:

        for table in Base.metadata.sorted_tables:

            if not inspector.has_table(table.name):

                continue

            existing = {
                column["name"]
                for column in inspector.get_columns(
                    table.name
                )
            }

            for column in table.columns:

                if column.name in existing:

                    continue

                ddl = CreateColumn(column).compile(
                    dialect=engine.dialect
                )

                conn.execute(
                    text(
                        f"ALTER TABLE {table.name} "
                        f"ADD COLUMN {ddl}"
                    )
                )
