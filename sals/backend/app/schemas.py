"""
Pydantic 请求/响应模型
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

# ── 用户 ──────────────────────────────────────────
class UserBase(BaseModel):
    sys_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    user_name: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    mobile_phone: Optional[str] = None
    title: Optional[str] = None
    active: Optional[str] = None


class UserOut(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── 公司 ──────────────────────────────────────────
class CompanyBase(BaseModel):
    sys_id: str
    name: Optional[str] = None


class CompanyCreate(CompanyBase):
    pass


class CompanyOut(CompanyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── 工单 ──────────────────────────────────────────
class IncidentBase(BaseModel):
    number: str
    short_description: Optional[str] = None
    company: Optional[str] = None
    caller: Optional[str] = None
    priority: Optional[str] = None
    state: Optional[str] = None
    category: Optional[str] = None
    assignment_group: Optional[str] = None
    assigned_to: Optional[str] = None


class IncidentCreate(IncidentBase):
    pass


class IncidentOut(IncidentBase):
    id: int
    parent_incident: Optional[str]
    created_by: Optional[str]
    resolution_code: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    resolve_hours: Optional[float]
    sla_limit: Optional[float]
    is_sla_met: Optional[int]
    month: Optional[str]
    weekday: Optional[str]
    hour: Optional[int]

    class Config:
        from_attributes = True


# ── 筛选参数 ──────────────────────────────────────
class IncidentFilter(BaseModel):
    start_date: Optional[str] = None   # YYYY-MM-DD
    end_date: Optional[str] = None
    priorities: Optional[List[str]] = None
    groups: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    states: Optional[List[str]] = None
    companies: Optional[List[str]] = None


# ── 统计聚合 ──────────────────────────────────────
class KpiStat(BaseModel):
    total: int
    pending: int
    in_progress: int
    resolved: int
    closed: int
    canceled: int
    resolved_rate: float  # (resolved + closed) / total * 100
    sla_rate: float
    avg_resolve_hours: float
    p1_total: int
    p1_overdue: int
    p2_total: int


class PriorityDist(BaseModel):
    priority: str
    count: int


class StateDist(BaseModel):
    state: str
    count: int


class GroupStat(BaseModel):
    group: str
    count: int
    avg_hours: float
    resolved_rate: float


class AssigneeStat(BaseModel):
    assignee: str
    count: int
    avg_hours: float
    pending_count: int


class MonthlyTrend(BaseModel):
    month: str
    total: int
    avg_hours: float


class CustomerStat(BaseModel):
    company: str
    count: int
    resolved_count: int
    resolve_rate: float
    avg_hours: float
    category: str


class ProductStat(BaseModel):
    category: str
    count: int


class KeywordStat(BaseModel):
    keyword: str
    count: int


class SlaStat(BaseModel):
    priority: str
    count: int
    sla_met: int
    sla_rate: float
    avg_hours: float
    sla_limit: float


class DailyBreakdown(BaseModel):
    weekday_dist: dict
    hourly_dist: dict


# ── Dashboard 全量数据 ────────────────────────────
class DashboardData(BaseModel):
    kpi: KpiStat
    priority_dist: List[PriorityDist]
    state_dist: List[StateDist]
    monthly_trend: List[MonthlyTrend]
    group_stats: List[GroupStat]
    assignee_stats: List[AssigneeStat]
    customer_stats: List[CustomerStat]
    product_stats: List[ProductStat]
    sla_stats: List[SlaStat]
    focus_cards: dict
