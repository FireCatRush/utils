import os
import subprocess
import argparse

def find_git_repos(base_path):
    """递归查找指定路径下的所有 Git 仓库"""
    git_repos = []
    for root, dirs, files in os.walk(base_path):
        if ".git" in dirs:
            git_repos.append(root)
            dirs[:] = []  # 停止递归进入子目录
    return git_repos

def get_remote_url(repo_path):
    """获取 Git 仓库的远程 URL"""
    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "remote", "get-url", "origin"],
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
            ["git", "-C", repo_path, "remote", "set-url", "origin", new_url],
            check=True
        )
        print(f"Updated: {repo_path}\n  Old URL: {old_url}\n  New URL: {new_url}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to update {repo_path}: {e}")

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="批量修改 Git 仓库的远程 URL",
        epilog="示例: python update_git_urls.py --path /path/to/repositories --old olduser --new newuser"
    )
    parser.add_argument(
        "--path",
        required=True,
        help="存储 Git 仓库的文件夹路径 (例如: /path/to/repositories)"
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

    base_path = args.path
    old_username = args.old
    new_username = args.new

    # 查找所有 Git 仓库
    print("\n正在搜索 Git 仓库...")
    git_repos = find_git_repos(base_path)
    if not git_repos:
        print("未找到任何 Git 仓库。")
        return

    # 收集需要修改的仓库信息
    changes = []
    for repo in git_repos:
        remote_url = get_remote_url(repo)
        if remote_url and old_username in remote_url:
            new_url = remote_url.replace(old_username, new_username)
            changes.append((repo, remote_url, new_url))

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
    for repo, old_url, new_url in changes:
        update_remote_url(repo, old_url, new_url)

    print("\n所有修改已完成！")

if __name__ == "__main__":
    main()
