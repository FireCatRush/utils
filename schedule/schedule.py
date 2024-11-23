"""
高级任务调度器实现
支持:
- 前台/后台运行模式
- 周期性任务
- 时间窗口限制
- 任务优先级
- 任务状态管理
- 装饰器语法
"""

import time
from abc import ABC, abstractmethod
from datetime import datetime, time as dtime, timedelta
from enum import Enum, auto
from threading import Thread, Event, Lock, Timer
from typing import Optional, Dict, List, Union, Callable
from functools import wraps
from dataclasses import dataclass
import uuid


class SchedulerMode(Enum):
    """调度器运行模式"""
    FOREGROUND = auto()  # 前台模式（阻塞运行）
    BACKGROUND = auto()  # 后台模式（非阻塞运行）


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "PENDING"  # 等待执行
    RUNNING = "RUNNING"  # 正在执行
    COMPLETED = "COMPLETED"  # 执行完成
    FAILED = "FAILED"  # 执行失败
    PAUSED = "PAUSED"  # 暂停状态
    STOPPED = "STOPPED"  # 停止状态
    CANCELLED = "CANCELLED"  # 取消执行


class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class TimeWindow:
    """时间窗口定义"""
    start_time: dtime
    end_time: dtime

    def is_in_window(self, current_time: Optional[datetime] = None) -> bool:
        """检查给定时间是否在时间窗口内"""
        current = current_time or datetime.now()
        current_time = current.time()
        if self.start_time <= self.end_time:
            return self.start_time <= current_time <= self.end_time
        else:
            return current_time >= self.start_time or current_time <= self.end_time

    def next_window_start(self, current_time: Optional[datetime] = None) -> datetime:
        """计算下一个窗口的开始时间"""
        current = current_time or datetime.now()
        start_today = datetime.combine(current.date(), self.start_time)

        if self.start_time <= self.end_time:
            if current.time() > self.end_time:
                return start_today + timedelta(days=1)
            elif current.time() < self.start_time:
                return start_today
            else:
                return current
        else:
            if self.end_time < current.time() < self.start_time:
                return start_today
            else:
                return current


class TaskControlError(Exception):
    """任务控制相关的异常"""
    pass


class BaseTask(ABC):
    """任务基类"""

    def __init__(
            self,
            name: str,
            priority: TaskPriority = TaskPriority.NORMAL,
            interval: Optional[float] = None,
            time_windows: Optional[List[TimeWindow]] = None,
            max_running_time: Optional[float] = None
    ):
        self.task_id = str(uuid.uuid4())
        self.name = name
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.interval = interval
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.error_count = 0
        self.time_windows = time_windows or []
        self.max_running_time = max_running_time

        # 控制机制
        self._stop_event = Event()
        self._pause_event = Event()
        self._pause_event.set()

        # 回调和同步
        self._lock = Lock()
        self._on_success_callbacks = []
        self._on_failure_callbacks = []
        self._on_status_change_callbacks = []

        # 执行状态
        self._execution_start_time: Optional[datetime] = None
        self._execution_timer: Optional[Timer] = None

    def _is_in_time_window(self) -> bool:
        """检查当前是否在任意时间窗口内"""
        if not self.time_windows:
            return True
        return any(window.is_in_window() for window in self.time_windows)

    def _get_next_window_start(self) -> Optional[datetime]:
        """获取下一个可用时间窗口的开始时间"""
        if not self.time_windows:
            return None
        next_times = [window.next_window_start() for window in self.time_windows]
        return min(next_times)

    def _check_interrupt(self) -> bool:
        """检查是否应该中断执行"""
        if self._stop_event.is_set():
            return False

        if not self._pause_event.is_set():
            self._update_status(TaskStatus.PAUSED)
            self._pause_event.wait()
            if self._stop_event.is_set():
                return False
            self._update_status(TaskStatus.PENDING)

        return True

    def _check_execution_time(self) -> bool:
        """检查执行时间是否超限"""
        if (self.max_running_time and self._execution_start_time and
                (datetime.now() - self._execution_start_time).total_seconds() > self.max_running_time):
            return False
        return True

    def pause(self):
        """暂停任务"""
        with self._lock:
            if self.status == TaskStatus.STOPPED:
                raise TaskControlError("Cannot pause a stopped task")
            self._pause_event.clear()
            if self.status != TaskStatus.RUNNING:
                self._update_status(TaskStatus.PAUSED)

    def resume(self):
        """恢复任务"""
        with self._lock:
            if self.status == TaskStatus.STOPPED:
                raise TaskControlError("Cannot resume a stopped task")
            self._pause_event.set()
            if self.status == TaskStatus.PAUSED:
                self._update_status(TaskStatus.PENDING)
                if self.interval is not None:
                    self.next_run = datetime.now() + timedelta(seconds=self.interval)

    def stop(self):
        """停止任务"""
        with self._lock:
            self._stop_event.set()
            self._pause_event.set()
            self._update_status(TaskStatus.STOPPED)

    def reset(self):
        """重置任务状态"""
        with self._lock:
            self._stop_event.clear()
            self._pause_event.set()
            self.error_count = 0
            self._update_status(TaskStatus.PENDING)
            self._update_next_run_time()

    def _update_status(self, new_status: TaskStatus):
        """更新任务状态并触发回调"""
        old_status = self.status
        self.status = new_status
        for callback in self._on_status_change_callbacks:
            callback(self, old_status, new_status)

    def add_status_change_callback(self, callback: Callable[['BaseTask', TaskStatus, TaskStatus], None]):
        """添加状态变更回调"""
        self._on_status_change_callbacks.append(callback)

    def add_success_callback(self, callback: Callable[['BaseTask'], None]):
        """添加任务成功回调"""
        self._on_success_callbacks.append(callback)

    def add_failure_callback(self, callback: Callable[['BaseTask'], None]):
        """添加任务失败回调"""
        self._on_failure_callbacks.append(callback)

    def _update_next_run_time(self):
        """更新下次运行时间，考虑时间窗口限制"""
        if self.interval is None:
            self.next_run = datetime.now()
            return

        if self.last_run is None:
            base_next_run = datetime.now()
        else:
            base_next_run = self.last_run + timedelta(seconds=self.interval)

        if not self.time_windows:
            self.next_run = base_next_run
            return

        current_time = base_next_run
        while not any(window.is_in_window(current_time) for window in self.time_windows):
            next_window = min(window.next_window_start(current_time) for window in self.time_windows)
            current_time = next_window

        self.next_run = current_time

    def __lt__(self, other):
        """支持任务优先级比较"""
        if not isinstance(other, BaseTask):
            return NotImplemented
        return self.priority.value > other.priority.value

    @abstractmethod
    def run(self) -> bool:
        """执行任务的抽象方法"""
        pass


class PeriodicTask(BaseTask):
    """周期性任务实现"""

    def __init__(
            self,
            name: str,
            interval: float,
            task_func: Callable,
            priority: TaskPriority = TaskPriority.NORMAL,
            time_windows: Optional[List[TimeWindow]] = None,
            max_running_time: Optional[float] = None
    ):
        super().__init__(
            name=name,
            priority=priority,
            interval=interval,
            time_windows=time_windows,
            max_running_time=max_running_time
        )
        self._task_func = task_func
        self.next_run = datetime.now()

    def run(self) -> bool:
        if not self._check_interrupt():
            return False

        try:
            with self._lock:
                if not self._check_interrupt():
                    return False
                self._update_status(TaskStatus.RUNNING)
                self._execution_start_time = datetime.now()

            try:
                if hasattr(self._task_func, 'supports_interrupt'):
                    result = self._task_func(
                        check_interrupt=lambda: self._check_interrupt() and self._check_execution_time()
                    )
                else:
                    result = self._task_func()
            finally:
                if self._execution_timer:
                    self._execution_timer.cancel()
                    self._execution_timer = None

            if not self._check_interrupt() or not self._check_execution_time():
                return False

            with self._lock:
                self._execution_start_time = None
                self._update_status(TaskStatus.COMPLETED)
                self.last_run = datetime.now()
                self._update_next_run_time()
                for callback in self._on_success_callbacks:
                    callback(self)
            return True

        except Exception as e:
            with self._lock:
                self._execution_start_time = None
                self._update_status(TaskStatus.FAILED)
                self.error_count += 1
                for callback in self._on_failure_callbacks:
                    callback(self)
            return False


class Scheduler:
    """集成了运行模式的调度器"""

    def __init__(
            self,
            mode: SchedulerMode = SchedulerMode.FOREGROUND,
            check_interval: float = 0.1
    ):
        self._tasks: Dict[str, BaseTask] = {}
        self._lock = Lock()
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._mode = mode
        self.check_interval = check_interval
        self.task = TaskDecorator(self)

    @property
    def mode(self) -> SchedulerMode:
        """获取当前运行模式"""
        return self._mode

    @mode.setter
    def mode(self, value: SchedulerMode):
        """设置运行模式（必须在启动前设置）"""
        if self.is_running:
            raise RuntimeError("Cannot change mode while scheduler is running")
        self._mode = value

    @property
    def is_running(self) -> bool:
        """检查调度器是否正在运行"""
        return (self._thread is not None and self._thread.is_alive()) or \
            (not self._stop_event.is_set() and self._mode == SchedulerMode.FOREGROUND)

    def start(self):
        """启动调度器"""
        if self.is_running:
            raise RuntimeError("Scheduler is already running")

        self._stop_event.clear()

        if self._mode == SchedulerMode.BACKGROUND:
            self._thread = Thread(target=self._run, daemon=True)
            self._thread.start()
        else:
            self._run()

    def stop(self):
        """停止调度器"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            self._thread = None

    def _run(self):
        """调度器运行循环"""
        while not self._stop_event.is_set():
            current_time = datetime.now()

            with self._lock:
                ready_tasks = [
                    task for task in self._tasks.values()
                    if task.status not in [TaskStatus.RUNNING, TaskStatus.STOPPED, TaskStatus.CANCELLED]
                       and task.next_run and task.next_run <= current_time
                       and task._is_in_time_window()
                ]
                ready_tasks.sort()

            for task in ready_tasks:
                if self._stop_event.is_set():
                    break
                task.run()

            self._stop_event.wait(self.check_interval)

    def add_task(self, task: BaseTask) -> str:
        """添加任务到调度器"""
        with self._lock:
            self._tasks[task.task_id] = task
            return task.task_id

    def remove_task(self, task_id: str):
        """从调度器中移除任务"""
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].stop()
                del self._tasks[task_id]

    def get_task(self, task_id: str) -> Optional[BaseTask]:
        """获取任务实例"""
        return self._tasks.get(task_id)


class TaskDecorator:
    def __init__(self, scheduler: Scheduler):
        self.scheduler = scheduler

    def periodic(
            self,
            interval: Union[int, float, timedelta],
            name: Optional[str] = None,
            priority: TaskPriority = TaskPriority.NORMAL,
            time_windows: Optional[List[TimeWindow]] = None,
            start_immediately: bool = True,
            max_running_time: Optional[float] = None
    ):
        def decorator(func: Callable):
            if isinstance(interval, timedelta):
                interval_seconds = interval.total_seconds()
            else:
                interval_seconds = float(interval)

            task_name = name or func.__name__

            @wraps(func)  # 保留原函数的元信息
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            # 创建任务实例
            task = PeriodicTask(
                name=task_name,
                interval=interval_seconds,
                task_func=wrapper,
                priority=priority,
                time_windows=time_windows,
                max_running_time=max_running_time
            )

            if not start_immediately:
                task._update_next_run_time()

            task_id = self.scheduler.add_task(task)
            wrapper.task_id = task_id
            wrapper.task = task

            return wrapper

        return decorator
