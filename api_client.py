#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import json
import time
import uuid
import logging
from typing import Optional, Dict, Any, List

import requests

logger = logging.getLogger(__name__)


class SignatureGenerator:
    def __init__(self, language: int = 7):
        self.language = language
    
    def generate_random(self) -> str:
        return uuid.uuid4().hex
    
    def generate_signature(self, data: Dict[str, Any]) -> Dict[str, Any]:
        clean_data = {k: v for k, v in data.items() 
                     if k not in ['signature', 'timestamp']}
        clean_data['language'] = self.language
        clean_data['random'] = self.generate_random()
        
        sorted_data = {}
        for key in sorted(clean_data.keys()):
            value = clean_data[key]
            if value is not None and value != '':
                sorted_data[key] = value
        
        json_string = json.dumps(sorted_data, separators=(',', ':'))
        signature = hashlib.md5(json_string.encode()).hexdigest().upper()
        timestamp = int(time.time())
        
        return {
            **clean_data,
            'signature': signature,
            'timestamp': timestamp
        }


class APIClient:
    SITE_CONFIGS = {
        '777BIGWIN': {
            'base_url': 'https://api.bigwinqaz.com/api/webapi',
            'ar_origin': 'https://www.777bigwingame.app',
            'authority': 'api.bigwinqaz.com',
            'min_bet': 10,
        },
        '6LOTTERY': {
            'base_url': 'https://6lotteryapi.com/api/webapi',
            'ar_origin': 'https://www.6win566.com',
            'authority': '6lotteryapi.com',
            'min_bet': 100,
        }
    }
    
    def __init__(self, site: str = '777BIGWIN', token: str = "", language: int = 7):
        self.site = site
        self.site_config = self.SITE_CONFIGS.get(site, self.SITE_CONFIGS['777BIGWIN'])
        self.base_url = self.site_config['base_url']
        self.token = token
        self.language = language
        self.sig_gen = SignatureGenerator(language)
        self.session = requests.Session()
        self._last_request_time = 0
        self._min_request_interval = 2.0
        self._setup_headers()
    
    def _setup_headers(self):
        config = self.site_config
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/json;charset=UTF-8',
            'pragma': 'no-cache',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            'authority': config.get('authority', 'api.bigwinqaz.com'),
            'ar-origin': config.get('ar_origin', 'https://www.777bigwingame.app'),
            'ar-real-ip': '',
            'origin': config.get('ar_origin', 'https://www.777bigwingame.app'),
            'referer': config.get('ar_origin', 'https://www.777bigwingame.app/'),
        }
        self.session.headers.update(headers)
    
    def get_min_bet(self) -> int:
        return self.site_config.get('min_bet', 10)
    
    def set_token(self, token: str):
        self.token = token
        self.session.headers['authorization'] = f'Bearer {token}'
    
    def _rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            time.sleep(sleep_time)
        self._last_request_time = time.time()
    
    def _post(self, endpoint: str, data: Dict[str, Any], retry: int = 3) -> Dict[str, Any]:
        self._rate_limit()
        for attempt in range(retry):
            try:
                signed_data = self.sig_gen.generate_signature(data)
                response = self.session.post(
                    f"{self.base_url}/{endpoint}",
                    json=signed_data,
                    timeout=30
                )
                result = response.json()
                if result.get('code') == 13:
                    logger.warning(f"Rate limited, waiting 5 seconds...")
                    time.sleep(5)
                    continue
                return result
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout, retry {attempt+1}/{retry}")
                time.sleep(2)
            except Exception as e:
                logger.error(f"Request error: {e}")
                if attempt == retry - 1:
                    raise
        return {'code': -1, 'msg': 'Max retries exceeded'}
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        data = {
            'username': username,
            'pwd': password,
            'phonetype': 1,
            'logintype': 'mobile',
            'packId': '',
            'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6',
            'pixelId': '',
            'fbcId': '',
            'fbc': '',
            'fbp': '',
            'adId': '',
        }
        return self._post('Login', data)
    
    def get_game_issue(self, type_id: int) -> Optional[str]:
        try:
            result = self._post('GetGameIssue', {'typeId': type_id})
            if result.get('code') != 0:
                return None
            data = result.get('data')
            if isinstance(data, dict):
                for key in ['issueNo', 'issuenumber', 'issueNumber']:
                    if key in data and data[key]:
                        return str(data[key])
            elif isinstance(data, str):
                return data
            elif isinstance(data, list) and len(data) > 0:
                return str(data[0])
            return None
        except Exception as e:
            logger.error(f"GetGameIssue error: {e}")
            return None
    
    def get_noaverage_emergd_list(self, type_id: int = 30, page_size: int = 10, page_no: int = 1) -> List[Dict]:
        try:
            result = self._post('GetNoaverageEmerdList', {
                'typeId': type_id,
                'pageSize': page_size,
                'pageNo': page_no
            })
            if result.get('code') == 0:
                data = result.get('data', {})
                if isinstance(data, dict):
                    return data.get('list', [])
                elif isinstance(data, list):
                    return data
            return []
        except Exception as e:
            logger.error(f"GetNoaverageEmerdList error: {e}")
            return []
    
    def place_bet(self, type_id: int, issue: str, select_type: int, 
                  amount: int, bet_count: int = 1, game_type: int = 2) -> Dict:
        return self._post('GameBetting', {
            'typeId': type_id,
            'issuenumber': issue,
            'amount': amount,
            'betCount': bet_count,
            'gameType': game_type,
            'selectType': select_type,
        })
    
    def get_balance(self) -> float:
        try:
            result = self._post('GetBalance', {})
            if result.get('code') == 0:
                data = result.get('data', {})
                if isinstance(data, dict):
                    return float(data.get('amount', 0))
            return 0.0
        except:
            return 0.0
    
    async def close(self):
        self.session.close()
