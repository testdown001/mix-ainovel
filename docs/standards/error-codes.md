# API 错误码规范

> 对应路线图 M0。新接口必须遵循本规范；旧接口在修改时逐步迁移，不要求一次性破坏兼容。

## 响应格式

```json
{
  "detail": {
    "code": "VOLUME_NOT_FOUND",
    "message": "未找到指定分卷。",
    "meta": { "可选": "的机器可读上下文" }
  }
}
```

HTTP 状态码表达协议语义，`code` 表达稳定的业务语义；前端不可通过中文 `message` 判断分支。

## M0/M1/M2/M3 代码表

| HTTP | 错误码 | 含义 |
|---:|---|---|
| 400 | `INVALID_REQUEST` | 请求字段或组合不合法 |
| 401 | `AUTH_REQUIRED` | 未登录或会话失效 |
| 403 | `FEATURE_NOT_AVAILABLE` | 当前套餐或功能开关不允许操作 |
| 404 | `PROJECT_NOT_FOUND` | 作品不存在或当前用户无权访问 |
| 404 | `VOLUME_NOT_FOUND` | 卷不存在或不属于该作品 |
| 404 | `CHAPTER_NOT_FOUND` | 章节不存在或不属于该作品 |
| 404 | `CHAPTER_VERSION_NOT_FOUND` | 历史版本不存在或不属于该作品 |
| 409 | `VERSION_CONFLICT` | 客户端修订号落后，存在并发覆盖风险 |
| 409 | `WORLD_STATE_SOURCE_MISMATCH` | 状态切片的章节、版本或父切片不一致 |
| 404 | `WORLD_STATE_NOT_FOUND` | 指定章节尚无已确认的状态切片 |
| 422 | `WORLD_STATE_INVALID` | 世界状态结构或证据范围不合法 |
| 500 | `DOMAIN_PERSISTENCE_FAILED` | 领域数据持久化失败，调用方可安全重试 |

`VERSION_CONFLICT` 的 `meta` 仅包含章节号、服务端修订号、内容哈希和当前选中版本 ID；
正文须经专用读取接口获得，不能出现在错误响应或日志中。

## 迁移规则

- 新端点通过 `backend/app/core/error_codes.py` 构造错误。
- `meta` 不能包含正文、密钥、LLM 原始响应或可识别的其他用户数据。
- 日志必须包含错误码、项目 ID（如有）和请求 ID。
