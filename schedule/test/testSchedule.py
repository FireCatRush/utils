import unittest
from unittest.mock import Mock, patch
import time
from datetime import datetime, time as dtime, timedelta
import threading

from ..schedule import (
    Scheduler, TaskDecorator, TimeWindow, TaskStatus,
    TaskPriority, SchedulerMode, TaskControlError, PeriodicTask
)


class TestTimeWindow(unittest.TestCase):
    """时间窗口单元测试"""

    def test_normal_window(self):
        """测试普通时间窗口（不跨天）"""
        window = TimeWindow(dtime(9, 0), dtime(17, 0))

        # 测试窗口内的时间
        dt = datetime(2024, 1, 1, 12, 0)
        self.assertTrue(window.is_in_window(dt))

        # 测试窗口外的时间
        dt = datetime(2024, 1, 1, 8, 0)
        self.assertFalse(window.is_in_window(dt))

        # 测试边界值
        dt = datetime(2024, 1, 1, 9, 0)
        self.assertTrue(window.is_in_window(dt))
        dt = datetime(2024, 1, 1, 17, 0)
        self.assertTrue(window.is_in_window(dt))

    def test_cross_day_window(self):
        """测试跨天时间窗口"""
        window = TimeWindow(dtime(22, 0), dtime(3, 0))

        # 测试窗口内的时间
        dt = datetime(2024, 1, 1, 23, 0)
        self.assertTrue(window.is_in_window(dt))
        dt = datetime(2024, 1, 1, 2, 0)
        self.assertTrue(window.is_in_window(dt))

        # 测试窗口外的时间
        dt = datetime(2024, 1, 1, 12, 0)
        self.assertFalse(window.is_in_window(dt))

    def test_next_window_start(self):
        """测试下一个窗口开始时间计算"""
        window = TimeWindow(dtime(9, 0), dtime(17, 0))

        # 当前时间在窗口前
        dt = datetime(2024, 1, 1, 8, 0)
        next_start = window.next_window_start(dt)
        self.assertEqual(next_start.hour, 9)
        self.assertEqual(next_start.minute, 0)

        # 当前时间在窗口后
        dt = datetime(2024, 1, 1, 18, 0)
        next_start = window.next_window_start(dt)
        self.assertEqual(next_start.date(), dt.date() + timedelta(days=1))
        self.assertEqual(next_start.hour, 9)
        self.assertEqual(next_start.minute, 0)


class TestPeriodicTask(unittest.TestCase):
    """周期性任务单元测试"""

    def setUp(self):
        self.mock_func = Mock()
        self.task = PeriodicTask(
            name="test_task",
            interval=5,
            task_func=self.mock_func,
            priority=TaskPriority.NORMAL
        )

    def test_task_execution(self):
        """测试任务执行"""
        result = self.task.run()

        self.assertTrue(result)
        self.mock_func.assert_called_once()
        self.assertEqual(self.task.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(self.task.last_run)
        self.assertIsNotNone(self.task.next_run)

    def test_task_failure(self):
        """测试任务失败"""
        self.mock_func.side_effect = Exception("Test error")  # raise

        result = self.task.run()

        self.assertFalse(result)
        self.assertEqual(self.task.status, TaskStatus.FAILED)
        self.assertEqual(self.task.error_count, 1)

    def test_task_control(self):
        """测试任务控制功能"""
        # 测试暂停
        self.task.pause()
        self.assertEqual(self.task.status, TaskStatus.PAUSED)

        # 测试恢复
        self.task.resume()
        self.assertEqual(self.task.status, TaskStatus.PENDING)

        # 测试停止
        self.task.stop()
        self.assertEqual(self.task.status, TaskStatus.STOPPED)

        # 测试重置
        self.task.reset()
        self.assertEqual(self.task.status, TaskStatus.PENDING)


class TestScheduler(unittest.TestCase):
    """调度器单元测试"""

    def setUp(self):
        self.scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)

    def test_task_scheduling(self):
        """测试任务调度"""
        execute_times = []

        @self.scheduler.task.periodic(interval=0.1)
        def test_task():
            execute_times.append(datetime.now())

        self.scheduler.start()
        time.sleep(0.5)
        self.scheduler.stop()

        self.assertGreater(len(execute_times), 2)
        for i in range(1, len(execute_times)):
            interval = (execute_times[i] - execute_times[i-1]).total_seconds()
            self.assertAlmostEqual(interval, 0.1, delta=0.05)

    def test_priority_scheduling(self):
        """测试优先级调度"""
        execution_order = []

        @self.scheduler.task.periodic(interval=0.1, priority=TaskPriority.LOW)
        def low_priority_task():
            execution_order.append('low')

        @self.scheduler.task.periodic(interval=0.1, priority=TaskPriority.HIGH)
        def high_priority_task():
            execution_order.append('high')

        self.scheduler.start()
        time.sleep(0.3)
        self.scheduler.stop()

        # 验证高优先级任务先执行
        self.assertEqual(execution_order[0], 'high')


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_time_window_and_scheduling(self):
        """测试时间窗口和调度的集成"""
        scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)
        execute_times = []

        # 创建一个只在特定时间窗口执行的任务
        window = TimeWindow(
            datetime.now().time(),  # 从现在开始
            (datetime.now() + timedelta(minutes=5)).time()  # 5分钟后结束
        )

        @scheduler.task.periodic(
            interval=0.1,
            time_windows=[window]
        )
        def windowed_task():
            execute_times.append(datetime.now())

        scheduler.start()
        time.sleep(0.5)
        scheduler.stop()

        self.assertGreater(len(execute_times), 0)

    def test_multiple_tasks_interaction(self):
        """测试多个任务的交互"""
        scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)
        shared_data = {'count': 0}
        lock = threading.Lock()

        @scheduler.task.periodic(interval=0.1)
        def increment_task():
            with lock:
                shared_data['count'] += 1

        @scheduler.task.periodic(interval=0.2)
        def check_task():
            with lock:
                self.assertGreaterEqual(shared_data['count'], 0)

        scheduler.start()
        time.sleep(1.0)
        scheduler.stop()

        self.assertGreater(shared_data['count'], 0)


def run_performance_test():
    """性能测试"""
    scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)
    task_count = 1000
    execution_times = []

    def task_func():
        execution_times.append(datetime.now())

    # 压力测试
    for i in range(task_count):
        task = PeriodicTask(
            name=f"task_{i}",
            interval=0.1,
            task_func=task_func
        )
        scheduler.add_task(task)

    start_time = time.perf_counter()
    scheduler.start()
    startup_time = time.perf_counter() - start_time

    time.sleep(1.0)
    scheduler.stop()

    # 计算性能指标
    total_executions = len(execution_times)
    executions_per_second = total_executions / 1.0

    return {
        'startup_time': startup_time,
        'total_executions': total_executions,
        'executions_per_second': executions_per_second
    }


if __name__ == '__main__':
    unittest.main(verbosity=2)

    print("\n=== 性能测试结果 ===")
    results = run_performance_test()
    print(f"启动时间: {results['startup_time']:.3f} 秒")
    print(f"总执行次数: {results['total_executions']}")
    print(f"每秒执行次数: {results['executions_per_second']:.1f}")