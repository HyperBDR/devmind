"""
Initial migration for sals app: Company, User, Incident models.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name="Company",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sys_id", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="OneProCloud sys_id")),
                ("name", models.CharField(blank=True, max_length=256, null=True, verbose_name="公司名称")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="记录时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "SALS Company",
                "verbose_name_plural": "SALS Companies",
                "db_table": "sals_company",
                "ordering": ["name", "sys_id"],
            },
        ),
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sys_id", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="OneProCloud sys_id")),
                ("name", models.CharField(blank=True, max_length=256, null=True, verbose_name="用户姓名")),
                ("email", models.CharField(blank=True, db_index=True, max_length=256, null=True, verbose_name="电子邮箱")),
                ("user_name", models.CharField(blank=True, db_index=True, max_length=128, null=True, verbose_name="登录名")),
                ("department", models.CharField(blank=True, max_length=128, null=True, verbose_name="部门")),
                ("phone", models.CharField(blank=True, max_length=64, null=True, verbose_name="电话")),
                ("mobile_phone", models.CharField(blank=True, max_length=64, null=True, verbose_name="手机")),
                ("title", models.CharField(blank=True, max_length=128, null=True, verbose_name="职位")),
                ("active", models.CharField(blank=True, max_length=8, null=True, verbose_name="是否激活")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="记录时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "SALS User",
                "verbose_name_plural": "SALS Users",
                "db_table": "sals_user",
                "ordering": ["name", "sys_id"],
            },
        ),
        migrations.CreateModel(
            name="Incident",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(db_index=True, max_length=32, unique=True, verbose_name="工单编号")),
                ("parent_incident", models.CharField(blank=True, max_length=32, null=True, verbose_name="父工单")),
                ("short_description", models.TextField(blank=True, null=True, verbose_name="问题简述")),
                ("company", models.CharField(db_index=True, default="未知", max_length=128, verbose_name="客户公司")),
                ("caller", models.CharField(db_index=True, default="未知", max_length=128, verbose_name="提单人")),
                ("created_by", models.CharField(default="", max_length=64, verbose_name="创建人")),
                ("priority", models.CharField(db_index=True, default="P3", max_length=4, verbose_name="优先级 P1-P4")),
                ("assigned_to", models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name="处理人")),
                ("state", models.CharField(db_index=True, default="Unknown", max_length=32, verbose_name="状态")),
                ("resolution_code", models.CharField(blank=True, max_length=64, null=True, verbose_name="解决代码")),
                ("category", models.CharField(db_index=True, default="未知", max_length=64, verbose_name="产品分类")),
                ("assignment_group", models.CharField(db_index=True, default="未分配", max_length=64, verbose_name="处理组")),
                ("updated_by", models.CharField(blank=True, max_length=64, null=True, verbose_name="更新人")),
                ("created_at", models.DateTimeField(db_index=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(verbose_name="更新时间")),
                ("resolve_hours", models.FloatField(blank=True, null=True, verbose_name="处理时长(小时)")),
                ("sla_limit", models.FloatField(blank=True, null=True, verbose_name="SLA时限(小时)")),
                ("is_sla_met", models.BooleanField(blank=True, null=True, verbose_name="SLA是否达标")),
                ("month", models.CharField(blank=True, db_index=True, max_length=7, null=True, verbose_name="年月 YYYY-MM")),
                ("weekday", models.CharField(blank=True, max_length=16, null=True, verbose_name="星期")),
                ("hour", models.IntegerField(blank=True, null=True, verbose_name="创建小时")),
            ],
            options={
                "verbose_name": "SALS Incident",
                "verbose_name_plural": "SALS Incidents",
                "db_table": "sals_incident",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="incident",
            index=models.Index(fields=["state", "priority"], name="sals_inc_state_prio_idx"),
        ),
        migrations.AddIndex(
            model_name="incident",
            index=models.Index(fields=["assignment_group", "state"], name="sals_inc_group_state_idx"),
        ),
        migrations.AddIndex(
            model_name="incident",
            index=models.Index(fields=["company", "state"], name="sals_inc_company_state_idx"),
        ),
    ]
