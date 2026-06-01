# AIMETA P=短信服务_验证码下发|R=阿里云短信对接(可配置)+mock降级|NR=不含验证码生成/校验|E=SmsService|X=internal|A=服务类|D=httpx,hmac|S=net|RD=./README.ai
"""短信验证码下发服务（配置驱动，默认对接阿里云短信 Dysmsapi）。

配置（SystemConfig，后台可配）：
  sms.provider           = aliyun | mock（默认 mock，便于开发/未配置时不阻塞）
  sms.access_key_id       阿里云 AccessKeyId
  sms.access_key_secret   阿里云 AccessKeySecret
  sms.sign_name           短信签名
  sms.template_code       短信模板 CODE（模板变量名默认 code，可用 sms.template_param 覆写）
  sms.region              区域（默认 cn-hangzhou）

mock 模式仅记录日志、不真正发送，返回 True（开发联调用）；生产务必配 aliyun 并填齐密钥。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..repositories.system_config_repository import SystemConfigRepository

logger = logging.getLogger(__name__)


class SmsService:
    def __init__(self, session):
        self.session = session
        self.config_repo = SystemConfigRepository(session)

    async def _cfg(self, key: str) -> Optional[str]:
        record = await self.config_repo.get_by_key(key)
        return record.value if record else None

    async def send_code(self, phone: str, code: str) -> bool:
        """下发验证码短信。返回是否成功；未配置/失败时记录日志并返回 False（mock 返回 True）。"""
        provider = (await self._cfg("sms.provider") or "mock").strip().lower()
        if provider in ("", "mock", "none", "disabled"):
            logger.info("[SMS mock] 向 %s 发送验证码 %s（未配置真实服务商，仅记录日志）", phone, code)
            return True
        if provider == "aliyun":
            return await self._send_aliyun(phone, code)
        logger.warning("未知短信服务商: %s，跳过发送", provider)
        return False

    @staticmethod
    def _percent_encode(value: str) -> str:
        # 阿里云签名要求 RFC3986 编码，且 ~ 不编码
        return urllib.parse.quote(str(value), safe="~")

    async def _send_aliyun(self, phone: str, code: str) -> bool:
        akid = await self._cfg("sms.access_key_id")
        secret = await self._cfg("sms.access_key_secret")
        sign_name = await self._cfg("sms.sign_name")
        template_code = await self._cfg("sms.template_code")
        region = (await self._cfg("sms.region")) or "cn-hangzhou"
        param_key = (await self._cfg("sms.template_param")) or "code"
        if not all([akid, secret, sign_name, template_code]):
            logger.error("阿里云短信参数未配置完整（access_key_id/secret/sign_name/template_code）")
            return False

        params = {
            "AccessKeyId": akid,
            "Action": "SendSms",
            "Format": "JSON",
            "PhoneNumbers": phone,
            "RegionId": region,
            "SignName": sign_name,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureNonce": uuid.uuid4().hex,
            "SignatureVersion": "1.0",
            "TemplateCode": template_code,
            "TemplateParam": json.dumps({param_key: code}, ensure_ascii=False),
            "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Version": "2017-05-25",
        }
        canonical = "&".join(
            f"{self._percent_encode(k)}={self._percent_encode(v)}"
            for k, v in sorted(params.items())
        )
        string_to_sign = "GET&%2F&" + self._percent_encode(canonical)
        signature = base64.b64encode(
            hmac.new((secret + "&").encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()
        ).decode("utf-8")
        url = f"https://dysmsapi.aliyuncs.com/?Signature={self._percent_encode(signature)}&{canonical}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                data = resp.json()
        except Exception as exc:
            logger.warning("阿里云短信请求异常: %s", exc)
            return False

        if data.get("Code") == "OK":
            logger.info("阿里云短信发送成功: phone=%s biz_id=%s", phone, data.get("BizId"))
            return True
        logger.warning("阿里云短信发送失败: phone=%s code=%s msg=%s", phone, data.get("Code"), data.get("Message"))
        return False
