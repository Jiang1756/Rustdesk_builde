# RustDesk 自动化编译工具

这是一个用于自动化编译 RustDesk 客户端的 Python 工具，可以自动修改服务器地址和公钥，并触发 GitHub Actions 进行编译。

## 功能

- 自动克隆 rustdesk 和 hbb_common 仓库
- 修改服务器地址和公钥配置
- 修改子模块
- 自动创建 GitHub 仓库并推送代码
- 设置 GitHub Actions 权限
- 创建版本标签触发自动编译

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

1. 配置GitHub并填入信息到`config.json`中 ：

```json
{
    "github_token": "你的GitHub个人访问令牌",
    "github_username": "你的GitHub用户名",
    "server_address": "你的RustDesk服务器IP地址",
    "public_key": "你的RustDesk服务器公钥"
}
```

### 获取 GitHub Personal Access Token

1. 登录 GitHub，进入 Settings > Developer settings > Personal access tokens > Tokens (classic)
2. 点击 "Generate new token (classic)"
3. 设置权限，至少需要以下权限：
   - `repo` (完整仓库访问权限)
   - `workflow` (工作流权限)
   - `admin:repo_hook` (仓库钩子管理权限)

## 使用方法

1. 确保已安装 Python 3.7+
2. 安装依赖：`pip install -r requirements.txt`
3. 配置 `config.json` 文件
4. 运行脚本：`python rustdesk_auto_build.py`

## 工作流程

该工具将按以下步骤执行：

1. 克隆 rustdesk 和 hbb_common 仓库到本地
2. 修改 hbb_common/src/config.rs 中的服务器地址和公钥
3. 提交修改到本地仓库
4. 在 GitHub 创建新的 hbb_common 仓库（格式：hbb_common_日期_时间）
5. 推送修改后的 hbb_common 到 GitHub
6. 更新 rustdesk 仓库的 hbb_common 子模块
7. 在 GitHub 创建新的 rustdesk 仓库（格式：rustdesk_日期_时间）
8. 推送修改后的 rustdesk 到 GitHub
9. 设置仓库的 Actions 权限
10. 创建版本标签并推送，触发 GitHub Actions 编译

## 注意事项

- 确保你的 GitHub 账户有足够的权限创建公开仓库
- 网络连接需要稳定，因为需要克隆大型仓库
- 编译过程可能需要较长时间，请耐心等待
- 建议在运行前备份重要数据

## 日志文件

程序运行时会生成 `rustdesk_build.log` 日志文件，记录详细的执行过程和错误信息。

## 故障排除

如果遇到问题，请检查：

1. GitHub token 是否有效且权限充足
2. 网络连接是否稳定
3. 配置文件格式是否正确
4. 查看日志文件了解详细错误信息

## 许可证

本工具仅供学习和个人使用，请遵守相关开源协议。
