# Python Advanced Task Scheduler

一个功能强大的 Python 任务调度器，支持精确的时间控制、优先级管理、时间窗口限制等高级特性。

## 特性

- ✨ 支持前台和后台运行模式
- 🕒 精确的时间间隔控制
- 🎯 任务优先级管理
- ⏰ 时间窗口限制
- 🔄 任务状态监控和控制
- ⚡ 高性能和线程安全
- 🛠 灵活的装饰器语法

## 安装

```bash
# 克隆仓库
git clone https://your-repository/python-scheduler.git

# 安装依赖
pip install -r requirements.txt
```

## 快速开始

### 基本使用

```python
from schedule import Scheduler, SchedulerMode

# 创建调度器（后台模式）
scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)

# 定义一个周期性任务
@scheduler.task.periodic(interval=60)  # 每60秒执行一次
def my_task():
    print("Task executing...")

# 启动调度器
scheduler.start()

# 主程序继续运行
while True:
    time.sleep(1)
```

### 时间窗口限制

```python
from datetime import time
from schedule import TimeWindow

# 定义工作时间窗口 (9:00-17:00)
work_hours = TimeWindow(time(9, 0), time(17, 0))

@scheduler.task.periodic(
    interval=300,  # 5分钟
    time_windows=[work_hours]
)
def business_hour_task():
    print("Only runs during business hours")
```

### 任务优先级

```python
from schedule import TaskPriority

@scheduler.task.periodic(
    interval=60,
    priority=TaskPriority.HIGH
)
def high_priority_task():
    print("High priority task")

@scheduler.task.periodic(
    interval=60,
    priority=TaskPriority.LOW
)
def low_priority_task():
    print("Low priority task")
```

### 执行时间限制

```python
@scheduler.task.periodic(
    interval=300,
    max_running_time=60  # 最多运行60秒
)
def limited_time_task():
    print("Task with time limit")
```

### 任务状态监控

```python
def on_status_change(task, old_status, new_status):
    print(f"Task '{task.name}' status changed: {old_status} -> {new_status}")

def on_task_success(task):
    print(f"Task '{task.name}' completed successfully")

def on_task_failure(task):
    print(f"Task '{task.name}' failed")

# 添加回调
task.add_status_change_callback(on_status_change)
task.add_success_callback(on_task_success)
task.add_failure_callback(on_task_failure)
```

### 任务控制

```python
# 暂停任务
task.pause()

# 恢复任务
task.resume()

# 停止任务
task.stop()

# 重置任务
task.reset()
```

## 高级用例

### 服务集成

```python
class DataService:
    def __init__(self):
        self.scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)
        self._setup_tasks()
    
    def _setup_tasks(self):
        @self.scheduler.task.periodic(interval=300)
        def sync_data():
            self._sync_data()
        
        @self.scheduler.task.periodic(
            interval=3600,
            time_windows=[night_window]
        )
        def cleanup():
            self._cleanup()
    
    def start(self):
        self.scheduler.start()
    
    def stop(self):
        self.scheduler.stop()
```

### 多时间窗口

```python
# 定义多个时间窗口
morning_window = TimeWindow(time(9, 0), time(12, 0))
afternoon_window = TimeWindow(time(14, 0), time(17, 0))

@scheduler.task.periodic(
    interval=1800,  # 30分钟
    time_windows=[morning_window, afternoon_window]
)
def multi_window_task():
    print("Runs in morning and afternoon")
```

## API 参考

### Scheduler

主调度器类，管理所有任务的执行。

```python
scheduler = Scheduler(
    mode=SchedulerMode.BACKGROUND,  # 运行模式
    check_interval=0.1  # 检查间隔（秒）
)
```

### TaskDecorator

用于定义周期性任务的装饰器。


```python
@scheduler.task.periodic(
    interval: Union[int, float, timedelta],  # 执行间隔
    name: Optional[str] = None,  # 任务名称
    priority: TaskPriority = TaskPriority.NORMAL,  # 优先级
    time_windows: Optional[List[TimeWindow]] = None,  # 时间窗口
    start_immediately: bool = True,  # 是否立即开始
    max_running_time: Optional[float] = None  # 最大运行时间
)
```

### TimeWindow

定义任务的执行时间窗口。

```python
window = TimeWindow(
    start_time: time,  # 开始时间
    end_time: time  # 结束时间
)
```

### TaskStatus

任务状态枚举：
- `PENDING`: 等待执行
- `RUNNING`: 正在执行
- `COMPLETED`: 执行完成
- `FAILED`: 执行失败
- `PAUSED`: 暂停状态
- `STOPPED`: 停止状态
- `CANCELLED`: 取消执行

### TaskPriority

任务优先级枚举：
- `LOW`: 低优先级
- `NORMAL`: 普通优先级
- `HIGH`: 高优先级
- `CRITICAL`: 关键优先级

# 调度器运行模式详解

## 运行模式对比

### 前台模式 (FOREGROUND)

前台模式会阻塞当前线程，适合调度器是程序的主要或唯一功能的场景。

```python
from schedule import Scheduler, SchedulerMode

# 创建前台模式调度器
scheduler = Scheduler(mode=SchedulerMode.FOREGROUND)

@scheduler.task.periodic(interval=5)
def my_task():
    print("Task executing...")

# 这行会阻塞，程序会一直在这里运行，直到被中断
scheduler.start()

# 下面的代码不会立即执行，要等调度器停止后才会执行
print("Scheduler stopped")
```

使用场景：
1. 简单的定时任务脚本
```python
# 比如一个定时备份脚本
scheduler = Scheduler(mode=SchedulerMode.FOREGROUND)

@scheduler.task.periodic(interval=3600)  # 每小时执行一次
def backup_data():
    perform_backup()

scheduler.start()  # 程序会在这里持续运行
```

2. 独立的任务调度程序
```python
scheduler = Scheduler(mode=SchedulerMode.FOREGROUND)

@scheduler.task.periodic(interval=300)
def task1():
    print("Task 1")

@scheduler.task.periodic(interval=600)
def task2():
    print("Task 2")

try:
    scheduler.start()  # 程序会在这里等待
except KeyboardInterrupt:
    scheduler.stop()
```

### 后台模式 (BACKGROUND)

后台模式在单独的线程中运行调度器，不会阻塞主程序，适合将调度器作为程序一部分的场景。

```python
# 创建后台模式调度器
scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)

@scheduler.task.periodic(interval=5)
def background_task():
    print("Background task executing...")

# 这行不会阻塞，调度器在后台运行
scheduler.start()

# 下面的代码会立即执行
print("Main program continues...")
while True:
    print("Doing other things...")
    time.sleep(1)
```

使用场景：
1. Web服务中的定时任务
```python
class WebServer:
    def __init__(self):
        self.scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)
        
        @self.scheduler.task.periodic(interval=300)
        def clean_sessions():
            self.cleanup_expired_sessions()
    
    def start(self):
        # 启动调度器（在后台运行）
        self.scheduler.start()
        # 启动Web服务
        self.run_web_server()  # 不会被调度器阻塞
```

2. GUI应用中的定时任务
```python
class MyGUIApp:
    def __init__(self):
        self.scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)
        
        @self.scheduler.task.periodic(interval=60)
        def refresh_data():
            self.update_display()
    
    def run(self):
        # 启动后台任务
        self.scheduler.start()
        # 运行GUI主循环
        self.mainloop()  # GUI不会被调度器阻塞
```

## 模式选择建议

### 使用前台模式 (FOREGROUND) 
when：
1. 调度器是程序的主要功能
2. 不需要同时执行其他操作
3. 希望程序随调度器的停止而结束
4. 编写简单的定时任务脚本

```python
# 前台模式示例
def run_scheduler():
    scheduler = Scheduler(mode=SchedulerMode.FOREGROUND)
    
    @scheduler.task.periodic(interval=60)
    def main_task():
        process_data()
    
    # 程序会在这里等待，直到调度器停止
    scheduler.start()
```

### 使用后台模式 (BACKGROUND) 
when：
1. 调度器只是程序的一个组件
2. 需要同时执行其他操作
3. 需要在主程序中控制调度器
4. 实现服务类应用

```python
# 后台模式示例
class DataService:
    def __init__(self):
        self.scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)
        
        @self.scheduler.task.periodic(interval=60)
        def background_task():
            self.process_data()
    
    def start(self):
        # 启动后台调度器
        self.scheduler.start()
        # 继续执行其他操作
        self.do_other_things()
```

## 注意事项

1. **前台模式**:
   - `start()` 调用会阻塞当前线程
   - 需要使用 Ctrl+C 或其他方式中断
   - 适合命令行工具和脚本

2. **后台模式**:
   - `start()` 调用立即返回
   - 需要手动管理调度器的生命周期
   - 记得在程序结束时调用 `stop()`

3. **切换模式**:
   - 只能在调度器启动前切换模式
   - 运行过程中不能更改模式

```python
# 错误示例
scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)
scheduler.start()
scheduler.mode = SchedulerMode.FOREGROUND  # 将抛出异常

# 正确示例
scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)
scheduler.mode = SchedulerMode.FOREGROUND  # 在启动前切换模式
scheduler.start()
```

## 推荐用法

1. **前台模式 - 简单脚本**:
```python
def main():
    scheduler = Scheduler(mode=SchedulerMode.FOREGROUND)
    
    @scheduler.task.periodic(interval=60)
    def my_task():
        do_work()
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.stop()

if __name__ == '__main__':
    main()
```

2. **后台模式 - 服务组件**:
```python
class MyService:
    def __init__(self):
        self.scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)
        self._setup_tasks()
    
    def _setup_tasks(self):
        @self.scheduler.task.periodic(interval=300)
        def maintenance():
            self._do_maintenance()
    
    def start(self):
        self.scheduler.start()
        # 继续其他操作...
    
    def stop(self):
        self.scheduler.stop()
```

## 最佳实践

1. **选择合适的运行模式**
   - 用作服务组件时使用后台模式
   - 独立运行时使用前台模式

2. **合理设置时间间隔**
   - 避免过于频繁的执行
   - 考虑任务执行时间

3. **使用任务回调**
   - 监控任务状态
   - 处理执行异常
   - 记录执行日志

4. **资源管理**
   - 及时停止不需要的任务
   - 合理设置最大运行时间
   - 使用完后停止调度器

## 注意事项

1. 任务函数应当是可重入的
2. 长时间运行的任务应设置 max_running_time
3. 注意不同时区的影响
4. 定期检查任务的错误计数
5. 合理处理任务异常

## 常见问题

**Q: 如何确保任务按时执行？**

A: 调度器会尽最大努力按时执行任务，但执行时间可能受系统负载影响。建议：
- 设置合理的检查间隔
- 避免任务长时间运行
- 监控任务的实际执行时间

**Q: 如何处理任务失败？**

A: 可以通过以下方式处理：
- 添加失败回调
- 检查 error_count
- 实现自动重试逻辑

**Q: 如何在关闭程序时正确停止调度器？**

A: 使用以下模式：
```python
try:
    scheduler.start()
    # 主程序逻辑
except KeyboardInterrupt:
    scheduler.stop()
```

## 开发计划

- [ ] 添加任务重试机制
- [ ] 抢占式任务计划
- [ ] 支持分布式调度

[//]: # (- [ ] 支持 cron 表达式)

[//]: # (- [ ] 添加持久化支持)

[//]: # (- [ ] 提供 Web 监控界面)

## 贡献

欢迎提交 Issue 和 Pull Request。

## 许可证

[MIT License](LICENSE)