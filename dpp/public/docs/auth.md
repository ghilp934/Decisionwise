# Authentication

## API Key Authentication

Decisionwise uses API keys for authentication. Include your API key in the `X-API-Key` header:

```http
X-API-Key: dw_live_abc123...
```

### Key Formats

- **Live keys**: `dw_live_*` (production)
- **Test keys**: `dw_test_*` (sandbox)

### Example Request

```bash
curl -X GET https://api.decisionwise.ai/v1/health \
  -H "X-API-Key: dw_live_abc123..."
```

## Error Responses

### 401 Unauthorized

API key is missing or invalid.

```json
{
  "type": "https://iana.org/assignments/http-problem-types#unauthorized",
  "title": "Unauthorized",
  "status": 401,
  "detail": "Invalid or missing API key"
}
```

**Billable**: No (non-billable per billing rules)

### 403 Forbidden

API key is valid but lacks permissions for the requested resource.

```json
{
  "type": "https://iana.org/assignments/http-problem-types#forbidden",
  "title": "Forbidden",
  "status": 403,
  "detail": "API key does not have permission to access this resource"
}
```

**Billable**: No (non-billable per billing rules)

## Security Best Practices

- Never commit API keys to version control
- Rotate keys regularly
- Use test keys for development/testing
- Restrict API keys to specific IP addresses (contact support)
