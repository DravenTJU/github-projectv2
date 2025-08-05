# GitHub ProjectV2 CSV Importer

一个用于将CSV文件数据批量导入GitHub ProjectV2项目的Python脚本。

## 功能特性

- 支持从CSV文件读取数据并添加到GitHub ProjectV2项目
- 支持创建草稿Issue、添加现有Issue/PR
- 支持更新项目自定义字段（状态、优先级、工作量估算等）
- 提供详细的日志记录和错误处理
- 支持干运行模式用于测试

## 环境设置

### 使用 uv（推荐）

[uv](https://github.com/astral-sh/uv) 是一个快速的Python包管理工具。

```bash
# 安装uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境
uv venv

# 激活虚拟环境
source .venv/bin/activate  # macOS/Linux
# 或
.venv\Scripts\activate     # Windows

# 安装依赖
uv pip install requests PyYAML
```

### 使用 pip（传统方式）

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
source .venv/bin/activate  # macOS/Linux
# 或
.venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

## 配置文件

推荐使用配置文件来管理GitHub Token和其他设置。创建 `config.yaml` 文件：

```bash
cp config.yaml.example config.yaml
# 编辑config.yaml，填入你的GitHub Token
```

### 配置文件结构

```yaml
github:
  token: "ghp_your_token_here"  # GitHub Personal Access Token
  default_project_id: ""        # 默认项目ID（可选）

api:
  timeout: 30        # API请求超时时间
  max_retries: 3     # 最大重试次数
  retry_delay: 1     # 重试间隔（秒）

import:
  batch_size: 10     # 批处理大小
  batch_delay: 1.0   # 批次间延迟（秒）
  continue_on_error: true  # 遇到错误时是否继续

logging:
  level: "INFO"      # 日志级别
  file: ""           # 日志文件路径（可选）

csv:
  encoding: "utf-8"  # CSV文件编码
  field_mapping:     # 字段映射
    "Status": "status"
    "Priority": "priority"
```

## 使用方法

### 基本用法

**使用配置文件（推荐）：**
```bash
python github_project_importer.py --csv data.csv --config config.yaml
```

**使用命令行参数：**
```bash
python github_project_importer.py --csv data.csv --project PROJECT_ID --token YOUR_TOKEN
```

### 参数说明

- `--csv`: CSV文件路径（必需）
- `--config`: 配置文件路径（推荐）
- `--project`: GitHub Project ID（节点ID，可在配置文件中设置）
- `--token`: GitHub Personal Access Token（可在配置文件中设置）
- `--verbose/-v`: 启用详细日志
- `--dry-run`: 干运行模式，只显示将要导入的项目

### 获取Project ID

使用GitHub CLI或GraphQL API获取项目ID：

```bash
gh api graphql -f query='
{
  user(login: "YOUR_USERNAME") {
    projectsV2(first: 10) {
      nodes {
        id
        title
      }
    }
  }
}'
```

## CSV文件格式

### 必需列

| 列名 | 说明 | 示例 |
|------|------|------|
| `title` | 项目标题 | "实现用户认证功能" |
| `content_type` | 内容类型 | "draft", "issue", "pull_request" |

### 可选列

| 列名 | 说明 | 示例 |
|------|------|------|
| `description` | 项目描述 | "添加JWT认证和用户登录功能" |
| `assignees` | 分配人员（逗号分隔） | "john,mary" |
| `labels` | 标签（逗号分隔） | "feature,backend" |
| `milestone` | 里程碑名称 | "v1.0" |
| `status` | 状态 | "Todo", "In Progress", "Done" |
| `priority` | 优先级 | "High", "Medium", "Low" |
| `estimate` | 工作量估算 | "5" |
| `repository` | 仓库名称 | "myorg/myrepo" |
| `issue_number` | Issue/PR编号 | "123" |

### CSV示例

```csv
title,content_type,description,assignees,labels,milestone,status,priority,estimate,repository,issue_number
"实现用户认证功能",draft,"添加JWT认证和用户登录功能","john,mary","feature,backend","v1.0","Todo","High","5","",""
"修复登录页面样式问题",draft,"修复响应式布局问题","alice","bug,frontend","v1.0","In Progress","Medium","2","",""
"添加现有Issue",issue,"","charlie","enhancement","","Todo","High","","myorg/myrepo","123"
```

## 内容类型说明

1. **draft**: 创建新的草稿Issue
2. **issue**: 添加现有Issue到项目（需要repository和issue_number）
3. **pull_request**: 添加现有PR到项目（需要repository和issue_number）

## GitHub Token权限

Personal Access Token需要以下权限：
- `project` (读写项目权限)
- `read:org` (读取组织信息，如果是组织项目)
- `repo` (如果需要访问私有仓库的Issue/PR)

## 使用示例

### 1. 配置文件方式（推荐）

**创建配置文件：**
```bash
# 复制示例配置文件并修改
cp config.yaml config.yaml.local
# 编辑config.yaml.local，填入你的GitHub Token和项目ID
```

**使用 uv 运行：**
```bash
# 干运行测试
uv run python github_project_importer.py \
  --csv example_data.csv \
  --config config.yaml.local \
  --dry-run \
  --verbose

# 实际导入
uv run python github_project_importer.py \
  --csv example_data.csv \
  --config config.yaml.local \
  --verbose
```

**使用激活的虚拟环境：**
```bash
# 先激活虚拟环境
source .venv/bin/activate

# 干运行测试
python github_project_importer.py \
  --csv example_data.csv \
  --config config.yaml.local \
  --dry-run \
  --verbose

# 实际导入
python github_project_importer.py \
  --csv example_data.csv \
  --config config.yaml.local \
  --verbose
```

### 2. 命令行参数方式

**使用 uv 运行：**
```bash
# 干运行测试
uv run python github_project_importer.py \
  --csv example_data.csv \
  --project "PVT_kwDOBkEhgs4AApI0" \
  --token "ghp_xxxxxxxxxxxx" \
  --dry-run \
  --verbose

# 实际导入
uv run python github_project_importer.py \
  --csv example_data.csv \
  --project "PVT_kwDOBkEhgs4AApI0" \
  --token "ghp_xxxxxxxxxxxx" \
  --verbose
```

**使用激活的虚拟环境：**
```bash
# 先激活虚拟环境
source .venv/bin/activate

# 干运行测试
python github_project_importer.py \
  --csv example_data.csv \
  --project "PVT_kwDOBkEhgs4AApI0" \
  --token "ghp_xxxxxxxxxxxx" \
  --dry-run \
  --verbose

# 实际导入
python github_project_importer.py \
  --csv example_data.csv \
  --project "PVT_kwDOBkEhgs4AApI0" \
  --token "ghp_xxxxxxxxxxxx" \
  --verbose
```

## 高级功能

### 批处理和速率限制

脚本支持批处理导入，可以在配置文件中设置：

```yaml
import:
  batch_size: 10     # 每批处理10个项目
  batch_delay: 1.0   # 批次间等待1秒
  continue_on_error: true  # 遇到错误时继续处理其他项目
```

### 日志配置

可以将日志输出到文件：

```yaml
logging:
  level: "DEBUG"     # 详细日志
  file: "import.log"  # 日志文件路径
```

### API重试机制

内置API重试机制，避免临时网络问题：

```yaml
api:
  max_retries: 3     # 最大重试3次
  retry_delay: 1     # 重试间隔1秒
  timeout: 30        # 请求超时30秒
```

## 注意事项

1. **配置文件安全**: 配置文件包含敏感的GitHub Token，请勿提交到版本控制系统
2. **字段映射**: 脚本会自动将CSV中的字段映射到项目的自定义字段
3. **单选字段**: 对于状态、优先级等单选字段，值必须完全匹配项目中的选项
4. **错误处理**: 可配置单个项目导入失败时的处理策略
5. **速率限制**: 内置批处理和延迟机制，避免触发GitHub API速率限制

## 故障排除

### 常见错误

1. **"未找到项目"**: 检查Project ID是否正确
2. **"GraphQL错误"**: 检查Token权限和API查询语法  
3. **"未找到Issue/PR"**: 检查仓库名称和Issue/PR编号
4. **"配置文件未找到"**: 检查配置文件路径是否正确
5. **"未提供GitHub访问令牌"**: 检查配置文件或命令行参数中的token设置

### 日志级别

- 使用 `--verbose` 参数启用详细日志
- 在配置文件中设置日志级别：`DEBUG`, `INFO`, `WARNING`, `ERROR`
- 可选择将日志输出到文件进行长期保存

### 配置文件模板

项目提供了 `config.yaml` 模板文件，包含所有可配置选项的说明。复制并修改此文件来创建你的个人配置。

## 安全建议

1. **Token安全**: 将GitHub Token存储在配置文件中，并将配置文件添加到`.gitignore`
2. **权限最小化**: 只为Token分配必要的权限（`project`，以及访问相关仓库的权限）
3. **定期轮换**: 定期更换GitHub Personal Access Token
4. **环境隔离**: 为不同环境（开发、测试、生产）使用不同的配置文件

## 故障恢复

如果导入过程中断，可以：

1. 检查日志了解失败原因
2. 修复数据或配置问题
3. 使用 `--dry-run` 测试修复效果
4. 重新运行导入（脚本会跳过已存在的项目）

## 许可证

MIT License