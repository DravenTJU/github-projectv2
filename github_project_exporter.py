#!/usr/bin/env python3
"""
GitHub ProjectV2 任务导出工具

此脚本使用 GitHub GraphQL API 获取指定 ProjectV2 项目中所有任务的详细信息，
包括 assignees、size、status、priority 等字段。

使用方法:
    python github_project_exporter.py --config config.yaml
    python github_project_exporter.py --project PROJECT_ID --token TOKEN
    python github_project_exporter.py --config config.yaml --output tasks.json
"""

import argparse
import logging
import sys
import json
import csv
from typing import Dict, List, Optional, Any
import requests
import yaml
from datetime import datetime
from dataclasses import dataclass, field, asdict


@dataclass
class TaskInfo:
    """表示一个项目任务的详细信息"""
    id: str
    title: str
    content_type: str  # "Issue", "PullRequest", "DraftIssue"
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    size: Optional[str] = None
    estimate: Optional[str] = None
    assignees: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    milestone: Optional[str] = None
    repository: Optional[str] = None
    number: Optional[int] = None
    url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    closed_at: Optional[str] = None
    state: Optional[str] = None
    comments: List[Dict[str, Any]] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)


class GitHubProjectExporter:
    """处理从GitHub ProjectV2导出任务数据的主要类"""
    
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
                import time
                time.sleep(self.retry_delay)
        
        if response.status_code != 200:
            raise Exception(f"GraphQL请求失败: {response.status_code} - {response.text}")
            
        result = response.json()
        
        if "errors" in result:
            raise Exception(f"GraphQL错误: {result['errors']}")
            
        return result.get("data", {})
    
    def get_project_tasks(self) -> List[TaskInfo]:
        """获取项目中所有任务的详细信息"""
        query = """
        query($projectId: ID!, $cursor: String) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    id
                    title
                    fields(first: 50) {
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
                            ... on ProjectV2IterationField {
                                id
                                name
                                dataType
                                configuration {
                                    iterations {
                                        id
                                        title
                                        startDate
                                        duration
                                    }
                                }
                            }
                        }
                    }
                    items(first: 100, after: $cursor) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        nodes {
                            id
                            type
                            fieldValues(first: 20) {
                                nodes {
                                    ... on ProjectV2ItemFieldTextValue {
                                        text
                                        field {
                                            ... on ProjectV2Field {
                                                id
                                                name
                                            }
                                        }
                                    }
                                    ... on ProjectV2ItemFieldNumberValue {
                                        number
                                        field {
                                            ... on ProjectV2Field {
                                                id
                                                name
                                            }
                                        }
                                    }
                                    ... on ProjectV2ItemFieldSingleSelectValue {
                                        optionId
                                        name
                                        field {
                                            ... on ProjectV2SingleSelectField {
                                                id
                                                name
                                            }
                                        }
                                    }
                                    ... on ProjectV2ItemFieldDateValue {
                                        date
                                        field {
                                            ... on ProjectV2Field {
                                                id
                                                name
                                            }
                                        }
                                    }
                                    ... on ProjectV2ItemFieldIterationValue {
                                        title
                                        startDate
                                        duration
                                        field {
                                            ... on ProjectV2IterationField {
                                                id
                                                name
                                            }
                                        }
                                    }
                                }
                            }
                            content {
                                ... on Issue {
                                    id
                                    title
                                    body
                                    number
                                    url
                                    state
                                    createdAt
                                    updatedAt
                                    closedAt
                                    assignees(first: 10) {
                                        nodes {
                                            login
                                            name
                                        }
                                    }
                                    labels(first: 20) {
                                        nodes {
                                            name
                                            color
                                        }
                                    }
                                    milestone {
                                        title
                                    }
                                    repository {
                                        name
                                        owner {
                                            login
                                        }
                                    }
                                    comments(first: 50, orderBy: {field: UPDATED_AT, direction: ASC}) {
                                        nodes {
                                            id
                                            body
                                            createdAt
                                            updatedAt
                                            author {
                                                login
                                                ... on User {
                                                    name
                                                }
                                            }
                                        }
                                    }
                                }
                                ... on PullRequest {
                                    id
                                    title
                                    body
                                    number
                                    url
                                    state
                                    createdAt
                                    updatedAt
                                    closedAt
                                    assignees(first: 10) {
                                        nodes {
                                            login
                                            name
                                        }
                                    }
                                    labels(first: 20) {
                                        nodes {
                                            name
                                            color
                                        }
                                    }
                                    milestone {
                                        title
                                    }
                                    repository {
                                        name
                                        owner {
                                            login
                                        }
                                    }
                                    comments(first: 50, orderBy: {field: UPDATED_AT, direction: ASC}) {
                                        nodes {
                                            id
                                            body
                                            createdAt
                                            updatedAt
                                            author {
                                                login
                                                ... on User {
                                                    name
                                                }
                                            }
                                        }
                                    }
                                }
                                ... on DraftIssue {
                                    id
                                    title
                                    body
                                    createdAt
                                    updatedAt
                                    assignees(first: 10) {
                                        nodes {
                                            login
                                            name
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        all_tasks = []
        cursor = None
        
        while True:
            variables = {"projectId": self.project_id}
            if cursor:
                variables["cursor"] = cursor
                
            result = self.execute_graphql(query, variables)
            project = result.get("node")
            
            if not project:
                raise Exception(f"未找到项目: {self.project_id}")
            
            self.logger.info(f"项目: {project['title']}")
            
            # 构建字段映射
            field_map = {}
            for field in project.get("fields", {}).get("nodes", []):
                field_map[field["id"]] = field
            
            # 处理任务
            items = project.get("items", {}).get("nodes", [])
            for item in items:
                task = self._parse_task_item(item, field_map)
                if task:
                    all_tasks.append(task)
            
            # 检查分页
            page_info = project.get("items", {}).get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
            
            self.logger.info(f"已获取 {len(all_tasks)} 个任务，继续获取下一页...")
        
        return all_tasks
    
    def _parse_task_item(self, item: Dict[str, Any], field_map: Dict[str, Any]) -> Optional[TaskInfo]:
        """解析单个任务条目"""
        content = item.get("content")
        if not content:
            return None
        
        # 确定内容类型
        content_type = "DraftIssue"
        if "number" in content:
            if "pullRequest" in str(type(content)).lower() or "state" in content:
                content_type = "PullRequest" if content.get("url", "").find("/pull/") > 0 else "Issue"
        
        # 基础信息
        task = TaskInfo(
            id=item["id"],
            title=content.get("title", ""),
            content_type=content_type,
            description=content.get("body", ""),
            number=content.get("number"),
            url=content.get("url"),
            created_at=content.get("createdAt"),
            updated_at=content.get("updatedAt"),
            closed_at=content.get("closedAt"),
            state=content.get("state")
        )
        
        # 处理assignees
        assignees_data = content.get("assignees", {}).get("nodes", [])
        task.assignees = [assignee.get("login", "") for assignee in assignees_data if assignee.get("login")]
        
        # 处理labels
        labels_data = content.get("labels", {}).get("nodes", [])
        task.labels = [label.get("name", "") for label in labels_data if label.get("name")]
        
        # 处理milestone
        milestone_data = content.get("milestone")
        if milestone_data:
            task.milestone = milestone_data.get("title")
        
        # 处理repository
        repo_data = content.get("repository")
        if repo_data:
            owner = repo_data.get("owner", {}).get("login", "")
            repo_name = repo_data.get("name", "")
            if owner and repo_name:
                task.repository = f"{owner}/{repo_name}"
        
        # 处理comments
        comments_data = content.get("comments", {}).get("nodes", [])
        task.comments = []
        for comment in comments_data:
            if comment.get("body"):  # 只包含有内容的评论
                author = comment.get("author", {})
                comment_info = {
                    "id": comment.get("id"),
                    "body": comment.get("body"),
                    "created_at": comment.get("createdAt"),
                    "updated_at": comment.get("updatedAt"),
                    "author": {
                        "login": author.get("login", ""),
                        "name": author.get("name", "")
                    }
                }
                task.comments.append(comment_info)
        
        # 处理自定义字段
        field_values = item.get("fieldValues", {}).get("nodes", [])
        for field_value in field_values:
            field_info = field_value.get("field")
            if not field_info:
                continue
                
            field_name = field_info.get("name", "").lower()
            field_id = field_info.get("id")
            
            # 获取字段值
            value = None
            if "text" in field_value:
                value = field_value["text"]
            elif "number" in field_value:
                value = str(field_value["number"])
            elif "name" in field_value:  # 单选字段
                value = field_value["name"]
            elif "date" in field_value:
                value = field_value["date"]
            elif "title" in field_value:  # 迭代字段
                value = field_value["title"]
            
            if value:
                task.custom_fields[field_name] = value
                
                # 映射到标准字段
                if field_name in ["status", "状态"]:
                    task.status = value
                elif field_name in ["priority", "优先级"]:
                    task.priority = value
                elif field_name in ["size", "大小", "尺寸"]:
                    task.size = value
                elif field_name in ["estimate", "估算", "工作量"]:
                    task.estimate = value
        
        return task


def setup_logging(config: Dict = None, verbose: bool = False):
    """设置日志配置"""
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


def export_to_json(tasks: List[TaskInfo], output_file: str):
    """导出任务到JSON文件"""
    tasks_data = [asdict(task) for task in tasks]
    
    export_data = {
        "export_time": datetime.now().isoformat(),
        "total_tasks": len(tasks),
        "tasks": tasks_data
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)


def export_to_csv(tasks: List[TaskInfo], output_file: str):
    """导出任务到CSV文件"""
    if not tasks:
        return
    
    # 准备CSV字段
    fieldnames = [
        'id', 'title', 'content_type', 'description', 'status', 'priority', 'size', 'estimate',
        'assignees', 'labels', 'milestone', 'repository', 'number', 'url',
        'created_at', 'updated_at', 'closed_at', 'state', 'comments_count'
    ]
    
    # 添加自定义字段
    all_custom_fields = set()
    for task in tasks:
        all_custom_fields.update(task.custom_fields.keys())
    
    fieldnames.extend(sorted(all_custom_fields))
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for task in tasks:
            row = asdict(task)
            # 处理列表字段
            row['assignees'] = ','.join(task.assignees)
            row['labels'] = ','.join(task.labels)
            
            # 处理comments - 在CSV中只显示评论数量
            row['comments_count'] = len(task.comments)
            
            # 添加自定义字段
            for field_name in all_custom_fields:
                row[field_name] = task.custom_fields.get(field_name, '')
            
            # 移除复杂字段
            row.pop('custom_fields', None)
            row.pop('comments', None)  # CSV中不包含完整的评论内容
            
            writer.writerow(row)


def print_summary(tasks: List[TaskInfo]):
    """打印任务摘要统计"""
    if not tasks:
        print("未找到任何任务")
        return
    
    print(f"\n=== 任务统计摘要 ===")
    print(f"总任务数: {len(tasks)}")
    
    # 按内容类型统计
    content_types = {}
    for task in tasks:
        content_types[task.content_type] = content_types.get(task.content_type, 0) + 1
    
    print(f"\n按类型统计:")
    for content_type, count in content_types.items():
        print(f"  {content_type}: {count}")
    
    # 按状态统计
    statuses = {}
    for task in tasks:
        status = task.status or "未设置状态"
        statuses[status] = statuses.get(status, 0) + 1
    
    if any(task.status for task in tasks):
        print(f"\n按状态统计:")
        for status, count in statuses.items():
            print(f"  {status}: {count}")
    
    # 按优先级统计
    priorities = {}
    for task in tasks:
        priority = task.priority or "未设置优先级"
        priorities[priority] = priorities.get(priority, 0) + 1
    
    if any(task.priority for task in tasks):
        print(f"\n按优先级统计:")
        for priority, count in priorities.items():
            print(f"  {priority}: {count}")
    
    # 按负责人统计
    assignee_counts = {}
    for task in tasks:
        if task.assignees:
            for assignee in task.assignees:
                assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1
        else:
            assignee_counts["未分配"] = assignee_counts.get("未分配", 0) + 1
    
    if assignee_counts:
        print(f"\n按负责人统计:")
        for assignee, count in sorted(assignee_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {assignee}: {count}")
    
    # 按评论数统计
    comment_stats = {}
    total_comments = 0
    for task in tasks:
        comment_count = len(task.comments)
        total_comments += comment_count
        if comment_count == 0:
            comment_stats["无评论"] = comment_stats.get("无评论", 0) + 1
        elif comment_count <= 5:
            comment_stats["1-5条评论"] = comment_stats.get("1-5条评论", 0) + 1
        elif comment_count <= 10:
            comment_stats["6-10条评论"] = comment_stats.get("6-10条评论", 0) + 1
        else:
            comment_stats["10条以上评论"] = comment_stats.get("10条以上评论", 0) + 1
    
    if total_comments > 0:
        print(f"\n评论统计:")
        print(f"  总评论数: {total_comments}")
        print(f"  平均每个任务: {total_comments / len(tasks):.1f} 条评论")
        for stat, count in comment_stats.items():
            print(f"  {stat}: {count}")
    
    # 显示有描述的任务数量
    tasks_with_desc = sum(1 for task in tasks if task.description and task.description.strip())
    print(f"\n内容统计:")
    print(f"  有描述的任务: {tasks_with_desc}/{len(tasks)} ({tasks_with_desc/len(tasks)*100:.1f}%)")
    print(f"  有评论的任务: {len(tasks) - comment_stats.get('无评论', 0)}/{len(tasks)} ({(len(tasks) - comment_stats.get('无评论', 0))/len(tasks)*100:.1f}%)")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="导出GitHub ProjectV2任务详情")
    parser.add_argument("--config", help="配置文件路径")
    parser.add_argument("--project", help="GitHub项目ID")
    parser.add_argument("--token", help="GitHub个人访问令牌")
    parser.add_argument("--output", help="输出文件路径 (支持.json和.csv格式)")
    parser.add_argument("--format", choices=["json", "csv", "summary"], default="summary", 
                       help="输出格式 (默认: summary)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    
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
        # 初始化导出工具
        exporter = GitHubProjectExporter(token, project_id, config)
        
        # 获取所有任务
        logger.info("正在获取项目任务...")
        tasks = exporter.get_project_tasks()
        logger.info(f"成功获取 {len(tasks)} 个任务")
        
        # 输出结果
        if args.output:
            output_file = args.output
            if output_file.endswith('.json'):
                export_to_json(tasks, output_file)
                logger.info(f"任务已导出到JSON文件: {output_file}")
            elif output_file.endswith('.csv'):
                export_to_csv(tasks, output_file)
                logger.info(f"任务已导出到CSV文件: {output_file}")
            else:
                logger.error("不支持的输出文件格式。请使用.json或.csv扩展名。")
                sys.exit(1)
        elif args.format == "json":
            tasks_data = [asdict(task) for task in tasks]
            print(json.dumps(tasks_data, ensure_ascii=False, indent=2))
        elif args.format == "csv":
            # 输出CSV到标准输出
            import io
            output = io.StringIO()
            if tasks:
                fieldnames = list(asdict(tasks[0]).keys())
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                for task in tasks:
                    row = asdict(task)
                    row['assignees'] = ','.join(task.assignees)
                    row['labels'] = ','.join(task.labels)
                    writer.writerow(row)
            print(output.getvalue())
        else:
            # 默认显示摘要
            print_summary(tasks)
            
    except Exception as e:
        logger.error(f"导出失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()