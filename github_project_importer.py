#!/usr/bin/env python3
"""
GitHub ProjectV2 CSV 导入工具

此脚本从CSV文件读取数据，并使用GitHub GraphQL API将项目添加到GitHub ProjectV2项目中。

必需的CSV列:
- title: 项目标题 (必需)
- content_type: 内容类型 (issue/pull_request/draft) (必需)

可选的CSV列:
- description: 项目描述
- assignees: GitHub用户名列表（逗号分隔）
- labels: 标签列表（逗号分隔）
- milestone: 里程碑名称
- status: 项目状态字段值
- priority: 项目优先级字段值
- estimate: 工作量估算
- repository: 仓库名称 (用于issues/PRs)
- issue_number: Issue/PR编号 (用于添加现有项目)

使用方法:
    python github_project_importer.py --csv data.csv --project PROJECT_ID --token TOKEN
    python github_project_importer.py --csv data.csv --config config.yaml
"""

import csv
import argparse
import logging
import sys
import time
from typing import Dict, List, Optional, Any
import requests
import yaml
from dataclasses import dataclass, field


@dataclass
class ProjectItem:
    """表示要导入的项目条目"""
    title: str
    content_type: str
    description: Optional[str] = None
    assignees: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    milestone: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    estimate: Optional[str] = None
    size: Optional[str] = None
    repository: Optional[str] = None
    issue_number: Optional[int] = None


class GitHubProjectImporter:
    """处理CSV数据导入到GitHub ProjectV2的主要类"""
    
    def __init__(self, token: str, project_id: str, config: Optional[Dict] = None):
        self.token = token
        self.project_id = project_id
        self.config = config or {}
        
        # API配置
        api_config = self.config.get('api', {})
        self.api_url = api_config.get('endpoint', 'https://api.github.com/graphql')
        self.timeout = api_config.get('timeout', 30)
        self.max_retries = api_config.get('max_retries', 3)
        self.retry_delay = api_config.get('retry_delay', 1)
        
        # 导入配置
        import_config = self.config.get('import', {})
        self.batch_size = import_config.get('batch_size', 10)
        self.batch_delay = import_config.get('batch_delay', 1.0)
        self.continue_on_error = import_config.get('continue_on_error', True)
        
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self.logger = logging.getLogger(__name__)
        
    def execute_graphql(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """对GitHub API执行GraphQL查询"""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
            
        # 实现重试机制
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout
                )
                break
            except requests.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise Exception(f"API请求失败: {str(e)}")
                self.logger.warning(f"API请求失败，{self.retry_delay}秒后重试... (尝试 {attempt + 1}/{self.max_retries})")
                time.sleep(self.retry_delay)
        
        if response.status_code != 200:
            raise Exception(f"GraphQL请求失败: {response.status_code} - {response.text}")
            
        result = response.json()
        
        if "errors" in result:
            raise Exception(f"GraphQL错误: {result['errors']}")
            
        return result.get("data", {})
    
    def get_project_info(self) -> Dict[str, Any]:
        """获取项目信息，包括字段信息"""
        query = """
        query($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    id
                    title
                    fields(first: 20) {
                        nodes {
                            ... on ProjectV2Field {
                                id
                                name
                                dataType
                            }
                            ... on ProjectV2SingleSelectField {
                                id
                                name
                                dataType
                                options {
                                    id
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {"projectId": self.project_id}
        result = self.execute_graphql(query, variables)
        
        project = result.get("node")
        if not project:
            raise Exception(f"未找到项目: {self.project_id}")
            
        return project
    
    def create_draft_issue(self, item: ProjectItem) -> str:
        """在项目中创建草稿issue"""
        # 首先获取assignee用户ID
        assignee_ids = []
        if item.assignees:
            for assignee_login in item.assignees:
                try:
                    user_id = self.get_user_id(assignee_login)
                    if user_id:
                        assignee_ids.append(user_id)
                except Exception as e:
                    self.logger.warning(f"无法获取用户 {assignee_login} 的ID: {str(e)}")
        
        mutation = """
        mutation($projectId: ID!, $title: String!, $body: String, $assigneeIds: [ID!]) {
            addProjectV2DraftIssue(input: {
                projectId: $projectId,
                title: $title,
                body: $body,
                assigneeIds: $assigneeIds
            }) {
                projectItem {
                    id
                }
            }
        }
        """
        
        variables = {
            "projectId": self.project_id,
            "title": item.title,
            "body": item.description or "",
            "assigneeIds": assignee_ids
        }
        
        result = self.execute_graphql(mutation, variables)
        return result["addProjectV2DraftIssue"]["projectItem"]["id"]
    
    def get_user_id(self, username: str) -> Optional[str]:
        """获取用户的GitHub节点ID"""
        query = """
        query($login: String!) {
            user(login: $login) {
                id
            }
        }
        """
        
        variables = {"login": username}
        
        try:
            result = self.execute_graphql(query, variables)
            user_data = result.get("user")
            if user_data:
                return user_data["id"]
            else:
                self.logger.warning(f"未找到用户: {username}")
                return None
        except Exception as e:
            self.logger.warning(f"获取用户 {username} 信息失败: {str(e)}")
            return None
    
    def add_existing_item(self, content_id: str) -> str:
        """将现有的issue或PR添加到项目中"""
        mutation = """
        mutation($projectId: ID!, $contentId: ID!) {
            addProjectV2ItemById(input: {
                projectId: $projectId,
                contentId: $contentId
            }) {
                item {
                    id
                }
            }
        }
        """
        
        variables = {
            "projectId": self.project_id,
            "contentId": content_id
        }
        
        result = self.execute_graphql(mutation, variables)
        return result["addProjectV2ItemById"]["item"]["id"]
    
    def get_issue_id(self, repository: str, issue_number: int) -> str:
        """获取issue或PR的GitHub节点ID"""
        owner, repo = repository.split("/") if "/" in repository else ("", repository)
        
        query = """
        query($owner: String!, $repo: String!, $number: Int!) {
            repository(owner: $owner, name: $repo) {
                issue(number: $number) {
                    id
                }
                pullRequest(number: $number) {
                    id
                }
            }
        }
        """
        
        variables = {
            "owner": owner,
            "repo": repo,
            "number": issue_number
        }
        
        result = self.execute_graphql(query, variables)
        repo_data = result.get("repository", {})
        
        # 先尝试issue，然后尝试PR
        if repo_data.get("issue"):
            return repo_data["issue"]["id"]
        elif repo_data.get("pullRequest"):
            return repo_data["pullRequest"]["id"]
        else:
            raise Exception(f"在 {repository} 中未找到 Issue/PR #{issue_number}")
    
    def update_field_value(self, item_id: str, field_id: str, value: str, field_type: str = "TEXT"):
        """更新项目条目的字段值"""
        if field_type == "SINGLE_SELECT":
            mutation = """
            mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $singleSelectOptionId: String!) {
                updateProjectV2ItemFieldValue(input: {
                    projectId: $projectId,
                    itemId: $itemId,
                    fieldId: $fieldId,
                    value: {
                        singleSelectOptionId: $singleSelectOptionId
                    }
                }) {
                    projectV2Item {
                        id
                    }
                }
            }
            """
            variables = {
                "projectId": self.project_id,
                "itemId": item_id,
                "fieldId": field_id,
                "singleSelectOptionId": value
            }
        elif field_type == "NUMBER":
            mutation = """
            mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $number: Float!) {
                updateProjectV2ItemFieldValue(input: {
                    projectId: $projectId,
                    itemId: $itemId,
                    fieldId: $fieldId,
                    value: {
                        number: $number
                    }
                }) {
                    projectV2Item {
                        id
                    }
                }
            }
            """
            variables = {
                "projectId": self.project_id,
                "itemId": item_id,
                "fieldId": field_id,
                "number": float(value)
            }
        else:
            mutation = """
            mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $text: String!) {
                updateProjectV2ItemFieldValue(input: {
                    projectId: $projectId,
                    itemId: $itemId,
                    fieldId: $fieldId,
                    value: {
                        text: $text
                    }
                }) {
                    projectV2Item {
                        id
                    }
                }
            }
            """
            variables = {
                "projectId": self.project_id,
                "itemId": item_id,
                "fieldId": field_id,
                "text": value
            }
        
        self.execute_graphql(mutation, variables)
    
    def import_item(self, item: ProjectItem, project_fields: Dict[str, Any]) -> str:
        """将单个条目导入到项目中"""
        self.logger.info(f"正在导入条目: {item.title}")
        
        # 确定如何添加条目
        if item.content_type == "draft":
            item_id = self.create_draft_issue(item)
        elif item.repository and item.issue_number:
            # 添加现有的issue/PR
            content_id = self.get_issue_id(item.repository, item.issue_number)
            item_id = self.add_existing_item(content_id)
        else:
            # 默认创建草稿issue
            item_id = self.create_draft_issue(item)
        
        # 更新自定义字段
        field_map = {field["name"].lower(): field for field in project_fields.get("nodes", [])}
        
        # 将条目字段映射到项目字段
        field_updates = {
            "status": item.status,
            "priority": item.priority,
            "estimate": item.estimate,
            "size": item.size,
        }
        
        for field_name, field_value in field_updates.items():
            if field_value and field_name in field_map:
                field_info = field_map[field_name]
                field_id = field_info["id"]
                
                field_data_type = field_info.get("dataType")
                
                if field_data_type == "SINGLE_SELECT":
                    # 为单选字段查找选项ID
                    options = field_info.get("options", [])
                    option_id = None
                    for option in options:
                        if option["name"].lower() == field_value.lower():
                            option_id = option["id"]
                            break
                    
                    if option_id:
                        self.update_field_value(item_id, field_id, option_id, "SINGLE_SELECT")
                    else:
                        self.logger.warning(f"未找到字段 '{field_name}' 的选项 '{field_value}'")
                        
                elif field_data_type == "NUMBER":
                    # 处理数字字段
                    try:
                        # 验证是否为有效数字
                        float(field_value)
                        self.update_field_value(item_id, field_id, field_value, "NUMBER")
                    except ValueError:
                        self.logger.warning(f"字段 '{field_name}' 的值 '{field_value}' 不是有效的数字，跳过更新")
                        
                else:
                    # 默认作为文本字段处理
                    self.update_field_value(item_id, field_id, field_value, "TEXT")
        
        self.logger.info(f"成功导入: {item.title}")
        return item_id


def parse_csv_row(row: Dict[str, str]) -> ProjectItem:
    """将CSV行解析为ProjectItem对象"""
    # 分割逗号分隔的值
    assignees = [a.strip() for a in row.get("assignees", "").split(",") if a.strip()]
    labels = [l.strip() for l in row.get("labels", "").split(",") if l.strip()]
    
    # 解析issue编号
    issue_number = None
    if row.get("issue_number"):
        try:
            issue_number = int(row["issue_number"])
        except ValueError:
            pass
    
    return ProjectItem(
        title=row["title"],
        content_type=row.get("content_type", "draft"),
        description=row.get("description"),
        assignees=assignees,
        labels=labels,
        milestone=row.get("milestone"),
        status=row.get("status"),
        priority=row.get("priority"),
        estimate=row.get("estimate"),
        size=row.get("size"),
        repository=row.get("repository"),
        issue_number=issue_number
    )


def setup_logging(config: Dict = None, verbose: bool = False):
    """设置日志配置"""
    # 从配置文件读取日志设置
    log_config = config.get('logging', {}) if config else {}
    
    if verbose:
        level = logging.DEBUG
    else:
        level_str = log_config.get('level', 'INFO')
        level = getattr(logging, level_str.upper(), logging.INFO)
    
    log_format = log_config.get('format', '%(asctime)s - %(levelname)s - %(message)s')
    date_format = log_config.get('date_format', '%Y-%m-%d %H:%M:%S')
    log_file = log_config.get('file')
    
    logging_config = {
        'level': level,
        'format': log_format,
        'datefmt': date_format
    }
    
    if log_file:
        logging_config['filename'] = log_file
    
    logging.basicConfig(**logging_config)


def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise Exception(f"配置文件未找到: {config_path}")
    except yaml.YAMLError as e:
        raise Exception(f"配置文件格式错误: {str(e)}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="将CSV数据导入到GitHub ProjectV2")
    parser.add_argument("--csv", required=True, help="CSV文件路径")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--project", help="GitHub项目ID")
    parser.add_argument("--token", help="GitHub个人访问令牌")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    parser.add_argument("--dry-run", action="store_true", help="干运行模式（不执行实际导入）")
    
    args = parser.parse_args()
    
    # 加载配置文件
    config = {}
    if args.config:
        config = load_config(args.config)
    
    # 设置日志
    setup_logging(config, args.verbose)
    logger = logging.getLogger(__name__)
    
    # 获取token和project_id
    token = args.token or config.get('github', {}).get('token')
    project_id = args.project or config.get('github', {}).get('default_project_id')
    
    if not token:
        logger.error("未提供GitHub访问令牌。请使用--token参数或在配置文件中设置。")
        sys.exit(1)
        
    if not project_id:
        logger.error("未提供项目ID。请使用--project参数或在配置文件中设置。")
        sys.exit(1)
    
    try:
        # 初始化导入工具
        importer = GitHubProjectImporter(token, project_id, config)
        
        # 获取项目信息
        logger.info("正在获取项目信息...")
        project_info = importer.get_project_info()
        logger.info(f"项目: {project_info['title']}")
        
        # 读取CSV文件
        logger.info(f"正在读取CSV文件: {args.csv}")
        items = []
        
        csv_encoding = config.get('csv', {}).get('encoding', 'utf-8')
        with open(args.csv, 'r', encoding=csv_encoding) as csvfile:
            reader = csv.DictReader(csvfile)
            
            # 验证必需的列
            required_columns = config.get('csv', {}).get('required_columns', ['title', 'content_type'])
            missing_columns = [col for col in required_columns if col not in reader.fieldnames]
            if missing_columns:
                raise Exception(f"缺少必需的列: {missing_columns}")
            
            for row in reader:
                if not row.get("title", "").strip():
                    logger.warning(f"跳过标题为空的行: {row}")
                    continue
                    
                items.append(parse_csv_row(row))
        
        logger.info(f"找到 {len(items)} 个条目待导入")
        
        if args.dry_run:
            logger.info("干运行模式 - 不会执行实际导入")
            for item in items:
                logger.info(f"将导入: {item.title} ({item.content_type})")
            return
        
        # 导入条目
        success_count = 0
        for i, item in enumerate(items, 1):
            try:
                logger.info(f"正在处理条目 {i}/{len(items)}: {item.title}")
                importer.import_item(item, project_info.get("fields", {}))
                success_count += 1
                
                # 批次延迟
                if i % importer.batch_size == 0 and i < len(items):
                    logger.info(f"已处理 {i} 个条目，等待 {importer.batch_delay} 秒...")
                    time.sleep(importer.batch_delay)
                    
            except Exception as e:
                logger.error(f"导入 '{item.title}' 失败: {str(e)}")
                if not importer.continue_on_error:
                    logger.error("遇到错误，停止导入")
                    break
                continue
        
        logger.info(f"导入完成: {success_count}/{len(items)} 个条目成功导入")
        
    except Exception as e:
        logger.error(f"导入失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()