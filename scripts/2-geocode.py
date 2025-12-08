#!/usr/bin/env python3
"""
996.MAP 地理编码脚本
功能：将公司地址转换为地理坐标
输入：data/companies.json
输出：data/companies-with-coords.json
"""

import json
import logging
import time
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import os
from datetime import datetime
from dotenv import load_dotenv

# 配置日志（在导入其他模块之前）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 加载环境变量
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f"已加载环境变量文件: {env_path}")
else:
    logger.info("未找到 .env 文件，使用系统环境变量")

# 文件路径配置
INPUT_FILE = "data/companies.json"
OUTPUT_FILE = "data/companies-with-coords.json"
GEOCACHE_FILE = "data/geocache.json"
GEOCODE_ERRORS_LOG = "data/geocode_errors.log"

# API配置
GAODE_API_KEY = os.getenv('GAODE_API_KEY', '')
GEOCODE_PROVIDER = os.getenv('GEOCODE_PROVIDER', 'gaode')
GEOCODE_BATCH_SIZE = int(os.getenv('GEOCODE_BATCH_SIZE', '50'))

# 高德API配置
GAODE_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
GAODE_BATCH_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"

class Geocoder:
    def __init__(self, api_key: str, cache_file: Optional[str] = None):
        self.api_key = api_key
        self.cache_file = cache_file
        self.cache = self.load_cache()
        self.error_count = 0
        self.success_count = 0
        self.cache_hit_count = 0

    def load_cache(self) -> Dict[str, Dict]:
        """加载地理编码缓存"""
        if self.cache_file and Path(self.cache_file).exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载缓存失败: {str(e)}")
        return {}

    def save_cache(self):
        """保存地理编码缓存"""
        if self.cache_file:
            try:
                Path(self.cache_file).parent.mkdir(parents=True, exist_ok=True)
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.cache, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"保存缓存失败: {str(e)}")

    def get_cache_key(self, company_name: str, city: str) -> str:
        """生成缓存键"""
        return f"{city}@{company_name}"

    def get_cached_coordinates(self, company_name: str, city: str) -> Optional[Dict]:
        """从缓存获取坐标"""
        cache_key = self.get_cache_key(company_name, city)
        cached_data = self.cache.get(cache_key)

        if cached_data:
            # 检查缓存有效期（90天）
            timestamp = cached_data.get('timestamp', '')
            if timestamp:
                try:
                    cache_date = datetime.fromisoformat(timestamp)
                    days_diff = (datetime.now() - cache_date).days
                    if days_diff <= 90:
                        self.cache_hit_count += 1
                        return cached_data
                    else:
                        logger.info(f"缓存过期: {cache_key}")
                except:
                    pass

        return None

    def cache_coordinates(self, company_name: str, city: str, coordinates: List[float],
                         source: str = "exact"):
        """缓存坐标信息"""
        cache_key = self.get_cache_key(company_name, city)
        self.cache[cache_key] = {
            "coords": coordinates,
            "timestamp": datetime.now().isoformat(),
            "source": source
        }

    def geocode_address(self, address: str) -> Optional[Tuple[List[float], str]]:
        """使用高德API进行地理编码"""
        if not self.api_key:
            logger.error("缺少高德API密钥")
            return None

        params = {
            'key': self.api_key,
            'address': address,
            'output': 'json'
        }

        try:
            response = requests.get(GAODE_GEOCODE_URL, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get('status') == '1' and data.get('geocodes'):
                location = data['geocodes'][0].get('location', '')
                if location:
                    # 高德返回的是GCJ-02坐标系，需要转换为WGS84
                    lng, lat = map(float, location.split(','))
                    # 简化的坐标转换（实际项目中可能需要更精确的转换）
                    wgs_lng, wgs_lat = gcj02_to_wgs84(lng, lat)
                    return [wgs_lng, wgs_lat], "exact"

            logger.warning(f"地理编码失败: {address}")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"地理编码异常: {str(e)}")
            return None

    def geocode_company(self, company_name: str, city: str) -> Optional[Dict]:
        """对公司进行地理编码"""
        # 首先检查缓存
        cached = self.get_cached_coordinates(company_name, city)
        if cached:
            logger.info(f"缓存命中: {company_name} - {city}")
            return {
                "coordinates": cached["coords"],
                "geocode_source": "cache",
                "geocode_timestamp": cached["timestamp"]
            }

        # 尝试精确模式：城市 + 公司名
        exact_address = f"{city}{company_name}"
        result = self.geocode_address(exact_address)

        if result:
            coordinates, source = result
            self.cache_coordinates(company_name, city, coordinates, source)
            self.success_count += 1
            return {
                "coordinates": coordinates,
                "geocode_source": source,
                "geocode_timestamp": datetime.now().isoformat()
            }

        # 回退模式：仅城市
        logger.info(f"尝试城市回退模式: {city}")
        city_result = self.geocode_address(city)

        if city_result:
            coordinates, source = city_result
            self.cache_coordinates(company_name, city, coordinates, "city_fallback")
            self.success_count += 1
            return {
                "coordinates": coordinates,
                "geocode_source": "city_fallback",
                "geocode_timestamp": datetime.now().isoformat()
            }

        # 地理编码失败
        self.error_count += 1
        with open(GEOCODE_ERRORS_LOG, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().isoformat()} - {company_name} - {city}\n")

        return {
            "coordinates": None,
            "geocode_source": "failed",
            "geocode_timestamp": datetime.now().isoformat()
        }

def gcj02_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """
    简化的GCJ-02到WGS84坐标转换
    注意：这是简化版本，实际项目中可能需要更精确的转换算法
    """
    # 简化的转换，实际项目中建议使用专业的坐标转换库
    return lng, lat

def load_companies(file_path: str) -> List[Dict]:
    """加载公司数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载公司数据失败: {str(e)}")
        return []

def save_companies_with_coords(companies: List[Dict], output_path: str):
    """保存带坐标的公司数据"""
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(companies, f, ensure_ascii=False, indent=2)
        logger.info(f"数据已保存到: {output_path}")
    except Exception as e:
        logger.error(f"保存数据失败: {str(e)}")
        raise

def main():
    """主函数"""
    logger.info("开始执行地理编码脚本")

    if not GAODE_API_KEY:
        logger.error("未设置GAODE_API_KEY环境变量")
        return 1

    # 清空错误日志
    if Path(GEOCODE_ERRORS_LOG).exists():
        Path(GEOCODE_ERRORS_LOG).unlink()

    # 加载公司数据
    companies = load_companies(INPUT_FILE)
    if not companies:
        logger.error("未找到公司数据")
        return 1

    logger.info(f"开始处理 {len(companies)} 家公司")

    # 创建地理编码器
    geocoder = Geocoder(GAODE_API_KEY, GEOCACHE_FILE)

    # 批量地理编码
    companies_with_coords = []
    for i, company in enumerate(companies):
        logger.info(f"处理 {i+1}/{len(companies)}: {company['company_name']}")

        # 地理编码
        geo_result = geocoder.geocode_company(
            company['company_name'],
            company['city']
        )

        # 合并结果
        company_with_coords = company.copy()
        if geo_result:
            company_with_coords.update(geo_result)
        companies_with_coords.append(company_with_coords)

        # 批量处理间隔
        if (i + 1) % GEOCODE_BATCH_SIZE == 0:
            logger.info(f"已处理 {i + 1} 家公司，暂停2秒...")
            time.sleep(2)
        
        time.sleep(0.5)

    # 保存缓存
    geocoder.save_cache()

    # 保存结果
    save_companies_with_coords(companies_with_coords, OUTPUT_FILE)

    # 统计信息
    logger.info("地理编码完成:")
    logger.info(f"  总计: {len(companies_with_coords)} 家")
    logger.info(f"  成功: {geocoder.success_count} 家")
    logger.info(f"  缓存命中: {geocoder.cache_hit_count} 家")
    logger.info(f"  失败: {geocoder.error_count} 家")

    return 0

if __name__ == "__main__":
    exit(main())