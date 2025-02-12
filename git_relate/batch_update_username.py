import os
import subprocess
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time

def is_git_repo(path):
    """检查路径是否为 Git 仓库"""
    return (path / ".git").is_dir()

def find_git_repos(base_path, total_dirs):
    """递归查找指定路径下的所有 Git 仓库，并显示进度条"""
    git_repos = []
    processed_dirs = 0

    for root, dirs, _ in os.walk(base_path):
        # 快速过滤包含 .git 的目录
        if ".git" in dirs:
            git_repos.append(Path(root))
            dirs[:] = []  # 停止递归进入子目录

        processed_dirs += 1
        # 显示进度条
        progress = int((processed_dirs / total_dirs) * 50)  # 进度条宽度为 50 字符
        print(f"\r扫描目录: [{'#' * progress}{'.' * (50 - progress)}] {processed_dirs}/{total_dirs}", end="")

    print("\n")  # 换行
    return git_repos

def get_remote_url(repo_path):
    """获取 Git 仓库的远程 URL"""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return None
    except Exception as e:
        print(f"Error fetching remote URL for {repo_path}: {e}")
        return None

def update_remote_url(repo_path, old_url, new_url):
    """更新 Git 仓库的远程 URL"""
    try:
        subprocess.run(
            ["git", "-C", str(repo_path), "remote", "set-url", "origin", new_url],
            check=True
        )
        print(f"Updated: {repo_path}\n  Old URL: {old_url}\n  New URL: {new_url}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to update {repo_path}: {e}")

def process_repo(repo_path, old_username, new_username, changes):
    """处理单个 Git 仓库"""
    remote_url = get_remote_url(repo_path)
    if remote_url and old_username in remote_url:
        new_url = remote_url.replace(old_username, new_username)
        changes.append((repo_path, remote_url, new_url))

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="批量修改 Git 仓库的远程 URL",
        epilog="示例: python update_git_urls.py --path /path/to/repositories --old olduser --new newuser"
    )
    parser.add_argument(
        "--path",
        required=True,
        help="存储 Git 仓库的文件夹路径 (例如: /path/to/repositories 或 C:\\path\\to\\repositories)"
    )
    parser.add_argument(
        "--old",
        required=True,
        help="旧的 GitHub 用户名 (例如: olduser)"
    )
    parser.add_argument(
        "--new",
        required=True,
        help="新的 GitHub 用户名 (例如: newuser)"
    )
    args = parser.parse_args()

    # 跨平台路径解析
    base_path = Path(args.path).resolve()  # 自动解析为绝对路径并标准化
    if not base_path.exists():
        print(f"错误：路径 '{args.path}' 不存在。")
        return
    if not base_path.is_dir():
        print(f"错误：路径 '{args.path}' 不是有效的文件夹。")
        return

    old_username = args.old
    new_username = args.new

    # 查找所有 Git 仓库
    print("\n正在搜索 Git 仓库...")
    start_time = time.time()  # 记录开始时间

    # 统计总目录数
    total_dirs = sum(len(dirs) for _, dirs, _ in os.walk(base_path))
    git_repos = find_git_repos(base_path, total_dirs)

    elapsed_time = time.time() - start_time  # 计算运行时长
    print(f"搜索完成！共找到 {len(git_repos)} 个 Git 仓库。耗时: {elapsed_time:.2f} 秒")

    if not git_repos:
        print("未找到任何 Git 仓库。")
        return

    # 并行处理 Git 仓库
    changes = []
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(process_repo, repo, old_username, new_username, changes)
            for repo in git_repos
        ]
        for future in futures:
            future.result()  # 等待所有任务完成

    # 打印修改计划
    if not changes:
        print(f"\n未找到与用户名 '{old_username}' 相关的仓库链接。")
        return

    print("\n以下是需要修改的仓库链接：")
    for repo, old_url, new_url in changes:
        print(f"仓库路径: {repo}")
        print(f"  当前 URL: {old_url}")
        print(f"  新 URL: {new_url}")
        print("-" * 50)

    # 确认修改
    confirm = input("\n是否确认修改？(输入 'yes' 继续): ").strip().lower()
    if confirm != "yes":
        print("操作已取消。")
        return

    # 执行修改
    print("\n开始批量修改...")
    start_time = time.time()  # 记录开始时间
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(update_remote_url, repo, old_url, new_url)
            for repo, old_url, new_url in changes
        ]
        for future in futures:
            future.result()  # 等待所有任务完成

    elapsed_time = time.time() - start_time  # 计算运行时长
    print(f"\n所有修改已完成！耗时: {elapsed_time:.2f} 秒")

if __name__ == "__main__":
    main()