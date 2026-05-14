"""
ETL 集成测试（Company / User 同步）
使用真实临时数据库验证 ETL 逻辑：
1. 首次同步：新增数据
2. 再次同步：跳过已存在记录（skipped > 0）
3. sys_id 唯一性验证
4. sync_from_api() 集成调用
"""
import os
import sys
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Mock API 数据 ──────────────────────────────────
MOCK_COMPANIES = [
    {"sys_id": "co-001", "name": "测试公司 A"},
    {"sys_id": "co-002", "name": "测试公司 B"},
    {"sys_id": "co-003", "name": "测试公司 C"},
]

MOCK_USERS = [
    {"sys_id": "us-001", "name": "张三", "email": "zhangsan@test.com", "user_name": "zhangsan", "department": "IT", "phone": "13800000001", "mobile_phone": "13800000001", "title": "工程师", "active": "true"},
    {"sys_id": "us-002", "name": "李四", "email": "lisi@test.com", "user_name": "lisi", "department": "运维", "phone": "13800000002", "mobile_phone": "13800000002", "title": "运维工程师", "active": "true"},
    {"sys_id": "us-003", "name": "王五", "email": "wangwu@test.com", "user_name": "wangwu", "department": "销售", "phone": "13800000003", "mobile_phone": "13800000003", "title": "销售经理", "active": "false"},
]


# ── 临时数据库 fixture ─────────────────────────────
@pytest.fixture
def fresh_db():
    """
    创建干净的临时 SQLite 数据库，测试后清理。
    通过 patch SessionLocal 确保 ETL 使用临时数据库。
    """
    # 创建临时目录中的 db 文件（确保可写）
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test.db")

    # 先创建表
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.models import Company, User, Incident

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine)

    # 真正替换 SessionLocal（双向 patch）
    import app.database as db_mod
    import app.etl as etl_mod

    db_mod.SessionLocal = SessionFactory
    etl_mod.SessionLocal = SessionFactory

    yield db_path, SessionFactory

    # 清理
    engine.dispose()
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)


def get_db_conn(db_path):
    return sqlite3.connect(db_path)


# ── 测试 Company ETL ───────────────────────────────

def test_company_sync_first_run_creates_data(fresh_db):
    """首次同步：应新增所有记录，skipped = 0"""
    db_path, _ = fresh_db
    from app.etl import sync_companies_from_api

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_companies_from_api", lambda t: MOCK_COMPANIES):
        result = sync_companies_from_api()

    assert result["status"] == "ok"
    assert result["added"] == 3, f"期望新增 3 条，实际: {result}"
    assert result["skipped"] == 0, f"首次同步 skipped 应为 0，实际: {result['skipped']}"
    assert result["total"] == 3


def test_company_sync_second_run_skips_existing(fresh_db):
    """再次同步：已存在记录应被跳过，skipped > 0"""
    db_path, _ = fresh_db
    from app.etl import sync_companies_from_api

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_companies_from_api", lambda t: MOCK_COMPANIES):
        r1 = sync_companies_from_api()
        r2 = sync_companies_from_api()

    assert r1["status"] == "ok"
    assert r1["added"] == 3
    assert r1["skipped"] == 0

    assert r2["status"] == "ok"
    assert r2["added"] == 0, f"二次同步应新增 0 条，实际: {r2['added']}"
    assert r2["skipped"] == 3, f"二次同步应跳过 3 条，实际: {r2['skipped']}"
    assert r2["total"] == 3


def test_company_idempotent(fresh_db):
    """幂等性：多次同步不产生重复数据"""
    db_path, _ = fresh_db
    from app.etl import sync_companies_from_api

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_companies_from_api", lambda t: MOCK_COMPANIES):
        for i in range(5):
            r = sync_companies_from_api()
            assert r["total"] == 3, f"第 {i+1} 次同步后总量应为 3，实际: {r['total']}"


def test_company_logic_deduplicates_by_sys_id(fresh_db):
    """逻辑去重：相同 sys_id 第二次会被识别为已存在而跳过"""
    db_path, _ = fresh_db
    from app.etl import sync_companies_from_api

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_companies_from_api", lambda t: [
             {"sys_id": "dup-id", "name": "公司 A"},
             {"sys_id": "dup-id", "name": "公司 B（重复）"},
         ]):
        result = sync_companies_from_api()

    assert result["status"] == "ok"
    assert result["added"] == 1
    assert result["skipped"] == 1
    assert result["total"] == 1


def test_company_sys_id_unique_constraint_in_db(fresh_db):
    """数据库模型：sys_id 列声明了 unique=True"""
    db_path, _ = fresh_db
    from app.models import Company

    assert Company.__table__.c.sys_id.unique is True

    conn = get_db_conn(db_path)
    # 验证 SQLite 实际创建了唯一索引
    indexes = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='companies' AND sql LIKE '%sys_id%'"
    ).fetchall()
    conn.close()
    assert len(indexes) >= 1, f"sys_id 缺少唯一索引，实际索引: {indexes}"


def test_company_partial_new_data(fresh_db):
    """部分新增：混合数据（部分已存在 + 部分新增）"""
    db_path, _ = fresh_db
    from app.etl import sync_companies_from_api

    fetch_count = [0]

    def mock_fetch(token):
        fetch_count[0] += 1
        if fetch_count[0] == 1:
            return MOCK_COMPANIES[:2]   # co-001, co-002
        else:
            return [
                {"sys_id": "co-001", "name": "测试公司 A"},
                {"sys_id": "co-002", "name": "测试公司 B"},
                {"sys_id": "co-003", "name": "测试公司 C"},  # 新增
            ]

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_companies_from_api", mock_fetch):
        r1 = sync_companies_from_api()
        assert r1["added"] == 2, f"首次应新增 2 条: {r1}"
        assert r1["total"] == 2

        r2 = sync_companies_from_api()
        assert r2["added"] == 1, f"二次应新增 1 条（co-003）: {r2}"
        assert r2["skipped"] == 2, f"二次应跳过 2 条: {r2}"
        assert r2["total"] == 3


# ── 测试 User ETL ──────────────────────────────────

def test_user_sync_first_run_creates_data(fresh_db):
    """首次同步：应新增所有用户记录"""
    db_path, _ = fresh_db
    from app.etl import sync_users_from_api

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_users_from_api", lambda t, limit=500: MOCK_USERS):
        result = sync_users_from_api()

    assert result["status"] == "ok"
    assert result["added"] == 3
    assert result["skipped"] == 0
    assert result["total"] == 3


def test_user_sync_second_run_skips_existing(fresh_db):
    """再次同步：已存在用户应被跳过"""
    db_path, _ = fresh_db
    from app.etl import sync_users_from_api

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_users_from_api", lambda t, limit=500: MOCK_USERS):
        r1 = sync_users_from_api()
        r2 = sync_users_from_api()

    assert r1["status"] == "ok"
    assert r1["added"] == 3

    assert r2["status"] == "ok"
    assert r2["added"] == 0
    assert r2["skipped"] == 3
    assert r2["total"] == 3


def test_user_idempotent(fresh_db):
    """幂等性：多次同步不产生重复用户"""
    db_path, _ = fresh_db
    from app.etl import sync_users_from_api

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_users_from_api", lambda t, limit=500: MOCK_USERS):
        for i in range(3):
            r = sync_users_from_api()
            assert r["total"] == 3, f"第 {i+1} 次同步后总量应为 3，实际: {r['total']}"


def test_user_all_fields_saved(fresh_db):
    """验证所有用户字段均正确写入数据库"""
    db_path, _ = fresh_db
    from app.etl import sync_users_from_api

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_users_from_api", lambda t, limit=500: MOCK_USERS):
        sync_users_from_api()

    conn = get_db_conn(db_path)
    row = conn.execute(
        "SELECT sys_id, name, email, user_name, department, phone, title, active FROM users WHERE sys_id = 'us-001'"
    ).fetchone()
    conn.close()

    assert row is not None, "us-001 用户记录不存在"
    assert row[0] == "us-001"
    assert row[1] == "张三"
    assert row[2] == "zhangsan@test.com"
    assert row[3] == "zhangsan"
    assert row[4] == "IT"
    assert row[5] == "13800000001"
    assert row[6] == "工程师"
    assert row[7] == "true"


# ── 测试集成 sync_from_api ─────────────────────────

def test_sync_from_api_includes_company_and_user(fresh_db):
    """sync_from_api() 应调用并返回 company 和 user 同步结果"""
    db_path, _ = fresh_db
    from app.etl import sync_from_api

    def mock_fetch_incidents(token, limit=200):
        return [{
            "number": "INC001", "short_description": "测试工单",
            "priority": "P1", "state": "New", "category": "网络",
            "assignment_group": "IT", "company": "测试公司 A",
            "caller": "张三",
            "sys_created_on": "2026-04-01 10:00:00",
            "sys_updated_on": "2026-04-01 10:00:00",
        }]

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_incidents_from_api", mock_fetch_incidents), \
         patch("app.etl.fetch_companies_from_api", lambda t: MOCK_COMPANIES), \
         patch("app.etl.fetch_users_from_api", lambda t, limit=500: MOCK_USERS):
        result = sync_from_api(full_sync=True)

    assert result["status"] == "ok"
    assert result["synced"] == 1
    assert result["companies"]["status"] == "ok"
    assert result["companies"]["added"] == 3
    assert result["users"]["status"] == "ok"
    assert result["users"]["added"] == 3

    conn = get_db_conn(db_path)
    inc_count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    co_count  = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    us_count  = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()

    assert inc_count == 1
    assert co_count == 3
    assert us_count == 3


# ── 测试边界情况 ───────────────────────────────────

def test_company_sync_empty_response(fresh_db):
    """API 返回空数据时应返回错误状态"""
    db_path, _ = fresh_db
    from app.etl import sync_companies_from_api

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_companies_from_api", lambda t: []):
        result = sync_companies_from_api()

    assert result["status"] == "error"
    assert "API 未返回任何公司记录" in result["message"]


def test_user_sync_empty_response(fresh_db):
    """API 返回空数据时应返回错误状态"""
    db_path, _ = fresh_db
    from app.etl import sync_users_from_api

    with patch("app.etl.login_api", lambda: "mock-token"), \
         patch("app.etl.fetch_users_from_api", lambda t, limit=500: []):
        result = sync_users_from_api()

    assert result["status"] == "error"
    assert "API 未返回任何用户记录" in result["message"]


def test_company_sync_auth_failure(fresh_db):
    """认证失败时应返回错误状态"""
    db_path, _ = fresh_db
    from app.etl import sync_companies_from_api

    with patch("app.etl.login_api", lambda: None):
        result = sync_companies_from_api()

    assert result["status"] == "error"
    assert "API 认证失败" in result["message"]
