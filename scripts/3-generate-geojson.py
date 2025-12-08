#!/usr/bin/env python3
"""
996.MAP GeoJSON生成脚本
功能：将带坐标的公司数据转换为GeoJSON格式
输入：data/companies-with-coords.json
输出：public/companies.geojson
"""

import json
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 文件路径配置
INPUT_FILE = "data/companies-with-coords.json"
OUTPUT_FILE = "public/companies.geojson"

# 配色方案 - 根据制度类型
COLOR_SCHEME = {
    '996': '#ff5252',      # 红色
    '997': '#ff5252',      # 红色
    '007': '#ff5252',      # 红色
    '大小周': '#ffab40',    # 橙色
    '995': '#ffd740',      # 黄色
    '10106': '#ffd740',    # 黄色
    'default': '#bdbdbd'   # 灰色
}

def get_work_schedule_color(work_schedule: str) -> str:
    """根据制度描述获取颜色"""
    if not work_schedule:
        return COLOR_SCHEME['default']

    work_schedule_lower = work_schedule.lower()

    # 检查是否包含特定关键词
    if '996' in work_schedule_lower or '997' in work_schedule_lower or '007' in work_schedule_lower:
        return COLOR_SCHEME['996']
    elif '大小周' in work_schedule:
        return COLOR_SCHEME['大小周']
    elif '995' in work_schedule_lower or '10106' in work_schedule_lower:
        return COLOR_SCHEME['995']
    else:
        return COLOR_SCHEME['default']

def create_geojson_feature(company: Dict) -> Dict:
    """创建GeoJSON Feature对象"""
    # 获取坐标
    coordinates = company.get('coordinates')
    if not coordinates or len(coordinates) != 2:
        return None

    # 获取颜色
    color = get_work_schedule_color(company.get('work_schedule', ''))

    # 构建properties
    properties = {
        "city": company.get('city', ''),
        "name": company.get('company_name', ''),
        "url": company.get('company_url', ''),
        "schedule": company.get('work_schedule', ''),
        "evidence": company.get('evidence_links', [])[:3],  # 限制为3个证据
        "color": color,
        "update_date": datetime.now().strftime('%Y-%m-%d')
    }

    # 创建Feature对象
    feature = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": coordinates  # [经度, 纬度]
        },
        "properties": properties
    }

    return feature

def load_companies_with_coords(file_path: str) -> List[Dict]:
    """加载带坐标的公司数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载公司数据失败: {str(e)}")
        return []

def create_geojson_collection(companies: List[Dict]) -> Dict:
    """创建GeoJSON FeatureCollection"""
    features = []
    skipped_count = 0

    for company in companies:
        feature = create_geojson_feature(company)
        if feature:
            features.append(feature)
        else:
            skipped_count += 1
            logger.warning(f"跳过无有效坐标的公司: {company.get('company_name', 'Unknown')}")

    logger.info(f"GeoJSON转换: 成功 {len(features)} 个, 跳过 {skipped_count} 个")

    # 创建FeatureCollection
    geojson_collection = {
        "type": "FeatureCollection",
        "features": features
    }

    return geojson_collection

def validate_geojson(geojson_data: Dict) -> bool:
    """验证GeoJSON格式"""
    try:
        # 基本结构验证
        if geojson_data.get("type") != "FeatureCollection":
            logger.error("GeoJSON类型错误")
            return False

        if "features" not in geojson_data:
            logger.error("缺少features字段")
            return False

        features = geojson_data["features"]
        if not isinstance(features, list):
            logger.error("features必须是数组")
            return False

        if len(features) == 0:
            logger.error("features不能为空")
            return False

        # 验证每个feature
        for i, feature in enumerate(features):
            if feature.get("type") != "Feature":
                logger.error(f"Feature {i} 类型错误")
                return False

            if "geometry" not in feature:
                logger.error(f"Feature {i} 缺少geometry")
                return False

            geometry = feature["geometry"]
            if geometry.get("type") != "Point":
                logger.error(f"Feature {i} geometry类型错误")
                return False

            if "coordinates" not in geometry:
                logger.error(f"Feature {i} 缺少coordinates")
                return False

            coordinates = geometry["coordinates"]
            if not isinstance(coordinates, list) or len(coordinates) != 2:
                logger.error(f"Feature {i} coordinates格式错误")
                return False

            if not all(isinstance(coord, (int, float)) for coord in coordinates):
                logger.error(f"Feature {i} coordinates必须是数字")
                return False

            if "properties" not in feature:
                logger.error(f"Feature {i} 缺少properties")
                return False

        logger.info("GeoJSON格式验证通过")
        return True

    except Exception as e:
        logger.error(f"GeoJSON验证失败: {str(e)}")
        return False

def save_geojson(geojson_data: Dict, output_path: str):
    """保存GeoJSON文件"""
    try:
        # 确保输出目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(geojson_data, f, ensure_ascii=False, indent=2)

        logger.info(f"GeoJSON文件已保存: {output_path}")

        # 输出文件大小信息
        file_size = Path(output_path).stat().st_size
        logger.info(f"文件大小: {file_size:,} 字节 ({file_size/1024:.1f} KB)")

    except Exception as e:
        logger.error(f"保存GeoJSON文件失败: {str(e)}")
        raise

def generate_statistics(companies: List[Dict], features: List[Dict]):
    """生成统计信息"""
    logger.info("数据统计:")
    logger.info(f"  输入公司数: {len(companies)}")
    logger.info(f"  输出特征数: {len(features)}")

    # 按城市统计
    city_stats = {}
    for feature in features:
        city = feature["properties"]["city"]
        city_stats[city] = city_stats.get(city, 0) + 1

    logger.info(f"  涉及城市: {len(city_stats)} 个")
    if city_stats:
        top_cities = sorted(city_stats.items(), key=lambda x: x[1], reverse=True)[:5]
        logger.info(f"  前5城市: {top_cities}")

    # 按制度类型统计
    schedule_stats = {}
    for feature in features:
        schedule = feature["properties"]["schedule"]
        schedule_stats[schedule] = schedule_stats.get(schedule, 0) + 1

    logger.info(f"  制度类型: {len(schedule_stats)} 种")
    if schedule_stats:
        for schedule, count in schedule_stats.items():
            logger.info(f"    {schedule}: {count}")

def main():
    """主函数"""
    logger.info("开始执行GeoJSON生成脚本")

    # 加载公司数据
    companies = load_companies_with_coords(INPUT_FILE)
    if not companies:
        logger.error("未找到公司数据")
        return 1

    logger.info(f"加载了 {len(companies)} 家公司数据")

    # 创建GeoJSON
    geojson_collection = create_geojson_collection(companies)

    # 验证GeoJSON格式
    if not validate_geojson(geojson_collection):
        logger.error("GeoJSON格式验证失败")
        return 1

    # 保存GeoJSON文件
    save_geojson(geojson_collection, OUTPUT_FILE)

    # 生成统计信息
    generate_statistics(companies, geojson_collection["features"])

    logger.info("GeoJSON生成脚本执行完成")
    return 0

if __name__ == "__main__":
    exit(main())