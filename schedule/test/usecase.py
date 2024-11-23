import time
from datetime import datetime, time as dtime, timedelta
import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from schedule.schedule import (
    Scheduler, TimeWindow, TaskPriority, SchedulerMode, TaskStatus
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SchedulerDemo')


class DataProcessor:
    """模拟数据处理服务"""

    def __init__(self):
        # 创建后台模式的调度器
        self.scheduler = Scheduler(mode=SchedulerMode.BACKGROUND)
        self.data_count = 0
        self.is_running = False

        # 设置时间窗口
        self.work_hours = TimeWindow(dtime(9, 0), dtime(17, 0))  # 工作时间 9:00-17:00
        self.night_hours = TimeWindow(dtime(23, 0), dtime(5, 0))  # 夜间时间 23:00-5:00

        # 注册任务
        self._setup_tasks()

    def _setup_tasks(self):
        """配置所有定时任务"""

        # 1. 高优先级任务 - 每分钟执行的健康检查
        @self.scheduler.task.periodic(
            interval=60,
            name="HealthCheck",
            priority=TaskPriority.CRITICAL
        )
        def health_check():
            self._check_health()

        health_check.task.add_status_change_callback(self._on_task_status_change)

        # 2. 普通任务 - 工作时间内每5分钟处理数据
        @self.scheduler.task.periodic(
            interval=300,
            name="DataProcessing",
            priority=TaskPriority.NORMAL,
            time_windows=[self.work_hours]
        )
        def process_data():
            self._process_data()

        # 3. 低优先级任务 - 夜间清理任务
        @self.scheduler.task.periodic(
            interval=3600,
            name="Cleanup",
            priority=TaskPriority.LOW,
            time_windows=[self.night_hours]
        )
        def cleanup():
            self._cleanup()

        # 4. 限时任务 - 最多运行30秒的报告生成
        @self.scheduler.task.periodic(
            interval=900,  # 每15分钟
            name="ReportGeneration",
            max_running_time=30
        )
        def generate_report():
            self._generate_report()

        # 保存任务引用以便后续控制
        self.health_check_task = health_check.task
        self.process_task = process_data.task
        self.cleanup_task = cleanup.task
        self.report_task = generate_report.task

    def _on_task_status_change(self, task, old_status, new_status):
        """任务状态变更回调"""
        logger.info(f"Task '{task.name}' status changed: {old_status.value} -> {new_status.value}")

    def start(self):
        """启动服务"""
        logger.info("Starting data processor service...")
        self.is_running = True
        self.scheduler.start()
        logger.info("Service started")

    def stop(self):
        """停止服务"""
        logger.info("Stopping service...")
        self.is_running = False
        self.scheduler.stop()
        logger.info("Service stopped")

    def pause_processing(self):
        """暂停数据处理"""
        logger.info("Pausing data processing...")
        self.process_task.pause()

    def resume_processing(self):
        """恢复数据处理"""
        logger.info("Resuming data processing...")
        self.process_task.resume()

    def _check_health(self):
        """健康检查"""
        logger.info("Performing health check...")
        # 模拟健康检查
        if not self.is_running:
            logger.warning("Service health check failed!")
            return False
        logger.info("Health check passed")
        return True

    def _process_data(self):
        """数据处理"""
        logger.info("Processing data batch...")
        self.data_count += 1
        # 模拟数据处理
        time.sleep(2)
        logger.info(f"Processed batch #{self.data_count}")

    def _cleanup(self):
        """清理任务"""
        logger.info("Running cleanup task...")
        # 模拟清理操作
        time.sleep(3)
        logger.info("Cleanup completed")

    def _generate_report(self):
        """生成报告"""
        logger.info("Generating report...")
        # 模拟报告生成
        time.sleep(5)
        logger.info(f"Report generated. Total processed batches: {self.data_count}")


def main():
    """主函数：演示各种功能"""
    processor = DataProcessor()

    try:
        # 1. 启动服务
        processor.start()
        logger.info("Service is running. Press Ctrl+C to stop.")

        # 2. 演示运行一段时间
        time.sleep(10)

        # 3. 演示暂停和恢复
        processor.pause_processing()
        logger.info("Data processing paused for 5 seconds...")
        time.sleep(5)

        processor.resume_processing()
        logger.info("Data processing resumed...")
        time.sleep(10)

        # 4. 检查任务状态
        tasks = [
            processor.health_check_task,
            processor.process_task,
            processor.cleanup_task,
            processor.report_task
        ]

        for task in tasks:
            logger.info(
                f"Task '{task.name}': "
                f"status={task.status.value}, "
                f"error_count={task.error_count}, "
                f"last_run={task.last_run}"
            )

    except KeyboardInterrupt:
        logger.info("Stopping service...")
    finally:
        processor.stop()
        logger.info("Service stopped.")


if __name__ == "__main__":
    main()
