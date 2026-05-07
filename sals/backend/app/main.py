"""
FastAPI 主应用
"""
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, Integer, case

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ── 加载 .env 环境变量（在所有 app 模块导入之前）──
load_dotenv(Path(__file__).parent.parent / ".env")

from app.database import get_db, engine, Base
from app.models import Incident, Company, User
from app.schemas import (
    IncidentOut, IncidentFilter,
    KpiStat, PriorityDist, StateDist, GroupStat,
    AssigneeStat, MonthlyTrend, CustomerStat,
    ProductStat, KeywordStat, SlaStat, DashboardData,
    DailyBreakdown, CompanyOut, UserOut,
)
from app import etl

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def _sync_job():
    """定时同步任务（后台运行，不阻塞请求）"""
    logger.info("[Scheduler] 开始定时 API 同步...")
    result = etl.sync_from_api(full_sync=False)
    logger.info(f"[Scheduler] 同步结果: {result}")


def _start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return
    interval_minutes = int(os.getenv("API_SYNC_INTERVAL_MINUTES", "60"))
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_sync_job, IntervalTrigger(minutes=interval_minutes), id="api_sync")
    _scheduler.start()
    logger.info(f"[Scheduler] 已启动，间隔 {interval_minutes} 分钟同步一次")


def _stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("[Scheduler] 已关闭")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期管理：启动时开定时器，关闭时关定时器"""
    _start_scheduler()
    yield
    _stop_scheduler()


# ── 应用初始化 ──────────────────────────────────────
app = FastAPI(
    title="售后管理 API",
    description="工单数据查询与统计分析",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保数据库存在
Base.metadata.create_all(bind=engine)


# ── 依赖：基础筛选查询 ────────────────────────────────
def apply_filter(q, db: Session, f: Optional[IncidentFilter]):
    if f is None:
        return q
    if f.start_date:
        q = q.filter(Incident.created_at >= f.start_date)
    if f.end_date:
        q = q.filter(Incident.created_at <= f.end_date + " 23:59:59")
    if f.priorities:
        q = q.filter(Incident.priority.in_(f.priorities))
    if f.groups:
        q = q.filter(Incident.assignment_group.in_(f.groups))
    if f.categories:
        q = q.filter(Incident.category.in_(f.categories))
    if f.states:
        q = q.filter(Incident.state.in_(f.states))
    if f.companies:
        q = q.filter(Incident.company.in_(f.companies))
    return q


# ── API 路由 ────────────────────────────────────────

@app.post("/api/init-db")
def init_db(
    source: str = Query("api", pattern="^(api|excel)$"),
    full_sync: bool = Query(True),
):
    """
    重新初始化/同步数据库（同步阻塞模式，方便排查任务）。

    - source=api  （默认）：从 OneProCloud API 拉取真实数据
    - source=excel ：从本地 Excel 加载（仅在无 API 凭证时使用）
    - full_sync=True    ：全量同步（清空后重写），False=增量更新
    - limit  ：已被移除，改用环境变量 API_SYNC_LIMIT 配置
    """
    try:
        if source == "api":
            result = etl.sync_from_api(full_sync=full_sync)
            return result
        else:
            result = etl.load_excel_to_db(etl.EXCEL_PATH)
            return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


class SyncResponse(BaseModel):
    status: str
    message: Optional[str] = None
    synced: Optional[int] = None
    total: Optional[int] = None
    mode: Optional[str] = None


@app.get("/api/sync/status")
def sync_status():
    """返回当前同步状态（最近一条同步结果，需从日志获取，此处返回调度器状态）"""
    return {
        "scheduler_running": _scheduler is not None and _scheduler.running,
        "api_configured": bool(etl.API_USERNAME or os.getenv("ONEPRO_BEARER_TOKEN", "")),
        "sync_limit": etl.API_SYNC_LIMIT,
    }


@app.get("/api/ping")
def ping():
    return {"pong": True, "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/stats/kpi", response_model=KpiStat)
def get_kpi(db: Session = Depends(get_db)):
    total = db.query(Incident).count()
    pending = db.query(Incident).filter(Incident.state == "Pending").count()
    in_progress = db.query(Incident).filter(Incident.state == "In Progress").count()
    resolved = db.query(Incident).filter(Incident.state == "Resolved").count()
    closed = db.query(Incident).filter(Incident.state == "Closed").count()
    canceled = db.query(Incident).filter(Incident.state == "Canceled").count()

    avg_h = db.query(func.avg(Incident.resolve_hours)).scalar() or 0

    sla_ok = db.query(Incident).filter(Incident.is_sla_met == 1).count()
    sla_rate = sla_ok / total * 100 if total > 0 else 0

    p1_q = db.query(Incident).filter(Incident.priority == "P1")
    p1_total = p1_q.count()
    p1_overdue = p1_q.filter(Incident.resolve_hours > 4).count()
    p2_total = db.query(Incident).filter(Incident.priority == "P2").count()

    resolved_total = resolved + closed
    resolved_rate = resolved_total / total * 100 if total > 0 else 0

    return KpiStat(
        total=total, pending=pending, in_progress=in_progress,
        resolved=resolved, closed=closed, canceled=canceled,
        resolved_rate=round(resolved_rate, 2), sla_rate=round(sla_rate, 2), avg_resolve_hours=round(avg_h, 2),
        p1_total=p1_total, p1_overdue=p1_overdue, p2_total=p2_total,
    )


@app.get("/api/stats/priority-dist", response_model=List[PriorityDist])
def get_priority_dist(db: Session = Depends(get_db)):
    rows = (
        db.query(Incident.priority, func.count(Incident.id))
        .group_by(Incident.priority)
        .order_by(Incident.priority)
        .all()
    )
    return [PriorityDist(priority=r[0] or "未知", count=r[1]) for r in rows]


@app.get("/api/stats/state-dist", response_model=List[StateDist])
def get_state_dist(db: Session = Depends(get_db)):
    rows = (
        db.query(Incident.state, func.count(Incident.id))
        .group_by(Incident.state)
        .all()
    )
    return [StateDist(state=r[0] or "未知", count=r[1]) for r in rows]


@app.get("/api/stats/monthly-trend", response_model=List[MonthlyTrend])
def get_monthly_trend(db: Session = Depends(get_db)):
    rows = (
        db.query(
            Incident.month,
            func.count(Incident.id).label("total"),
            func.avg(Incident.resolve_hours).label("avg_hours"),
        )
        .filter(Incident.month.isnot(None))
        .group_by(Incident.month)
        .order_by(Incident.month)
        .all()
    )
    return [
        MonthlyTrend(month=r[0], total=r[1], avg_hours=round(r[2] or 0, 2))
        for r in rows
    ]


@app.get("/api/stats/group-stats", response_model=List[GroupStat])
def get_group_stats(db: Session = Depends(get_db)):
    rows = (
        db.query(
            Incident.assignment_group,
            func.count(Incident.id).label("count"),
            func.avg(Incident.resolve_hours).label("avg_hours"),
            func.sum(
                case((Incident.state.in_(["Resolved", "Closed"]), 1), else_=0)
            ).label("resolved"),
        )
        .group_by(Incident.assignment_group)
        .all()
    )
    return [
        GroupStat(
            group=r[0] or "未知",
            count=r[1],
            avg_hours=round(r[2] or 0, 2),
            resolved_rate=round(r[1] and (r[3] or 0) / r[1] * 100, 1) or 0,
        )
        for r in rows
    ]


@app.get("/api/stats/assignee-stats", response_model=List[AssigneeStat])
def get_assignee_stats(
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(
            Incident.assigned_to,
            func.count(Incident.id).label("count"),
            func.avg(Incident.resolve_hours).label("avg_hours"),
            func.sum(
                case((~Incident.state.in_(["Resolved", "Closed", "Canceled"]), 1), else_=0)
            ).label("pending"),
        )
        .filter(Incident.assigned_to.isnot(None))
        .group_by(Incident.assigned_to)
        .order_by(func.count(Incident.id).desc())
        .limit(limit)
        .all()
    )
    return [
        AssigneeStat(
            assignee=r[0] or "未知", count=r[1],
            avg_hours=round(r[2] or 0, 2),
            pending_count=int(r[3] or 0),
        )
        for r in rows
    ]


@app.get("/api/stats/customer-stats", response_model=List[CustomerStat])
def get_customer_stats(
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db),
):
    from collections import defaultdict

    # 先按 (公司, 产品) 分组，获取各公司主要产品
    sub_rows = (
        db.query(
            Incident.company,
            Incident.category,
            func.count(Incident.id).label("cnt"),
        )
        .filter(Incident.company.isnot(None))
        .group_by(Incident.company, Incident.category)
        .all()
    )
    # 汇总到公司级别
    by_company: dict = defaultdict(
        lambda: {"count": 0, "resolved_count": 0, "avg_h_sum": 0.0, "cat_cnt": defaultdict(int)}
    )
    for co, cat, cnt in sub_rows:
        d = by_company[co]
        d["count"] += cnt
        d["cat_cnt"][cat] += cnt

    # 按公司汇总
    rows = (
        db.query(
            Incident.company,
            func.count(Incident.id).label("count"),
            func.sum(
                case((Incident.state.in_(["Resolved", "Closed"]), 1), else_=0)
            ).label("resolved_count"),
            func.avg(Incident.resolve_hours).label("avg_hours"),
        )
        .filter(Incident.company.isnot(None))
        .group_by(Incident.company)
        .order_by(func.count(Incident.id).desc())
        .limit(limit)
        .all()
    )

    return [
        CustomerStat(
            company=r[0] or "未知",
            count=r[1],
            resolved_count=int(r[2] or 0),
            resolve_rate=round(r[1] and r[2] / r[1] * 100, 1) or 0,
            avg_hours=round(r[3] or 0, 2),
            category=(
                max(by_company.get(r[0] or "", {}).get("cat_cnt", {}), key=lambda k: 0)
                if by_company.get(r[0] or "") else "未知"
            ) or "未知",
        )
        for r in rows
    ]


@app.get("/api/stats/product-stats", response_model=List[ProductStat])
def get_product_stats(db: Session = Depends(get_db)):
    rows = (
        db.query(Incident.category, func.count(Incident.id))
        .group_by(Incident.category)
        .order_by(func.count(Incident.id).desc())
        .all()
    )
    return [ProductStat(category=r[0] or "未知", count=r[1]) for r in rows]


@app.get("/api/stats/sla-stats", response_model=List[SlaStat])
def get_sla_stats(db: Session = Depends(get_db)):
    rows = (
        db.query(
            Incident.priority,
            func.count(Incident.id).label("count"),
            func.sum(Incident.is_sla_met.cast(Integer)).label("sla_met"),
            func.avg(Incident.resolve_hours).label("avg_hours"),
            func.min(Incident.sla_limit).label("sla_limit"),
        )
        .filter(Incident.priority.isnot(None))
        .group_by(Incident.priority)
        .all()
    )
    return [
        SlaStat(
            priority=r[0],
            count=r[1],
            sla_met=int(r[2] or 0),
            sla_rate=round(r[1] and (r[2] or 0) / r[1] * 100, 1) or 0,
            avg_hours=round(r[3] or 0, 2),
            sla_limit=float(r[4] or 0),
        )
        for r in rows
    ]


@app.get("/api/stats/keywords", response_model=List[KeywordStat])
def get_keywords(
    top: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """从 short_description 提取词频"""
    rows = db.query(Incident.short_description).all()
    import re
    from collections import Counter
    stopwords = {
        "the","a","an","and","or","to","of","in","for","on","is","it",
        "this","that","with","as","by","be","are","was","were",
        "has","have","had","not","but","from","at","can","will","my",
        "nan","null","fw","re","ll","ve","s","t","m",
        "nan","nan","的","了","在","是","我","你"
    }
    words = []
    for (text,) in rows:
        if not text:
            continue
        w = re.findall(r"[a-zA-Z]{3,}", str(text).lower())
        words.extend(x for x in w if x not in stopwords)
    counter = Counter(words)
    return [
        KeywordStat(keyword=k, count=c)
        for k, c in counter.most_common(top)
    ]


@app.get("/api/stats/product-state-matrix")
def get_product_state_matrix(db: Session = Depends(get_db)):
    """产品 × 状态 交叉矩阵"""
    rows = (
        db.query(Incident.category, Incident.state, func.count(Incident.id))
        .group_by(Incident.category, Incident.state)
        .all()
    )
    matrix = {}
    for cat, state, cnt in rows:
        matrix.setdefault(cat or "未知", {})[state or "未知"] = cnt
    return matrix


@app.get("/api/incidents", response_model=List[IncidentOut])
def list_incidents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    priority: Optional[str] = None,
    state: Optional[str] = None,
    group: Optional[str] = None,
    category: Optional[str] = None,
    company: Optional[str] = None,
    sort_by: Optional[str] = Query("created_at", pattern="^(created_at|priority|state|resolve_hours)$"),
    order: Optional[str] = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    q = db.query(Incident)
    if priority:
        q = q.filter(Incident.priority == priority)
    if state:
        q = q.filter(Incident.state == state)
    if group:
        q = q.filter(Incident.assignment_group == group)
    if category:
        q = q.filter(Incident.category == category)
    if company:
        q = q.filter(Incident.company == company)

    col = getattr(Incident, sort_by, Incident.created_at)
    if order == "desc":
        col = col.desc()
    q = q.order_by(col)

    offset = (page - 1) * page_size
    return q.offset(offset).limit(page_size).all()


@app.get("/api/incidents/count")
def count_incidents(
    priority: Optional[str] = None,
    state: Optional[str] = None,
    group: Optional[str] = None,
    category: Optional[str] = None,
    company: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Incident)
    if priority:
        q = q.filter(Incident.priority == priority)
    if state:
        q = q.filter(Incident.state == state)
    if group:
        q = q.filter(Incident.assignment_group == group)
    if category:
        q = q.filter(Incident.category == category)
    if company:
        q = q.filter(Incident.company == company)
    return {"count": q.count()}


class RecentIncident(BaseModel):
    number: str
    priority: Optional[str]
    state: Optional[str]
    company: Optional[str]
    short_description: Optional[str]
    assignment_group: Optional[str]
    assigned_to: Optional[str]
    created_at: datetime
    resolve_hours: Optional[float]
    is_sla_met: Optional[int]

    class Config:
        from_attributes = True


@app.get("/api/incidents/recent", response_model=List[RecentIncident])
def get_recent_incidents(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """返回最近的 N 条工单，按创建时间倒序，用于事件流展示"""
    rows = (
        db.query(Incident)
        .order_by(Incident.created_at.desc())
        .limit(limit)
        .all()
    )
    return rows


@app.get("/api/stats/daily-breakdown", response_model=DailyBreakdown)
def get_daily_breakdown(db: Session = Depends(get_db)):
    """工作日分布 + 小时分布"""
    from collections import defaultdict

    wd_rows = (
        db.query(Incident.weekday, func.count(Incident.id))
        .filter(Incident.weekday.isnot(None))
        .group_by(Incident.weekday)
        .all()
    )
    weekday_dist = {r[0]: r[1] for r in wd_rows}

    hr_rows = (
        db.query(Incident.hour, func.count(Incident.id))
        .filter(Incident.hour.isnot(None))
        .group_by(Incident.hour)
        .all()
    )
    hourly_dist = {str(r[0]): r[1] for r in hr_rows}

    return DailyBreakdown(weekday_dist=weekday_dist, hourly_dist=hourly_dist)


@app.get("/api/companies", response_model=List[CompanyOut])
def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """列出所有公司（支持分页）"""
    offset = (page - 1) * page_size
    return db.query(Company).offset(offset).limit(page_size).all()


@app.get("/api/companies/count")
def count_companies(db: Session = Depends(get_db)):
    return {"count": db.query(Company).count()}


@app.post("/api/companies/sync")
def sync_companies():
    """从 OneProCloud API 同步 company 数据（按需增量）"""
    try:
        result = etl.sync_companies_from_api()
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── 用户 API ──────────────────────────────────────
@app.get("/api/users", response_model=List[UserOut])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    department: Optional[str] = None,
    active: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """列出所有用户（支持分页和筛选）"""
    q = db.query(User)
    if department:
        q = q.filter(User.department == department)
    if active is not None:
        q = q.filter(User.active == active)
    offset = (page - 1) * page_size
    return q.offset(offset).limit(page_size).all()


@app.get("/api/users/count")
def count_users(
    department: Optional[str] = None,
    active: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """统计用户数量"""
    q = db.query(User)
    if department:
        q = q.filter(User.department == department)
    if active is not None:
        q = q.filter(User.active == active)
    return {"count": q.count()}


@app.post("/api/users/sync")
def sync_users():
    """从 OneProCloud API 同步 user 数据（按需增量）"""
    try:
        result = etl.sync_users_from_api()
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    """一次性返回 Dashboard 所有数据"""
    return {
        "kpi": get_kpi(db),
        "priority_dist": get_priority_dist(db),
        "state_dist": get_state_dist(db),
        "monthly_trend": get_monthly_trend(db),
        "group_stats": get_group_stats(db),
        "assignee_stats": get_assignee_stats(limit=12, db=db),
        "customer_stats": get_customer_stats(limit=15, db=db),
        "product_stats": get_product_stats(db),
        "sla_stats": get_sla_stats(db),
        "product_state_matrix": get_product_state_matrix(db),
    }
