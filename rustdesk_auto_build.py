#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RustDesk 自动化编译工具
自动修改服务器地址和公钥，并触发 GitHub Actions 编译
"""

import os
import re
import json
import shutil
import logging
import subprocess
from datetime import datetime
from typing import Dict, Any, Iterable

import git
import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rustdesk_build.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RustDeskAutoBuild:
    """RustDesk 自动化编译工具类"""
    
    def __init__(self, config_file: str = "config.json"):
        """初始化工具"""
        self.config = self.load_config(config_file)
        self.github_token = self.config.get('github_token')
        self.github_username = self.config.get('github_username')
        self.server_address = self.config.get('server_address')
        self.public_key = self.config.get('public_key')
        
        # 验证必要配置
        if not all([self.github_token, self.github_username, self.server_address, self.public_key]):
            raise ValueError("配置文件中缺少必要信息：github_token, github_username, server_address, public_key")
        
        # GitHub API 基础 URL
        self.github_api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # 工作目录
        self.work_dir = os.path.join(os.getcwd(), "rustdesk_build_workspace")
        self.rustdesk_dir = os.path.join(self.work_dir, "rustdesk")
        self.hbb_common_dir = os.path.join(self.work_dir, "hbb_common")

    def _request(
        self,
        method: str,
        url: str,
        expected_status: Iterable[int],
        **kwargs: Any
    ) -> requests.Response:
        """统一处理 GitHub API 请求和错误日志"""
        expected = tuple(expected_status)
        timeout = kwargs.pop("timeout", 30)
        kwargs.setdefault("headers", self.headers)

        response = requests.request(method, url, timeout=timeout, **kwargs)
        if response.status_code not in expected:
            logger.error(
                "GitHub API 请求失败: %s %s -> %s %s",
                method.upper(),
                url,
                response.status_code,
                response.text,
            )
            raise Exception(f"GitHub API 请求失败: {response.text}")
        return response

    @staticmethod
    def _remove_directory(path: str):
        """在存在时安全删除目录"""
        if os.path.exists(path):
            logger.info("删除已存在的目录: %s", path)
            shutil.rmtree(path, ignore_errors=True)
        
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"配置文件 {config_file} 不存在")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"配置文件格式错误: {e}")
            return {}
    
    def setup_workspace(self):
        """设置工作目录"""
        os.makedirs(self.work_dir, exist_ok=True)
        logger.info(f"工作目录已就绪: {self.work_dir}")
        
        # 配置 Git 用户信息
        self.setup_git_config()
    
    def setup_git_config(self):
        """配置 Git 用户信息"""
        try:
            # 设置全局 Git 配置
            subprocess.run(['git', 'config', '--global', 'user.name', self.github_username], check=True)
            subprocess.run(['git', 'config', '--global', 'user.email', f'{self.github_username}@users.noreply.github.com'], check=True)
            logger.info(f"已配置 Git 用户信息: {self.github_username}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"配置 Git 用户信息失败: {e}")
            # 如果全局配置失败，在每个仓库中单独配置
            pass
    
    def clone_repositories(self):
        """克隆 rustdesk 和 hbb_common 仓库"""
        logger.info("开始克隆仓库...")
        
        # 克隆 hbb_common
        self._remove_directory(self.hbb_common_dir)
        logger.info("克隆 hbb_common 仓库...")
        git.Repo.clone_from("https://github.com/rustdesk/hbb_common.git", self.hbb_common_dir)
        
        # 克隆 rustdesk
        self._remove_directory(self.rustdesk_dir)
        logger.info("克隆 rustdesk 仓库...")
        git.Repo.clone_from("https://github.com/rustdesk/rustdesk.git", self.rustdesk_dir)
        
        logger.info("仓库克隆完成")
    
    def modify_config_file(self):
        """修改 hbb_common 中的配置文件"""
        config_path = os.path.join(self.hbb_common_dir, "src", "config.rs")
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        logger.info(f"修改配置文件: {config_path}")
        
        # 读取文件内容
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 修改服务器地址
        server_pattern = r'pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[.*?\];'
        new_server_line = f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{self.server_address}"];'
        content = re.sub(server_pattern, new_server_line, content, flags=re.DOTALL)
        
        # 修改公钥
        key_pattern = r'pub const RS_PUB_KEY: &str = ".*?";'
        new_key_line = f'pub const RS_PUB_KEY: &str = "{self.public_key}";'
        content = re.sub(key_pattern, new_key_line, content)
        
        # 写回文件
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info("配置文件修改完成")
    
    def commit_hbb_common_changes(self):
        """提交 hbb_common 的修改"""
        logger.info("提交 hbb_common 修改...")
        
        repo = git.Repo(self.hbb_common_dir)
        repo.git.add('.')
        repo.index.commit("修改服务器中继信息")
        
        logger.info("hbb_common 修改已提交到本地仓库")
    
    def create_github_repository(self, repo_name: str, description: str = "") -> str:
        """在 GitHub 创建新仓库"""
        logger.info(f"创建 GitHub 仓库: {repo_name}")
        
        url = f"{self.github_api_base}/user/repos"
        data = {
            "name": repo_name,
            "description": description,
            "private": False,
            "auto_init": False
        }
        response = self._request("post", url, (201,), json=data)
        repo_info = response.json()
        logger.info(f"仓库创建成功: {repo_info['html_url']}")
        return repo_info['clone_url']
    
    def push_to_github(self, local_repo_path: str, remote_url: str):
        """推送本地仓库到 GitHub"""
        logger.info(f"推送 {local_repo_path} 到 {remote_url}")
        
        repo = git.Repo(local_repo_path)
        
        # 获取当前分支名称
        current_branch = repo.active_branch.name
        logger.info(f"当前分支: {current_branch}")
        
        # 添加远程仓库
        try:
            origin = repo.remote('origin')
            origin.set_url(remote_url)
        except:
            origin = repo.create_remote('origin', remote_url)
        
        # 推送到远程仓库，使用当前分支名称
        origin.push(refspec=f'{current_branch}:{current_branch}')
        logger.info("推送完成")
    
    def update_rustdesk_submodule(self, new_hbb_common_url: str):
        """更新 rustdesk 仓库的 hbb_common 子模块"""
        logger.info("更新 rustdesk 子模块...")
        
        repo = git.Repo(self.rustdesk_dir)
        
        # 删除现有子模块
        logger.info("删除现有 hbb_common 子模块")
        try:
            repo.git.rm('-rf', 'libs/hbb_common')
            repo.index.commit("删除 hbb_common 子模块")
        except Exception as e:
            logger.warning(f"删除子模块时出现警告: {e}")
        
        # 添加新的子模块
        logger.info(f"添加新的 hbb_common 子模块: {new_hbb_common_url}")
        repo.git.submodule('add', '-f', new_hbb_common_url, 'libs/hbb_common')
        
        # 更新子模块
        repo.git.submodule('update', '--init', '--recursive', '--force')
        
        # 提交修改
        repo.git.add('.')
        repo.index.commit("重新添加子模块")
        
        logger.info("子模块更新完成")
    
    def get_rustdesk_version(self) -> str:
        """获取 rustdesk 仓库的版本号"""
        cargo_toml_path = os.path.join(self.rustdesk_dir, "Cargo.toml")
        
        with open(cargo_toml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
        if version_match:
            return version_match.group(1)
        else:
            return "1.0.0"  # 默认版本
    
    def create_tag_and_push(self, repo_path: str, version: str):
        """创建标签并推送以触发 GitHub Actions"""
        # 创建符合 GitHub Actions 触发条件的标签格式
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        tag_name = f"{version}-{timestamp}"
        
        logger.info(f"创建标签 {tag_name} 并推送...")
        
        repo = git.Repo(repo_path)
        
        # 删除可能存在的本地标签
        try:
            repo.delete_tag(tag_name)
            logger.info(f"删除已存在的本地标签: {tag_name}")
        except:
            pass  # 标签不存在，忽略错误
        
        # 删除可能存在的远程标签
        try:
            origin = repo.remote('origin')
            origin.push(f":refs/tags/{tag_name}")
            logger.info(f"删除已存在的远程标签: {tag_name}")
        except:
            pass  # 标签不存在，忽略错误
        
        # 创建标签
        tag_message = "修改服务器和 key"
        repo.create_tag(tag_name, message=tag_message)
        
        # 推送标签
        origin = repo.remote('origin')
        origin.push(tag_name)
        
        logger.info(f"标签 {tag_name} 已推送，GitHub Actions 将开始编译")
    
    def set_repository_permissions(self, repo_name: str):
        """设置仓库的 Actions 权限"""
        logger.info(f"设置仓库 {repo_name} 的 Actions 权限...")
        
        # 设置 Actions 权限
        url = f"{self.github_api_base}/repos/{self.github_username}/{repo_name}/actions/permissions"
        data = {
            "enabled": True,
            "allowed_actions": "all"
        }
        
        try:
            self._request("put", url, (200, 204), json=data)
        except Exception as exc:
            logger.warning(f"设置 Actions 权限失败: {exc}")
        
        # 设置工作流权限
        url = f"{self.github_api_base}/repos/{self.github_username}/{repo_name}/actions/permissions/workflow"
        data = {
            "default_workflow_permissions": "write",
            "can_approve_pull_request_reviews": True
        }
        
        try:
            self._request("put", url, (200, 204), json=data)
        except Exception as exc:
            logger.warning(f"设置工作流权限失败: {exc}")
        
        logger.info("权限设置完成")
    
    def run(self):
        """运行完整的自动化流程"""
        try:
            logger.info("开始 RustDesk 自动化编译流程...")
            
            # 1. 设置工作环境
            self.setup_workspace()
            
            # 2. 克隆仓库
            self.clone_repositories()
            
            # 3. 修改配置文件
            self.modify_config_file()
            
            # 4. 提交 hbb_common 修改
            self.commit_hbb_common_changes()
            
            # 5. 创建 hbb_common 仓库
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            hbb_common_repo_name = f"hbb_common_{timestamp}"
            hbb_common_url = self.create_github_repository(
                hbb_common_repo_name, 
                "Modified hbb_common with custom server settings"
            )
            
            # 6. 推送 hbb_common 到 GitHub
            self.push_to_github(self.hbb_common_dir, hbb_common_url)
            
            # 7. 更新 rustdesk 子模块
            self.update_rustdesk_submodule(hbb_common_url)
            
            # 8. 创建 rustdesk 仓库
            rustdesk_repo_name = f"rustdesk_{timestamp}"
            rustdesk_url = self.create_github_repository(
                rustdesk_repo_name,
                "Modified RustDesk with custom server settings"
            )
            
            # 9. 推送 rustdesk 到 GitHub
            self.push_to_github(self.rustdesk_dir, rustdesk_url)
            
            # 10. 设置仓库权限
            self.set_repository_permissions(rustdesk_repo_name)
            
            # 11. 获取版本号并创建标签
            version = self.get_rustdesk_version()
            self.create_tag_and_push(self.rustdesk_dir, version)
            
            logger.info("自动化流程完成！")
            logger.info(f"hbb_common 仓库: https://github.com/{self.github_username}/{hbb_common_repo_name}")
            logger.info(f"rustdesk 仓库: https://github.com/{self.github_username}/{rustdesk_repo_name}")
            logger.info("GitHub Actions 编译已触发，请查看仓库的 Actions 页面")
            
        except Exception as e:
            logger.error(f"流程执行失败: {e}")
            raise


if __name__ == "__main__":
    try:
        builder = RustDeskAutoBuild()
        builder.run()
    except Exception as e:
        logger.error(f"程序执行失败: {e}")
        exit(1)
