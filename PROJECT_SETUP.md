# 项目设置说明

## 快速开始

### 1. 配置文件设置
复制 `config_example.json` 为 `config.json` 并填入您的实际信息：

```bash
cp config_example.json config.json
```

然后编辑 `config.json`：
```json
{
    "github_token": "您的GitHub个人访问令牌",
    "github_username": "您的GitHub用户名",
    "server_address": "您的服务器IP地址",
    "public_key": "您的公钥",
    "dry_run": true
}
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 使用工具

#### GitHub仓库清理工具
```bash
# 预览模式（安全）
python github_repo_cleaner.py

# 实际删除模式
python github_repo_cleaner.py --no-dry-run
```

#### RustDesk自动构建工具
```bash
python rustdesk_auto_build.py
```

## 安全提示

- `config.json` 包含敏感信息，已被 `.gitignore` 过滤，不会上传到GitHub
- 建议在生产环境中使用环境变量而不是配置文件存储敏感信息
- 首次使用删除工具时，请务必使用预览模式确认要删除的仓库

## 文件说明

- `github_repo_cleaner.py` - GitHub仓库批量删除工具
- `rustdesk_auto_build.py` - RustDesk自动构建工具
- `config_example.json` - 配置文件示例
- `删除模式使用说明.md` - 删除工具详细使用说明
- `README_github_cleaner.md` - GitHub清理工具说明