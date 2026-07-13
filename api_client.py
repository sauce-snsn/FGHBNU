#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import json
import time
import uuid
import logging
from typing import Optional, Dict, Any, List, Tuple

import aiohttp
import requests

logger = logging.getLogger(__name__)


class SignatureGenerator:
    """Generate API signature exactly like frontend"""
    
    def __init__(self, language: int = 7):
        self.language = language
    
    def generate_random(self) -> str:
        return uuid.uuid4().hex
    
    def generate_signature(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate signature with MD5 hash"""
        # Remove existing signature and timestamp
        clean_data = {k: v for k, v in data.items() 
                     if k not in ['signature', 'timestamp']}
        
        # Add language and random
        clean_data['language'] = self.language
        clean_data['random'] = self.generate_random()
        
        # Sort keys alphabetically
        sorted_data = {}
        for key in sorted(clean_data.keys()):
            value = clean_data[key]
            if value is not None and value != '':
                sorted_data[key] = value
        
        # JSON stringify and MD5 hash
        json_string = json.dumps(sorted_data, separators=(',', ':'))
        signature = hashlib.md5(json_string.encode()).hexdigest().upper()
        timestamp = int(time.time())
        
        return {
            **clean_data,
            'signature': signature,
            'timestamp': timestamp
        }


class APIClient:
    """API client with auto-signature and rate limiting"""
    
    # Site configurations - ONLY API URLs, no login URLs needed!
    SITES = {
        '777BIGWIN': {
            'base_url': 'https://api.bigwinqaz.com/api/webapi',
            'site_name': '777BIGWIN',
        },
        '6LOTTERY': {
            'base_url': 'https://6lotteryapi.com/api/webapi',
            'site_name': '6LOTTERY',
        }
    }
    
    def __init__(self, site: str = '777BIGWIN', token: str = "", language: int = 7):
        self.site = site
        self.site_config = self.SITES.get(site, self.SITES['777BIGWIN'])
        self.base_url = self.site_config['base_url']
        self.token = token
        self.language = language
        self.sig_gen = SignatureGenerator(language)
        self.session = requests.Session()
        self._aio_session = None
        self._last_request_time = 0
        self._min_request_interval = 2.0
        self._setup_headers()
    
    def _setup_headers(self):
        self.session.headers.update({
            'authority': 'api.bigwinqaz.com',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'ar-origin': 'https://www.777bigwingame.app',
            'cache-control': 'no-cache',
            'content-type': 'application/json;charset=UTF-8',
            'origin': 'https://www.777bigwingame.app',
            'pragma': 'no-cache',
            'referer': 'https://www.777bigwingame.app/',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        })
    
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
        """Sync POST request with signature"""
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
                
                # Rate limit (code 13 = access too often)
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
    
    async def _apost(self, endpoint: str, data: Dict[str, Any], retry: int = 3) -> Dict[str, Any]:
        """Async POST request with signature"""
        self._rate_limit()
        
        if self._aio_session is None:
            self._aio_session = aiohttp.ClientSession()
        
        for attempt in range(retry):
            try:
                signed_data = self.sig_gen.generate_signature(data)
                async with self._aio_session.post(
                    f"{self.base_url}/{endpoint}",
                    json=signed_data,
                    timeout=30
                ) as response:
                    result = await response.json()
                    
                    if result.get('code') == 13:
                        logger.warning(f"Rate limited, waiting 5 seconds...")
                        await asyncio.sleep(5)
                        continue
                    
                    return result
                    
            except aiohttp.ClientTimeout:
                logger.warning(f"Request timeout, retry {attempt+1}/{retry}")
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Request error: {e}")
                if attempt == retry - 1:
                    raise
        
        return {'code': -1, 'msg': 'Max retries exceeded'}
    
    async def close(self):
        if self._aio_session:
            await self._aio_session.close()
    
    # ============================================================
    # LOGIN - API Only! No browser needed!
    # ============================================================
    
    def login(self, username: str, password: str, device_id: str = None) -> Dict[str, Any]:
        """Login to the platform via API - NO BROWSER NEEDED!"""
        if device_id is None:
            device_id = '51ed4ee0f338a1bb24063ffdfcd31ce6'
        
        data = {
            'username': username,
            'pwd': password,
            'phonetype': 1,
            'logintype': 'mobile',
            'packId': '',
            'deviceId': device_id,
            'pixelId': '',
            'fbcId': '',
            'fbc': '',
            'fbp': '',
            'adId': '',
        }
        return self._post('Login', data)
    
    async def alogin(self, username: str, password: str, device_id: str = None) -> Dict[str, Any]:
        """Async login via API"""
        if device_id is None:
            device_id = '51ed4ee0f338a1bb24063ffdfcd31ce6'
        
        data = {
            'username': username,
            'pwd': password,
            'phonetype': 1,
            'logintype': 'mobile',
            'packId': '',
            'deviceId': device_id,
            'pixelId': '',
            'fbcId': '',
            'fbc': '',
            'fbp': '',
            'adId': '',
        }
        return await self._apost('Login', data)
    
    # ============================================================
    # USER INFO
    # ============================================================
    
    def get_user_info(self) -> Dict[str, Any]:
        """Get user information"""
        return self._post('GetUserInfo', {})
    
    async def aget_user_info(self) -> Dict[str, Any]:
        return await self._apost('GetUserInfo', {})
    
    def get_balance(self) -> float:
        """Get user balance"""
        try:
            result = self._post('GetBalance', {})
            if result.get('code') == 0:
                data = result.get('data', {})
                if isinstance(data, dict):
                    return float(data.get('amount', 0))
            return 0.0
        except:
            return 0.0
    
    async def aget_balance(self) -> float:
        try:
            result = await self._apost('GetBalance', {})
            if result.get('code') == 0:
                data = result.get('data', {})
                if isinstance(data, dict):
                    return float(data.get('amount', 0))
            return 0.0
        except:
            return 0.0
    
    # ============================================================
    # GAME METHODS
    # ============================================================
    
    def get_game_issue(self, type_id: int = 30) -> Optional[str]:
        """Get current issue number"""
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
    
    async def aget_game_issue(self, type_id: int = 30) -> Optional[str]:
        try:
            result = await self._apost('GetGameIssue', {'typeId': type_id})
            
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
        """Get betting history/trends"""
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
    
    async def aget_noaverage_emergd_list(self, type_id: int = 30, page_size: int = 10, page_no: int = 1) -> List[Dict]:
        try:
            result = await self._apost('GetNoaverageEmerdList', {
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
    
    def get_win_result(self, issue_numbers: List[str]) -> List[Dict]:
        """Get lottery results for specific issues"""
        try:
            result = self._post('GetWinTheLotteryResult', {
                'issueNumber': issue_numbers
            })
            
            if result.get('code') == 0:
                data = result.get('data', [])
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get('list', [])
            return []
            
        except Exception as e:
            logger.error(f"GetWinResult error: {e}")
            return []
    
    async def aget_win_result(self, issue_numbers: List[str]) -> List[Dict]:
        try:
            result = await self._apost('GetWinTheLotteryResult', {
                'issueNumber': issue_numbers
            })
            
            if result.get('code') == 0:
                data = result.get('data', [])
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get('list', [])
            return []
            
        except Exception as e:
            logger.error(f"GetWinResult error: {e}")
            return []
    
    # ============================================================
    # BETTING
    # ============================================================
    
    def place_bet(self, type_id: int, issue: str, select_type: int, 
                  amount: int, bet_count: int = 1, game_type: int = 2) -> Dict:
        """Place a bet"""
        return self._post('GameBetting', {
            'typeId': type_id,
            'issuenumber': issue,
            'amount': amount,
            'betCount': bet_count,
            'gameType': game_type,
            'selectType': select_type,
        })
    
    async def aplace_bet(self, type_id: int, issue: str, select_type: int, 
                         amount: int, bet_count: int = 1, game_type: int = 2) -> Dict:
        return await self._apost('GameBetting', {
            'typeId': type_id,
            'issuenumber': issue,
            'amount': amount,
            'betCount': bet_count,
            'gameType': game_type,
            'selectType': select_type,
        })
    
    # ============================================================
    # UTILITY
    # ============================================================
    
    def extract_result(self, result_data: Dict) -> Tuple[int, str]:
        """Extract number and size from result"""
        try:
            number = int(result_data.get('number', 0))
            if number >= 5:
                size = "BIG"
            else:
                size = "SMALL"
            return number, size
        except:
            return 0, "UNKNOWN"
    
    def get_bet_choice(self, prediction: str) -> str:
        """Convert prediction to bet choice"""
        mapping = {
            'big': 'big',
            'small': 'small',
            'red': 'red',
            'green': 'green',
            'violet': 'violet',
            'purple': 'violet'
        }
        return mapping.get(prediction.lower(), 'big')


# For async methods
import asyncio
