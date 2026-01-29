# Task Management App

统一的任务管理模块，用于全局性管理任务的执行和追踪运行记录。

## 功能特性

- **统一任务追踪**: 所有模块的任务执行记录都统一存储和管理
- **任务状态同步**: 自动与 Celery 结果后端同步任务状态
- **任务查询**: 支持按模块、任务名、状态、用户等条件查询任务
- **用户关联**: 每个任务都与创建用户关联，支持按用户查询和统计
- **任务统计**: 提供任务执行统计信息，支持按用户统计
- **API 接口**: 提供完整的 REST API 用于任务管理

## 使用方式

### 1. 在视图中注册任务

当触发一个 Celery 任务时，使用 `register_task_execution` 函数注册任务：

```python
from task_manager.utils import register_task_execution
from celery import shared_task

@shared_task(name='myapp.tasks.my_task')
def my_task(arg1, arg2):
    # Task implementation
    pass

# 在视图中触发任务
def my_view(request):
    task = my_task.delay(arg1, arg2)

    # 注册任务到统一管理系统
    register_task_execution(
        task_id=task.id,
        task_name='myapp.tasks.my_task',
        module='myapp',
        task_kwargs={'arg1': arg1, 'arg2': arg2},
        created_by=request.user if request.user.is_authenticated else None,
        metadata={'source': 'manual_trigger'}
    )

    return Response({'task_id': task.id})
```

### 2. API 端点

#### 获取任务列表
```
GET /api/v1/tasks/executions/
```

**默认行为**: 默认只返回当前用户创建的任务。要查看所有任务，需要设置 `my_tasks=false` 参数。

查询参数：
- `module`: 按模块过滤
- `task_name`: 按任务名过滤
- `status`: 按状态过滤 (PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED)
- `created_by`: 按创建者用户ID过滤（指定查看某个用户的任务）
- `my_tasks`: 设置为 `false` 可查看所有任务（需要相应权限）
- `start_date`: 开始日期
- `end_date`: 结束日期

#### 获取我的任务
```
GET /api/v1/tasks/executions/my-tasks/
```

获取当前用户创建的所有任务，支持与列表接口相同的过滤参数。

#### 获取任务详情
```
GET /api/v1/tasks/executions/{id}/
```

#### 通过 task_id 获取任务
```
GET /api/v1/tasks/executions/by-task-id/{task_id}/
```

#### 获取任务状态
```
GET /api/v1/tasks/executions/status/?task_id={task_id}
```

#### 同步任务状态
```
POST /api/v1/tasks/executions/{id}/sync/
```

#### 获取任务统计
```
GET /api/v1/tasks/executions/stats/
```

**默认行为**: 默认统计当前用户的任务。要统计所有任务，需要设置 `my_tasks=false` 参数。

查询参数：
- `module`: 按模块过滤
- `task_name`: 按任务名过滤
- `created_by`: 按创建者用户ID过滤（统计某个用户的任务）
- `my_tasks`: 设置为 `false` 可统计所有任务（需要相应权限）

## 模型说明

### TaskExecution

任务执行记录模型，包含以下字段：

- `task_id`: Celery 任务 ID
- `task_name`: 任务名称
- `module`: 所属模块
- `status`: 任务状态
- `created_at`: 创建时间
- `started_at`: 开始执行时间
- `finished_at`: 完成时间
- `task_args`: 任务参数
- `task_kwargs`: 任务关键字参数
- `result`: 任务结果
- `error`: 错误信息
- `traceback`: 错误堆栈
- `created_by`: 创建者（User对象）
- `created_by_id`: 创建者ID（便于前端使用）
- `created_by_username`: 创建者用户名（便于前端显示）
- `metadata`: 额外元数据

## 服务说明

### TaskTracker

任务追踪服务，提供以下方法：

- `register_task()`: 注册新任务
- `update_task_status()`: 更新任务状态
- `sync_task_from_celery()`: 从 Celery 同步任务状态
- `get_task()`: 获取任务信息
- `get_task_stats()`: 获取任务统计信息

## 注意事项

1. 任务的实际执行仍然由各个模块负责
2. 任务管理模块只负责任务的追踪、查询和统计
3. 建议在触发任务后立即注册任务记录
4. 任务状态会自动与 Celery 结果后端同步
