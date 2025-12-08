#!/usr/bin/env python3
"""
996.MAP Markdown解析脚本
功能：从blacklist/README.md中提取公司黑名单信息并解析为JSON格式
输入：blacklist/README.md
输出：data/companies.json
"""

import json
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional
import markdown
from markdown.extensions.tables import TableExtension

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 文件路径配置
INPUT_FILE = "blacklist/README.md"
OUTPUT_FILE = "data/companies.json"
PARSE_ERRORS_LOG = "data/parse_errors.log"

def extract_markdown_table(content: str) -> Optional[str]:
    """从Markdown内容中提取表格部分"""
    # 查找"名单列表"标题后的表格，确保不包含"已取消996名单列表"部分
    # 使用更精确的模式，匹配"名单列表"后直到遇到下一个标题或空行
    pattern = r'名单列表\s*\n-{3,}\s*\n((?:\|.*\|\s*\n)+)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def parse_markdown_table(table_content: str) -> List[List[str]]:
    """解析Markdown表格为二维数组"""
    lines = table_content.strip().split('\n')
    table_data = []

    # 跳过表头行和分隔行
    skip_patterns = ['---', '所在城市', '公司名字', '曝光/施行时间', '制度描述', '证据内容']

    for line in lines:
        line = line.strip()
        if '|' in line and line.count('|') >= 5:  # 确保至少有5个分隔符
            # 检查是否是需要跳过的行
            should_skip = False
            for pattern in skip_patterns:
                if pattern in line:
                    should_skip = True
                    break

            if should_skip:
                continue

            # 分割单元格并清理空白
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if cells and any(cell for cell in cells):  # 确保不是空行
                # 确保有5个字段，不足的补空字符串
                while len(cells) < 5:
                    cells.append('')
                table_data.append(cells[:5])  # 只取前5个字段

    return table_data

def extract_company_info(raw_company_text: str) -> Dict[str, str]:
    """从公司名字段提取公司信息和URL"""
    company_info = {
        "company_name": raw_company_text,
        "company_url": ""
    }

    # 匹配Markdown链接格式 [名称](URL)
    link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    match = re.search(link_pattern, raw_company_text)

    if match:
        company_info["company_name"] = match.group(1).strip()
        company_info["company_url"] = match.group(2).strip()

    return company_info

def extract_evidence_links(evidence_content: str) -> Dict[str, List[str]]:
    """从证据内容中提取链接和图片"""
    evidence_links = []
    evidence_images = []

    # 匹配所有链接格式 [文本](URL)
    link_pattern = r'\[([^\]]*)\]\(([^)]+)\)'
    matches = re.findall(link_pattern, evidence_content)

    for text, url in matches:
        url = url.strip()
        # 检查是否为图片链接
        if url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            evidence_images.append(url)
        else:
            evidence_links.append(url)

    # 限制证据链接数量为3个
    evidence_links = evidence_links[:3]
    evidence_images = evidence_images[:3]

    return {
        "evidence_links": evidence_links,
        "evidence_images": evidence_images
    }

def parse_company_row(row: List[str], last_city: str) -> Optional[Dict]:
    """解析单行公司数据"""
    try:
        if len(row) < 5:
            logger.warning(f"行数据不完整，跳过: {row}")
            return None

        # 跳过表头行
        if row[0] == '所在城市' or row[1] == '公司名字':
            return None

        city = row[0] if row[0] else last_city
        raw_company_text = row[1]
        evidence_time = row[2]
        work_schedule = row[3]
        evidence_content = row[4] if len(row) > 4 else ""

        # 提取公司信息
        company_info = extract_company_info(raw_company_text)

        # 提取证据链接
        evidence_data = extract_evidence_links(evidence_content)

        return {
            "city": city,
            "company_name": company_info["company_name"],
            "company_url": company_info["company_url"],
            "evidence_time": evidence_time,
            "work_schedule": work_schedule,
            "evidence_links": evidence_data["evidence_links"],
            "evidence_images": evidence_data["evidence_images"],
            "raw_company_text": raw_company_text
        }

    except Exception as e:
        logger.error(f"解析行数据失败: {row}, 错误: {str(e)}")
        return None

def parse_blacklist_file(file_path: str) -> List[Dict]:
    """解析黑名单文件"""
    logger.info(f"开始解析文件: {file_path}")

    if not Path(file_path).exists():
        logger.error(f"输入文件不存在: {file_path}")
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取表格部分
        table_content = extract_markdown_table(content)
        if not table_content:
            logger.error("未找到黑名单表格")
            return []

        # 解析表格
        table_data = parse_markdown_table(table_content)
        if not table_data:
            logger.error("表格解析失败")
            return []

        logger.info(f"找到 {len(table_data)} 行数据")

        # 解析每一行
        companies = []
        last_city = ""
        error_count = 0

        for i, row in enumerate(table_data):
            company = parse_company_row(row, last_city)
            if company:
                companies.append(company)
                last_city = company["city"]  # 更新上一个城市
            else:
                error_count += 1
                # 记录错误行
                with open(PARSE_ERRORS_LOG, 'a', encoding='utf-8') as f:
                    f.write(f"行 {i+1}: {row}\n")

        logger.info(f"解析完成: 成功 {len(companies)} 条, 失败 {error_count} 条")
        return companies

    except Exception as e:
        logger.error(f"解析文件失败: {str(e)}")
        return []

def save_companies_json(companies: List[Dict], output_path: str):
    """保存公司数据到JSON文件"""
    try:
        # 确保输出目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(companies, f, ensure_ascii=False, indent=2)

        logger.info(f"数据已保存到: {output_path}")
        logger.info(f"总计 {len(companies)} 家公司")

    except Exception as e:
        logger.error(f"保存文件失败: {str(e)}")
        raise

def main():
    """主函数"""
    logger.info("开始执行Markdown解析脚本")

    # 清空错误日志
    if Path(PARSE_ERRORS_LOG).exists():
        Path(PARSE_ERRORS_LOG).unlink()

    # 解析黑名单文件
    companies = parse_blacklist_file(INPUT_FILE)

    if not companies:
        logger.error("未解析到任何公司数据")
        return 1

    # 保存结果
    save_companies_json(companies, OUTPUT_FILE)

    logger.info("Markdown解析脚本执行完成")
    return 0

if __name__ == "__main__":
    exit(main())