"""
SQLAlchemy 模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Company(Base):
    """客户公司表（ETL 按需同步，仅写入不存在的记录）"""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    sys_id = Column(String(64), unique=True, index=True, comment="OneProCloud sys_id")
    name = Column(String(256), nullable=True, comment="公司名称")
    created_at = Column(DateTime, default=datetime.utcnow, comment="记录时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def __repr__(self):
        return f"<Company {self.sys_id} {self.name}>"


class User(Base):
    """用户表（ETL 按需同步，仅写入不存在的记录）"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    sys_id = Column(String(64), unique=True, index=True, comment="OneProCloud sys_id")
    name = Column(String(256), nullable=True, comment="用户姓名")
    email = Column(String(256), nullable=True, index=True, comment="电子邮箱")
    user_name = Column(String(128), nullable=True, index=True, comment="登录名")
    department = Column(String(128), nullable=True, comment="部门")
    phone = Column(String(64), nullable=True, comment="电话")
    mobile_phone = Column(String(64), nullable=True, comment="手机")
    title = Column(String(128), nullable=True, comment="职位")
    active = Column(String(8), nullable=True, comment="是否激活")
    created_at = Column(DateTime, default=datetime.utcnow, comment="记录时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def __repr__(self):
        return f"<User {self.sys_id} {self.name}>"


class Incident(Base):
    """工单表"""
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String(32), unique=True, index=True, comment="工单编号")
    parent_incident = Column(String(32), nullable=True, comment="父工单")
    short_description = Column(Text, nullable=True, comment="问题简述")
    company = Column(String(128), index=True, comment="客户公司")
    caller = Column(String(128), index=True, comment="提单人")
    created_by = Column(String(128), comment="创建人")
    priority = Column(String(4), index=True, comment="优先级 P1-P4")
    assigned_to = Column(String(64), index=True, nullable=True, comment="处理人")
    state = Column(String(32), index=True, comment="状态")
    resolution_code = Column(String(64), nullable=True, comment="解决代码")
    category = Column(String(64), index=True, comment="产品分类")
    assignment_group = Column(String(64), index=True, comment="处理组")
    updated_by = Column(String(64), nullable=True, comment="更新人")

    # 时间戳（UTC 存储，本地展示时转换）
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 派生字段（由 ETL 计算写入）
    resolve_hours = Column(Float, nullable=True, comment="处理时长(小时)")
    sla_limit = Column(Float, nullable=True, comment="SLA时限(小时)")
    is_sla_met = Column(Integer, nullable=True, comment="SLA是否达标 0/1")
    month = Column(String(7), index=True, comment="年月 YYYY-MM")
    weekday = Column(String(16), nullable=True, comment="星期")
    hour = Column(Integer, nullable=True, comment="创建小时")

    def __repr__(self):
        return f"<Incident {self.number} {self.state}>"
