#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 仓库批量删除工具
用于快速清理测试时生成的多个仓库
版本: 1.0.0
"""

import os
import re
import json
import time
import logging
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Optional
import requests
from requests.auth import HTTPBasicAuth

# 设置 Windows 系统编码
if sys.platform.startswith('win'):
    import locale
    try:
        # 设置控制台编码为 UTF-8
        os.system('chcp 65001 >nul 2>&1')
        # 设置 Python 默认编码
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass


class GitHubRepoCleaner:
    """GitHub 仓库批量删除工具"""
    
    def __init__(self, config_file: str = "github_cleaner_config.json", args=None):
        """
        初始化 GitHub 仓库清理工具
        
        Args:
            config_file: 配置文件路径
            args: 命令行参数
        """
        self.config_file = config_file
        self.config = self.load_config()
        
        # 如果提供了命令行参数，覆盖配置文件设置
        if args:
            if hasattr(args, 'no_dry_run') and args.no_dry_run:
                self.config['dry_run'] = False
            if hasattr(args, 'dry_run') and args.dry_run:
                self.config['dry_run'] = True
        
        self.session = requests.Session()
        self.setup_logging()
        
        # 设置 GitHub API 认证
        if self.config.get('github_token'):
            self.session.headers.update({
                'Authorization': f"token {self.config['github_token']}",
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'GitHub-Repo-Cleaner/1.0'
            })
        elif self.config.get('github_username') and self.config.get('github_password'):
            self.session.auth = HTTPBasicAuth(
                self.config['github_username'], 
                self.config['github_password']
            )
            self.session.headers.update({
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'GitHub-Repo-Cleaner/1.0'
            })
        else:
            raise ValueError("请在配置文件中设置 GitHub 认证信息（Token 或用户名密码）")
    
    def load_config(self) -> Dict:
        """加载配置文件"""
        # 优先尝试读取 config.json
        main_config_file = "config.json"
        
        # 首先尝试从 config.json 读取
        if os.path.exists(main_config_file):
            try:
                with open(main_config_file, 'r', encoding='utf-8') as f:
                    main_config = json.load(f)
                
                # 检查是否包含必要的 GitHub 信息
                if 'github_token' in main_config and 'github_username' in main_config:
                    # 使用 config.json 中的信息创建完整配置
                    config = {
                        "github_username": main_config['github_username'],
                        "github_token": main_config['github_token'],
                        "github_password": "",
                        "safe_repos": [
                            "important-project",
                            "production-app", 
                            "main-website",
                            "rustdesk_auto_build"
                        ],
                        "delete_patterns": [
                            "rustdesk_*_*",
                            "rustdesk_custom_*_*",
                            "hbb_common_*_*",
                            "hbb_common_custom_*_*",
                            "*_20??????_??????",
                            "*_test_*",
                            "temp_*_*",
                            "demo_*_*"
                        ],
                        "dry_run": main_config.get('dry_run', True),
                        "confirm_each_delete": True,
                        "log_level": "INFO"
                    }
                    print(f"已从 {main_config_file} 加载 GitHub 认证信息")
                    return config
            except Exception as e:
                print(f"读取 {main_config_file} 失败: {e}")
        
        # 如果没有从 config.json 加载成功，尝试原配置文件
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                return self.create_default_config()
        else:
            return self.create_default_config()
    
    def create_default_config(self) -> Dict:
        """创建默认配置文件"""
        default_config = {
            "github_username": "",
            "github_token": "",
            "github_password": "",
            "safe_repos": [
                "important-project",
                "production-app",
                "main-website"
            ],
            "delete_patterns": [
                "rustdesk_*",
                "hbb_common_*",
                "test_*",
                "*_test",
                "temp_*"
            ],
            "dry_run": True,
            "confirm_each_delete": True,
            "log_level": "INFO"
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            print(f"已创建默认配置文件: {self.config_file}")
            print("请编辑配置文件并设置您的 GitHub 认证信息")
        except Exception as e:
            print(f"创建配置文件失败: {e}")
        
        return default_config
    
    def setup_logging(self):
        """设置日志记录"""
        log_level = getattr(logging, self.config.get('log_level', 'INFO').upper())
        
        # 创建日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 设置控制台日志
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # 设置文件日志
        log_filename = f"github_cleaner_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # 配置 logger
        self.logger = logging.getLogger('GitHubRepoCleaner')
        self.logger.setLevel(log_level)
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def get_user_repositories(self) -> List[Dict]:
        """获取用户的所有仓库"""
        repos = []
        page = 1
        per_page = 100
        
        self.logger.info("正在获取用户仓库列表...")
        
        while True:
            try:
                url = f"https://api.github.com/user/repos"
                params = {
                    'page': page,
                    'per_page': per_page,
                    'sort': 'updated',
                    'direction': 'desc'
                }
                
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                # 确保响应编码正确
                if response.encoding is None:
                    response.encoding = 'utf-8'
                
                page_repos = response.json()
                if not page_repos:
                    break
                
                repos.extend(page_repos)
                self.logger.info(f"已获取第 {page} 页，共 {len(page_repos)} 个仓库")
                
                page += 1
                time.sleep(0.5)  # 避免 API 限制
                
            except Exception as e:
                self.logger.error(f"获取仓库列表失败: {e}")
                break
        
        self.logger.info(f"总共获取到 {len(repos)} 个仓库")
        return repos
    
    def filter_repositories(self, repos: List[Dict]) -> List[Dict]:
        """根据配置筛选要删除的仓库"""
        filtered_repos = []
        safe_repos = self.config.get('safe_repos', [])
        delete_patterns = self.config.get('delete_patterns', [])
        
        self.logger.info("正在筛选要删除的仓库...")
        
        for repo in repos:
            repo_name = repo['name']
            
            # 检查是否在安全列表中
            if repo_name in safe_repos:
                self.logger.info(f"跳过安全仓库: {repo_name}")
                continue
            
            # 检查是否匹配删除模式
            should_delete = False
            for pattern in delete_patterns:
                if self.match_pattern(repo_name, pattern):
                    should_delete = True
                    self.logger.info(f"仓库 {repo_name} 匹配模式 {pattern}")
                    break
            
            if should_delete:
                filtered_repos.append(repo)
        
        self.logger.info(f"筛选出 {len(filtered_repos)} 个仓库待删除")
        return filtered_repos
    
    def match_pattern(self, repo_name: str, pattern: str) -> bool:
        """检查仓库名是否匹配模式"""
        # 将通配符模式转换为正则表达式
        regex_pattern = pattern.replace('*', '.*')
        regex_pattern = f"^{regex_pattern}$"
        
        try:
            return bool(re.match(regex_pattern, repo_name, re.IGNORECASE))
        except Exception:
            return False
    
    def display_repositories(self, repos: List[Dict]):
        """显示仓库列表"""
        if not repos:
            print("没有找到匹配的仓库")
            return
        
        print(f"\n找到 {len(repos)} 个匹配的仓库:")
        print("-" * 80)
        print(f"{'序号':<4} {'仓库名':<30} {'创建时间':<20} {'最后更新':<20}")
        print("-" * 80)
        
        for i, repo in enumerate(repos, 1):
            created_at = repo['created_at'][:10]
            updated_at = repo['updated_at'][:10]
            print(f"{i:<4} {repo['name']:<30} {created_at:<20} {updated_at:<20}")
        
        print("-" * 80)
    
    def delete_repository(self, repo: Dict) -> bool:
        """删除单个仓库"""
        repo_name = repo['name']
        owner = repo['owner']['login']
        
        if self.config.get('dry_run', True):
            self.logger.info(f"[DRY RUN] 模拟删除仓库: {owner}/{repo_name}")
            return True
        
        try:
            url = f"https://api.github.com/repos/{owner}/{repo_name}"
            response = self.session.delete(url)
            
            if response.status_code == 204:
                self.logger.info(f"成功删除仓库: {owner}/{repo_name}")
                return True
            else:
                self.logger.error(f"删除仓库失败: {owner}/{repo_name}, 状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除仓库时发生错误: {owner}/{repo_name}, 错误: {e}")
            return False
    

    
    def _batch_delete_mode(self, repos: List[Dict]):
        """批量删除模式"""
        print(f"\n⚠️  批量删除模式")
        print(f"将要删除 {len(repos)} 个仓库")
        
        # 第一步确认
        confirm1 = input(f"\n第一步确认: 确定要删除这 {len(repos)} 个仓库吗? (yes/no): ").lower().strip()
        if confirm1 != 'yes':
            print("取消操作")
            return
        
        # 第二步确认
        print(f"\n⚠️  最终确认!")
        if self.config.get('dry_run', True):
            confirm2 = input("第二步确认: 确定要执行预览删除吗? (YES/no): ").strip()
        else:
            confirm2 = input("第二步确认: 确定要真正删除这些仓库吗? 此操作不可恢复! (YES/no): ").strip()
        
        if confirm2 != 'YES':
            print("取消操作")
            return
        
        # 执行删除
        success_count = 0
        failed_count = 0
        
        print(f"\n开始批量删除...")
        for i, repo in enumerate(repos, 1):
            print(f"[{i}/{len(repos)}] 处理仓库: {repo['name']}")
            
            if self.delete_repository(repo):
                success_count += 1
            else:
                failed_count += 1
            
            # 添加延迟避免 API 限制
            if not self.config.get('dry_run', True):
                time.sleep(1)
        
        self._print_summary(success_count, failed_count)
    
    def _index_select_mode(self, repos: List[Dict]):
        """索引选择模式"""
        print(f"\n📋 索引选择模式")
        print("输入格式示例:")
        print("  单个: 1")
        print("  多个: 1,3,5")
        print("  范围: 1-5")
        print("  混合: 1,3-5,8")
        print("  全部: all")
        
        while True:
            selection = input(f"\n请输入要删除的仓库索引 (1-{len(repos)}): ").strip()
            
            if selection.lower() == 'all':
                selected_repos = repos
                break
            
            try:
                selected_indices = self._parse_indices(selection, len(repos))
                if selected_indices:
                    selected_repos = [repos[i-1] for i in selected_indices]
                    break
                else:
                    print("无效的索引选择")
            except Exception as e:
                print(f"输入格式错误: {e}")
        
        if not selected_repos:
            print("没有选择任何仓库")
            return
        
        # 显示选中的仓库
        print(f"\n选中的仓库 ({len(selected_repos)} 个):")
        for i, repo in enumerate(selected_repos, 1):
            print(f"{i:2d}   {repo['name']}")
        
        # 确认删除
        confirm = input(f"\n确认删除这 {len(selected_repos)} 个仓库? (yes/no): ").lower().strip()
        if confirm != 'yes':
            print("取消操作")
            return
        
        # 执行删除
        success_count = 0
        failed_count = 0
        
        for i, repo in enumerate(selected_repos, 1):
            print(f"[{i}/{len(selected_repos)}] 处理仓库: {repo['name']}")
            
            if self.delete_repository(repo):
                success_count += 1
            else:
                failed_count += 1
            
            # 添加延迟避免 API 限制
            if not self.config.get('dry_run', True):
                time.sleep(1)
        
        self._print_summary(success_count, failed_count)
    
    def _individual_confirm_mode(self, repos: List[Dict]):
        """逐个确认模式"""
        success_count = 0
        failed_count = 0
        
        for i, repo in enumerate(repos, 1):
            repo_name = repo['name']
            
            while True:
                choice = input(f"\n[{i}/{len(repos)}] 是否删除仓库 '{repo_name}'? (y/n/q): ").lower().strip()
                if choice in ['y', 'yes']:
                    break
                elif choice in ['n', 'no']:
                    print(f"跳过仓库: {repo_name}")
                    continue
                elif choice in ['q', 'quit']:
                    print("用户取消操作")
                    return
                else:
                    print("请输入 y(是), n(否), 或 q(退出)")
                    continue
            
            # 执行删除
            if self.delete_repository(repo):
                success_count += 1
            else:
                failed_count += 1
            
            # 添加延迟避免 API 限制
            if not self.config.get('dry_run', True):
                time.sleep(1)
        
        self._print_summary(success_count, failed_count)
    
    def _parse_indices(self, selection: str, max_index: int) -> List[int]:
        """解析索引选择"""
        indices = set()
        parts = selection.split(',')
        
        for part in parts:
            part = part.strip()
            if '-' in part:
                # 范围选择
                start, end = part.split('-', 1)
                start, end = int(start.strip()), int(end.strip())
                if start < 1 or end > max_index or start > end:
                    raise ValueError(f"范围 {start}-{end} 无效")
                indices.update(range(start, end + 1))
            else:
                # 单个选择
                index = int(part)
                if index < 1 or index > max_index:
                    raise ValueError(f"索引 {index} 超出范围 (1-{max_index})")
                indices.add(index)
        
        return sorted(list(indices))
    
    def _print_summary(self, success_count: int, failed_count: int):
        """打印删除结果摘要"""
        print(f"\n删除操作完成:")
        print(f"成功: {success_count}")
        print(f"失败: {failed_count}")
        print(f"总计: {success_count + failed_count}")
    
    def _select_delete_mode(self, repos_to_delete):
        """选择删除模式"""
        print(f"\n{'='*60}")
        print(f"删除模式: {'预览模式 (不会真正删除)' if self.config.get('dry_run', True) else '实际删除模式'}")
        print(f"{'='*60}")
        
        print("\n请选择删除模式:")
        print("1. 批量删除 - 两步确认删除所有仓库")
        print("2. 索引选择 - 输入索引号选择要删除的仓库")
        print("3. 逐个确认 - 逐个确认每个仓库 (原模式)")
        print("4. 退出")
        
        while True:
            choice = input("\n请输入选择 (1-4): ").strip()
            if choice in ['1', '2', '3', '4']:
                break
            print("无效选择，请输入 1-4")
        
        if choice == '4':
            print("用户取消操作")
            return
        elif choice == '1':
            self._batch_delete_mode(repos_to_delete)
        elif choice == '2':
            self._index_select_mode(repos_to_delete)
        elif choice == '3':
            self._individual_confirm_mode(repos_to_delete)
    
    def run(self):
        """运行主程序"""
        try:
            print("GitHub 仓库批量删除工具")
            print("=" * 50)
            
            # 检查配置
            if not self.config.get('github_token') and not (
                self.config.get('github_username') and self.config.get('github_password')
            ):
                print("错误: 请在配置文件中设置 GitHub 认证信息")
                return
            
            # 获取仓库列表
            all_repos = self.get_user_repositories()
            if not all_repos:
                print("没有找到任何仓库")
                return
            
            # 筛选要删除的仓库
            repos_to_delete = self.filter_repositories(all_repos)
            
            # 显示仓库列表
            self.display_repositories(repos_to_delete)
            
            if not repos_to_delete:
                return
            
            # 显示当前模式
            if self.config.get('dry_run', True):
                print(f"\n当前为 DRY RUN 模式，不会实际删除仓库")
                print("如需实际删除，请在配置文件中设置 'dry_run': false")
            
            # 选择删除模式并执行
            self._select_delete_mode(repos_to_delete)
            
        except KeyboardInterrupt:
            print("\n\n操作被用户中断")
        except Exception as e:
            self.logger.error(f"程序运行时发生错误: {e}")
            print(f"发生错误: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='GitHub 仓库批量删除工具')
    parser.add_argument('--no-dry-run', action='store_true', 
                       help='禁用预览模式，执行实际删除操作')
    parser.add_argument('--dry-run', action='store_true', 
                       help='启用预览模式（默认）')
    parser.add_argument('--config', default='github_cleaner_config.json',
                       help='配置文件路径')
    
    args = parser.parse_args()
    
    # 检查冲突的参数
    if args.dry_run and args.no_dry_run:
        print("错误: --dry-run 和 --no-dry-run 不能同时使用")
        sys.exit(1)
    
    cleaner = GitHubRepoCleaner(config_file=args.config, args=args)
    cleaner.run()


if __name__ == "__main__":
    main()
