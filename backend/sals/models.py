"""
SALS models: Company, User, Incident.
"""
from django.db import models


class Company(models.Model):
    """客户公司表（ETL 按需同步，仅写入不存在的记录）"""

    sys_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="OneProCloud sys_id",
    )
    name = models.CharField(max_length=256, null=True, blank=True, verbose_name="公司名称")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="记录时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        app_label = "sals"
        db_table = "sals_company"
        ordering = ["name", "sys_id"]

    def __str__(self):
        return f"{self.sys_id} {self.name}"


class User(models.Model):
    """用户表（ETL 按需同步，仅写入不存在的记录）"""

    sys_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="OneProCloud sys_id",
    )
    name = models.CharField(max_length=256, null=True, blank=True, verbose_name="用户姓名")
    email = models.CharField(max_length=256, null=True, blank=True, db_index=True, verbose_name="电子邮箱")
    user_name = models.CharField(max_length=128, null=True, blank=True, db_index=True, verbose_name="登录名")
    department = models.CharField(max_length=128, null=True, blank=True, verbose_name="部门")
    phone = models.CharField(max_length=64, null=True, blank=True, verbose_name="电话")
    mobile_phone = models.CharField(max_length=64, null=True, blank=True, verbose_name="手机")
    title = models.CharField(max_length=128, null=True, blank=True, verbose_name="职位")
    active = models.CharField(max_length=8, null=True, blank=True, verbose_name="是否激活")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="记录时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        app_label = "sals"
        db_table = "sals_user"
        ordering = ["name", "sys_id"]

    def __str__(self):
        return f"{self.sys_id} {self.name}"


class Incident(models.Model):
    """工单表"""

    number = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        verbose_name="工单编号",
    )
    parent_incident = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        verbose_name="父工单",
    )
    short_description = models.TextField(null=True, blank=True, verbose_name="问题简述")
    company = models.CharField(max_length=128, db_index=True, default="未知", verbose_name="客户公司")
    caller = models.CharField(max_length=128, db_index=True, default="未知", verbose_name="提单人")
    created_by = models.CharField(max_length=64, default="", verbose_name="创建人")
    priority = models.CharField(max_length=4, db_index=True, default="P3", verbose_name="优先级 P1-P4")
    assigned_to = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        verbose_name="处理人",
    )
    state = models.CharField(max_length=32, db_index=True, default="Unknown", verbose_name="状态")
    resolution_code = models.CharField(max_length=64, null=True, blank=True, verbose_name="解决代码")
    category = models.CharField(max_length=64, db_index=True, default="未知", verbose_name="产品分类")
    assignment_group = models.CharField(
        max_length=64,
        db_index=True,
        default="未分配",
        verbose_name="处理组",
    )
    updated_by = models.CharField(max_length=64, null=True, blank=True, verbose_name="更新人")

    created_at = models.DateTimeField(db_index=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(verbose_name="更新时间")

    resolve_hours = models.FloatField(null=True, blank=True, verbose_name="处理时长(小时)")
    sla_limit = models.FloatField(null=True, blank=True, verbose_name="SLA时限(小时)")
    is_sla_met = models.BooleanField(null=True, blank=True, verbose_name="SLA是否达标")
    month = models.CharField(
        max_length=7,
        db_index=True,
        null=True,
        blank=True,
        verbose_name="年月 YYYY-MM",
    )
    weekday = models.CharField(max_length=16, null=True, blank=True, verbose_name="星期")
    hour = models.IntegerField(null=True, blank=True, verbose_name="创建小时")

    class Meta:
        app_label = "sals"
        db_table = "sals_incident"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["state", "priority"], name="sals_inc_state_prio_idx"),
            models.Index(fields=["assignment_group", "state"], name="sals_inc_group_state_idx"),
            models.Index(fields=["company", "state"], name="sals_inc_company_state_idx"),
        ]

    def __str__(self):
        return f"{self.number} {self.state}"
